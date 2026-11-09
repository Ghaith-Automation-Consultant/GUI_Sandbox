# SPDX-License-Identifier: Apache-2.0
"""Run PySapGUI's password helpers (pysapgui.saplogonpwd) against the sandbox.

PySapGUI is a test-only dependency (GPL-2.0, see requirements-dev.txt); the app
never imports it. The library talks to the sandbox through the in-process COM
wrappers, exactly as it would to SAP GUI, so the IDs and behaviour it relies on
are checked here:

    wnd[1]/usr/pwdRSYST-NCODE, wnd[1]/usr/pwdRSYST-NCOD2        logon-time change
    /NSU3, wnd[0]/tbar[1]/btn[6]                                 SU3 change
    wnd[1]/usr/subSUBSCREEN:SAPMSYST:0043/pwdRSYST-BCODE|NCODE|NCOD2
    wnd[2] after Enter means the password was rejected
    wnd[0]/sbar MessageNumber 180/190 (can't change), 343 (no such transaction)
"""
import pytest

saplogonpwd = pytest.importorskip("pysapgui.saplogonpwd")
pytest.importorskip("win32com.client")

import win32com.client  # noqa: E402
from pysapgui.transaction import SAPTransaction  # noqa: E402

from bridge.com_server import ComSession, SessionHolder, _wrap  # noqa: E402
from engine.environments import find_environment, load_environments  # noqa: E402
from engine.navigation import HOME_TCODE, LOGON_TCODE, Navigator  # noqa: E402
from engine.users import UserStore  # noqa: E402

SAPLogonPwd = saplogonpwd.SAPLogonPwd
ENVS = load_environments()


def connect(env_id="WL"):
    nav = Navigator(users=UserStore.load())
    holder = SessionHolder()
    nav.subscribe(lambda session, _tcode: setattr(holder, "session", session))
    nav.connect(find_environment(ENVS, env_id))
    return nav, win32com.client.Dispatch(_wrap(ComSession(holder)))


def log_on(session, user, password):
    session.findById("wnd[0]/usr/txtRSYST-BNAME").text = user
    session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = password
    session.findById("wnd[0]").sendVKey(0)


@pytest.fixture(autouse=True)
def policy():
    """A 10-character policy fits the sandbox rules (8 to 40 characters)."""
    SAPLogonPwd.set_password_policy({"min_password_lng": 10, "min_password_digits": 2})
    yield
    SAPLogonPwd.password_policy = None


class TestLogonPasswordChange:
    def test_initial_password_is_changed(self):
        nav, session = connect()
        log_on(session, "USER_NEW", "welcome1")
        assert session.ActiveWindow.Type == "GuiModalWindow"
        assert SAPLogonPwd.is_change_password_window_while_connect(session) is None
        assert nav.tcode == HOME_TCODE
        assert session.Info.User == "USER_NEW"
        assert not nav.users.is_initial("WL", "USER_NEW")

    def test_new_password_works_at_next_logon(self):
        nav, session = connect()
        log_on(session, "USER_NEW", "welcome1")
        new = SAPLogonPwd._SAPLogonPwd__change_password_login(session)
        session.findById("wnd[0]/tbar[0]/okcd").text = "/nend"
        session.findById("wnd[0]").sendVKey(0)
        log_on(session, "USER_NEW", new)
        assert nav.tcode == HOME_TCODE

    def test_refusing_to_change_cancels_popup(self):
        nav, session = connect()
        log_on(session, "USER_NEW", "welcome1")
        with pytest.raises(RuntimeError, match="Change password"):
            SAPLogonPwd.is_change_password_window_while_connect(session, change_pwd=False)
        assert nav.popup is None and nav.tcode == LOGON_TCODE

    def test_no_popup_for_a_normal_user(self):
        nav, session = connect()
        log_on(session, "USER_STANDARD", "sandbox")
        assert SAPLogonPwd.is_change_password_window_while_connect(session) is None
        assert nav.tcode == HOME_TCODE

    def test_password_too_short_is_rejected(self):
        nav, session = connect()
        log_on(session, "USER_NEW", "welcome1")
        SAPLogonPwd.set_password_policy({"min_password_lng": 6})
        with pytest.raises(AttributeError, match="Couldn't set new password"):
            SAPLogonPwd.is_change_password_window_while_connect(session)
        assert session.findById("wnd[2]").Type == "GuiModalWindow"


class TestSU3PasswordChange:
    def test_change_own_password(self):
        nav, session = connect()
        log_on(session, "USER_STANDARD", "sandbox")
        new = SAPLogonPwd.change_password_su3(session, "sandbox")
        assert nav.tcode == "SU3"
        assert session.findById("wnd[0]/sbar").text == "Password changed"
        assert nav.users.check("WL", "USER_STANDARD", new)

    def test_rejected_password_raises_and_cleans_up(self):
        nav, session = connect()
        log_on(session, "USER_STANDARD", "sandbox")
        SAPLogonPwd.set_password_policy({"min_password_lng": 6})
        with pytest.raises(AttributeError, match="Couldn't set new password"):
            SAPLogonPwd.change_password_su3(session, "sandbox")
        assert session.Children.Count == 1  # the library closed wnd[2] and wnd[1]
        assert nav.users.check("WL", "USER_STANDARD", "sandbox")

    def test_wrong_old_password_raises(self):
        _nav, session = connect()
        log_on(session, "USER_STANDARD", "sandbox")
        with pytest.raises(AttributeError, match="Couldn't set new password"):
            SAPLogonPwd.change_password_su3(session, "not-my-password")

    def test_user_without_password_gets_190(self):
        _nav, session = connect("NL")
        with pytest.raises(RuntimeError, match="Password could not be changed"):
            SAPLogonPwd.change_password_su3(session, "anything")


class TestTransactionCall:
    def test_unknown_transaction_is_343(self):
        _nav, session = connect("NL")
        with pytest.raises(ValueError, match="Wrong transaction name"):
            SAPTransaction.call(session, "ZZ_NOPE")
