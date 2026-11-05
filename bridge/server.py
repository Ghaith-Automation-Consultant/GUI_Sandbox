# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer C — HTTP bridge server.

Exposes a sandbox Session over a JSON REST API so that automation scripts
running in a separate process (UiPath, a test harness, another Python script)
can interact with the sandbox the same way they would with a real SAP session.

Endpoints
─────────
GET  /info           Session metadata (transaction, user, screen, …)
GET  /tree           Full control tree as nested JSON
GET  /controls       Flat list of all controls in the session
GET  /log            Action recorder entries

POST /findById       {"path": "wnd[0]/usr/ctxtFOO"}  →  control JSON
POST /action         {"path": "...", "action": "...", ...}  →  {"result": ...}
POST /loadScreen     {"file": "screens/02_SE16_initial.json"}  →  loads screen

Supported actions (POST /action)
──────────────────────────────────
getText       → {"result": "current text"}
setText       → value: "new value"
press         → trigger press/click
select        → trigger select (tab / radio button)
sendVKey      → key: <int>   (0=Enter, 3=Back, 8=Execute, 11=Save, 12=Cancel)
getInfo       → full control dict including children
getChildren   → list of direct child control dicts
getCellValue  → row: int, col: int|str  (TableControl: col index; GridView: col name)
startTransaction  → value: "SE16"

Usage::

    from bridge import start_server
    from engine import load_screen

    server = start_server(load_screen("screens/02_SE16_initial.json"), port=7654)
    print(f"Bridge listening at {server.url}")
    # server runs in a background daemon thread; keep the main process alive
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from engine.control import Control, TableControl, GridView, StatusBar
from engine.session import Session, Window
from engine.loader import load_screen as _load_screen
from .recorder import ActionRecorder


# ──────────────────────────────────────────────────────────────────────────────
#  Serialisation helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ctrl_dict(ctrl: Control, *, include_children: bool = False) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id":          ctrl.id,
        "type":        type(ctrl).sap_type,
        "name":        ctrl.name,
        "text":        ctrl.text,
        "tooltip":     ctrl.tooltip,
        "enabled":     ctrl.enabled,
        "changeable":  ctrl.changeable,
        "visible":     ctrl.visible,
        "required":    ctrl.required,
        "max_length":  ctrl.max_length,
        "left":        ctrl.left,
        "top":         ctrl.top,
        "width":       ctrl.width,
        "height":      ctrl.height,
        "child_count": len(ctrl.children),
    }
    if isinstance(ctrl, (TableControl, GridView)):
        d["columns"]   = ctrl.columns
        d["row_count"] = ctrl.row_count
    if isinstance(ctrl, StatusBar):
        d["message_type"] = ctrl.message_type
    if include_children:
        d["children"] = [_ctrl_dict(c, include_children=True) for c in ctrl.children]
    return d


def _session_info_dict(session: Session) -> dict[str, Any]:
    info = session.info
    return {
        "transaction":   info.transaction,
        "program":       info.program,
        "screen_number": info.screen_number,
        "system_name":   info.system_name,
        "client":        info.client,
        "user":          info.user,
        "window_count":  len([c for c in session.children if isinstance(c, Window)]),
    }


# ──────────────────────────────────────────────────────────────────────────────
#  HTTP request handler
# ──────────────────────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):

    # suppress the default "127.0.0.1 - - [date] POST /action ..." lines
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _send(self, status: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _ok(self, data: Any) -> None:
        self._send(200, data)

    def _error(self, status: int, message: str) -> None:
        self._send(status, {"error": message})

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    # ── GET ──────────────────────────────────────────────────────────────────

    def do_GET(self) -> None:  # noqa: N802
        route = self.path.split("?")[0]
        srv: SandboxServer = self.server  # type: ignore[assignment]

        with srv.lock:
            if route in ("/", "/info"):
                self._ok(_session_info_dict(srv.session))

            elif route == "/tree":
                self._ok({
                    "id": srv.session.id,
                    "children": [
                        _ctrl_dict(c, include_children=True)
                        for c in srv.session.children
                    ],
                })

            elif route == "/controls":
                self._ok([_ctrl_dict(c) for c in srv.session.all_controls()])

            elif route == "/log":
                self._ok(srv.recorder.entries())

            else:
                self._error(404, f"No GET route: {route}")

    # ── POST ─────────────────────────────────────────────────────────────────

    def do_POST(self) -> None:  # noqa: N802
        route = self.path.split("?")[0]
        try:
            body = self._read_json()
        except Exception as exc:
            self._error(400, f"Bad JSON: {exc}")
            return

        dispatch = {
            "/findById":   self._find,
            "/action":     self._action,
            "/loadScreen": self._load_screen,
        }
        handler = dispatch.get(route)
        if handler:
            handler(body)
        else:
            self._error(404, f"No POST route: {route}")

    # ── /findById ─────────────────────────────────────────────────────────────

    def _find(self, body: dict) -> None:
        path = body.get("path", "")
        if not path:
            self._error(400, "Missing 'path'")
            return
        srv: SandboxServer = self.server  # type: ignore[assignment]
        with srv.lock:
            try:
                ctrl = srv.session.findById(path)
                srv.recorder.log("findById", path=path)
                self._ok(_ctrl_dict(ctrl))
            except RuntimeError as exc:
                self._error(404, str(exc))

    # ── /action ───────────────────────────────────────────────────────────────

    def _action(self, body: dict) -> None:  # noqa: C901
        path   = body.get("path", "")
        action = body.get("action", "")
        value  = body.get("value")
        key    = body.get("key")

        if not action:
            self._error(400, "Missing 'action'")
            return

        srv: SandboxServer = self.server  # type: ignore[assignment]

        with srv.lock:
            session = srv.session

            # startTransaction doesn't need a path
            if action == "startTransaction":
                tcode = str(value or "")
                session.start_transaction(tcode)
                srv.recorder.log("startTransaction", value=tcode)
                self._ok({"result": "ok"})
                return

            if not path:
                self._error(400, "Missing 'path'")
                return

            try:
                ctrl = session.findById(path)
            except RuntimeError as exc:
                self._error(404, str(exc))
                return

            try:
                result: Any

                if action == "getText":
                    result = ctrl.text

                elif action == "setText":
                    ctrl.value = str(value) if value is not None else ""
                    result = ctrl.text

                elif action == "press":
                    ctrl.press()
                    result = "ok"

                elif action == "select":
                    ctrl.select()
                    result = "ok"

                elif action == "sendVKey":
                    vkey_num = int(key) if key is not None else 0
                    if isinstance(ctrl, Window):
                        ctrl.send_vkey(vkey_num)
                    else:
                        node = ctrl.parent
                        while node is not None:
                            if isinstance(node, Window):
                                node.send_vkey(vkey_num)
                                break
                            node = node.parent
                    result = "ok"

                elif action == "getInfo":
                    result = _ctrl_dict(ctrl, include_children=True)

                elif action == "getChildren":
                    result = [_ctrl_dict(c) for c in ctrl.children]

                elif action == "getCellValue":
                    row = int(body.get("row", 0))
                    col = body.get("col", 0)
                    if isinstance(ctrl, GridView):
                        result = ctrl.get_cell_value(row, str(col))
                    elif isinstance(ctrl, TableControl):
                        result = ctrl.get_cell_value(row, int(col))
                    else:
                        result = ""

                else:
                    self._error(400, f"Unknown action: {action!r}")
                    return

                srv.recorder.log(action, path=path, value=value, result=result)
                self._ok({"result": result})

            except Exception as exc:
                self._error(500, str(exc))

    # ── /loadScreen ───────────────────────────────────────────────────────────

    def _load_screen(self, body: dict) -> None:
        file_path = body.get("file", "")
        if not file_path:
            self._error(400, "Missing 'file'")
            return
        try:
            new_session = _load_screen(file_path)
        except Exception as exc:
            self._error(500, str(exc))
            return

        srv: SandboxServer = self.server  # type: ignore[assignment]
        with srv.lock:
            srv.session = new_session
            srv.recorder.log("loadScreen", value=file_path)

        self._ok({"loaded": file_path, "info": _session_info_dict(new_session)})


# ──────────────────────────────────────────────────────────────────────────────
#  Server class
# ──────────────────────────────────────────────────────────────────────────────

class SandboxServer(ThreadingHTTPServer):
    """
    HTTP server that exposes a sandbox Session over a JSON REST API.

    The server is thread-safe: all session access goes through self.lock
    (a reentrant lock so nested calls in a single request are safe).
    """

    def __init__(
        self,
        session: Session,
        host: str = "localhost",
        port: int = 7654,
        recorder: ActionRecorder | None = None,
    ) -> None:
        self.session  = session
        self.recorder = recorder if recorder is not None else ActionRecorder()
        self.lock     = threading.RLock()
        self._host    = host
        self._port    = port
        super().__init__((host, port), _Handler)

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def __repr__(self) -> str:
        tcode = self.session.info.transaction
        return f"<SandboxServer {self.url} tcode={tcode!r}>"


def start_server(
    session: Session,
    host: str = "localhost",
    port: int = 7654,
    recorder: ActionRecorder | None = None,
) -> SandboxServer:
    """
    Start the HTTP bridge server in a background daemon thread.

    Returns the SandboxServer immediately; the caller keeps its process alive
    however it likes (event loop, input(), time.sleep(), …).

    Usage::

        server = start_server(load_screen("screens/02_SE16_initial.json"), port=7654)
        print(f"Bridge at {server.url}")
        input("Press Enter to stop…")
    """
    server = SandboxServer(session, host, port, recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
