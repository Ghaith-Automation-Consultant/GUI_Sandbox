# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Transaction Router — maps SAP transaction codes to screen JSON files
and handles navigation via the command field.

Supports:
  /nTCODE  — navigate to transaction (replace current screen)
  /oTCODE  — same as /n for now (no multi-session support yet)
  TCODE    — same as /nTCODE
  /nend, /nex — log off (back to the logon screen)

When the router is created with require_logon=True, the logon screen
(transaction S000) is shown first and every other transaction is blocked
until a logon succeeds.
"""
from __future__ import annotations

from pathlib import Path

from engine.loader import load_screen
from engine.logon import check_logon
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

# Home transaction (shown after logon)
HOME_TCODE = "SESSION_MANAGER"

# Logon screen: not reachable from the command field, only shown while logged off
LOGON_TCODE = "S000"
LOGON_SCREEN = "00_LOGON.json"
LOGOFF_COMMANDS = {"/NEND", "/NEX"}

_LOGON_FIELDS = {
    "client":   "wnd[0]/usr/txtRSYST-MANDT",
    "user":     "wnd[0]/usr/txtRSYST-BNAME",
    "password": "wnd[0]/usr/pwdRSYST-BCODE",
    "language": "wnd[0]/usr/txtRSYST-LANGU",
}


class TransactionRouter:
    """Routes transaction codes to screen sessions."""

    def __init__(self, renderer, require_logon: bool = False):
        self.renderer = renderer
        self._current_tcode: str = ""
        self._current_step: int = 0
        self._on_navigate = None
        self.require_logon = require_logon
        self.logged_on = not require_logon
        self._logon: dict[str, str] = {}
        # Runs a callable on the GUI thread; MainWindow replaces it with a Qt invoker
        self._invoke = lambda fn: fn()

    @property
    def current_tcode(self) -> str:
        return self._current_tcode

    def set_navigate_callback(self, callback) -> None:
        """Register a callback(session, tcode) for after navigation."""
        self._on_navigate = callback

    def set_gui_invoker(self, invoker) -> None:
        """Register invoker(fn) that runs fn on the GUI thread and waits for it.

        Needed because scripts (COM, HTTP) send Enter from their own thread.
        """
        self._invoke = invoker

    def _status(self, message: str) -> None:
        self.renderer.main_window.statusBar().showMessage(message)

    def _load(self, path: Path) -> Session:
        """Load a screen file and stamp it with the logged-on user's details."""
        session = load_screen(str(path))
        if self._logon:
            session.info.user = self._logon["user"]
            session.info.client = self._logon["client"]
            session.info.language = self._logon["language"]
        return session

    def _show(self, session: Session, tcode: str, step: int) -> Session:
        self._current_tcode = tcode
        self._current_step = step
        self.renderer.clear()
        self.renderer.render(session)
        self._wire_flow_buttons(session)
        if self._on_navigate:
            self._on_navigate(session, tcode)
        return session

    # ── Logon ────────────────────────────────────────────────────────────────

    def show_logon(self) -> Session | None:
        """Show the logon screen (S000)."""
        path = SCREEN_DIR / LOGON_SCREEN
        if not path.exists():
            self._status(f"Screen file not found: {LOGON_SCREEN}")
            return None
        session = load_screen(str(path))
        session.info.user = ""  # nobody is logged on yet, as in SAP GUI
        wnd = session.get_window(0)
        if wnd:
            wnd.on("vkey", lambda w, key, label, s=session: self._on_logon_vkey(s, key))
        return self._show(session, LOGON_TCODE, 0)

    def _on_logon_vkey(self, session: Session, key: int) -> None:
        if key == 0:  # Enter
            self._invoke(lambda: self.attempt_logon(session))

    def attempt_logon(self, session: Session) -> Session | None:
        """Check the logon fields; go to Easy Access on success, else show the error."""
        values = {}
        for key, path in _LOGON_FIELDS.items():
            try:
                values[key] = session.findById(path).text or ""
            except RuntimeError:
                values[key] = ""

        error = check_logon(values["client"], values["user"], values["password"], values["language"])
        if error:
            # SAP GUI clears the password after a failed logon
            try:
                session.findById(_LOGON_FIELDS["password"]).value = ""
            except RuntimeError:
                pass
            session.set_status(error, "E")
            self.renderer.refresh_status_bar()
            return None

        self.logged_on = True
        self._logon = {
            "user": values["user"].strip().upper(),
            "client": values["client"].strip(),
            "language": (values["language"].strip() or "EN").upper(),
        }
        return self.navigate(HOME_TCODE)

    def log_off(self) -> Session | None:
        """Forget the logged-on user and return to the logon screen."""
        self.logged_on = False
        self._logon = {}
        return self.show_logon()

    def navigate(self, tcode: str) -> Session | None:
        """Load the initial screen for a transaction and render it."""
        tcode = tcode.upper().strip()
        if not self.logged_on:
            self._status("Log on to the system first")
            return None
        screens = TRANSACTIONS.get(tcode)
        if not screens:
            self._status(f"Transaction {tcode} not found in sandbox")
            return None

        path = SCREEN_DIR / screens[0]
        if not path.exists():
            self.renderer.main_window.statusBar().showMessage(
                f"Screen file not found: {screens[0]}"
            )
            return None

        return self._show(self._load(path), tcode, 0)

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

        return self._show(self._load(path), self._current_tcode, next_idx)

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
        if not self.logged_on:
            return None
        if self._current_step > 0:
            screens = TRANSACTIONS.get(self._current_tcode, [])
            prev_idx = self._current_step - 1
            path = SCREEN_DIR / screens[prev_idx]
            if not path.exists():
                return self.go_home()

            return self._show(self._load(path), self._current_tcode, prev_idx)
        return self.go_home()

    def go_home(self) -> Session | None:
        """Navigate to the home screen (SESSION_MANAGER), or the logon screen if logged off."""
        if not self.logged_on:
            if self._current_tcode == LOGON_TCODE:
                return None  # already there; keep what the user typed
            return self.show_logon()
        return self.navigate(HOME_TCODE)

    def handle_command(self, command: str) -> Session | None:
        """Parse a command field entry and navigate.

        Supports: /nTCODE, /oTCODE, TCODE, /n (go home)
        """
        command = command.strip()
        if not command:
            return None

        if command.upper() in LOGOFF_COMMANDS:
            return self.log_off()

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
