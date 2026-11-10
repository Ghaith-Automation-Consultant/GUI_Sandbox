# SPDX-License-Identifier: Apache-2.0
"""Users per environment (users.json) and the set / forced / SU3 / reset password popups."""
import json
import threading
import time

import pytest
from PySide6.QtWidgets import QLineEdit, QPushButton

from engine.environments import find_environment, load_environments
from engine.navigation import HOME_TCODE, LOGON_TCODE, Navigator
from engine.session import ModalWindow
from engine.users import USERS_FILE, UserStore, validate_new_password

WL = find_environment(load_environments(), "WL")
NEW, REPEAT = "wnd[1]/usr/pwdRSYST-NCODE", "wnd[1]/usr/pwdRSYST-NCOD2"
SU3_FIELDS = "wnd[1]/usr/subSUBSCREEN:SAPMSYST:0043/pwdRSYST-"


def logon_fields(session, user, password):
    session.findById("wnd[0]/usr/txtRSYST-MANDT").value = "000"
    session.findById("wnd[0]/usr/txtRSYST-BNAME").value = user
    session.findById("wnd[0]/usr/pwdRSYST-BCODE").value = password


def log_on(nav, user="USER_STANDARD", password="sandbox"):
    logon_fields(nav.session, user, password)
    nav.session.findById("wnd[0]").send_vkey(0)


def enter_new(session, new, repeat=None):
    session.findById(NEW).value = new
    session.findById(REPEAT).value = new if repeat is None else repeat
    session.findById("wnd[1]").send_vkey(0)


@pytest.fixture
def nav():
    nav = Navigator(users=UserStore.load())
    nav.connect(WL)
    return nav


# ── users.json and the rules ──────────────────────────────────────────────────

class TestUserStore:
    def test_shipped_users(self):
        store = UserStore.load(environment_ids=["WL", "NL"])
        assert store.users("WL") == ["USER_STANDARD", "USER_NEW"]
        assert store.check("WL", "user_standard", "sandbox")
        assert not store.check("WL", "USER_STANDARD", "SANDBOX")
        assert store.is_initial("WL", "USER_NEW")
        assert store.users("NL") == []

    def test_changes_stay_in_memory(self):
        before = USERS_FILE.read_text(encoding="utf-8")
        store = UserStore.load()
        assert store.change_password("WL", "USER_STANDARD", "sandbox", "longer-pw1", "longer-pw1") is None
        assert store.check("WL", "USER_STANDARD", "longer-pw1")
        assert UserStore.load().check("WL", "USER_STANDARD", "sandbox")
        assert USERS_FILE.read_text(encoding="utf-8") == before

    @pytest.mark.parametrize("data, match", [
        ({"WL": [{"user": "A", "password": "x"}, {"user": "a", "password": "y"}]}, "duplicate user"),
        ({"WL": [{"password": "x"}]}, "user"),
        ({"XX": []}, "unknown environment"),
    ])
    def test_bad_files_rejected(self, tmp_path, data, match):
        path = tmp_path / "users.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match=match):
            UserStore.load(path, environment_ids=["WL"])

    @pytest.mark.parametrize("old, new, repeat, expected", [
        ("old-pass1", "", "", "Enter a new password"),
        ("old-pass1", "new-pass1", "new-pass2", "do not match"),
        ("same-pass1", "same-pass1", "same-pass1", "different from your current"),
        ("old-pass1", "short", "short", "at least 8"),
        ("old-pass1", "x" * 41, "x" * 41, "at most 40"),
        ("old-pass1", "new-pass1", "new-pass1", None),
    ])
    def test_rules(self, old, new, repeat, expected):
        error = validate_new_password(old, new, repeat)
        assert error is None if expected is None else expected in error


# ── Set: New Password on the logon screen ─────────────────────────────────────

class TestSetPassword:
    def test_opens_popup_after_checking_credentials(self, nav):
        logon_fields(nav.session, "USER_STANDARD", "sandbox")
        nav.session.findById("wnd[0]/tbar[1]/btn[5]").press()
        popup = nav.session.active_window
        assert isinstance(popup, ModalWindow) and popup.sap_type == "GuiModalWindow"
        assert popup.id.endswith("wnd[1]")
        assert nav.session.findById(NEW) is not None

    def test_wrong_credentials_open_no_popup(self, nav):
        logon_fields(nav.session, "USER_STANDARD", "wrong")
        nav.session.findById("wnd[0]").send_vkey(5)
        assert nav.popup is None
        assert "incorrect" in nav.session.findById("wnd[0]/sbar").text

    def test_change_logs_on(self, nav):
        logon_fields(nav.session, "USER_STANDARD", "sandbox")
        nav.session.findById("wnd[0]").send_vkey(5)
        enter_new(nav.session, "brand-new-1")
        assert nav.tcode == HOME_TCODE and nav.popup is None
        assert nav.session.findById("wnd[0]/sbar").text == "Password changed"
        assert nav.users.check("WL", "USER_STANDARD", "brand-new-1")

    def test_mismatch_shows_message_popup(self, nav):
        logon_fields(nav.session, "USER_STANDARD", "sandbox")
        nav.session.findById("wnd[0]").send_vkey(5)
        session = nav.session
        enter_new(session, "brand-new-1", "brand-new-2")
        message = session.findById("wnd[2]")
        assert message.sap_type == "GuiModalWindow"
        assert "do not match" in session.findById("wnd[2]/usr/txtMESSTXT1").text
        assert session.findById("wnd[0]/sbar").message_type == "E"
        session.findById("wnd[1]").send_vkey(0)  # blocked while wnd[2] is open
        assert session.get_window(2) is not None
        session.findById("wnd[2]").send_vkey(0)
        assert session.get_window(2) is None and session.get_window(1) is not None
        enter_new(session, "brand-new-1")
        assert nav.tcode == HOME_TCODE

    def test_cancel_stays_logged_off(self, nav):
        logon_fields(nav.session, "USER_STANDARD", "sandbox")
        nav.session.findById("wnd[0]").send_vkey(5)
        nav.session.findById("wnd[1]/tbar[0]/btn[12]").press()
        assert nav.popup is None and nav.tcode == LOGON_TCODE and not nav.logged_on

    def test_main_window_keys_blocked_while_popup_open(self, nav):
        logon_fields(nav.session, "USER_STANDARD", "sandbox")
        nav.session.findById("wnd[0]").send_vkey(5)
        nav.session.findById("wnd[0]").send_vkey(0)
        assert nav.tcode == LOGON_TCODE and nav.popup is not None


# ── Forced: initial password ──────────────────────────────────────────────────

class TestForcedChange:
    def test_initial_user_must_change(self, nav):
        log_on(nav, "USER_NEW", "welcome1")
        assert nav.tcode == LOGON_TCODE and nav.popup is not None
        assert "Choose a new password" in nav.session.findById("wnd[1]/usr/lblMESSAGE").text
        enter_new(nav.session, "welcome1")
        assert "different" in nav.session.findById("wnd[2]/usr/txtMESSTXT1").text
        nav.session.findById("wnd[2]/tbar[0]/btn[0]").press()
        enter_new(nav.session, "welcome22")
        assert nav.tcode == HOME_TCODE
        assert nav.session.info.user == "USER_NEW"
        assert nav.session.findById("wnd[0]/titl").text == "Easy Access - Menu for USER_NEW"
        assert not nav.users.is_initial("WL", "USER_NEW")

    def test_cancel_stays_logged_off(self, nav):
        log_on(nav, "USER_NEW", "welcome1")
        nav.session.findById("wnd[1]").send_vkey(12)
        assert nav.tcode == LOGON_TCODE and not nav.logged_on
        assert nav.users.is_initial("WL", "USER_NEW")


# ── SU3: change your own password ─────────────────────────────────────────────

class TestSU3:
    def test_change_own_password(self, nav):
        log_on(nav)
        nav.handle_command("/nSU3")
        session = nav.session
        assert session.findById("wnd[0]/usr/txtSUID_ST_BNAME-BNAME").text == "USER_STANDARD"
        session.findById("wnd[0]/tbar[1]/btn[6]").press()
        session.findById(SU3_FIELDS + "BCODE").value = "sandbox"
        session.findById(SU3_FIELDS + "NCODE").value = "su3-pass-1"
        session.findById(SU3_FIELDS + "NCOD2").value = "su3-pass-1"
        session.findById("wnd[1]").send_vkey(0)
        assert session.get_window(1) is None
        assert session.findById("wnd[0]/sbar").text == "Password changed"
        assert nav.users.check("WL", "USER_STANDARD", "su3-pass-1")

    def test_wrong_old_password(self, nav):
        log_on(nav)
        nav.handle_command("/nSU3")
        session = nav.session
        session.findById("wnd[0]/tbar[1]/btn[6]").press()
        session.findById(SU3_FIELDS + "BCODE").value = "wrong"
        session.findById(SU3_FIELDS + "NCODE").value = "su3-pass-1"
        session.findById(SU3_FIELDS + "NCOD2").value = "su3-pass-1"
        session.findById("wnd[1]").send_vkey(0)
        assert session.get_window(2) is not None

    def test_no_logon_user_gets_message_190(self):
        nav = Navigator(users=UserStore.load())
        nav.connect(find_environment(load_environments(), "NL"))
        nav.handle_command("/nSU3")
        nav.session.findById("wnd[0]/tbar[1]/btn[6]").press()
        sbar = nav.session.findById("wnd[0]/sbar")
        assert sbar.message_number == "190" and sbar.message_type == "E"
        assert nav.popup is None


# ── Reset: SU01 ───────────────────────────────────────────────────────────────

class TestReset:
    def reset(self, nav, user):
        nav.handle_command("/nSU01")
        nav.session.findById("wnd[0]/usr/ctxtSUID_ST_BNAME-BNAME").value = user
        nav.session.findById("wnd[0]").send_vkey(20)

    def test_reset_forces_change_at_next_logon(self, nav):
        log_on(nav)
        self.reset(nav, "USER_STANDARD")
        assert "USER_STANDARD" in nav.session.findById("wnd[1]").text
        enter_new(nav.session, "reset-pw-1")
        assert nav.session.findById("wnd[0]/sbar").text == "Password for user USER_STANDARD was reset"
        nav.handle_command("/nend")
        log_on(nav, "USER_STANDARD", "reset-pw-1")
        assert nav.tcode == LOGON_TCODE and nav.popup is not None
        enter_new(nav.session, "after-reset-1")
        assert nav.tcode == HOME_TCODE

    def test_button_opens_popup(self, nav):
        log_on(nav)
        nav.handle_command("/nSU01")
        nav.session.findById("wnd[0]/usr/ctxtSUID_ST_BNAME-BNAME").value = "user_new"
        nav.session.findById("wnd[0]/tbar[1]/btn[20]").press()
        assert nav.popup is not None

    def test_unknown_user(self, nav):
        log_on(nav)
        self.reset(nav, "NOBODY")
        assert nav.popup is None
        assert nav.session.findById("wnd[0]/sbar").text == "User NOBODY does not exist"


class TestMessageNumber:
    def test_unknown_transaction_is_343(self, nav):
        log_on(nav)
        nav.handle_command("/nZZ_NOPE")
        assert nav.session.findById("wnd[0]/sbar").message_number == "343"


# ── The Qt dialog ─────────────────────────────────────────────────────────────

@pytest.fixture
def window(qapp):
    from main import MainWindow
    win = MainWindow()
    win.open_environment(WL)
    yield win
    for dialog in list(win.router.dialogs.values()):
        dialog.close_from_engine()
    win.close()
    win.deleteLater()


class TestPopupDialog:
    def test_dialog_shows_masked_fields_and_continue_works(self, window, qapp):
        session = window.renderer.session
        logon_fields(session, "USER_NEW", "welcome1")
        session.findById("wnd[0]").send_vkey(0)
        dialog = window.router.dialogs[1]
        assert dialog.isVisible() and dialog.windowTitle() == "Change Password"
        field = dialog.findChild(QLineEdit, "/app/con[0]/ses[0]/" + NEW)
        assert field.echoMode() == QLineEdit.EchoMode.Password
        field.setText("dialog-pw-1")
        dialog.findChild(QLineEdit, "/app/con[0]/ses[0]/" + REPEAT).setText("dialog-pw-1")
        dialog.findChild(QPushButton, "/app/con[0]/ses[0]/wnd[1]/tbar[0]/btn[0]").click()
        qapp.processEvents()
        assert window.router.current_tcode == HOME_TCODE
        assert window.router.dialogs == {}

    def test_closing_dialog_cancels(self, window, qapp):
        session = window.renderer.session
        logon_fields(session, "USER_NEW", "welcome1")
        session.findById("wnd[0]").send_vkey(0)
        window.router.dialogs[1].reject()  # Esc
        qapp.processEvents()
        assert window.router.dialogs == {}
        assert window.router.current_tcode == LOGON_TCODE

    def test_popup_from_script_thread(self, window, qapp):
        session = window.renderer.session
        logon_fields(session, "USER_NEW", "welcome1")
        done = threading.Event()
        threading.Thread(target=lambda: (session.findById("wnd[0]").send_vkey(0), done.set()),
                         daemon=True).start()
        deadline = time.monotonic() + 5
        while not done.is_set() and time.monotonic() < deadline:
            qapp.processEvents()
        assert done.is_set()
        assert 1 in window.router.dialogs
