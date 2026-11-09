# SPDX-License-Identifier: Apache-2.0
"""COM collection access the way VBScript does it: obj.Children(0) in one call."""
import pytest

pythoncom = pytest.importorskip("pythoncom")
win32com_client = pytest.importorskip("win32com.client")

from bridge.com_server import ComApplication, SessionHolder, _wrap  # noqa: E402
from engine import load_screen  # noqa: E402
from engine.navigation import SCREEN_DIR  # noqa: E402

# VBScript sends a call with an argument as method and property-get at once.
VBS_CALL = pythoncom.DISPATCH_METHOD | pythoncom.DISPATCH_PROPERTYGET


def vbs_index(disp, name, index):
    """Call disp.name(index) as VBScript does, and return the result as a Dispatch."""
    ole = disp._oleobj_ if hasattr(disp, "_oleobj_") else disp
    dispid = ole.GetIDsOfNames(name)
    return win32com_client.Dispatch(ole.Invoke(dispid, 0, VBS_CALL, True, index))


@pytest.fixture
def app():
    session = load_screen(SCREEN_DIR / "01_SESSION_MANAGER.json")
    return win32com_client.Dispatch(_wrap(ComApplication(SessionHolder(session))))


def test_children_index_returns_the_item(app):
    connection = vbs_index(app, "Children", 0)
    assert connection.Type == "GuiConnection"
    session = vbs_index(connection, "Children", 0)
    assert session.Type == "GuiSession"
    assert vbs_index(session, "Children", 0).Type == "GuiMainWindow"


def test_connections_and_sessions_index(app):
    connection = vbs_index(app, "Connections", 0)
    assert vbs_index(connection, "Sessions", 0).Type == "GuiSession"


def test_children_without_index_is_a_collection(app):
    assert app.Children.Count == 1
    assert app.Children.Item(0).Type == "GuiConnection"


def test_control_children_index(app):
    session = app.Children.Item(0).Children.Item(0)
    wnd = session.findById("wnd[0]")
    assert vbs_index(wnd, "Children", 0).Type == wnd.Children.Item(0).Type
