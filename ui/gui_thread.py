# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer A — run work on the Qt GUI thread.

Scripts reach the engine from other threads, such as the COM STA thread, but Qt
widgets may only be touched from the thread that owns them.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

CALL_TIMEOUT_SECONDS = 15.0


class GuiInvoker(QObject):
    """Runs callables on the thread this object was created on."""

    _queued = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._queued.connect(self._run, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _run(self, fn: Callable[[], None]) -> None:
        fn()

    def _on_owner_thread(self) -> bool:
        return QThread.currentThread() is self.thread()

    def post(self, fn: Callable[[], None]) -> None:
        """Run fn on the GUI thread without waiting for it."""
        if self._on_owner_thread():
            fn()
        else:
            self._queued.emit(fn)

    def call(self, fn: Callable[[], Any]) -> Any:
        """Run fn on the GUI thread, wait for it, and return its result."""
        if self._on_owner_thread():
            return fn()

        done = threading.Event()
        outcome: dict[str, Any] = {}

        def task() -> None:
            try:
                outcome["result"] = fn()
            except Exception as exc:
                outcome["error"] = exc
            finally:
                done.set()

        self._queued.emit(task)
        if not done.wait(CALL_TIMEOUT_SECONDS):
            raise RuntimeError("GUI thread did not respond")
        if "error" in outcome:
            raise outcome["error"]
        return outcome.get("result")


_invoker: Optional[GuiInvoker] = None


def invoker() -> GuiInvoker:
    """Return the shared invoker. The first call must be on the GUI thread."""
    global _invoker
    if _invoker is None:
        _invoker = GuiInvoker()
    return _invoker
