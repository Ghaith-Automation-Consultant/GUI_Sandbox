# SPDX-License-Identifier: Apache-2.0
"""SAP Logon pad: the environment list, opening an environment, and OpenConnection."""
import json

import pytest
from PySide6.QtWidgets import QPushButton, QTreeWidget

from engine.environments import find_environment, load_environments
from engine.logon import SANDBOX_CLIENT
from engine.navigation import HOME_TCODE, LOGON_TCODE, Navigator
from ui.logon_pad import LogonPad

ENVS = load_environments()
WL = find_environment(ENVS, "WL")
NL = find_environment(ENVS, "NL")
USER, PASSWORD = "USER_STANDARD", "sandbox"  # from users.json


def log_on(session):
    session.findById("wnd[0]/usr/txtRSYST-MANDT").value = SANDBOX_CLIENT
    session.findById("wnd[0]/usr/txtRSYST-BNAME").value = USER
    session.findById("wnd[0]/usr/pwdRSYST-BCODE").value = PASSWORD
    session.findById("wnd[0]").send_vkey(0)


# ── The list ──────────────────────────────────────────────────────────────────

class TestEnvironmentList:
    def test_shipped_entries(self):
        assert [env.id for env in ENVS] == ["WL", "NL"]
        assert WL.logon and not NL.logon
        assert WL.description == "WL - With logon"

    @pytest.mark.parametrize("name", ["WL", "wl", "WL - With logon", " wl - with LOGON "])
    def test_find_by_id_or_description(self, name):
        assert find_environment(ENVS, name) == WL

    def test_unknown_name(self):
        assert find_environment(ENVS, "PRD") is None

    def test_duplicate_id_rejected(self, tmp_path):
        entry = {"id": "A", "description": "A", "system": "SBX", "client": "000", "logon": True}
        path = tmp_path / "envs.json"
        path.write_text(json.dumps([entry, {**entry, "description": "B"}]), encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate id"):
            load_environments(path)

    def test_missing_field_rejected(self, tmp_path):
        path = tmp_path / "envs.json"
        path.write_text(json.dumps([{"id": "A", "description": "A"}]), encoding="utf-8")
        with pytest.raises(ValueError, match="system"):
            load_environments(path)


# ── The Navigator ─────────────────────────────────────────────────────────────

class TestConnect:
    def test_with_logon_starts_on_logon_screen(self):
        nav = Navigator()
        session = nav.connect(WL)
        assert nav.tcode == LOGON_TCODE
        assert session.info.system_name == WL.system
        assert nav.start_transaction("SE16") is None
        log_on(session)
        assert nav.tcode == HOME_TCODE
        assert nav.session.info.user == USER

    def test_no_logon_starts_on_easy_access(self):
        nav = Navigator()
        session = nav.connect(NL)
        assert nav.tcode == HOME_TCODE
        assert nav.logged_on
        assert session.info.system_name == NL.system
        assert session.info.client == NL.client
        assert nav.start_transaction("SE16") is not None

    def test_connecting_again_replaces_the_session(self):
        nav = Navigator()
        log_on(nav.connect(WL))
        nav.connect(WL)
        assert nav.tcode == LOGON_TCODE  # a fresh connection logs on again
        first = nav.session
        nav.connect(NL)
        assert nav.session is not first
        assert nav.environment == NL

    def test_disconnect(self):
        nav = Navigator()
        seen = []
        nav.subscribe(lambda session, tcode: seen.append((session, tcode)))
        nav.connect(NL)
        nav.disconnect()
        assert nav.session is None and nav.environment is None
        assert seen[-1] == (None, "")


# ── The pad and the window ────────────────────────────────────────────────────

@pytest.fixture
def pad(qapp):
    opened = []
    pad = LogonPad(ENVS, on_open=opened.append)
    pad.opened = opened
    yield pad
    pad.close()
    pad.deleteLater()


class TestLogonPad:
    def test_lists_entries(self, pad):
        tree = pad.findChild(QTreeWidget, "logon_pad/connections")
        assert tree.topLevelItemCount() == 2
        assert "WL - With logon" in tree.topLevelItem(0).text(0)
        assert tree.topLevelItem(1).text(1) == "SBX"
        assert pad.findChild(QPushButton, "logon_pad/btn_logon") is not None

    def test_double_click_opens(self, pad):
        tree = pad.connections
        tree.itemActivated.emit(tree.topLevelItem(0), 0)
        assert pad.opened == [WL]

    def test_log_on_button_opens_selection(self, pad):
        pad.select("NL")
        pad.btn_logon.click()
        assert pad.opened == [NL]


class TestWindowWithPad:
    def test_open_then_close_returns_to_pad(self, main_window, pad):
        main_window.logon_pad = pad
        pad.show()
        main_window.open_environment(WL)
        assert main_window.isVisible()
        assert main_window.router.current_tcode == LOGON_TCODE

        main_window.close()
        assert not main_window.isVisible()
        assert main_window.router.navigator.session is None
        assert pad.isVisible()

        main_window.open_environment(NL)
        assert main_window.router.current_tcode == HOME_TCODE
        main_window.logon_pad = None


# ── COM ───────────────────────────────────────────────────────────────────────

pythoncom = pytest.importorskip("pythoncom")
win32com_client = pytest.importorskip("win32com.client")
from bridge.com_server import ComApplication, SessionHolder, _wrap  # noqa: E402


@pytest.fixture
def com_app():
    nav = Navigator()
    holder = SessionHolder()

    def opener(description):
        env = find_environment(ENVS, description)
        if env is not None:
            holder.session = nav.connect(env)
            holder.environment = env
        return env

    holder.opener = opener
    return win32com_client.Dispatch(_wrap(ComApplication(holder)))


def vbs_call(disp, name, *args):
    """Call disp.name(args) the way VBScript does."""
    ole = disp._oleobj_
    flags = pythoncom.DISPATCH_METHOD | pythoncom.DISPATCH_PROPERTYGET
    return win32com_client.Dispatch(ole.Invoke(ole.GetIDsOfNames(name), 0, flags, True, *args))


class TestOpenConnection:
    def test_no_connection_until_opened(self, com_app):
        assert com_app.Children.Count == 0
        assert com_app.Connections.Count == 0

    def test_open_connection(self, com_app):
        connection = vbs_call(com_app, "OpenConnection", "WL - With logon", True)
        assert connection.Description == "WL - With logon"
        session = vbs_call(connection, "Children", 0)
        assert session.Info.Transaction == LOGON_TCODE
        assert session.Info.SystemName == "SBX"
        assert com_app.Children.Count == 1

    def test_open_by_id_from_python(self, com_app):
        connection = com_app.OpenConnection("NL", True)
        assert connection.Children(0).Info.Transaction == HOME_TCODE

    def test_unknown_entry_raises(self, com_app):
        with pytest.raises(pythoncom.com_error):
            com_app.OpenConnection("PRD - Production", True)
        assert com_app.Children.Count == 0
