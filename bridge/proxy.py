# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer C — In-process proxy objects.

ControlProxy and SessionProxy wrap engine.Session / engine.Control and present
a SAP GUI Scripting COM-compatible interface so that existing RPA scripts
(written for the real SAP COM engine) work against the sandbox with minimal
or zero changes.

COM patterns fully supported:
  session.findById("wnd[0]/usr/ctxtFOO")          → ControlProxy
  ctrl.Text = "SFLIGHT"   /  ctrl.text = "SFLIGHT"       → set value
  ctrl.Text            /  ctrl.text                 → read value
  ctrl.Press()         /  ctrl.press()              → button click
  ctrl.Select()        /  ctrl.select()             → tab/radio select
  session.findById("wnd[0]").sendVKey(0)            → VKey
  session.Info.Transaction                          → metadata
  ctrl.Children.Count  /  ctrl.Children.Item(i)     → tree navigation
  table.Columns.Item(i).Title                       → column metadata
  table.GetCell(r, c).Text                          → cell read
  grid.ColumnTitles.ElementAt(i)                    → grid column title
  grid.GetCellValue(r, col_name)                    → grid cell read
  table.VerticalScrollbar.Position = 10             → scroll a table control
  grid.FirstVisibleRow = 40 / grid.SetCurrentCell(r, col)  → scroll an ALV grid

Member names are case-insensitive, as in COM: ``table.verticalScrollbar.position``
works too. After a table control scrolls, objects taken from it before the
scroll raise RuntimeError, as SAP GUI does: find the table again.
"""
from __future__ import annotations

from typing import Any, Optional

from engine.control import (
    Control, TableControl, GridView, StatusBar, is_stale, reference_token,
)
from engine.session import Session, Window
from engine.navigation import Navigator

from .recorder import ActionRecorder


# ──────────────────────────────────────────────────────────────────────────────
#  Collection helpers
# ──────────────────────────────────────────────────────────────────────────────

class _ComStyle:
    """COM-like member access: names ignore case, and stale objects refuse use.

    Subclasses set ``_target`` (the engine object) and ``_token`` (its
    ``reference_token`` when wrapped).
    """

    _target: Any = None
    _token: Any = None

    @classmethod
    def _member(cls, name: str) -> Optional[str]:
        if hasattr(cls, name):
            return name
        lower = name.lower()
        for attr in dir(cls):
            if not attr.startswith("_") and attr.lower() == lower:
                return attr
        return None

    def _check(self) -> None:
        target = object.__getattribute__(self, "_target")
        if target is not None and is_stale(target, object.__getattribute__(self, "_token")):
            raise RuntimeError(f"Control not found: {getattr(target, 'id', '')!r} "
                               "(the table scrolled; find it again)")

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("_"):
            object.__getattribute__(self, "_check")()
        return object.__getattribute__(self, name)

    def __getattr__(self, name: str) -> Any:
        member = type(self)._member(name) if not name.startswith("_") else None
        if member is None or member == name:
            raise AttributeError(name)
        return getattr(self, member)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        self._check()
        member = type(self)._member(name)
        if member is None or not isinstance(getattr(type(self), member, None), property):
            raise AttributeError(f"{type(self).__name__} has no settable property {name!r}")
        try:
            object.__setattr__(self, member, value)
        except (ValueError, IndexError, KeyError) as exc:
            raise RuntimeError(str(exc)) from None


class ChildrenCollection:
    """Emulates GuiComponentCollection — exposes .Count and .Item(i)."""

    def __init__(self, ctrl: Control, recorder: Optional[ActionRecorder] = None) -> None:
        self._ctrl     = ctrl
        self._recorder = recorder

    @property
    def Count(self) -> int:
        return len(self._ctrl.children)

    def Item(self, index: int) -> "ControlProxy":
        if not (0 <= index < len(self._ctrl.children)):
            raise IndexError(f"Children index {index} out of range (Count={self.Count})")
        return ControlProxy(self._ctrl.children[index], self._recorder)

    def __call__(self, index: int) -> "ControlProxy":
        """SAP COM also supports Children(i) without .Item."""
        return self.Item(index)

    def __iter__(self):
        for child in self._ctrl.children:
            yield ControlProxy(child, self._recorder)

    def __len__(self) -> int:
        return self.Count


class _ColumnProxy:
    """One column entry in a TableControl (title, name, id)."""

    def __init__(self, col: dict) -> None:
        self._col = col

    @property
    def Title(self) -> str:
        return self._col.get("title", "")

    @property
    def Name(self) -> str:
        return self._col.get("name", "")

    @property
    def Id(self) -> str:
        return self._col.get("id", "")


class ColumnsCollection:
    """Emulates the Columns collection of GuiTableControl."""

    def __init__(self, columns: list[dict]) -> None:
        self._cols = columns

    @property
    def Count(self) -> int:
        return len(self._cols)

    def Item(self, index: int) -> _ColumnProxy:
        return _ColumnProxy(self._cols[index])

    def __call__(self, index: int) -> _ColumnProxy:
        return self.Item(index)

    def __iter__(self):
        for col in self._cols:
            yield _ColumnProxy(col)

    def __len__(self) -> int:
        return self.Count


class ColumnTitlesCollection:
    """Emulates the GuiGridView.ColumnTitles collection — supports .ElementAt(i)."""

    def __init__(self, columns: list[dict]) -> None:
        self._cols = columns

    def ElementAt(self, index: int) -> str:
        if 0 <= index < len(self._cols):
            return self._cols[index].get("title", "")
        return ""

    def __iter__(self):
        for col in self._cols:
            yield col.get("title", "")

    def __len__(self) -> int:
        return len(self._cols)


class SessionInfoProxy:
    """Emulates GuiSessionInfo with COM-style property names (PascalCase)."""

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


# ──────────────────────────────────────────────────────────────────────────────
#  ControlProxy
# ──────────────────────────────────────────────────────────────────────────────

class ControlProxy(_ComStyle):
    """
    Duck-type proxy for engine.Control matching the SAP GUI Scripting COM API.

    Both PascalCase (SAP COM style) and snake_case (Pythonic) property names
    are supported, so scripts written for the real SAP COM engine work unchanged.
    """

    def __init__(self, ctrl: Control, recorder: Optional[ActionRecorder] = None) -> None:
        self._ctrl     = ctrl
        self._recorder = recorder
        self._target   = ctrl
        self._token    = reference_token(ctrl)

    def _log(self, action: str, value: Any = None, result: Any = None) -> None:
        if self._recorder:
            self._recorder.log(action, path=self._ctrl.id, value=value, result=result)

    # ── identity ─────────────────────────────────────────────────────────────

    @property
    def Id(self) -> str:
        return self._ctrl.id

    @property
    def Type(self) -> str:
        return type(self._ctrl).sap_type

    @property
    def Name(self) -> str:
        return self._ctrl.name

    # ── text / value ─────────────────────────────────────────────────────────

    @property
    def Text(self) -> str:
        return self._ctrl.text

    @Text.setter
    def Text(self, v: str) -> None:
        self._log("setText", value=v)
        self._ctrl.value = str(v)

    @property
    def text(self) -> str:
        return self._ctrl.text

    @text.setter
    def text(self, v: str) -> None:
        self.Text = v

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

    # ── position / size ───────────────────────────────────────────────────────

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

    # ── table — row / column counts ───────────────────────────────────────────

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

    # ── table — GuiTableControl API ───────────────────────────────────────────

    @property
    def Columns(self) -> ColumnsCollection:
        if isinstance(self._ctrl, TableControl):
            return ColumnsCollection(self._ctrl.columns)
        return ColumnsCollection([])

    def _visible_cell(self, row: int, col: int) -> Control:
        cell = self._ctrl.get_cell(int(row), int(col))
        if cell is None:
            raise RuntimeError(f"Row {row}, column {col} is not in the visible area "
                               f"(rows 0..{self._ctrl.visible_row_count - 1}); scroll first")
        return cell

    def GetCell(self, row: int, col: int) -> Optional["ControlProxy"]:
        """The cell at a visible row: 0 is the top row on screen, as in SAP GUI."""
        if isinstance(self._ctrl, TableControl):
            return ControlProxy(self._visible_cell(row, col), self._recorder)
        return None

    @property
    def VerticalScrollbar(self) -> Optional["ScrollbarProxy"]:
        if isinstance(self._ctrl, TableControl):
            return ScrollbarProxy(self._ctrl.vertical_scrollbar, self._recorder)
        return None

    @property
    def Rows(self) -> "RowsCollection":
        """The visible rows, as SAP GUI's Rows collection."""
        rows = self._ctrl.rows if isinstance(self._ctrl, TableControl) else []
        return RowsCollection([TableRowProxy(r, self._recorder) for r in rows])

    def GetAbsoluteRow(self, row: int) -> Optional["TableRowProxy"]:
        if not isinstance(self._ctrl, TableControl):
            return None
        try:
            return TableRowProxy(self._ctrl.get_absolute_row(int(row)), self._recorder)
        except IndexError as exc:
            raise RuntimeError(str(exc)) from None

    # ── grid — GuiGridView API ────────────────────────────────────────────────

    @property
    def ColumnOrder(self) -> list[str]:
        if isinstance(self._ctrl, GridView):
            return self._ctrl.column_order
        return []

    @property
    def ColumnTitles(self) -> ColumnTitlesCollection:
        if isinstance(self._ctrl, GridView):
            return ColumnTitlesCollection(self._ctrl.columns)
        return ColumnTitlesCollection([])

    def GetCellValue(self, row: int, col: Any) -> str:
        """GuiGridView: absolute row and column name. Table control: visible row, column index."""
        if isinstance(self._ctrl, GridView):
            try:
                self._ctrl.check_cell(int(row), str(col))
            except (IndexError, KeyError) as exc:
                raise RuntimeError(str(exc)) from None
            return self._ctrl.get_cell_value(int(row), str(col))
        if isinstance(self._ctrl, TableControl):
            return self._visible_cell(row, col).text
        return ""

    def _grid(self) -> GridView:
        if not isinstance(self._ctrl, GridView):
            raise RuntimeError(f"{self._ctrl.id} is not a GuiGridView")
        return self._ctrl

    @property
    def FirstVisibleRow(self) -> int:
        return self._ctrl.first_visible_row if isinstance(self._ctrl, GridView) else 0

    @FirstVisibleRow.setter
    def FirstVisibleRow(self, row: int) -> None:
        self._log("setFirstVisibleRow", value=row)
        self._grid().first_visible_row = int(row)

    @property
    def CurrentCellRow(self) -> int:
        return self._ctrl.current_cell_row if isinstance(self._ctrl, GridView) else -1

    @CurrentCellRow.setter
    def CurrentCellRow(self, row: int) -> None:
        grid = self._grid()
        self.SetCurrentCell(int(row), grid.current_cell_column or grid.column_order[0])

    @property
    def CurrentCellColumn(self) -> str:
        return self._ctrl.current_cell_column if isinstance(self._ctrl, GridView) else ""

    @CurrentCellColumn.setter
    def CurrentCellColumn(self, col: str) -> None:
        grid = self._grid()
        self.SetCurrentCell(max(grid.current_cell_row, 0), str(col))

    def SetCurrentCell(self, row: int, col: str) -> None:
        self._log("setCurrentCell", value=[row, col])
        try:
            self._grid().set_current_cell(int(row), str(col))
        except (IndexError, KeyError) as exc:
            raise RuntimeError(str(exc)) from None

    @property
    def SelectedRows(self) -> str:
        return self._ctrl.selected_rows_text if isinstance(self._ctrl, GridView) else ""

    @SelectedRows.setter
    def SelectedRows(self, rows: str) -> None:
        self._log("setSelectedRows", value=rows)
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
        self._log("press")
        self._ctrl.press()

    def press(self) -> None:
        self.Press()

    def Select(self) -> None:
        self._log("select")
        self._ctrl.select()

    def select(self) -> None:
        self.Select()

    def sendVKey(self, key: int) -> None:
        self._log("sendVKey", value=key)
        if isinstance(self._ctrl, Window):
            self._ctrl.send_vkey(key)
            return
        # Walk up to the nearest Window ancestor
        node = self._ctrl.parent
        while node is not None:
            if isinstance(node, Window):
                node.send_vkey(key)
                return
            node = node.parent

    # ── children ─────────────────────────────────────────────────────────────

    @property
    def Children(self) -> ChildrenCollection:
        return ChildrenCollection(self._ctrl, self._recorder)

    # ── nested findById ───────────────────────────────────────────────────────

    def findById(self, path: str) -> "ControlProxy":
        """Find a descendant by full or relative ID path."""
        ctrl = self._ctrl.find_control(path)
        if ctrl is None:
            ctrl = self._ctrl.find_control(f"{self._ctrl.id}/{path}")
        if ctrl is None:
            raise RuntimeError(f"Control not found: {path!r}")
        return ControlProxy(ctrl, self._recorder)

    def __repr__(self) -> str:
        return f"<ControlProxy {self._ctrl.id!r} [{type(self._ctrl).__name__}]>"


class ScrollbarProxy(_ComStyle):
    """A table control's vertical scrollbar (GuiScrollbar)."""

    def __init__(self, bar: Any, recorder: Optional[ActionRecorder] = None) -> None:
        self._bar = bar
        self._recorder = recorder
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
        if self._recorder:
            self._recorder.log("setScrollPosition", path=self._bar.table.id, value=int(value))
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


class TableRowProxy(_ComStyle):
    """One table control row (GuiTableRow): its cells and its selection."""

    def __init__(self, row: Any, recorder: Optional[ActionRecorder] = None) -> None:
        self._row = row
        self._recorder = recorder
        self._target = row
        self._token = reference_token(row)

    @property
    def Type(self) -> str:
        return "GuiTableRow"

    @property
    def Count(self) -> int:
        return len(self._row.cells)

    def Item(self, index: int) -> ControlProxy:
        cells = self._row.cells
        if not 0 <= int(index) < len(cells):
            raise RuntimeError(f"Cell {index} is not in this row, or the row is not on screen")
        return ControlProxy(cells[int(index)], self._recorder)

    def ElementAt(self, index: int) -> ControlProxy:
        return self.Item(index)

    def __call__(self, index: int) -> ControlProxy:
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


class RowsCollection:
    """The visible rows of a table control."""

    def __init__(self, rows: list[TableRowProxy]) -> None:
        self._rows = rows

    @property
    def Count(self) -> int:
        return len(self._rows)

    def Item(self, index: int) -> TableRowProxy:
        return self._rows[int(index)]

    def ElementAt(self, index: int) -> TableRowProxy:
        return self.Item(index)

    def __call__(self, index: int) -> TableRowProxy:
        return self.Item(index)

    def __iter__(self):
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)


# ──────────────────────────────────────────────────────────────────────────────
#  SessionProxy
# ──────────────────────────────────────────────────────────────────────────────

class SessionProxy:
    """
    In-process scripting bridge — wraps engine.Session with the SAP COM interface.

    This is the primary Layer C object for scripts running in the same process
    as the sandbox. Every operation is automatically logged to the recorder.

    Usage::

        from bridge import SandboxSession
        from engine import load_screen

        session = SandboxSession(load_screen("screens/02_SE16_initial.json"))

        # Exact SAP GUI Scripting syntax — works unchanged
        session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
        session.findById("wnd[0]").sendVKey(0)
        print(session.Info.Transaction)

        # Also accepts Pythonic lowercase
        session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").text = "SCARR"
    """

    def __init__(
        self,
        session: Session,
        recorder: Optional[ActionRecorder] = None,
    ) -> None:
        self._session  = session
        self._recorder = recorder if recorder is not None else ActionRecorder()
        Navigator.for_session(session).subscribe(self._follow)

    def _follow(self, session: Session, _tcode: str) -> None:
        self._session = session

    # ── SAP COM-style API ─────────────────────────────────────────────────────

    def findById(self, path: str) -> ControlProxy:
        ctrl = self._session.findById(path)
        self._recorder.log("findById", path=path)
        return ControlProxy(ctrl, self._recorder)

    def StartTransaction(self, tcode: str) -> None:
        self._recorder.log("startTransaction", value=tcode)
        self._session.start_transaction(tcode)

    def startTransaction(self, tcode: str) -> None:
        self.StartTransaction(tcode)

    @property
    def Info(self) -> SessionInfoProxy:
        return SessionInfoProxy(self._session.info)

    @property
    def Children(self) -> ChildrenCollection:
        return ChildrenCollection(self._session, self._recorder)

    @property
    def ActiveWindow(self) -> Optional[ControlProxy]:
        wnd = self._session.active_window
        return ControlProxy(wnd, self._recorder) if wnd else None

    # ── extras ────────────────────────────────────────────────────────────────

    def set_status(self, message: str, message_type: str = "S") -> None:
        """Update the status bar programmatically (S/W/E/A/I)."""
        self._session.set_status(message, message_type)

    @property
    def recorder(self) -> ActionRecorder:
        return self._recorder

    @property
    def session(self) -> Session:
        return self._session

    def __repr__(self) -> str:
        tcode = self._session.info.transaction
        return f"<SessionProxy tcode={tcode!r}>"
