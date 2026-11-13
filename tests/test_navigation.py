# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""Script-driven navigation: engine, in-process, HTTP, and the live Qt window."""
import threading

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QTableView

from bridge import RemoteSession, SandboxSession, start_server
from engine import load_screen
from engine.navigation import SCREEN_DIR, Navigator

TABLE_FIELD = "wnd[0]/usr/ctxtDATABROWSE-TABLENAME"
GRID = "wnd[0]/usr/cntlGRID1/shellcont/shell"
OKCD = "wnd[0]/tbar[0]/okcd"


def home():
    return load_screen(SCREEN_DIR / "01_SESSION_MANAGER.json")


class TestNavigator:
    def test_start_transaction_loads_the_screen(self):
        nav = Navigator(home())
        session = nav.start_transaction("SE16")
        assert session.info.transaction == "SE16"
        assert session.findById(TABLE_FIELD) is not None
        assert nav.session is session

    def test_old_session_start_transaction_navigates(self):
        first = home()
        nav = Navigator(first)
        first.start_transaction("se16")
        assert nav.tcode == "SE16"
        assert nav.session.findById(TABLE_FIELD) is not None

    def test_unknown_transaction_stays_put_and_reports(self):
        first = home()
        nav = Navigator(first)
        assert nav.start_transaction("ZZ_FAKE") is None
        assert nav.session is first
        assert nav.tcode == "SESSION_MANAGER"
        assert "ZZ_FAKE" in first.findById("wnd[0]/sbar").text

    def test_command_field_and_enter_navigate(self):
        nav = Navigator(home())
        nav.session.findById(OKCD).value = "/nSE38"
        nav.session.send_vkey(0)
        assert nav.tcode == "SE38"

    def test_slash_n_alone_goes_home(self):
        nav = Navigator()
        nav.start_transaction("SE16")
        nav.session.findById(OKCD).value = "/n"
        nav.session.send_vkey(0)
        assert nav.tcode == "SESSION_MANAGER"

    def test_vkeys_walk_the_se16_flow(self):
        nav = Navigator()
        nav.start_transaction("SE16")
        nav.session.send_vkey(7)
        assert nav.step == 1
        nav.session.send_vkey(8)
        assert nav.step == 2
        assert nav.session.findById(GRID).row_count == 120

    def test_back_steps_then_goes_home(self):
        nav = Navigator()
        nav.start_transaction("SE16")
        nav.session.send_vkey(7)
        nav.session.send_vkey(3)
        assert (nav.tcode, nav.step) == ("SE16", 0)
        nav.session.send_vkey(3)
        assert nav.tcode == "SESSION_MANAGER"

    def test_button_press_advances(self):
        nav = Navigator()
        nav.start_transaction("SE16")
        nav.session.findById("wnd[0]/tbar[1]/btn[7]").press()
        assert nav.step == 1

    def test_press_on_a_replaced_screen_is_ignored(self):
        nav = Navigator()
        old = nav.start_transaction("SE16")
        button = old.findById("wnd[0]/tbar[1]/btn[7]")
        nav.start_transaction("SE38")
        button.press()
        assert (nav.tcode, nav.step) == ("SE38", 0)

    def test_session_loaded_mid_flow_knows_its_step(self):
        session = load_screen(SCREEN_DIR / "03_SE16_SFLIGHT_selection_screen.json")
        nav = Navigator(session)
        assert (nav.tcode, nav.step) == ("SE16", 1)

    def test_listeners_receive_each_new_session(self):
        seen = []
        nav = Navigator()
        nav.subscribe(lambda session, tcode: seen.append((session, tcode)))
        session = nav.start_transaction("SM37")
        assert seen == [(session, "SM37")]


class TestSessionWithoutNavigator:
    def test_start_transaction_still_only_records_the_code(self):
        session = home()
        session.start_transaction("SE16")
        assert session.info.transaction == "SE16"
        assert session.navigator is None


class TestInProcessBridge:
    def test_full_flow(self):
        session = SandboxSession(home())
        session.StartTransaction("SE16")
        session.findById(TABLE_FIELD).Text = "SFLIGHT"
        session.findById("wnd[0]").sendVKey(7)
        session.findById("wnd[0]").sendVKey(8)
        assert session.findById(GRID).GetCellValue(0, "CARRID") == "SX"
        assert session.Info.Transaction == "SE16"

    def test_status_bar_message_type(self):
        session = SandboxSession(home())
        session.StartTransaction("ZZ_FAKE")
        sbar = session.findById("wnd[0]/sbar")
        assert sbar.MessageType == "E"
        assert sbar.MessageId == ""
        assert session.findById(OKCD).MessageType == ""


class TestHttpBridge:
    @pytest.fixture
    def remote(self):
        server = start_server(home(), port=0)
        yield RemoteSession(server.url)
        server.shutdown()
        server.server_close()

    def test_full_flow(self, remote):
        remote.StartTransaction("SE16")
        remote.findById(TABLE_FIELD).Text = "SFLIGHT"
        remote.findById("wnd[0]").sendVKey(7)
        remote.findById("wnd[0]").sendVKey(8)
        grid = remote.findById(GRID)
        assert grid.RowCount == 120
        assert grid.GetCellValue(0, "CARRID") == "SX"

    def test_command_field(self, remote):
        remote.findById(OKCD).Text = "SU01"
        remote.findById("wnd[0]").sendVKey(0)
        assert remote.Info.Transaction == "SU01"

    def test_unknown_transaction_sets_status(self, remote):
        remote.StartTransaction("ZZ_FAKE")
        assert remote.Info.Transaction == "SESSION_MANAGER"
        sbar = remote.findById("wnd[0]/sbar")
        assert "ZZ_FAKE" in sbar.Text
        assert sbar.MessageType == "E"
        assert sbar.MessageId == ""

    def test_load_screen_keeps_navigation_working(self, remote):
        remote.load_screen(str(SCREEN_DIR / "02_SE16_initial.json"))
        remote.findById("wnd[0]").sendVKey(7)
        assert remote.findById("wnd[0]/usr/ctxtI1-LOW") is not None


def run_in_thread(qapp, fn):
    """Run fn on a worker thread, as a COM call would, while Qt keeps running."""
    outcome = {}

    def work():
        try:
            outcome["result"] = fn()
        except Exception as exc:
            outcome["error"] = exc

    thread = threading.Thread(target=work)
    thread.start()
    while thread.is_alive():
        qapp.processEvents()
        thread.join(0.01)
    qapp.processEvents()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")


class TestLiveWindow:
    @pytest.fixture
    def ready(self, qapp, main_window):
        main_window.load_initial_screen()
        return main_window

    def test_script_thread_navigates_and_window_renders(self, qapp, ready):
        session = ready.router.navigator.session
        run_in_thread(qapp, lambda: session.start_transaction("SE38"))
        assert ready.router.current_tcode == "SE38"
        assert "SE38" in ready.windowTitle()

    def test_script_thread_full_flow_renders_the_grid(self, qapp, ready):
        def script():
            nav = ready.router.navigator
            nav.session.start_transaction("SE16")
            nav.session.send_vkey(7)
            nav.session.send_vkey(8)

        run_in_thread(qapp, script)
        qapp.processEvents()
        assert ready.router._current_step == 2
        workspace = ready.findChild(type(ready.centralWidget()), "workspace_panel")
        assert any(t.isVisibleTo(ready) for t in workspace.findChildren(QTableView))

    def test_script_thread_field_write_updates_the_widget(self, qapp, ready):
        ready.router.navigate("SE16")
        session = ready.router.navigator.session
        run_in_thread(qapp, lambda: setattr(session.findById(TABLE_FIELD), "value", "SFLIGHT"))
        qapp.processEvents()
        workspace = ready.findChild(type(ready.centralWidget()), "workspace_panel")
        assert "SFLIGHT" in [w.text() for w in workspace.findChildren(QLineEdit)]

    def test_script_thread_unknown_transaction_shows_status(self, qapp, ready):
        session = ready.router.navigator.session
        run_in_thread(qapp, lambda: session.start_transaction("ZZ_FAKE"))
        assert "ZZ_FAKE" in ready.statusBar().currentMessage()

    def test_returning_home_then_opening_a_transaction(self, qapp, ready):
        """Widgets queued for deletion on the way home must not be reused."""
        for tcode in ("SE16", "SESSION_MANAGER", "SE16", "SESSION_MANAGER", "SE38"):
            ready.router.navigate(tcode)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            qapp.processEvents()
        assert ready.router.current_tcode == "SE38"

    def test_script_thread_se38_source_renders_editor(self, qapp, ready):
        def script():
            nav = ready.router.navigator
            nav.session.start_transaction("SE38")
            nav.session.send_vkey(7)

        run_in_thread(qapp, script)
        assert ready.findChildren(QPlainTextEdit)
