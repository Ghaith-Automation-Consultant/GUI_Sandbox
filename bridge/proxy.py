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
"""
from __future__ import annotations

from typing import Any, Optional

from engine.control import (
    Control, TableControl, GridView, StatusBar,
)
from engine.session import Session, Window
from .recorder import ActionRecorder


# ──────────────────────────────────────────────────────────────────────────────
#  Collection helpers
# ──────────────────────────────────────────────────────────────────────────────

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

class ControlProxy:
    """
    Duck-type proxy for engine.Control matching the SAP GUI Scripting COM API.

    Both PascalCase (SAP COM style) and snake_case (Pythonic) property names
    are supported, so scripts written for the real SAP COM engine work unchanged.
    """

    def __init__(self, ctrl: Control, recorder: Optional[ActionRecorder] = None) -> None:
        self._ctrl     = ctrl
        self._recorder = recorder

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
        return self.RowCount

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

    def GetCell(self, row: int, col: int) -> Optional["ControlProxy"]:
        if isinstance(self._ctrl, TableControl):
            cell = self._ctrl.get_cell(row, col)
            if cell:
                return ControlProxy(cell, self._recorder)
        return None

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

    def GetCellValue(self, row: int, col_name: str) -> str:
        if isinstance(self._ctrl, GridView):
            return self._ctrl.get_cell_value(row, col_name)
        return ""

    # ── status bar ───────────────────────────────────────────────────────────

    @property
    def MessageId(self) -> str:
        if isinstance(self._ctrl, StatusBar):
            return self._ctrl.message_type
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
