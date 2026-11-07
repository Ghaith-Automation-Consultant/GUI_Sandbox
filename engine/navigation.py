# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — Navigator: moves a session between transactions and flow steps.

The navigator has no UI dependency, so every bridge gets the same behaviour.
It loads the next screen and wires its buttons, virtual keys, and command field.
Listeners are told about each new session: the Qt router renders it and the
bridges start exposing it to scripts.

Usage::

    nav = Navigator()
    session = nav.start_transaction("SE16")
    session.findById("wnd[0]").send_vkey(7)   # Table Contents
    nav.session.info.transaction              # "SE16"
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from .loader import load_screen
from .session import Session

SCREEN_DIR = Path(__file__).resolve().parent.parent / "screens"

# Transaction code → screen files, one per flow step; the first is the initial screen.
TRANSACTIONS: dict[str, list[str]] = {
    "SESSION_MANAGER": ["01_SESSION_MANAGER.json"],
    "SE16": [
        "02_SE16_initial.json",
        "03_SE16_SFLIGHT_selection_screen.json",
        "04_SE16_SFLIGHT_results.json",
    ],
    "SE16N": [
        "05_SE16N_initial.json",
        "06_SE16N_SFLIGHT_selection.json",
    ],
    "SE38": [
        "07_SE38_initial.json",
        "08_SE38_source_ZSBX_DEMO.json",
        "09_SE38_attributes_ZSBX_DEMO.json",
    ],
    "SM37": ["10_SM37_initial.json"],
    "SU01": ["11_SU01_initial.json"],
    "VA03": [
        "12_VA03_initial.json",
        "13_VA03_overview.json",
    ],
    "MM03": ["14_MM03_initial.json"],
}

HOME_TCODE = "SESSION_MANAGER"

# (transaction, step) → virtual keys that advance the flow.
_ADVANCE_KEYS: dict[tuple[str, int], set[int]] = {
    ("SE16", 0): {0, 7},
    ("SE16", 1): {8},
    ("SE16N", 0): {0, 8},
    ("SE38", 0): {7},
    ("SE38", 1): {8},
    ("VA03", 0): {0, 8},
}

_VKEY_ENTER, _VKEY_BACK, _VKEY_CANCEL, _VKEY_EXIT = 0, 3, 12, 15


def _run_directly(fn: Callable[[], Any]) -> Any:
    return fn()


def _locate(session: Session) -> tuple[str, int]:
    """Find a loaded session's transaction and flow step from its source file."""
    for tcode, screens in TRANSACTIONS.items():
        if session.source in screens:
            return tcode, screens.index(session.source)
    return session.info.transaction, 0


class Navigator:
    """
    Tracks the active session and moves it through the transaction flows.

    ``dispatcher`` runs a callable on the thread that owns the sessions and
    returns its result. A GUI passes one that hands work to its own thread, so
    scripts on other threads can navigate safely and wait for the new screen.
    """

    def __init__(
        self,
        session: Optional[Session] = None,
        *,
        dispatcher: Callable[[Callable[[], Any]], Any] = _run_directly,
    ) -> None:
        self._dispatch = dispatcher
        self._listeners: list[Callable[[Session, str], None]] = []
        self._message_listeners: list[Callable[[str], None]] = []
        self._session: Optional[Session] = None
        self._tcode = ""
        self._step = 0
        if session is not None:
            tcode, step = _locate(session)
            self._adopt(session, tcode, step)

    @classmethod
    def for_session(cls, session: Session) -> "Navigator":
        """Return the session's navigator, creating one if it has none."""
        return session.navigator or cls(session)

    # ── state ─────────────────────────────────────────────────────────────────

    @property
    def session(self) -> Optional[Session]:
        return self._session

    @property
    def tcode(self) -> str:
        return self._tcode

    @property
    def step(self) -> int:
        return self._step

    def subscribe(self, listener: Callable[[Session, str], None]) -> None:
        """Call listener(session, tcode) whenever a new screen becomes active."""
        self._listeners.append(listener)

    def subscribe_messages(self, listener: Callable[[str], None]) -> None:
        """Call listener(text) whenever navigation reports a problem."""
        self._message_listeners.append(listener)

    # ── navigation ────────────────────────────────────────────────────────────

    def start_transaction(self, tcode: str) -> Optional[Session]:
        """Load a transaction's initial screen. Returns None if it isn't available."""
        return self._dispatch(lambda: self._start(tcode))

    def next_step(self) -> Optional[Session]:
        """Advance to the next screen in the current flow."""
        return self._dispatch(self._next)

    def go_back(self) -> Optional[Session]:
        """Go back one step, or home from a transaction's first screen."""
        return self._dispatch(self._back)

    def go_home(self) -> Optional[Session]:
        return self.start_transaction(HOME_TCODE)

    def handle_command(self, command: str) -> Optional[Session]:
        """Run a command field entry: TCODE, /nTCODE, /oTCODE, or /n for home."""
        command = command.strip()
        if not command:
            return None
        if command[:2].lower() in ("/n", "/o"):
            tcode = command[2:].strip()
            return self.start_transaction(tcode) if tcode else self.go_home()
        return self.start_transaction(command)

    # ── implementation (runs on the dispatcher's thread) ──────────────────────

    def _start(self, tcode: str) -> Optional[Session]:
        tcode = tcode.upper().strip()
        screens = TRANSACTIONS.get(tcode)
        if not screens:
            self._report(f"Transaction {tcode} not found in sandbox")
            return None
        return self._show(tcode, 0)

    def _next(self) -> Optional[Session]:
        screens = TRANSACTIONS.get(self._tcode, [])
        if self._step + 1 >= len(screens):
            self._report("End of transaction flow")
            return None
        return self._show(self._tcode, self._step + 1)

    def _back(self) -> Optional[Session]:
        if self._step > 0:
            return self._show(self._tcode, self._step - 1)
        return self._start(HOME_TCODE)

    def _show(self, tcode: str, step: int) -> Optional[Session]:
        name = TRANSACTIONS[tcode][step]
        path = SCREEN_DIR / name
        if not path.exists():
            self._report(f"Screen file not found: {name}")
            return None
        session = load_screen(path)
        self._adopt(session, tcode, step)
        for listener in self._listeners:
            listener(session, tcode)
        return session

    def _adopt(self, session: Session, tcode: str, step: int) -> None:
        self._session = session
        self._tcode = tcode
        self._step = step
        session.navigator = self
        self._wire(session)

    def _report(self, message: str) -> None:
        if self._session is not None:
            self._session.set_status(message, "E")
        for listener in self._message_listeners:
            listener(message)

    # ── wiring ────────────────────────────────────────────────────────────────

    def _wire(self, session: Session) -> None:
        """Connect the screen's virtual keys and buttons to the flow."""
        wnd = session.get_window(0)
        if not wnd:
            return

        def on_vkey(_window, key, _label):
            if session is self._session:
                self._on_vkey(session, key)

        wnd.on("vkey", on_vkey)

        for ctrl in wnd.all_controls():
            action = self._button_action(ctrl)
            if action:
                ctrl.on("press", lambda _c, act=action: act() if session is self._session else None)

    def _button_action(self, ctrl) -> Optional[Callable[[], Any]]:
        tooltip = (ctrl.tooltip or "").lower()
        text = (ctrl.text or "").lower()
        ctrl_id = (ctrl.id or "").lower()

        if "(f3)" in tooltip or "back" in tooltip:
            return self.go_back

        tcode, step = self._tcode, self._step
        advances = False
        if tcode == "SE16":
            advances = ("(f7)" in tooltip or "table contents" in tooltip) if step == 0 else "(f8)" in tooltip
        elif tcode == "SE16N":
            advances = "(f8)" in tooltip or "online" in tooltip
        elif tcode == "SE38":
            if step == 0:
                advances = "btnshop" in ctrl_id or "display" in text
            elif step == 1:
                advances = "(f8)" in tooltip
        elif tcode == "VA03":
            advances = "(f8)" in tooltip
        elif tcode == "SU01":
            advances = "(f7)" in tooltip or "display" in tooltip
        return self.next_step if advances else None

    def _on_vkey(self, session: Session, key: int) -> None:
        if key == _VKEY_ENTER:
            wnd = session.get_window(0)
            okcd = wnd.command_field if wnd else None
            command = (okcd.text if okcd else "").strip()
            if command:
                okcd.text = ""
                self.handle_command(command)
                return
        if key in (_VKEY_BACK, _VKEY_CANCEL):
            self.go_back()
        elif key == _VKEY_EXIT:
            self.go_home()
        elif key in _ADVANCE_KEYS.get((self._tcode, self._step), ()):
            self.next_step()
