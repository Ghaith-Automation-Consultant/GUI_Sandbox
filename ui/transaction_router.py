# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Transaction Router — maps SAP transaction codes to screen JSON files
and handles navigation via the command field.

Supports:
  /nTCODE  — navigate to transaction (replace current screen)
  /oTCODE  — same as /n for now (no multi-session support yet)
  TCODE    — same as /nTCODE
"""
from __future__ import annotations

from pathlib import Path

from engine.loader import load_screen
from engine.session import Session


SCREEN_DIR = Path(__file__).resolve().parent.parent / "screens"

# Transaction code → list of screen JSON files (flow steps)
# First file is the initial screen for that transaction
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

# Home transaction (shown on startup)
HOME_TCODE = "SESSION_MANAGER"


class TransactionRouter:
    """Routes transaction codes to screen sessions."""

    def __init__(self, renderer):
        self.renderer = renderer
        self._current_tcode: str = ""
        self._current_step: int = 0
        self._on_navigate = None

    @property
    def current_tcode(self) -> str:
        return self._current_tcode

    def set_navigate_callback(self, callback) -> None:
        """Register a callback(session, tcode) for after navigation."""
        self._on_navigate = callback

    def navigate(self, tcode: str) -> Session | None:
        """Load the initial screen for a transaction and render it."""
        tcode = tcode.upper().strip()
        screens = TRANSACTIONS.get(tcode)
        if not screens:
            self.renderer.main_window.statusBar().showMessage(
                f"Transaction {tcode} not found in sandbox"
            )
            return None

        path = SCREEN_DIR / screens[0]
        if not path.exists():
            self.renderer.main_window.statusBar().showMessage(
                f"Screen file not found: {screens[0]}"
            )
            return None

        session = load_screen(str(path))
        self._current_tcode = tcode
        self._current_step = 0

        self.renderer.clear()
        self.renderer.render(session)
        self._wire_flow_buttons(session)

        if self._on_navigate:
            self._on_navigate(session, tcode)

        return session

    def next_step(self) -> Session | None:
        """Navigate to the next screen in the current transaction flow."""
        screens = TRANSACTIONS.get(self._current_tcode, [])
        next_idx = self._current_step + 1
        if next_idx >= len(screens):
            self.renderer.main_window.statusBar().showMessage(
                "End of transaction flow"
            )
            return None

        path = SCREEN_DIR / screens[next_idx]
        if not path.exists():
            return None

        session = load_screen(str(path))
        self._current_step = next_idx

        self.renderer.clear()
        self.renderer.render(session)
        self._wire_flow_buttons(session)

        if self._on_navigate:
            self._on_navigate(session, self._current_tcode)

        return session

    def _wire_flow_buttons(self, session: Session) -> None:
        """Register press handlers on buttons that advance the flow."""
        wnd = session.get_window(0)
        if not wnd:
            return

        all_ctrls = wnd.all_controls()

        for ctrl in all_ctrls:
            tooltip = (ctrl.tooltip or "").lower()
            text = (ctrl.text or "").lower()
            (ctrl.name or "").lower()
            ctrl_id = (ctrl.id or "").lower()

            should_advance = False

            if self._current_tcode == "SE16":
                if self._current_step == 0:
                    # "Table Contents (F7)" on initial screen
                    if "(f7)" in tooltip or "table contents" in tooltip:
                        should_advance = True
                else:
                    # "Execute (F8)" on selection screens
                    if "(f8)" in tooltip:
                        should_advance = True

            elif self._current_tcode == "SE16N":
                if "(f8)" in tooltip or "online" in tooltip:
                    should_advance = True

            elif self._current_tcode == "SE38":
                if self._current_step == 0:
                    if "btnshop" in ctrl_id or "display" in text:
                        should_advance = True
                elif self._current_step == 1:
                    if "(f8)" in tooltip:
                        should_advance = True

            elif self._current_tcode == "VA03":
                if "(f8)" in tooltip:
                    should_advance = True

            elif self._current_tcode == "SU01":
                if "(f7)" in tooltip or "display" in tooltip:
                    should_advance = True

            if should_advance:
                ctrl.on("press", lambda c, router=self: router.next_step())

            # Wire Back (F3) buttons to go_back
            if "(f3)" in tooltip or "back" in tooltip:
                ctrl.on("press", lambda c, router=self: router.go_back())

    def go_back(self) -> Session | None:
        """Go back one step or return home if at the first step."""
        if self._current_step > 0:
            screens = TRANSACTIONS.get(self._current_tcode, [])
            prev_idx = self._current_step - 1
            path = SCREEN_DIR / screens[prev_idx]
            if not path.exists():
                return self.go_home()

            session = load_screen(str(path))
            self._current_step = prev_idx

            self.renderer.clear()
            self.renderer.render(session)
            self._wire_flow_buttons(session)

            if self._on_navigate:
                self._on_navigate(session, self._current_tcode)
            return session
        return self.go_home()

    def go_home(self) -> Session | None:
        """Navigate to the home screen (SESSION_MANAGER)."""
        return self.navigate(HOME_TCODE)

    def handle_command(self, command: str) -> Session | None:
        """Parse a command field entry and navigate.

        Supports: /nTCODE, /oTCODE, TCODE, /n (go home)
        """
        command = command.strip()
        if not command:
            return None

        if command.startswith("/n") or command.startswith("/o"):
            tcode = command[2:].strip()
            if not tcode:
                return self.go_home()
            return self.navigate(tcode)

        return self.navigate(command)

    @staticmethod
    def available_transactions() -> list[str]:
        """Return list of available transaction codes."""
        return sorted(TRANSACTIONS.keys())
