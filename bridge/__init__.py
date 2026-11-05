# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer C — Scripting Bridge.

Exposes the engine.Session (Layer B) to external automation scripts via two
complementary mechanisms:

──────────────────────────────────────────────────────────────────────────────
1. In-process Python API  (same process)
──────────────────────────────────────────────────────────────────────────────
Wrap any engine.Session in a SandboxSession to get a SAP GUI Scripting
COM-compatible interface — both PascalCase (SAP COM) and snake_case (Pythonic)
property names are supported.

    from bridge import SandboxSession
    from engine import load_screen

    session = SandboxSession(load_screen("screens/02_SE16_initial.json"))

    # SAP COM style (unchanged from real RPA scripts)
    session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
    session.findById("wnd[0]").sendVKey(0)
    print(session.Info.Transaction)

    # Pythonic lowercase works too
    session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").text = "SCARR"

    # Check the action log
    for entry in session.recorder.entries():
        print(entry)

──────────────────────────────────────────────────────────────────────────────
2. HTTP JSON API  (separate process / UiPath / any language)
──────────────────────────────────────────────────────────────────────────────
start_server() runs the sandbox as a local REST service.
RemoteSession connects to it with the exact same API as SandboxSession.

    # === Server process (sandbox) ===
    from bridge import start_server
    from engine import load_screen

    server = start_server(load_screen("screens/02_SE16_initial.json"), port=7654)
    print(f"Bridge at {server.url}")
    input("Press Enter to stop…")

    # === Client process (automation script) ===
    from bridge import RemoteSession

    session = RemoteSession("http://localhost:7654")
    assert session.ping()
    session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
    session.findById("wnd[0]").sendVKey(0)
    print(session.get_log())

    # Load a different captured screen on the server
    session.load_screen("screens/03_SE16_SFLIGHT_selection_screen.json")
"""

from .proxy import (
    SessionProxy as SandboxSession,
    ControlProxy,
    ChildrenCollection,
    ColumnsCollection,
    ColumnTitlesCollection,
    SessionInfoProxy,
)
from .server import SandboxServer, start_server
from .client import RemoteSession, RemoteControlProxy
from .recorder import ActionRecorder
from .com_thread import ComBridge
from .com_server import ComSapGui, SessionHolder

__all__ = [
    # In-process API
    "SandboxSession",
    "ControlProxy",
    "ChildrenCollection",
    "ColumnsCollection",
    "ColumnTitlesCollection",
    "SessionInfoProxy",
    # HTTP server
    "SandboxServer",
    "start_server",
    # HTTP client
    "RemoteSession",
    "RemoteControlProxy",
    # Logging
    "ActionRecorder",
    # COM bridge
    "ComBridge",
    "ComSapGui",
    "SessionHolder",
]
