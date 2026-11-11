# SPDX-License-Identifier: Apache-2.0
"""
Layer B — reactive transaction flows: screens that respond to what you enter.

A fixed flow always shows the same next screen. A reactive flow first checks
what was typed (``check``), refuses to move on with a status bar error when the
input is wrong, and fills the next screen with the matching data (``fill``).

The Navigator looks flows up in ``REACTIVE_FLOWS`` by transaction code. To add
one, subclass ``ReactiveFlow`` in its own module, call ``register()`` there,
and import that module in ``engine/navigation.py``.
"""
from __future__ import annotations

from typing import Any, Optional

from .control import Control
from .session import Session


class ReactiveFlow:
    """One transaction whose flow depends on the user's input."""

    tcode: str = ""
    screens: list[str] = []
    # Flow step -> virtual keys that try to advance from that step.
    advance_keys: dict[int, set[int]] = {}

    def check(self, session: Session, step: int) -> tuple[Optional[str], Any]:
        """Validate the input on ``step`` before moving on.

        Returns ``(error, context)``: an error message stops the flow, otherwise
        ``context`` is handed to ``fill`` for every screen shown afterwards.
        """
        return None, None

    def fill(self, session: Session, step: int, context: Any) -> None:
        """Write data into a freshly loaded screen. ``context`` may be None."""

    def advance_button(self, ctrl: Control, step: int) -> bool:
        """Whether pressing ``ctrl`` on ``step`` tries to advance the flow."""
        return False


REACTIVE_FLOWS: dict[str, ReactiveFlow] = {}


def register(flow: ReactiveFlow) -> ReactiveFlow:
    REACTIVE_FLOWS[flow.tcode.upper()] = flow
    return flow


def set_text(session: Session, path: str, text: str) -> None:
    """Set a field's text if the screen has it."""
    try:
        session.findById(path).value = text
    except RuntimeError:
        pass


def get_text(session: Session, path: str) -> str:
    try:
        return (session.findById(path).text or "").strip()
    except RuntimeError:
        return ""
