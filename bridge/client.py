# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer C — HTTP bridge client.

RemoteSession connects to a running SandboxServer and presents the same
interface as SessionProxy / the real SAP COM object, so automation scripts
can target either the sandbox (via RemoteSession) or real SAP (via COM)
with only a one-line import change.

Usage::

    from bridge import RemoteSession
    session = RemoteSession("http://localhost:7654")

    # Identical to real SAP COM usage
    session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
    session.findById("wnd[0]").sendVKey(0)
    print(session.Info.Transaction)

    # Check server is up
    assert session.ping()

    # Load a different screen on the server
    session.load_screen("screens/03_SE16_SFLIGHT_selection_screen.json")
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────────────────────
#  Remote control proxy
# ──────────────────────────────────────────────────────────────────────────────

class RemoteControlProxy:
    """
    Proxy for a single control on a remote SandboxServer.

    Read-only properties are served from cached metadata fetched by findById.
    Writes and actions make HTTP calls to the server.
    """

    def __init__(self, data: dict[str, Any], session: "RemoteSession") -> None:
        self._data    = data
        self._session = session

    def _action(self, action: str, **kwargs: Any) -> Any:
        payload = {"path": self._data["id"], "action": action, **kwargs}
        return self._session._post("/action", payload).get("result")

    # ── identity ─────────────────────────────────────────────────────────────

    @property
    def Id(self) -> str:
        return self._data.get("id", "")

    @property
    def Type(self) -> str:
        return self._data.get("type", "")

    @property
    def Name(self) -> str:
        return self._data.get("name", "")

    # ── text / value ─────────────────────────────────────────────────────────

    @property
    def Text(self) -> str:
        return self._data.get("text", "")

    @Text.setter
    def Text(self, value: str) -> None:
        self._action("setText", value=value)
        self._data["text"] = str(value)

    @property
    def text(self) -> str:
        return self.Text

    @text.setter
    def text(self, value: str) -> None:
        self.Text = value

    # ── state (from cached metadata) ──────────────────────────────────────────

    @property
    def Enabled(self) -> bool:
        return bool(self._data.get("enabled", True))

    @property
    def Changeable(self) -> bool:
        return bool(self._data.get("changeable", True))

    @property
    def Visible(self) -> bool:
        return bool(self._data.get("visible", True))

    @property
    def Required(self) -> bool:
        return bool(self._data.get("required", False))

    @property
    def Tooltip(self) -> str:
        return self._data.get("tooltip", "")

    @property
    def DefaultTooltip(self) -> str:
        return self._data.get("tooltip", "")

    @property
    def MaxLength(self) -> int:
        return int(self._data.get("max_length", 0))

    @property
    def Left(self) -> int:
        return int(self._data.get("left", 0))

    @property
    def Top(self) -> int:
        return int(self._data.get("top", 0))

    @property
    def Width(self) -> int:
        return int(self._data.get("width", 0))

    @property
    def Height(self) -> int:
        return int(self._data.get("height", 0))

    @property
    def RowCount(self) -> int:
        return int(self._data.get("row_count", 0))

    @property
    def ColumnCount(self) -> int:
        return len(self._data.get("columns", []))

    @property
    def MessageId(self) -> str:
        return self._data.get("message_type", "")

    # ── actions ──────────────────────────────────────────────────────────────

    def Press(self) -> None:
        self._action("press")

    def press(self) -> None:
        self.Press()

    def Select(self) -> None:
        self._action("select")

    def select(self) -> None:
        self.Select()

    def sendVKey(self, key: int) -> None:
        self._action("sendVKey", key=key)

    # ── table / grid ─────────────────────────────────────────────────────────

    def GetCellValue(self, row: int, col: "int | str") -> str:
        return str(self._action("getCellValue", row=row, col=col) or "")

    def GetCell(self, row: int, col: int) -> Optional["RemoteControlProxy"]:
        val = self._action("getCellValue", row=row, col=col)
        if val is None:
            return None
        return RemoteControlProxy(
            {"id": f"{self.Id}/cell[{row},{col}]", "text": str(val)},
            self._session,
        )

    # ── children ─────────────────────────────────────────────────────────────

    @property
    def Children(self) -> "_RemoteChildren":
        return _RemoteChildren(self._data["id"], self._session,
                               self._data.get("child_count", 0))

    # ── nested findById ───────────────────────────────────────────────────────

    def findById(self, path: str) -> "RemoteControlProxy":
        return self._session.findById(path)

    def __repr__(self) -> str:
        return f"<RemoteControlProxy {self._data.get('id', '?')!r}>"


class _RemoteChildren:
    """Children collection for a remote control — fetched lazily."""

    def __init__(self, parent_id: str, session: "RemoteSession", count: int) -> None:
        self._parent_id = parent_id
        self._session   = session
        self._count     = count
        self._cache: list[dict] | None = None

    def _fetch(self) -> list[dict]:
        if self._cache is None:
            self._cache = self._session._post(
                "/action",
                {"path": self._parent_id, "action": "getChildren"},
            ).get("result", [])
        return self._cache

    @property
    def Count(self) -> int:
        return self._count

    def Item(self, index: int) -> RemoteControlProxy:
        children = self._fetch()
        if not (0 <= index < len(children)):
            raise IndexError(f"Children index {index} out of range")
        return RemoteControlProxy(children[index], self._session)

    def __call__(self, index: int) -> RemoteControlProxy:
        return self.Item(index)

    def __iter__(self):
        for child in self._fetch():
            yield RemoteControlProxy(child, self._session)

    def __len__(self) -> int:
        return self._count


# ──────────────────────────────────────────────────────────────────────────────
#  Remote session info
# ──────────────────────────────────────────────────────────────────────────────

class _RemoteSessionInfo:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def Transaction(self) -> str:
        return self._data.get("transaction", "")

    @property
    def Program(self) -> str:
        return self._data.get("program", "")

    @property
    def ScreenNumber(self) -> int:
        return int(self._data.get("screen_number", 0))

    @property
    def SystemName(self) -> str:
        return self._data.get("system_name", "")

    @property
    def Client(self) -> str:
        return self._data.get("client", "")

    @property
    def User(self) -> str:
        return self._data.get("user", "")


# ──────────────────────────────────────────────────────────────────────────────
#  RemoteSession
# ──────────────────────────────────────────────────────────────────────────────

class RemoteSession:
    """
    HTTP client that connects to a SandboxServer and presents the SAP COM API.

    Drop-in replacement for SessionProxy (in-process) or the real COM session
    (via win32com). Scripts only need to change where they get the session from.

    Usage::

        from bridge import RemoteSession
        session = RemoteSession("http://localhost:7654")
        session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
        session.findById("wnd[0]").sendVKey(0)
    """

    def __init__(self, url: str = "http://localhost:7654", timeout: float = 10.0) -> None:
        self.url     = url.rstrip("/")
        self.timeout = timeout

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, endpoint: str) -> Any:
        req = urllib.request.Request(f"{self.url}{endpoint}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                json.loads(exc.read().decode("utf-8")).get("error", str(exc))
            ) from exc

    def _post(self, endpoint: str, data: dict) -> Any:
        body = json.dumps(data).encode("utf-8")
        req  = urllib.request.Request(
            f"{self.url}{endpoint}",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                msg = json.loads(raw).get("error", raw)
            except json.JSONDecodeError:
                msg = raw
            raise RuntimeError(msg) from exc

    # ── SAP API ──────────────────────────────────────────────────────────────

    def findById(self, path: str) -> RemoteControlProxy:
        data = self._post("/findById", {"path": path})
        return RemoteControlProxy(data, self)

    def StartTransaction(self, tcode: str) -> None:
        self._post("/action", {"action": "startTransaction", "value": tcode})

    def startTransaction(self, tcode: str) -> None:
        self.StartTransaction(tcode)

    @property
    def Info(self) -> _RemoteSessionInfo:
        return _RemoteSessionInfo(self._get("/info"))

    @property
    def ActiveWindow(self) -> Optional[RemoteControlProxy]:
        info = self._get("/info")
        if int(info.get("window_count", 0)) > 0:
            return self.findById("wnd[0]")
        return None

    # ── server-side helpers ───────────────────────────────────────────────────

    def load_screen(self, file_path: str) -> None:
        """Tell the server to load a captured screen JSON file."""
        self._post("/loadScreen", {"file": file_path})

    def get_log(self) -> list[dict]:
        """Retrieve the server's action recorder entries."""
        return self._get("/log")

    def ping(self) -> bool:
        """Return True if the server is reachable."""
        try:
            self._get("/info")
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<RemoteSession {self.url!r}>"
