# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer C — COM Scripting Bridge: wrapper classes.

Exposes the engine.Session control tree as Windows COM objects registered
in the Running Object Table (ROT).  External scripts access the sandbox via::

    import win32com.client
    sap = win32com.client.GetObject("SAPGUI")
    app = sap.GetScriptingEngine
    session = app.Children(0).Children(0)
    session.findById("wnd[0]/usr/ctxtFOO").Text = "SFLIGHT"
    session.findById("wnd[0]").sendVKey(0)

The hierarchy mirrors the real SAP GUI Scripting Engine:

    GetObject("SAPGUI")        →  ComSapGui
      .GetScriptingEngine       →  ComApplication
        .Children(0)            →  ComConnection
          .Children(0)          →  ComSession
            .findById(path)     →  ComControl  (wraps any engine.Control)
"""
from __future__ import annotations

import threading
from typing import Any, Optional

import win32com.server.util

from engine.control import (
    Control, TableControl, GridView, StatusBar,
    CheckBox, RadioButton,
)
from engine.session import Session, Window


def _wrap(obj: Any) -> Any:
    """Wrap a Python COM class as an IDispatch pointer for COM clients."""
    return win32com.server.util.wrap(obj)


_SAP_TYPE_NUMBERS: dict[str, int] = {
    "GuiApplication":        10,
    "GuiConnection":         11,
    "GuiSession":            12,
    "GuiMainWindow":         21,
    "GuiModalWindow":        22,
    "GuiStatusbar":          103,
    "GuiOkCodeField":        35,
    "GuiButton":             40,
    "GuiLabel":              30,
    "GuiTextField":          31,
    "GuiCTextField":         32,
    "GuiPasswordField":      33,
    "GuiCheckBox":           42,
    "GuiRadioButton":        43,
    "GuiComboBox":           34,
    "GuiToolbar":            101,
    "GuiTitlebar":           102,
    "GuiMenubar":            110,
    "GuiMenu":               111,
    "GuiMenuItem":           112,
    "GuiTab":                91,
    "GuiTabStrip":           90,
    "GuiUserArea":           74,
    "GuiShell":              122,
    "GuiTableControl":       80,
    "GuiGridView":           201,
    "GuiTree":               200,
    "GuiBox":                62,
    "GuiScrollContainer":    72,
    "GuiSimpleContainer":    71,
    "GuiSplitterContainer":  75,
    "GuiControl":            0,
}


class SessionHolder:
    """Thread-safe wrapper for the active Session reference."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._lock = threading.Lock()

    @property
    def session(self) -> Session:
        with self._lock:
            return self._session

    @session.setter
    def session(self, value: Session) -> None:
        with self._lock:
            self._session = value


# ──────────────────────────────────────────────────────────────────────────────
#  ComCollection
# ──────────────────────────────────────────────────────────────────────────────

class ComCollection:
    """
    Indexed COM collection — supports .Count, .Item(i), and default-index
    access (col(i) in VBScript / Python).

    The ``_value_`` method maps to DISPID_VALUE (0) so that
    ``coll(i)`` works without calling ``.Item(i)`` explicitly.
    """

    _public_methods_ = ["Item"]
    _public_attrs_ = ["Count"]
    _readonly_attrs_ = ["Count"]

    def __init__(self, items: list) -> None:
        self._items = items

    def _value_(self, index: int) -> Any:
        return self._items[int(index)]

    @property
    def Count(self) -> int:
        return len(self._items)

    def Item(self, index: int) -> Any:
        return self._items[int(index)]


# ──────────────────────────────────────────────────────────────────────────────
#  ComSessionInfo
# ──────────────────────────────────────────────────────────────────────────────

class ComSessionInfo:
    """Read-only session metadata — mirrors GuiSessionInfo."""

    _public_methods_: list[str] = []
    _public_attrs_ = [
        "Transaction", "Program", "ScreenNumber",
        "SystemName", "Client", "User",
        "IsLowSpeedConnection", "Language",
    ]
    _readonly_attrs_ = _public_attrs_[:]

    def __init__(self, info: Any) -> None:
        self._info = info

    @property
    def Transaction(self) -> str:
        return self._info.transaction

    @property
    def Program(self) -> str:
        return self._info.program

    @property
    def ScreenNumber(self) -> int:
        return self._info.screen_number

    @property
    def SystemName(self) -> str:
        return self._info.system_name

    @property
    def Client(self) -> str:
        return self._info.client

    @property
    def User(self) -> str:
        return self._info.user

    @property
    def IsLowSpeedConnection(self) -> bool:
        return False

    @property
    def Language(self) -> str:
        return getattr(self._info, "language", "EN")


# ──────────────────────────────────────────────────────────────────────────────
#  ComControl — universal control wrapper
# ──────────────────────────────────────────────────────────────────────────────

class ComControl:
    """
    Wraps any engine.Control and exposes SAP COM-compatible properties.

    Both read-only properties (Id, Type, Name, Enabled, …) and read-write
    properties (Text) are supported.  Action methods (Press, Select,
    sendVKey, findById) delegate to the underlying engine control.
    """

    _public_methods_ = [
        "findById", "Press", "Select", "sendVKey",
        "GetCellValue", "GetCell",
    ]
    _public_attrs_ = [
        "Id", "Type", "TypeAsNumber", "Name", "Text",
        "Tooltip", "DefaultTooltip",
        "Enabled", "Changeable", "Visible", "Required",
        "MaxLength", "Left", "Top", "Width", "Height",
        "ScreenLeft", "ScreenTop",
        "RowCount", "VisibleRowCount", "ColumnCount",
        "Children", "ColumnOrder",
        "MessageId", "Selected",
    ]
    _readonly_attrs_ = [
        "Id", "Type", "TypeAsNumber", "Name",
        "Tooltip", "DefaultTooltip",
        "Enabled", "Changeable", "Visible", "Required",
        "MaxLength", "Left", "Top", "Width", "Height",
        "ScreenLeft", "ScreenTop",
        "RowCount", "VisibleRowCount", "ColumnCount",
        "Children", "ColumnOrder",
        "MessageId", "Selected",
    ]

    def __init__(self, ctrl: Control, session: Optional[Session] = None) -> None:
        self._ctrl = ctrl
        self._session = session

    # ── identity ─────────────────────────────────────────────────────────────

    @property
    def Id(self) -> str:
        return self._ctrl.id

    @property
    def Type(self) -> str:
        return type(self._ctrl).sap_type

    @property
    def TypeAsNumber(self) -> int:
        return _SAP_TYPE_NUMBERS.get(type(self._ctrl).sap_type, 0)

    @property
    def Name(self) -> str:
        return self._ctrl.name

    # ── text / value ─────────────────────────────────────────────────────────

    @property
    def Text(self) -> str:
        return self._ctrl.text

    @Text.setter
    def Text(self, v: str) -> None:
        self._ctrl.value = str(v)

    # ── state ────────────────────────────────────────────────────────────────

    @property
    def Enabled(self) -> bool:
        return self._ctrl.enabled

    @property
    def Changeable(self) -> bool:
        return self._ctrl.changeable

    @property
    def Visible(self) -> bool:
        return self._ctrl.visible

    @property
    def Required(self) -> bool:
        return self._ctrl.required

    @property
    def Tooltip(self) -> str:
        return self._ctrl.tooltip

    @property
    def DefaultTooltip(self) -> str:
        return self._ctrl.tooltip

    @property
    def MaxLength(self) -> int:
        return self._ctrl.max_length

    # ── position / size ──────────────────────────────────────────────────────

    @property
    def Left(self) -> int:
        return self._ctrl.left

    @property
    def Top(self) -> int:
        return self._ctrl.top

    @property
    def Width(self) -> int:
        return self._ctrl.width

    @property
    def Height(self) -> int:
        return self._ctrl.height

    @property
    def ScreenLeft(self) -> int:
        return self._ctrl.left

    @property
    def ScreenTop(self) -> int:
        return self._ctrl.top

    # ── selection state (checkbox / radio) ────────────────────────────────────

    @property
    def Selected(self) -> bool:
        if isinstance(self._ctrl, (CheckBox, RadioButton)):
            return self._ctrl.selected
        return False

    # ── table / grid ─────────────────────────────────────────────────────────

    @property
    def RowCount(self) -> int:
        if isinstance(self._ctrl, (TableControl, GridView)):
            return self._ctrl.row_count
        return 0

    @property
    def VisibleRowCount(self) -> int:
        return self.RowCount

    @property
    def ColumnCount(self) -> int:
        if isinstance(self._ctrl, (TableControl, GridView)):
            return len(self._ctrl.columns)
        return 0

    @property
    def ColumnOrder(self) -> Any:
        if isinstance(self._ctrl, GridView):
            return self._ctrl.column_order
        return []

    def GetCellValue(self, row: int, col: Any) -> str:
        if isinstance(self._ctrl, GridView):
            return self._ctrl.get_cell_value(int(row), str(col))
        if isinstance(self._ctrl, TableControl):
            return self._ctrl.get_cell_value(int(row), int(col))
        return ""

    def GetCell(self, row: int, col: int) -> Any:
        if isinstance(self._ctrl, TableControl):
            cell = self._ctrl.get_cell(int(row), int(col))
            if cell:
                return _wrap(ComControl(cell, self._session))
        return None

    # ── status bar ───────────────────────────────────────────────────────────

    @property
    def MessageId(self) -> str:
        if isinstance(self._ctrl, StatusBar):
            return self._ctrl.message_type
        return ""

    # ── actions ──────────────────────────────────────────────────────────────

    def Press(self) -> None:
        self._ctrl.press()

    def Select(self) -> None:
        self._ctrl.select()

    def sendVKey(self, key: int) -> None:
        if isinstance(self._ctrl, Window):
            self._ctrl.send_vkey(int(key))
            return
        node = self._ctrl.parent
        while node is not None:
            if isinstance(node, Window):
                node.send_vkey(int(key))
                return
            node = node.parent

    # ── children ─────────────────────────────────────────────────────────────

    @property
    def Children(self) -> Any:
        items = [_wrap(ComControl(c, self._session)) for c in self._ctrl.children]
        return _wrap(ComCollection(items))

    # ── findById ─────────────────────────────────────────────────────────────

    def findById(self, path: str) -> Any:
        if self._session is not None:
            ctrl = self._session.findById(path)
        else:
            ctrl = self._ctrl.find_control(path)
            if ctrl is None:
                ctrl = self._ctrl.find_control(f"{self._ctrl.id}/{path}")
            if ctrl is None:
                raise RuntimeError(f"Control not found: {path!r}")
        return _wrap(ComControl(ctrl, self._session))


# ──────────────────────────────────────────────────────────────────────────────
#  ComSession — wraps engine.Session
# ──────────────────────────────────────────────────────────────────────────────

class ComSession:
    """Wraps engine.Session — the primary scripting entry point."""

    _public_methods_ = ["findById", "StartTransaction", "sendVKey"]
    _public_attrs_ = ["Info", "ActiveWindow", "Children", "Id", "Type", "Name", "Busy"]
    _readonly_attrs_ = ["Info", "ActiveWindow", "Children", "Id", "Type", "Name", "Busy"]

    def __init__(self, holder: SessionHolder) -> None:
        self._holder = holder

    @property
    def _session(self) -> Session:
        return self._holder.session

    @property
    def Id(self) -> str:
        return self._session.id

    @property
    def Type(self) -> str:
        return "GuiSession"

    @property
    def Name(self) -> str:
        return "ses[0]"

    @property
    def Busy(self) -> bool:
        return False

    def findById(self, path: str) -> Any:
        session = self._session
        ctrl = session.findById(path)
        return _wrap(ComControl(ctrl, session))

    def StartTransaction(self, tcode: str) -> None:
        self._session.start_transaction(tcode)

    def sendVKey(self, key: int, wnd_index: int = 0) -> None:
        self._session.send_vkey(int(key), int(wnd_index))

    @property
    def Info(self) -> Any:
        return _wrap(ComSessionInfo(self._session.info))

    @property
    def ActiveWindow(self) -> Any:
        session = self._session
        wnd = session.active_window
        if wnd:
            return _wrap(ComControl(wnd, session))
        return None

    @property
    def Children(self) -> Any:
        session = self._session
        items = [_wrap(ComControl(c, session)) for c in session.children]
        return _wrap(ComCollection(items))


# ──────────────────────────────────────────────────────────────────────────────
#  ComConnection / ComApplication — structural wrappers
# ──────────────────────────────────────────────────────────────────────────────

class ComConnection:
    """One SAP connection — holds a single session."""

    _public_methods_: list[str] = []
    _public_attrs_ = ["Children", "Sessions", "Description", "Id", "Type", "DisabledByServer"]
    _readonly_attrs_ = _public_attrs_[:]

    def __init__(self, holder: SessionHolder) -> None:
        self._holder = holder

    @property
    def Id(self) -> str:
        return "/app/con[0]"

    @property
    def Type(self) -> str:
        return "GuiConnection"

    @property
    def Description(self) -> str:
        return f"SIM {self._holder.session.info.system_name}"

    @property
    def DisabledByServer(self) -> bool:
        return False

    @property
    def Children(self) -> Any:
        return _wrap(ComCollection([_wrap(ComSession(self._holder))]))

    @property
    def Sessions(self) -> Any:
        return self.Children


class ComApplication:
    """Top-level application object."""

    _public_methods_: list[str] = []
    _public_attrs_ = [
        "Connections", "Children", "Id", "Type",
        "HistoryEnabled", "MajorVersion", "MinorVersion",
        "PatchLevel", "Revision",
    ]
    _readonly_attrs_ = [
        "Connections", "Children", "Id", "Type",
        "MajorVersion", "MinorVersion", "PatchLevel", "Revision",
    ]

    def __init__(self, holder: SessionHolder) -> None:
        self._holder = holder
        self._history_enabled = True

    @property
    def Id(self) -> str:
        return "/app"

    @property
    def Type(self) -> str:
        return "GuiApplication"

    @property
    def HistoryEnabled(self) -> bool:
        return self._history_enabled

    @HistoryEnabled.setter
    def HistoryEnabled(self, value: bool) -> None:
        self._history_enabled = bool(value)

    @property
    def MajorVersion(self) -> int:
        return 770

    @property
    def MinorVersion(self) -> int:
        return 0

    @property
    def PatchLevel(self) -> int:
        return 0

    @property
    def Revision(self) -> int:
        return 0

    @property
    def Connections(self) -> Any:
        return _wrap(ComCollection([_wrap(ComConnection(self._holder))]))

    @property
    def Children(self) -> Any:
        return self.Connections


# ──────────────────────────────────────────────────────────────────────────────
#  ComSapGui — ROT entry point (GetObject("SAPGUI"))
# ──────────────────────────────────────────────────────────────────────────────

class ComSapGui:
    """
    Entry point registered in the Running Object Table.

    External scripts access this via::

        Set sap = GetObject("SAPGUI")
        Set app = sap.GetScriptingEngine
    """

    _public_methods_ = ["GetScriptingEngine"]
    _public_attrs_ = ["GetScriptingEngine", "Id"]
    _readonly_attrs_ = _public_attrs_[:]

    def __init__(self, holder: SessionHolder) -> None:
        self._holder = holder

    def GetScriptingEngine(self) -> Any:
        return _wrap(ComApplication(self._holder))

    @property
    def Id(self) -> str:
        return "SAPGUI"
