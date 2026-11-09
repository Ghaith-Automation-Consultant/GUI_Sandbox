# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — Navigator: moves a session between transactions and flow steps.

The navigator has no UI dependency, so every bridge gets the same behaviour.
It loads the next screen and wires its buttons, virtual keys, and command field.
Listeners are told about each new session: the Qt router renders it and the
bridges start exposing it to scripts.

With ``require_logon=True`` the navigator starts logged off: home is the logon
screen (transaction S000), every other transaction is blocked, and Enter on the
logon screen checks the fields against ``engine.logon``. ``/nend`` and ``/nex``
log off again.

Usage::

    nav = Navigator()
    session = nav.start_transaction("SE16")
    session.findById("wnd[0]").send_vkey(7)   # Table Contents
    nav.session.info.transaction              # "SE16"
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from . import popups
from .environments import Environment
from .loader import load_screen
from .logon import check_logon
from .session import ModalWindow, Session
from .users import DEFAULT_ENVIRONMENT, UserStore

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
    "SU3": ["15_SU3_initial.json"],
}

HOME_TCODE = "SESSION_MANAGER"

# Logon screen: not reachable from the command field, only shown while logged off.
LOGON_TCODE = "S000"
LOGON_SCREEN = "00_LOGON.json"
LOGOFF_COMMANDS = {"/NEND", "/NEX"}

_LOGON_FIELDS = {
    "client":   "wnd[0]/usr/txtRSYST-MANDT",
    "user":     "wnd[0]/usr/txtRSYST-BNAME",
    "password": "wnd[0]/usr/pwdRSYST-BCODE",
    "language": "wnd[0]/usr/txtRSYST-LANGU",
}

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
_VKEY_NEW_PASSWORD = 5        # F5 on the logon screen
_VKEY_CHANGE_PASSWORD = 20    # Shift+F8 in SU01

SU01_USER_FIELD = "wnd[0]/usr/ctxtSUID_ST_BNAME-BNAME"

# Popup field names: wnd[1]/usr/pwdRSYST-NCODE and wnd[1]/usr/pwdRSYST-NCOD2
NEW_PASSWORD, REPEAT_PASSWORD = "RSYST-NCODE", "RSYST-NCOD2"
_PASSWORD_FIELDS = [(NEW_PASSWORD, "New Password"), (REPEAT_PASSWORD, "Repeat Password")]


def _run_directly(fn: Callable[[], Any]) -> Any:
    return fn()


def _locate(session: Session) -> tuple[str, int]:
    """Find a loaded session's transaction and flow step from its source file."""
    if session.source == LOGON_SCREEN:
        return LOGON_TCODE, 0
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
        require_logon: bool = False,
        users: Optional[UserStore] = None,
    ) -> None:
        self._dispatch = dispatcher
        self._listeners: list[Callable[[Session, str], None]] = []
        self._message_listeners: list[Callable[[str], None]] = []
        self._popup_listeners: list[Callable[[Session, Optional[ModalWindow]], None]] = []
        self._users = users
        # The open popup's purpose: {"kind": "set" | "forced" | "reset", ...}
        self._popup: Optional[dict[str, str]] = None
        self._session: Optional[Session] = None
        self._tcode = ""
        self._step = 0
        self.require_logon = require_logon
        self._logon: dict[str, str] = {}
        self._logged_on = not require_logon
        self._environment: Optional[Environment] = None
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

    @property
    def logged_on(self) -> bool:
        return self._logged_on

    @property
    def environment(self) -> Optional[Environment]:
        """The environment opened with connect(), if any."""
        return self._environment

    def subscribe(self, listener: Callable[[Optional[Session], str], None]) -> None:
        """Call listener(session, tcode) whenever a new screen becomes active.

        After disconnect() the listener is called once with (None, "").
        """
        self._listeners.append(listener)

    def subscribe_messages(self, listener: Callable[[str], None]) -> None:
        """Call listener(text) whenever navigation reports a message."""
        self._message_listeners.append(listener)

    def subscribe_popups(self, listener: Callable[[Session, Optional[ModalWindow]], None]) -> None:
        """Call listener(session, window) when a popup opens, and (session, None) when it closes."""
        self._popup_listeners.append(listener)

    @property
    def users(self) -> UserStore:
        """The test users; loaded from users.json on first use unless one was passed in."""
        if self._users is None:
            self._users = UserStore.load()
        return self._users

    @property
    def environment_id(self) -> str:
        return self._environment.id if self._environment else DEFAULT_ENVIRONMENT

    @property
    def popup(self) -> Optional[ModalWindow]:
        """The open popup window (wnd[1]), if any."""
        return popups.popup(self._session) if self._popup else None

    # ── passwords ─────────────────────────────────────────────────────────────

    def open_new_password(self) -> Optional[ModalWindow]:
        """Logon screen, New Password: check the credentials, then ask for a new password."""
        return self._dispatch(self._open_new_password)

    def open_su3_password(self) -> Optional[ModalWindow]:
        """SU3, Change Password: ask for the old password and a new one."""
        return self._dispatch(self._open_su3_password)

    def open_reset_password(self) -> Optional[ModalWindow]:
        """SU01, Change Password: ask for an initial password for the user in the User field."""
        return self._dispatch(self._open_reset_password)

    def popup_continue(self) -> Optional[Session]:
        """Continue (Enter) in the open popup."""
        return self._dispatch(self._popup_continue)

    def popup_cancel(self) -> None:
        """Cancel (F12) in the open popup."""
        self._dispatch(self._popup_cancel)

    # ── connection ────────────────────────────────────────────────────────────

    def connect(self, environment: Environment) -> Optional[Session]:
        """Open an environment, replacing any open one, and show its first screen.

        An environment with logon starts on the logon screen; one without
        starts on Easy Access.
        """
        return self._dispatch(lambda: self._connect(environment))

    def disconnect(self) -> None:
        """Close the open environment. Listeners are told with (None, "")."""
        self._dispatch(self._disconnect)

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
        """Go to Easy Access, or to the logon screen while logged off."""
        return self._dispatch(self._home)

    def attempt_logon(self) -> Optional[Session]:
        """Check the logon screen's fields; go home on success, else report the error."""
        return self._dispatch(self._attempt_logon)

    def log_off(self) -> Optional[Session]:
        """Forget the logged-on user and return to the logon screen."""
        return self._dispatch(self._log_off)

    def handle_command(self, command: str) -> Optional[Session]:
        """Run a command field entry: TCODE, /nTCODE, /oTCODE, /n for home, /nend to log off."""
        command = command.strip()
        if not command:
            return None
        if command.upper() in LOGOFF_COMMANDS:
            return self.log_off()
        if command[:2].lower() in ("/n", "/o"):
            tcode = command[2:].strip()
            return self.start_transaction(tcode) if tcode else self.go_home()
        return self.start_transaction(command)

    # ── implementation (runs on the dispatcher's thread) ──────────────────────

    def _connect(self, environment: Environment) -> Optional[Session]:
        self._reset()
        self._environment = environment
        self.require_logon = environment.logon
        self._logged_on = not environment.logon
        return self._home()

    def _disconnect(self) -> None:
        self._reset()
        self._environment = None
        for listener in self._listeners:
            listener(None, "")

    def _reset(self) -> None:
        self._popup = None
        self._session = None
        self._tcode = ""
        self._step = 0
        self._logon = {}

    def _start(self, tcode: str) -> Optional[Session]:
        tcode = tcode.upper().strip()
        if not self._logged_on:
            self._report("Log on to the system first")
            return None
        screens = TRANSACTIONS.get(tcode)
        if not screens:
            self._report(f"Transaction {tcode} does not exist", number="343")
            return None
        return self._show(tcode, 0)

    def _next(self) -> Optional[Session]:
        screens = TRANSACTIONS.get(self._tcode, [])
        if self._step + 1 >= len(screens):
            self._report("End of transaction flow")
            return None
        return self._show(self._tcode, self._step + 1)

    def _back(self) -> Optional[Session]:
        if not self._logged_on:
            return None
        if self._step > 0:
            return self._show(self._tcode, self._step - 1)
        return self._start(HOME_TCODE)

    def _home(self) -> Optional[Session]:
        if self._logged_on:
            return self._start(HOME_TCODE)
        if self._tcode == LOGON_TCODE and self._session is not None:
            return None  # Already there; keep what the user typed.
        return self._show_logon()

    def _show_logon(self) -> Optional[Session]:
        session = self._load(LOGON_SCREEN)
        if session is None:
            return None
        session.info.user = ""  # Nobody is logged on yet, as in SAP GUI.
        return self._activate(session, LOGON_TCODE, 0)

    def _checked_logon_values(self) -> Optional[dict[str, str]]:
        """Read and check the logon screen's fields; report and return None if they fail."""
        session = self._session
        if session is None or self._tcode != LOGON_TCODE:
            return None
        values = {}
        for key, path in _LOGON_FIELDS.items():
            try:
                values[key] = session.findById(path).text or ""
            except RuntimeError:
                values[key] = ""

        error = check_logon(values["client"], values["user"], values["password"], values["language"],
                            users=self.users, environment=self.environment_id)
        if error:
            # SAP GUI clears the password after a failed logon.
            try:
                session.findById(_LOGON_FIELDS["password"]).value = ""
            except RuntimeError:
                pass
            self._report(error)
            return None
        return values

    def _attempt_logon(self) -> Optional[Session]:
        values = self._checked_logon_values()
        if values is None:
            return None
        if self.users.is_initial(self.environment_id, values["user"]):
            # An initial password must be changed before the user gets in.
            self._open_password_popup("forced", "Change Password", _PASSWORD_FIELDS,
                                      "Choose a new password", values=values)
            return None
        return self._complete_logon(values)

    def _complete_logon(self, values: dict[str, str]) -> Optional[Session]:
        self._logged_on = True
        self._logon = {
            "user": values["user"].strip().upper(),
            "client": values["client"].strip(),
            "language": (values["language"].strip() or "EN").upper(),
        }
        return self._start(HOME_TCODE)

    # ── password popups ───────────────────────────────────────────────────────

    def _open_new_password(self) -> Optional[ModalWindow]:
        values = self._checked_logon_values()
        if values is None:
            return None
        return self._open_password_popup("set", "Change Password", _PASSWORD_FIELDS,
                                         "Enter a new password", values=values)

    def _open_su3_password(self) -> Optional[ModalWindow]:
        user = self._logon.get("user", "")
        if self._tcode != "SU3" or not user or not self.users.exists(self.environment_id, user):
            self._report("The password of this user cannot be changed", number="190")
            return None
        fields = [("RSYST-BCODE", "Old Password")] + _PASSWORD_FIELDS
        return self._open_password_popup("su3", "Change Password", fields, subscreen="SAPMSYST:0043",
                                         user=user)

    def _open_reset_password(self) -> Optional[ModalWindow]:
        if self._tcode != "SU01" or self._session is None:
            return None
        try:
            user = (self._session.findById(SU01_USER_FIELD).text or "").strip().upper()
        except RuntimeError:
            user = ""
        if not user:
            self._report("Enter a user name")
            return None
        if not self.users.exists(self.environment_id, user):
            self._report(f"User {user} does not exist")
            return None
        return self._open_password_popup("reset", f"Change Password for User {user}", _PASSWORD_FIELDS,
                                         "Enter an initial password", user=user)

    def _open_password_popup(self, kind: str, title: str, fields, message: str = "",
                             subscreen: str = "", **state) -> ModalWindow:
        wnd = popups.open_popup(self._session, title, fields, message, subscreen=subscreen)
        self._popup = {"kind": kind, **state}
        self._wire_popup(self._session, wnd)
        self._notify_popups()
        return wnd

    def _popup_continue(self) -> Optional[Session]:
        session, state = self._session, self._popup
        wnd = popups.popup(session)
        if state is None or wnd is None:
            return None
        if popups.popup(session, popups.MESSAGE_INDEX) is not None:
            return self._close_message()

        env, kind = self.environment_id, state["kind"]
        new = popups.field_text(wnd, NEW_PASSWORD)
        repeat = popups.field_text(wnd, REPEAT_PASSWORD)
        if kind in ("set", "forced"):
            values = state["values"]
            error = self.users.change_password(env, values["user"], values["password"], new, repeat)
        elif kind == "su3":
            old = popups.field_text(wnd, "RSYST-BCODE")
            error = self.users.change_password(env, state["user"], old, new, repeat)
        else:
            error = self.users.reset_password(env, state["user"], new, repeat)

        if error:
            # As in SAP, a rejected password is reported in a second popup.
            popups.clear_fields(wnd)
            self._report(error)
            message = popups.open_message(session, error)
            self._wire_message(session, message)
            self._notify_popups()
            return None

        self._close_popups()
        if kind in ("set", "forced"):
            result = self._complete_logon({**state["values"], "password": new})
            self._report("Password changed", "S")
            return result
        if kind == "su3":
            self._report("Password changed", "S")
        else:
            self._report(f"Password for user {state['user']} was reset", "S")
        return session

    def _popup_cancel(self) -> None:
        if self._popup is None:
            return
        self._close_popups()
        self._report("Password change cancelled", "W")

    def _close_message(self) -> None:
        if self._session is not None:
            popups.close_popup(self._session, popups.MESSAGE_INDEX)
            self._notify_popups()

    def _close_popups(self) -> None:
        self._popup = None
        if self._session is not None:
            popups.close_popup(self._session)
            self._notify_popups()

    def _notify_popups(self) -> None:
        session = self._session
        if session is None:
            return
        top = session.active_window
        window = top if isinstance(top, ModalWindow) else None
        for listener in self._popup_listeners:
            listener(session, window)

    def _log_off(self) -> Optional[Session]:
        self._logged_on = False
        self._logon = {}
        return self._show_logon()

    def _show(self, tcode: str, step: int) -> Optional[Session]:
        session = self._load(TRANSACTIONS[tcode][step])
        if session is None:
            return None
        if self._logon:
            session.info.user = self._logon["user"]
            session.info.client = self._logon["client"]
            session.info.language = self._logon["language"]
            if tcode == "SU3":  # SU3 shows the logged-on user's own profile
                try:
                    session.findById("wnd[0]/usr/txtSUID_ST_BNAME-BNAME").text = self._logon["user"]
                except RuntimeError:
                    pass
        return self._activate(session, tcode, step)

    def _load(self, name: str) -> Optional[Session]:
        path = SCREEN_DIR / name
        if not path.exists():
            self._report(f"Screen file not found: {name}")
            return None
        return load_screen(path)

    def _activate(self, session: Session, tcode: str, step: int) -> Session:
        if self._environment is not None:
            session.info.system_name = self._environment.system
            if not self._logon:
                session.info.client = self._environment.client
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

    def _report(self, message: str, message_type: str = "E", number: str = "") -> None:
        if self._session is not None:
            self._session.set_status(message, message_type, number)
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

    def _wire_popup(self, session: Session, wnd: ModalWindow) -> None:
        """Continue (Enter, btn[0]) and Cancel (F12, btn[12]) on the password popup."""
        def live() -> bool:
            return (session is self._session and self._popup is not None
                    and popups.popup(session, popups.MESSAGE_INDEX) is None)

        def on_vkey(_window, key, _label):
            if not live():
                return
            if key == _VKEY_ENTER:
                self.popup_continue()
            elif key == _VKEY_CANCEL:
                self.popup_cancel()

        wnd.on("vkey", on_vkey)
        self._wire_buttons(wnd, {popups.BTN_CONTINUE: self.popup_continue,
                                 popups.BTN_CANCEL: self.popup_cancel}, live)

    def _wire_message(self, session: Session, wnd: ModalWindow) -> None:
        """Any confirming key or Continue closes the message popup."""
        def close():
            if session is self._session:
                self._dispatch(self._close_message)

        wnd.on("vkey", lambda _w, key, _l: close() if key in (_VKEY_ENTER, _VKEY_CANCEL) else None)
        self._wire_buttons(wnd, {popups.BTN_CONTINUE: close}, lambda: True)

    @staticmethod
    def _wire_buttons(wnd: ModalWindow, actions: dict, live: Callable[[], bool]) -> None:
        for number, action in actions.items():
            button = wnd.find_control(f"{wnd.id}/tbar[0]/btn[{number}]")
            if button is not None:
                button.on("press", lambda _c, act=action: act() if live() else None)

    def _button_action(self, ctrl) -> Optional[Callable[[], Any]]:
        tooltip = (ctrl.tooltip or "").lower()
        text = (ctrl.text or "").lower()
        ctrl_id = (ctrl.id or "").lower()

        if "password" in tooltip:
            if self._tcode == LOGON_TCODE:
                return self.open_new_password
            if self._tcode == "SU01":
                return self.open_reset_password
            if self._tcode == "SU3":
                return self.open_su3_password

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
        if self._popup is not None:
            return  # A modal popup is open; the main window doesn't react.
        if self._tcode == LOGON_TCODE and key == _VKEY_NEW_PASSWORD:
            self.open_new_password()
            return
        if self._tcode == "SU01" and key == _VKEY_CHANGE_PASSWORD:
            self.open_reset_password()
            return
        if key == _VKEY_ENTER:
            wnd = session.get_window(0)
            okcd = wnd.command_field if wnd else None
            command = (okcd.text if okcd else "").strip()
            if command:
                okcd.text = ""
                self.handle_command(command)
                return
            if self._tcode == LOGON_TCODE:
                self.attempt_logon()
                return
        if self._tcode == LOGON_TCODE:
            return
        if key in (_VKEY_BACK, _VKEY_CANCEL):
            self.go_back()
        elif key == _VKEY_EXIT:
            self.go_home()
        elif key in _ADVANCE_KEYS.get((self._tcode, self._step), ()):
            self.next_step()
