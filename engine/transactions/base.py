# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — BaseTransaction: foundation for hand-authored transaction screens.

Each transaction extends this class, calls _build() to populate its window,
then exposes a ready Session through self.session.
"""
from __future__ import annotations

from engine.control import (
    UserArea, Toolbar, CommandField, StatusBar,
)
from engine.session import Session, Window


_SESSION_ID = "/app/con[0]/ses[0]"
_WND0_ID    = f"{_SESSION_ID}/wnd[0]"


class BaseTransaction:
    """
    Base class for a simulated transaction screen.

    Subclass contract:
        tcode  — SAP transaction code (e.g. "SE16")
        title  — window title string
        _build() — populate self.usr with the screen's interactive controls

    Usage::

        screen = SE16Transaction()
        field = screen.session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")
        field.value = "SFLIGHT"
        screen.session.send_vkey(0)
    """

    tcode: str = ""
    title: str = ""

    def __init__(self) -> None:
        self.session = Session(_SESSION_ID)
        self.session.info.transaction = self.tcode

        self.window = Window(
            _WND0_ID,
            index=0,
            name="wnd[0]",
            text=self.title,
        )

        # Standard chrome: command field + status bar
        self._add_toolbar()
        self._add_status_bar()

        # Blank user area — subclass fills it in _build()
        self.usr = UserArea(f"{_WND0_ID}/usr", name="usr")
        self._build()
        self.window.add_child(self.usr)

        self.session.add_window(self.window)

    def _add_toolbar(self) -> None:
        tbar = Toolbar(f"{_WND0_ID}/tbar[0]", name="tbar[0]")
        cmd  = CommandField(f"{_WND0_ID}/tbar[0]/okcd", name="okcd", changeable=True)
        tbar.add_child(cmd)
        self.window.add_child(tbar)

    def _add_status_bar(self) -> None:
        sbar = StatusBar(f"{_WND0_ID}/sbar", name="sbar")
        self.window.add_child(sbar)

    def _build(self) -> None:
        """Override in subclasses to populate self.usr with controls."""

    # ── convenience ──────────────────────────────────────────────────────────

    def find(self, path: str):
        """Shorthand for self.session.findById(path)."""
        return self.session.findById(path)

    def set_field(self, path: str, value: str) -> None:
        self.find(path).value = value

    def get_field(self, path: str) -> str:
        return self.find(path).text

    def press(self, path: str) -> None:
        self.find(path).press()

    def send_vkey(self, key: int) -> None:
        self.session.send_vkey(key)
