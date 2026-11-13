# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer C — COM Scripting Bridge: wrapper classes.

Exposes the engine.Session control tree as Windows COM objects registered
in the Running Object Table (ROT).  External scripts access the sandbox via::

    import win32com.client
    sap = win32com.client.GetObject("SAPGUI")
    app = sap.GetScriptingEngine
    connection = app.OpenConnection("WL - With logon", True)  # unless one is open
    session = connection.Children(0)
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
from typing import Any, Callable, Optional

import win32com.server.util
import winerror
from win32com.server.exception import COMException

from engine.control import (
    Control, TableControl, GridView, StatusBar,
    CheckBox, RadioButton, is_stale, reference_token,
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
    """Thread-safe wrapper for the active Session reference.

    ``session`` is None while no connection is open, as when SAP Logon is
    running with no system opened. ``opener(description)`` opens an
    environment for OpenConnection and returns it, or None if it is unknown.
    """

    def __init__(
        self,
        session: Optional[Session] = None,
        opener: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self._session = session
        self._lock = threading.Lock()
        self.opener = opener
        self.environment: Any = None

    @property
    def session(self) -> Optional[Session]:
        with self._lock:
            return self._session

    @session.setter
    def session(self, value: Optional[Session]) -> None:
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


def _not_found(path: str) -> COMException:
    # SAP GUI raises a COM error for an unknown ID; scripts test for elements this way.
    return COMException(desc=f"The control could not be found by id: {path}",
                        scode=winerror.DISP_E_EXCEPTION)


def _error(message: str) -> COMException:
    return COMException(desc=message, scode=winerror.DISP_E_EXCEPTION)


class _Checked:
    """Refuses every public member once the wrapped object went stale.

    A table scroll is a round trip in SAP GUI: objects a script held from
    before it stop working and the script finds the table again. The token
    taken at wrap time tells whether the object is still the one on screen.
    """

    _target: Any = None
    _token: Any = None

    def _check(self) -> None:
        target = object.__getattribute__(self, "_target")
        if is_stale(target, object.__getattribute__(self, "_token")):
            raise _not_found(getattr(target, "id", ""))

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("_"):
            object.__getattribute__(self, "_check")()
        return object.__getattribute__(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if not name.startswith("_"):
            self._check()
            try:
                object.__setattr__(self, name, value)
            except (ValueError, IndexError, KeyError) as exc:
                raise _error(str(exc)) from None
            return
        object.__setattr__(self, name, value)


def _find(session: Session, path: str) -> Control:
    try:
        return session.findById(path)
    except RuntimeError:
        raise _not_found(path) from None


def _collection(items: list, index: Any = None) -> Any:
    """Return a wrapped collection, or one item of it when an index is given.

    Collection getters such as ``Children`` are plain methods, not properties:
    pywin32 drops the arguments of a property get, so VBScript's
    ``obj.Children(0)`` would return the whole collection instead of item 0.
    A method receives the index in both the property-get and the call form.
    """
    if index is None:
        return _wrap(ComCollection(items))
    return items[int(index)]


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

class ComControl(_Checked):
    """
    Wraps any engine.Control and exposes SAP COM-compatible properties.

    Both read-only properties (Id, Type, Name, Enabled, …) and read-write
    properties (Text) are supported.  Action methods (Press, Select,
    sendVKey, findById) delegate to the underlying engine control.
    """

    _public_methods_ = [
        "findById", "Press", "Select", "sendVKey",
        "GetCellValue", "GetCell", "GetAbsoluteRow", "Rows", "SetCurrentCell",
    ]
    _public_attrs_ = [
        "Id", "Type", "TypeAsNumber", "Name", "Text",
        "Tooltip", "DefaultTooltip",
        "Enabled", "Changeable", "Visible", "Required",
        "MaxLength", "Left", "Top", "Width", "Height",
        "ScreenLeft", "ScreenTop",
        "RowCount", "VisibleRowCount", "ColumnCount",
        "Children", "ColumnOrder",
        "MessageType", "MessageId", "MessageNumber", "Selected",
        "VerticalScrollbar", "FirstVisibleRow", "CurrentCellRow",
        "CurrentCellColumn", "SelectedRows",
    ]
    _readonly_attrs_ = [
        "Id", "Type", "TypeAsNumber", "Name",
        "Tooltip", "DefaultTooltip",
        "Enabled", "Changeable", "Visible", "Required",
        "MaxLength", "Left", "Top", "Width", "Height",
        "ScreenLeft", "ScreenTop",
        "RowCount", "VisibleRowCount", "ColumnCount",
        "Children", "ColumnOrder",
        "MessageType", "MessageId", "MessageNumber", "Selected",
        "VerticalScrollbar",
    ]

    def __init__(self, ctrl: Control, session: Optional[Session] = None) -> None:
        self._ctrl = ctrl
        self._session = session
        self._target = ctrl
        self._token = reference_token(ctrl)

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
        if isinstance(self._ctrl, (TableControl, GridView)):
            return self._ctrl.visible_row_count
        return 0

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
        """GuiGridView: absolute row and column name. Table control: visible row, column index."""
        if isinstance(self._ctrl, GridView):
            try:
                self._ctrl.check_cell(int(row), str(col))
            except (IndexError, KeyError) as exc:
                raise _error(str(exc)) from None
            return self._ctrl.get_cell_value(int(row), str(col))
        if isinstance(self._ctrl, TableControl):
            return self._visible_cell(row, col).text
        return ""

    def _visible_cell(self, row: Any, col: Any) -> Control:
        cell = self._ctrl.get_cell(int(row), int(col))
        if cell is None:
            raise _error(f"Row {row}, column {col} is not in the visible area "
                         f"(rows 0..{self._ctrl.visible_row_count - 1}); scroll first")
        return cell

    def GetCell(self, row: int, col: int) -> Any:
        """The cell at a visible row: 0 is the top row on screen, as in SAP GUI."""
        if isinstance(self._ctrl, TableControl):
            return _wrap(ComControl(self._visible_cell(row, col), self._session))
        return None

    # ── table control: scrolling and rows ────────────────────────────────────

    @property
    def VerticalScrollbar(self) -> Any:
        if isinstance(self._ctrl, TableControl):
            return _wrap(ComScrollbar(self._ctrl.vertical_scrollbar))
        return None

    def Rows(self, index: Any = None) -> Any:
        """The visible rows (GuiTableRow), as SAP GUI's Rows collection."""
        if not isinstance(self._ctrl, TableControl):
            return _collection([], index)
        items = [_wrap(ComTableRow(r, self._session)) for r in self._ctrl.rows]
        return _collection(items, index)

    def GetAbsoluteRow(self, row: int) -> Any:
        if not isinstance(self._ctrl, TableControl):
            return None
        try:
            return _wrap(ComTableRow(self._ctrl.get_absolute_row(int(row)), self._session))
        except IndexError as exc:
            raise _error(str(exc)) from None

    # ── grid: scrolling, current cell, selection ─────────────────────────────

    def _grid(self) -> GridView:
        if not isinstance(self._ctrl, GridView):
            raise _error(f"{self._ctrl.id} is not a GuiGridView")
        return self._ctrl

    @property
    def FirstVisibleRow(self) -> int:
        return self._ctrl.first_visible_row if isinstance(self._ctrl, GridView) else 0

    @FirstVisibleRow.setter
    def FirstVisibleRow(self, row: int) -> None:
        self._grid().first_visible_row = int(row)

    @property
    def CurrentCellRow(self) -> int:
        return self._ctrl.current_cell_row if isinstance(self._ctrl, GridView) else -1

    @CurrentCellRow.setter
    def CurrentCellRow(self, row: int) -> None:
        grid = self._grid()
        grid.set_current_cell(int(row), grid.current_cell_column or grid.column_order[0])

    @property
    def CurrentCellColumn(self) -> str:
        return self._ctrl.current_cell_column if isinstance(self._ctrl, GridView) else ""

    @CurrentCellColumn.setter
    def CurrentCellColumn(self, col: str) -> None:
        grid = self._grid()
        grid.set_current_cell(max(grid.current_cell_row, 0), str(col))

    def SetCurrentCell(self, row: int, col: str) -> None:
        try:
            self._grid().set_current_cell(int(row), str(col))
        except (IndexError, KeyError) as exc:
            raise _error(str(exc)) from None

    @property
    def SelectedRows(self) -> str:
        return self._ctrl.selected_rows_text if isinstance(self._ctrl, GridView) else ""

    @SelectedRows.setter
    def SelectedRows(self, rows: str) -> None:
        self._grid().selected_rows_text = str(rows)

    # ── status bar ───────────────────────────────────────────────────────────

    @property
    def MessageType(self) -> str:
        """S success, W warning, E error, A abort, I information."""
        if isinstance(self._ctrl, StatusBar):
            return self._ctrl.message_type
        return ""

    @property
    def MessageId(self) -> str:
        """Message class, such as "00"."""
        if isinstance(self._ctrl, StatusBar):
            return self._ctrl.message_id
        return ""

    @property
    def MessageNumber(self) -> str:
        """Message number, such as "343"."""
        if isinstance(self._ctrl, StatusBar):
            return self._ctrl.message_number
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

    def Children(self, index: Any = None) -> Any:
        items = [_wrap(ComControl(c, self._session)) for c in self._ctrl.children]
        return _collection(items, index)

    # ── findById ─────────────────────────────────────────────────────────────

    def findById(self, path: str) -> Any:
        if self._session is not None:
            ctrl = _find(self._session, path)
        else:
            ctrl = self._ctrl.find_control(path)
            if ctrl is None:
                ctrl = self._ctrl.find_control(f"{self._ctrl.id}/{path}")
            if ctrl is None:
                raise _not_found(path)
        return _wrap(ComControl(ctrl, self._session))


class ComScrollbar(_Checked):
    """A table control's vertical scrollbar (GuiScrollbar)."""

    _public_methods_: list[str] = []
    _public_attrs_ = ["Position", "Minimum", "Maximum", "PageSize", "Range", "Id", "Type"]
    _readonly_attrs_ = ["Minimum", "Maximum", "PageSize", "Range", "Id", "Type"]

    def __init__(self, bar: Any) -> None:
        self._bar = bar
        self._target = bar
        self._token = reference_token(bar)

    @property
    def Id(self) -> str:
        return self._bar.id

    @property
    def Type(self) -> str:
        return "GuiScrollbar"

    @property
    def Position(self) -> int:
        return self._bar.position

    @Position.setter
    def Position(self, value: int) -> None:
        self._bar.position = int(value)

    @property
    def Minimum(self) -> int:
        return self._bar.minimum

    @property
    def Maximum(self) -> int:
        return self._bar.maximum

    @property
    def PageSize(self) -> int:
        return self._bar.page_size

    @property
    def Range(self) -> int:
        return self._bar.range


class ComTableRow(_Checked):
    """One table control row (GuiTableRow): its cells and its selection."""

    _public_methods_ = ["Item", "ElementAt"]
    _public_attrs_ = ["Count", "Selected", "Selectable", "Type"]
    _readonly_attrs_ = ["Count", "Selectable", "Type"]

    def __init__(self, row: Any, session: Optional[Session]) -> None:
        self._row = row
        self._session = session
        self._target = row
        self._token = reference_token(row)

    def _value_(self, index: int) -> Any:
        return self.Item(index)

    @property
    def Type(self) -> str:
        return "GuiTableRow"

    @property
    def Count(self) -> int:
        return len(self._row.cells)

    def Item(self, index: int) -> Any:
        cells = self._row.cells
        if not 0 <= int(index) < len(cells):
            raise _error(f"Cell {index} is not in this row, or the row is not on screen")
        return _wrap(ComControl(cells[int(index)], self._session))

    def ElementAt(self, index: int) -> Any:
        return self.Item(index)

    @property
    def Selected(self) -> bool:
        return self._row.selected

    @Selected.setter
    def Selected(self, on: bool) -> None:
        self._row.selected = bool(on)

    @property
    def Selectable(self) -> bool:
        return self._row.selectable


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
        return _wrap(ComControl(_find(session, path), session))

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

    def Children(self, index: Any = None) -> Any:
        session = self._session
        items = [_wrap(ComControl(c, session)) for c in session.children]
        return _collection(items, index)


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
        if self._holder.environment is not None:
            return self._holder.environment.description
        session = self._holder.session
        return f"SIM {session.info.system_name}" if session else ""

    @property
    def DisabledByServer(self) -> bool:
        return False

    def Children(self, index: Any = None) -> Any:
        return _collection([_wrap(ComSession(self._holder))], index)

    def Sessions(self, index: Any = None) -> Any:
        return self.Children(index)


class ComApplication:
    """Top-level application object."""

    _public_methods_ = ["OpenConnection"]
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

    def Connections(self, index: Any = None) -> Any:
        items = [_wrap(ComConnection(self._holder))] if self._holder.session is not None else []
        return _collection(items, index)

    def OpenConnection(self, description: str, sync: bool = True, raise_: bool = True) -> Any:
        """Open an environment from the SAP Logon list, as SAP GUI's OpenConnection does.

        The one open connection is replaced. Returns the new connection once its
        first screen is shown.
        """
        opener = self._holder.opener
        if opener is None:
            raise COMException(desc="Opening connections is not available", scode=winerror.E_NOTIMPL)
        if opener(str(description)) is None:
            raise COMException(desc=f"Connection entry not found: {description}",
                               scode=winerror.E_INVALIDARG)
        return _wrap(ComConnection(self._holder))

    def Children(self, index: Any = None) -> Any:
        return self.Connections(index)


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
