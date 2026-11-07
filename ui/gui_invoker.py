# SPDX-License-Identifier: Apache-2.0
"""
Run a callable on the Qt GUI thread and wait for it to finish.

Scripts reach the engine from other threads (the COM STA thread, HTTP server
threads). Anything that rebuilds widgets, such as navigating after a logon,
must run on the GUI thread. The caller blocks until the GUI thread is done, so
a script that sends Enter sees the next screen as soon as sendVKey returns.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot


class GuiInvoker(QObject):
    _call = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._call.connect(self._run, Qt.ConnectionType.BlockingQueuedConnection)

    @Slot(object)
    def _run(self, fn: Callable[[], object]) -> None:
        fn()

    def __call__(self, fn: Callable[[], object]) -> None:
        if QThread.currentThread() == self.thread():
            fn()
        else:
            self._call.emit(fn)
