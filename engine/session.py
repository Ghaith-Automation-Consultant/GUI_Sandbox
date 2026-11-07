# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — Session and Window: top-level simulation objects.

Session mirrors GuiSession from SAP GUI Scripting.
findById() is the primary API consumed by Layer C / automation scripts.
"""
from __future__ import annotations

from typing import Any, Optional

from .control import Control, Container, CommandField, StatusBar


# Virtual-key code descriptions (matches SAP vkey numbering)
VKEY_LABELS: dict[int, str] = {
    0:  "Enter",
    2:  "F2",
    3:  "F3 (Back)",
    4:  "F4 (Value Help)",
    5:  "F5",
    6:  "F6",
    7:  "F7",
    8:  "F8 (Execute)",
    9:  "F9",
    11: "F11 (Save)",
    12: "F12 (Cancel/Back)",
    14: "Shift+F2",
    15: "Shift+F3",
}


class SessionInfo:
    """Read-only metadata about a session (mirrors GuiSessionInfo)."""

    def __init__(self) -> None:
        self.system_name:   str = "SIM"
        self.client:        str = "000"
        self.user:          str = "DEVELOPER"
        self.language:      str = "EN"
        self.transaction:   str = "SESSION_MANAGER"
        self.program:       str = ""
        self.screen_number: int = 100


class Window(Container):
    """
    A top-level SAP window — wnd[0] is the main window,
    wnd[1..N] are modal popups.
    """

    sap_type = "GuiMainWindow"

    def __init__(self, control_id: str, *, index: int = 0, **kwargs) -> None:
        super().__init__(control_id, **kwargs)
        self.index = index

    def send_vkey(self, key: int) -> None:
        label = VKEY_LABELS.get(key, f"VKey({key})")
        self.trigger("vkey", self, key, label)

    @property
    def command_field(self) -> Optional[CommandField]:
        return self.find_control(f"{self.id}/tbar[0]/okcd")

    @property
    def status_bar(self) -> Optional[StatusBar]:
        return self.find_control(f"{self.id}/sbar")

    @property
    def user_area(self) -> Optional[Container]:
        return self.find_control(f"{self.id}/usr")


class Session(Container):
    """
    Top-level simulation object — mirrors GuiSession.

    Usage::

        session = load_screen("screens/02_SE16_initial.json")
        field = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")
        field.value = "SFLIGHT"
        session.send_vkey(0)   # Enter
    """

    sap_type = "GuiSession"

    def __init__(self, control_id: str = "/app/con[0]/ses[0]", **kwargs) -> None:
        super().__init__(control_id, **kwargs)
        self.info = SessionInfo()
        self._registry: dict[str, Control] = {}
        self.source: str = ""            # screen file this session was loaded from
        self.navigator: Any = None       # engine.navigation.Navigator, when attached

    # ── window management ─────────────────────────────────────────────────────

    def add_window(self, window: Window) -> Window:
        self.add_child(window)
        self._reindex(window)
        return window

    def get_window(self, index: int = 0) -> Optional[Window]:
        for child in self.children:
            if isinstance(child, Window) and child.index == index:
                return child
        return None

    def close_window(self, index: int) -> None:
        wnd = self.get_window(index)
        if wnd:
            for ctrl in wnd.all_controls():
                self._registry.pop(ctrl.id, None)
            self.remove_child(wnd)

    # ── registry ──────────────────────────────────────────────────────────────

    def _reindex(self, root: Control) -> None:
        """Register all controls under root for O(1) findById lookup."""
        for ctrl in root.all_controls():
            self._registry[ctrl.id] = ctrl

    def rebuild_registry(self) -> None:
        """Rebuild the full registry from the current tree."""
        self._registry.clear()
        for ctrl in self.all_controls():
            self._registry[ctrl.id] = ctrl

    # ── findById ──────────────────────────────────────────────────────────────

    def findById(self, path: str) -> Control:
        """
        Primary scripting API.  Accepts both full SAP paths and short paths:

            session.findById("/app/con[0]/ses[0]/wnd[0]/usr/ctxtFOO")
            session.findById("wnd[0]/usr/ctxtFOO")   # short form

        Raises RuntimeError if the control is not found (matches real SAP behaviour).
        """
        full_path = path if path.startswith("/app/") else f"{self.id}/{path}"

        ctrl = self._registry.get(full_path)
        if ctrl is None:
            # Fallback: tree walk (handles controls added after last reindex)
            ctrl = self.find_control(full_path)
        if ctrl is None:
            raise RuntimeError(f"Control not found: {path!r}")
        return ctrl

    # ── transaction navigation ────────────────────────────────────────────────

    def start_transaction(self, tcode: str) -> None:
        """Open a transaction through the navigator, or just record it without one."""
        if self.navigator is not None:
            self.navigator.start_transaction(tcode)
            return
        self.info.transaction = tcode
        self.trigger("transaction_change", self, tcode)

    # ── VKey passthrough ─────────────────────────────────────────────────────

    def send_vkey(self, key: int, window_index: int = 0) -> None:
        wnd = self.get_window(window_index)
        if wnd:
            wnd.send_vkey(key)
        self.trigger("vkey", self, key, window_index)

    # ── status bar shorthand ─────────────────────────────────────────────────

    def set_status(self, message: str, message_type: str = "S") -> None:
        wnd = self.get_window(0)
        if wnd:
            sbar = wnd.status_bar
            if isinstance(sbar, StatusBar):
                sbar.show(message, message_type)

    # ── convenience ──────────────────────────────────────────────────────────

    @property
    def active_window(self) -> Optional[Window]:
        """The topmost open window (highest index)."""
        windows = [c for c in self.children if isinstance(c, Window)]
        return max(windows, key=lambda w: w.index) if windows else None

    def __repr__(self) -> str:
        tcode = self.info.transaction
        n_wnd = len([c for c in self.children if isinstance(c, Window)])
        return f"<Session tcode={tcode!r} windows={n_wnd}>"
