# SPDX-License-Identifier: Apache-2.0
"""Tests for the logon screen (S000): rules, screen file, and the full UI flow."""
import threading
import time

import pytest
from PySide6.QtWidgets import QLineEdit, QTreeWidget

from engine.control import PasswordField, TextField
from engine.loader import load_screen
from engine.logon import SANDBOX_CLIENT, SANDBOX_USERS, check_logon
from ui.transaction_router import LOGON_SCREEN, LOGON_TCODE, SCREEN_DIR

USER, PASSWORD = next(iter(SANDBOX_USERS.items()))

CLIENT_ID = "wnd[0]/usr/txtRSYST-MANDT"
USER_ID = "wnd[0]/usr/txtRSYST-BNAME"
PASSWORD_ID = "wnd[0]/usr/pwdRSYST-BCODE"
LANGUAGE_ID = "wnd[0]/usr/txtRSYST-LANGU"


@pytest.fixture
def logon_window(qapp):
    from main import MainWindow
    win = MainWindow(require_logon=True)
    win.load_initial_screen()
    yield win
    win.close()
    win.deleteLater()


def fill(session, user=USER, password=PASSWORD, client=SANDBOX_CLIENT, language="EN"):
    session.findById(CLIENT_ID).value = client
    session.findById(USER_ID).value = user
    session.findById(PASSWORD_ID).value = password
    session.findById(LANGUAGE_ID).value = language


# ── Rules ─────────────────────────────────────────────────────────────────────

class TestCheckLogon:
    def test_valid(self):
        assert check_logon(SANDBOX_CLIENT, USER, PASSWORD, "EN") is None

    def test_user_is_case_insensitive(self):
        assert check_logon(SANDBOX_CLIENT, USER.lower(), PASSWORD) is None

    def test_password_is_case_sensitive(self):
        assert check_logon(SANDBOX_CLIENT, USER, PASSWORD.swapcase()) is not None

    def test_blank_language_is_accepted(self):
        assert check_logon(SANDBOX_CLIENT, USER, PASSWORD, "") is None

    @pytest.mark.parametrize("client, user, password, language, expected", [
        ("000", "", "x", "EN", "Enter a user name"),
        ("000", "SOMEONE", "", "EN", "Enter a password"),
        ("123", USER, PASSWORD, "EN", "Client 123 is not available"),
        ("000", USER, PASSWORD, "XX", "Language XX is not available"),
        ("000", USER, "wrong", "EN", "Name or password is incorrect"),
        ("000", "NOBODY", PASSWORD, "EN", "Name or password is incorrect"),
    ])
    def test_errors(self, client, user, password, language, expected):
        assert check_logon(client, user, password, language).startswith(expected)


# ── Screen file ───────────────────────────────────────────────────────────────

class TestLogonScreenFile:
    def test_standard_field_ids(self):
        session = load_screen(SCREEN_DIR / LOGON_SCREEN)
        assert isinstance(session.findById(CLIENT_ID), TextField)
        assert isinstance(session.findById(USER_ID), TextField)
        assert isinstance(session.findById(PASSWORD_ID), PasswordField)
        assert isinstance(session.findById(LANGUAGE_ID), TextField)

    def test_metadata(self):
        session = load_screen(SCREEN_DIR / LOGON_SCREEN)
        assert session.info.transaction == LOGON_TCODE
        assert session.findById(CLIENT_ID).text == SANDBOX_CLIENT


# ── UI flow ───────────────────────────────────────────────────────────────────

class TestLogonFlow:
    def test_starts_on_logon_screen(self, logon_window):
        router = logon_window.router
        assert router.current_tcode == LOGON_TCODE
        assert not router.logged_on
        assert router.renderer.session.info.user == ""

    def test_password_widget_is_masked(self, logon_window):
        w = logon_window.findChild(QLineEdit, "/app/con[0]/ses[0]/" + PASSWORD_ID)
        assert w is not None
        assert w.echoMode() == QLineEdit.EchoMode.Password

    def test_transactions_blocked_before_logon(self, logon_window):
        router = logon_window.router
        assert router.navigate("SE16") is None
        assert router.handle_command("/nSE16") is None
        assert router.go_back() is None
        assert router.current_tcode == LOGON_TCODE

    def test_wrong_password_shows_error_and_clears_password(self, logon_window):
        session = logon_window.renderer.session
        fill(session, password="wrong")
        session.send_vkey(0)
        assert logon_window.router.current_tcode == LOGON_TCODE
        assert "incorrect" in logon_window.statusBar().currentMessage()
        assert session.findById(PASSWORD_ID).text == ""
        assert session.findById(USER_ID).text == USER

    def test_logon_with_enter_vkey(self, logon_window):
        session = logon_window.renderer.session
        fill(session, user=USER.lower())
        session.send_vkey(0)
        router = logon_window.router
        assert router.logged_on
        assert router.current_tcode == "SESSION_MANAGER"
        assert router.renderer.session.info.user == USER
        assert logon_window.findChild(QTreeWidget, "nav_tree") is not None

    def test_user_carried_to_later_screens(self, logon_window):
        fill(logon_window.renderer.session)
        logon_window.renderer.session.send_vkey(0)
        session = logon_window.router.navigate("SE16")
        assert session.info.user == USER
        assert session.info.client == SANDBOX_CLIENT
        assert session.info.language == "EN"

    def test_logon_with_return_in_password_field(self, logon_window):
        fill(logon_window.renderer.session, password="")
        w = logon_window.findChild(QLineEdit, "/app/con[0]/ses[0]/" + PASSWORD_ID)
        w.setText(PASSWORD)
        w.returnPressed.emit()
        assert logon_window.router.current_tcode == "SESSION_MANAGER"

    def test_logon_with_toolbar_enter_and_empty_command(self, logon_window):
        fill(logon_window.renderer.session)
        logon_window._on_command_enter()
        assert logon_window.router.current_tcode == "SESSION_MANAGER"

    @pytest.mark.parametrize("command", ["/nend", "/NEX"])
    def test_log_off_command(self, logon_window, command):
        fill(logon_window.renderer.session)
        logon_window.renderer.session.send_vkey(0)
        logon_window.router.handle_command(command)
        assert logon_window.router.current_tcode == LOGON_TCODE
        assert not logon_window.router.logged_on
        assert logon_window.router.navigate("SE16") is None

    def test_logon_from_script_thread(self, logon_window, qapp):
        """A COM/HTTP script runs on another thread; sendVKey must wait for the new screen."""
        session = logon_window.renderer.session
        fill(session)
        done = threading.Event()
        errors = []

        def script():
            try:
                session.findById("wnd[0]").send_vkey(0)
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(exc)
            finally:
                done.set()

        threading.Thread(target=script, daemon=True).start()
        deadline = time.monotonic() + 5
        while not done.is_set() and time.monotonic() < deadline:
            qapp.processEvents()
        assert done.is_set() and not errors
        assert logon_window.router.current_tcode == "SESSION_MANAGER"

    def test_no_logon_by_default(self, main_window):
        main_window.load_initial_screen()
        assert main_window.router.logged_on
        assert main_window.router.current_tcode == "SESSION_MANAGER"

    def test_script_thread_field_write_reaches_widget(self, logon_window, qapp):
        """Field values set from a script thread show up in the widget via the GUI thread."""
        session = logon_window.renderer.session
        t = threading.Thread(target=lambda: setattr(session.findById(USER_ID), "value", "FROM_SCRIPT"))
        t.start()
        t.join()
        w = logon_window.findChild(QLineEdit, "/app/con[0]/ses[0]/" + USER_ID)
        deadline = time.monotonic() + 5
        while w.text() != "FROM_SCRIPT" and time.monotonic() < deadline:
            qapp.processEvents()
        assert w.text() == "FROM_SCRIPT"
        assert session.findById(USER_ID).text == "FROM_SCRIPT"
