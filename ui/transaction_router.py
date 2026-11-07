# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Transaction Router — connects the engine's Navigator to the Qt window.

The Navigator owns the flow, so scripts and the UI share it. The router renders
each new session and keeps navigation on the GUI thread.

Command field entries:
  /nTCODE  — navigate to transaction (replace current screen)
  /oTCODE  — same as /n for now (no multi-session support yet)
  TCODE    — same as /nTCODE
"""
from __future__ import annotations

from engine.navigation import HOME_TCODE, SCREEN_DIR, TRANSACTIONS, Navigator
from engine.session import Session

from . import gui_thread

__all__ = ["HOME_TCODE", "SCREEN_DIR", "TRANSACTIONS", "TransactionRouter"]


class TransactionRouter:
    """Renders the Navigator's sessions and exposes navigation to the window."""

    def __init__(self, renderer):
        self.renderer = renderer
        self._on_navigate = None
        self.navigator = Navigator(dispatcher=gui_thread.invoker().call)
        self.navigator.subscribe(self._render)
        self.navigator.subscribe_messages(self._show_message)

    @property
    def current_tcode(self) -> str:
        return self.navigator.tcode

    @property
    def _current_step(self) -> int:
        return self.navigator.step

    def set_navigate_callback(self, callback) -> None:
        """Register a callback(session, tcode) for after navigation."""
        self._on_navigate = callback

    def navigate(self, tcode: str) -> Session | None:
        """Load the initial screen for a transaction and render it."""
        return self.navigator.start_transaction(tcode)

    def next_step(self) -> Session | None:
        """Navigate to the next screen in the current transaction flow."""
        return self.navigator.next_step()

    def go_back(self) -> Session | None:
        """Go back one step or return home if at the first step."""
        return self.navigator.go_back()

    def go_home(self) -> Session | None:
        """Navigate to the home screen (SESSION_MANAGER)."""
        return self.navigator.go_home()

    def handle_command(self, command: str) -> Session | None:
        """Parse a command field entry and navigate."""
        return self.navigator.handle_command(command)

    def _render(self, session: Session, tcode: str) -> None:
        self.renderer.clear()
        self.renderer.render(session)
        if self._on_navigate:
            self._on_navigate(session, tcode)

    def _show_message(self, message: str) -> None:
        self.renderer.main_window.statusBar().showMessage(message)

    @staticmethod
    def available_transactions() -> list[str]:
        """Return list of available transaction codes."""
        return sorted(TRANSACTIONS.keys())
