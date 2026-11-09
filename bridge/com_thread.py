# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer C — COM bridge lifecycle.

Manages the background STA thread that hosts COM objects in the
Windows Running Object Table (ROT).  While the thread is running,
external scripts can connect via::

    import win32com.client
    sap = win32com.client.GetObject("SAPGUI")

Two monikers are registered so that both Recorder.exe (uses "SAPGUI")
and Tracker.exe (uses "SAPGUISERVER") can discover the sandbox.

Usage::

    from engine import load_screen
    from bridge.com_thread import ComBridge

    session = load_screen("screens/02_SE16_initial.json")
    bridge = ComBridge(session)   # or ComBridge(opener=...) to start with no connection
    bridge.start()     # registers in ROT
    # ... Qt app runs ...
    bridge.stop()      # revokes from ROT, joins thread
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Optional

import pythoncom
import win32com.server.util
import win32event

from engine.navigation import Navigator
from engine.session import Session
from .com_server import ComSapGui, SessionHolder

ROT_MONIKER_NAMES = ["SAPGUI", "SAPGUISERVER"]


def _com_thread_func(
    holder: SessionHolder,
    stop_handle: int,
    ready_event: threading.Event,
    error_holder: list,
) -> None:
    """STA thread: register COM object in ROT, pump messages until stopped."""
    try:
        pythoncom.CoInitialize()
    except Exception as exc:
        error_holder.append(exc)
        ready_event.set()
        return

    rot_handles: list[int] = []
    try:
        root = ComSapGui(holder)
        dispatch = win32com.server.util.wrap(root)
        rot = pythoncom.GetRunningObjectTable(0)

        for name in ROT_MONIKER_NAMES:
            moniker = pythoncom.CreateFileMoniker(name)
            try:
                handle = rot.Register(
                    pythoncom.ROTFLAGS_REGISTRATIONKEEPSALIVE,
                    dispatch,
                    moniker,
                )
                rot_handles.append(handle)
            except pythoncom.com_error as ce:
                # MK_S_MONIKERALREADYREGISTERED (0x000401E7 = 262631) is a
                # success code — the entry replaced a stale one from a
                # previous crash.  pythoncom raises it as an exception anyway.
                if ce.hresult == 262631 or (ce.args and ce.args[0] == 262631):
                    pass
                else:
                    raise

        ready_event.set()

        while win32event.WaitForSingleObject(stop_handle, 0) != win32event.WAIT_OBJECT_0:
            pythoncom.PumpWaitingMessages()
            win32event.MsgWaitForMultipleObjects(
                [stop_handle], False, 50, win32event.QS_ALLINPUT,
            )

    except Exception as exc:
        error_holder.append(exc)
        if not ready_event.is_set():
            ready_event.set()
    finally:
        if rot_handles:
            try:
                rot = pythoncom.GetRunningObjectTable(0)
                for handle in rot_handles:
                    rot.Revoke(handle)
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


class ComBridge:
    """
    Manages the COM server lifecycle.

    Call start() to launch the STA thread and register in the ROT.
    Call stop() to revoke from the ROT and join the thread.
    Call update_session() to swap the session exposed to COM clients.
    """

    def __init__(
        self,
        session: Optional[Session] = None,
        opener: Optional[Callable[[str], Any]] = None,
    ) -> None:
        """Expose ``session`` over COM, or no connection when it is None.

        ``opener(description)`` opens an environment for OpenConnection and
        returns it, or None when the description is unknown.
        """
        self._holder = SessionHolder(session, opener)
        if session is not None:
            Navigator.for_session(session).subscribe(lambda new, _tcode: self.update_session(new))
        self._stop_handle = win32event.CreateEvent(None, True, False, None)
        self._ready_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._errors: list = []

    def start(self) -> None:
        """Start the COM server thread. Blocks until ROT registration completes."""
        if self._thread and self._thread.is_alive():
            return

        win32event.ResetEvent(self._stop_handle)
        self._ready_event.clear()
        self._errors.clear()

        self._thread = threading.Thread(
            target=_com_thread_func,
            args=(self._holder, self._stop_handle, self._ready_event, self._errors),
            daemon=True,
            name="COM-STA",
        )
        self._thread.start()
        self._ready_event.wait(timeout=10.0)

        if self._errors:
            raise RuntimeError(f"COM bridge failed to start: {self._errors[0]}")

    def update_session(self, session: Optional[Session], environment: Any = None) -> None:
        """Swap the session exposed to COM clients (thread-safe).

        None closes the connection. ``environment`` names the connection.
        """
        self._holder.session = session
        self._holder.environment = environment if session is not None else None

    def stop(self) -> None:
        """Stop the COM server thread and revoke from the ROT."""
        if self._thread and self._thread.is_alive():
            win32event.SetEvent(self._stop_handle)
            self._thread.join(timeout=5.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
