# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
SAP GUI Scripting Bridge — core connection module.

Usage (attach to a running SAP session):
    from tools.sap_connect import get_session
    session = get_session()

Usage (launch SAP and log in programmatically):
    from tools.sap_connect import launch_and_login
    session = launch_and_login(system_name="MY_SYSTEM", client="000", user="...", password="...")
"""

import subprocess
import time
import win32com.client

SAP_LOGON_EXE = r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe"


def get_sap_app():
    """Return the running SAPGui Application COM object, or None."""
    try:
        sap_gui_auto = win32com.client.GetObject("SAPGUI")
        return sap_gui_auto.GetScriptingEngine  # property, not a method call
    except Exception:
        return None


def get_session(connection_index=0, session_index=0):
    """
    Attach to an already-open SAP GUI session.
    Returns a GuiSession object, or raises RuntimeError if SAP is not running.
    """
    app = get_sap_app()
    if app is None:
        raise RuntimeError(
            "SAP GUI is not running. Start it manually or call launch_and_login()."
        )
    if app.Connections.Count == 0:
        raise RuntimeError("SAP GUI is open but no connections are active. Log in first.")

    conn = app.Connections(connection_index)
    session = conn.Children(session_index)
    print(f"[sap_connect] Attached to: {conn.Description}  |  session {session_index}")
    return session


def launch_and_login(system_name: str, client: str, user: str, password: str,
                     language: str = "EN", connection_index: int = 0):
    """
    Launch SAP Logon (if not running), open a connection to system_name, and log in.

    system_name: the name as it appears in SAPUILandscape.xml (e.g. "My SAP System")
    Returns a GuiSession object.
    """
    app = get_sap_app()
    if app is None:
        subprocess.Popen([SAP_LOGON_EXE])
        time.sleep(4)
        app = get_sap_app()
        if app is None:
            raise RuntimeError("Could not start SAP GUI.")

    # Open a new connection by system name
    conn = app.OpenConnection(system_name, Sync=True)
    session = conn.Children(0)

    # Fill in the logon screen (wnd[0])
    session.findById("wnd[0]/usr/txtRSYST-MANDT").text = client
    session.findById("wnd[0]/usr/txtRSYST-BNAME").text = user
    session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = password
    session.findById("wnd[0]/usr/txtRSYST-LANGU").text = language
    session.findById("wnd[0]").sendVKey(0)  # Enter
    time.sleep(2)

    # Handle "already logged in" popup if it appears
    try:
        session.findById("wnd[1]")
        # Option: /radMULTI_LOGON_OPT2 = continue with new session
        session.findById("wnd[1]/usr/radMULTI_LOGON_OPT2").select()
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        time.sleep(1)
    except Exception:
        pass

    print(f"[sap_connect] Logged in as {user} on {system_name}")
    return session


def list_connections():
    """Print all open SAP connections and sessions."""
    app = get_sap_app()
    if app is None:
        print("SAP GUI is not running.")
        return
    for i in range(app.Connections.Count):
        conn = app.Connections(i)
        print(f"Connection [{i}]: {conn.Description}")
        for j in range(conn.Children.Count):
            s = conn.Children(j)
            print(f"  Session [{j}]: {s.Info.SystemName} / {s.Info.User} / {s.ActiveWindow.Text}")


if __name__ == "__main__":
    list_connections()
