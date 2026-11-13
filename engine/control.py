# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — Control Tree Engine: all control classes.

Type names mirror SAP GUI Scripting COM types so that loader.py can map
screen JSON directly to Python objects without translation tables elsewhere.
"""
from __future__ import annotations

from typing import Any, Callable, Optional


# ──────────────────────────────────────────────────────────────────────────────
#  Base
# ──────────────────────────────────────────────────────────────────────────────

class Control:
    """Atomic UI element — base for every SAP control."""

    sap_type: str = "GuiControl"

    def __init__(
        self,
        control_id: str,
        *,
        name: str = "",
        text: str = "",
        tooltip: str = "",
        enabled: bool = True,
        changeable: bool = True,
        visible: bool = True,
        required: bool = False,
        max_length: int = 0,
        left: int = 0,
        top: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> None:
        self.id          = control_id
        self.name        = name
        self.text        = text
        self.tooltip     = tooltip
        self.enabled     = enabled
        self.changeable  = changeable
        self.visible     = visible
        self.required    = required
        self.max_length  = max_length
        self.left        = left
        self.top         = top
        self.width       = width
        self.height      = height

        self.parent:   Optional[Control]   = None
        self.children: list[Control]       = []
        self.events:   dict[str, Callable] = {}

    # ── tree ─────────────────────────────────────────────────────────────────

    def add_child(self, child: "Control") -> "Control":
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child: "Control") -> None:
        self.children.remove(child)
        child.parent = None

    def find_control(self, control_id: str) -> Optional["Control"]:
        """Depth-first search by full SAP ID path."""
        if self.id == control_id:
            return self
        for child in self.children:
            found = child.find_control(control_id)
            if found:
                return found
        return None

    def all_controls(self) -> list["Control"]:
        """Self and all descendants, depth-first."""
        result = [self]
        for child in self.children:
            result.extend(child.all_controls())
        return result

    # ── events ───────────────────────────────────────────────────────────────

    def on(self, event: str, handler: Callable) -> None:
        """Register an event handler: ctrl.on("change", fn)."""
        self.events[event] = handler

    def trigger(self, event: str, *args: Any, **kwargs: Any) -> Any:
        if event in self.events:
            return self.events[event](*args, **kwargs)

    # ── value shorthand ──────────────────────────────────────────────────────

    @property
    def value(self) -> str:
        return self.text

    @value.setter
    def value(self, v: str) -> None:
        old = self.text
        self.text = v
        if old != v:
            self.trigger("change", self, v)

    # ── action shorthands ────────────────────────────────────────────────────

    def press(self) -> Any:
        """Simulate a button press."""
        return self.trigger("press", self)

    def select(self) -> Any:
        """Simulate a tab/radio select."""
        return self.trigger("select", self)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id!r} text={self.text!r}>"


# ──────────────────────────────────────────────────────────────────────────────
#  Container — any control that holds children
# ──────────────────────────────────────────────────────────────────────────────

class Container(Control):
    """Generic control that can hold child controls."""
    sap_type = "GuiContainerShell"


# ──────────────────────────────────────────────────────────────────────────────
#  Leaf controls
# ──────────────────────────────────────────────────────────────────────────────

class TextField(Control):
    """Plain editable text field (GuiTextField)."""
    sap_type = "GuiTextField"


class ComboTextField(Control):
    """Text field with F4 value-help dropdown (GuiCTextField, ctxt* IDs)."""
    sap_type = "GuiCTextField"


class PasswordField(Control):
    """Masked password field."""
    sap_type = "GuiPasswordField"


class Label(Control):
    """Read-only label."""
    sap_type = "GuiLabel"


class Button(Control):
    """Push button."""
    sap_type = "GuiButton"


class RadioButton(Control):
    """Radio button."""
    sap_type = "GuiRadioButton"

    def __init__(self, control_id: str, *, selected: bool = False, **kwargs: Any) -> None:
        super().__init__(control_id, **kwargs)
        self.selected = selected


class CheckBox(Control):
    """Check box."""
    sap_type = "GuiCheckBox"

    def __init__(self, control_id: str, *, selected: bool = False, **kwargs: Any) -> None:
        super().__init__(control_id, **kwargs)
        self.selected = selected


class ComboBox(Control):
    """Drop-down selection list."""
    sap_type = "GuiComboBox"

    def __init__(self, control_id: str, *, options: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(control_id, **kwargs)
        self.options: list[str] = options or []


class CommandField(Control):
    """SAP OK-code / transaction command field (wnd[0]/tbar[0]/okcd)."""
    sap_type = "GuiOkCodeField"


class StatusBar(Control):
    """Status bar at the bottom of a window."""
    sap_type = "GuiStatusbar"

    def __init__(self, control_id: str, **kwargs: Any) -> None:
        super().__init__(control_id, **kwargs)
        self.message_type: str = ""   # S=success W=warning E=error A=abort I=info
        self.message_id: str = ""     # Message class, such as "00"; empty for sandbox messages
        self.message_number: str = "" # Message number, such as "343" (transaction does not exist)

    def show(self, message: str, message_type: str = "S", message_id: str = "",
             message_number: str = "") -> None:
        self.text = message
        self.message_type = message_type
        self.message_id = message_id
        self.message_number = message_number


class Titlebar(Control):
    sap_type = "GuiTitlebar"


# ──────────────────────────────────────────────────────────────────────────────
#  Structural containers
# ──────────────────────────────────────────────────────────────────────────────

class UserArea(Container):
    """The usr area — the main content region below the toolbars."""
    sap_type = "GuiUserArea"


class Menubar(Container):
    sap_type = "GuiMenubar"


class Menu(Container):
    sap_type = "GuiMenu"


class MenuItem(Control):
    sap_type = "GuiMenuItem"


class Toolbar(Container):
    sap_type = "GuiToolbar"


class TabStrip(Container):
    sap_type = "GuiTabStrip"

    @property
    def active_tab(self) -> Optional["Tab"]:
        for child in self.children:
            if isinstance(child, Tab) and child.selected:
                return child
        return self.children[0] if self.children else None


class Tab(Container):
    sap_type = "GuiTab"

    def __init__(self, control_id: str, *, selected: bool = False, **kwargs: Any) -> None:
        super().__init__(control_id, **kwargs)
        self.selected = selected


class Shell(Container):
    """Generic shell container (used for ALV grids, trees, etc.)."""
    sap_type = "GuiShell"


class Splitter(Container):
    sap_type = "GuiSplitterContainer"


class ScrollContainer(Container):
    sap_type = "GuiScrollContainer"


class SimpleContainer(Container):
    sap_type = "GuiSimpleContainer"


class Box(Container):
    """Labelled group box."""
    sap_type = "GuiBox"


class Tree(Control):
    """SAP Tree control (navigation trees, org-chart style)."""
    sap_type = "GuiTree"


class Chart(Control):
    sap_type = "GuiSAPChart"


# ──────────────────────────────────────────────────────────────────────────────
#  Table controls
#
#  SAP GUI only sends the rows on screen. A GuiTableControl has a cell control
#  for each visible row, with IDs such as txtVBAP-POSNR[col,row] where row
#  counts from the top of the visible area. Scrolling is a round trip: the
#  cells are rebuilt, and objects a script held before it no longer work, so
#  scripts find the table again after each scroll.
# ──────────────────────────────────────────────────────────────────────────────

ROW_HEIGHT = 22      # pixels per table row, as drawn by the Qt shell
HEADER_HEIGHT = 26   # column header plus borders
DEFAULT_VISIBLE_ROWS = 10


def _visible_rows_for(height: int, visible_rows: int) -> int:
    if visible_rows > 0:
        return visible_rows
    if height > HEADER_HEIGHT + ROW_HEIGHT:
        return max(1, (height - HEADER_HEIGHT) // ROW_HEIGHT)
    return DEFAULT_VISIBLE_ROWS


def _registry_root(ctrl: Control) -> Optional[Control]:
    """The session at the top of ctrl's tree, if ctrl is attached to one."""
    node = ctrl
    while node.parent is not None:
        node = node.parent
    return node if hasattr(node, "_registry") else None


def reference_token(obj: Any) -> Optional[int]:
    """What ``is_stale`` compares against: the owning table's scroll count."""
    table = obj if isinstance(obj, TableControl) else getattr(obj, "table", None)
    return table.generation if isinstance(table, TableControl) else None


def is_stale(obj: Any, token: Optional[int]) -> bool:
    """Whether a reference a script took earlier stopped working.

    ``token`` is ``reference_token(obj)`` from when the reference was taken.
    Every scroll drops the table's cells; the table, its rows and its
    scrollbar stop working too, until the script finds the table again.
    """
    if getattr(obj, "detached", False):
        return True
    return token is not None and reference_token(obj) != token


class TableCell(TextField):
    """One cell of a GuiTableControl. Its text writes through to the table data."""
    sap_type = "GuiTextField"

    def __init__(
        self,
        control_id: str,
        *,
        row: int = 0,
        col: int = 0,
        col_name: str = "",
        table: Optional["TableControl"] = None,
        absolute_row: int = -1,
        **kwargs: Any,
    ) -> None:
        super().__init__(control_id, **kwargs)
        self.row = row                      # visible row, as in the ID
        self.col = col
        self.col_name = col_name
        self.table = table
        self.absolute_row = absolute_row if absolute_row >= 0 else row
        self.detached = False

    @property
    def value(self) -> str:
        return self.text

    @value.setter
    def value(self, v: str) -> None:
        old = self.text
        self.text = v
        table = self.table
        if table is not None and 0 <= self.absolute_row < len(table.data):
            table.data[self.absolute_row][self.col] = v
        if old != v:
            self.trigger("change", self, v)
            if table is not None:
                table.trigger("cell_change", table)


class TableCTextCell(TableCell):
    """A table cell with value help (ctxt* IDs)."""
    sap_type = "GuiCTextField"


class TableRow(Control):
    """One row of a GuiTableControl (GuiTableRow), seen through the visible area."""
    sap_type = "GuiTableRow"

    def __init__(self, table: "TableControl", absolute_row: int) -> None:
        visible = absolute_row - table.position
        super().__init__(f"{table.id}/row[{visible}]")
        self.table = table
        self.absolute_row = absolute_row
        self.index = visible

    @property
    def cells(self) -> list["TableCell"]:
        if 0 <= self.index < len(self.table.visible_cells):
            return list(self.table.visible_cells[self.index])
        return []

    @property
    def selected(self) -> bool:
        return self.absolute_row in self.table.selected_rows

    @selected.setter
    def selected(self, on: bool) -> None:
        if on:
            self.table.selected_rows.add(self.absolute_row)
        else:
            self.table.selected_rows.discard(self.absolute_row)
        self.table.trigger("selection", self.table)

    @property
    def selectable(self) -> bool:
        return 0 <= self.absolute_row < self.table.row_count


class Scrollbar:
    """A table's vertical scrollbar (GuiScrollbar). Setting position scrolls."""

    sap_type = "GuiScrollbar"

    def __init__(self, table: "TableControl") -> None:
        self.table = table

    @property
    def id(self) -> str:
        return f"{self.table.id}/vsb"

    @property
    def minimum(self) -> int:
        return 0

    @property
    def maximum(self) -> int:
        return max(0, self.table.row_count - 1)

    @property
    def page_size(self) -> int:
        return self.table.visible_row_count

    @property
    def range(self) -> int:
        return self.maximum - self.minimum

    @property
    def position(self) -> int:
        return self.table.position

    @position.setter
    def position(self, value: int) -> None:
        self.table.scroll_to(value)


class TableControl(Container):
    """Classic ABAP table control (GuiTableControl).

    ``data`` holds every row; only ``visible_row_count`` rows starting at
    ``position`` exist as cell controls. Columns are dicts with ``name`` and
    ``title``, and optionally ``field`` (the ID's field name, default ``name``)
    and ``prefix`` (``txt`` or ``ctxt``, default ``txt``).
    """
    sap_type = "GuiTableControl"

    def __init__(
        self,
        control_id: str,
        *,
        columns: list[dict] | None = None,
        visible_rows: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(control_id, **kwargs)
        self.columns: list[dict] = columns or []   # [{"name": str, "title": str}]
        self.data: list[list[str]] = []
        self.visible_row_count = _visible_rows_for(self.height, visible_rows)
        self.position = 0
        self.generation = 0                        # bumped by every scroll
        self.selected_rows: set[int] = set()
        self.vertical_scrollbar = Scrollbar(self)
        self.visible_cells: list[list[TableCell]] = []
        self._build_cells()

    # ── data ─────────────────────────────────────────────────────────────────

    def add_row(self, values: list[str]) -> None:
        width = max(len(self.columns), len(values))
        self.data.append([str(v) for v in values] + [""] * (width - len(values)))
        if self.position <= len(self.data) - 1 < self.position + self.visible_row_count:
            self._build_cells()

    @property
    def row_count(self) -> int:
        return len(self.data)

    def get_cell_value(self, row: int, col: int) -> str:
        """Text of an absolute row, on screen or not. Engine access, not SAP's API."""
        if 0 <= row < len(self.data) and 0 <= col < len(self.data[row]):
            return self.data[row][col]
        return ""

    # ── visible area ─────────────────────────────────────────────────────────

    def get_cell(self, row: int, col: int) -> Optional[TableCell]:
        """The cell at a visible row (0 = top of the visible area), as GetCell."""
        if 0 <= row < len(self.visible_cells):
            cells = self.visible_cells[row]
            if 0 <= col < len(cells):
                return cells[col]
        return None

    @property
    def rows(self) -> list[TableRow]:
        """The visible rows, as SAP's Rows collection."""
        return [TableRow(self, self.position + r) for r in range(len(self.visible_cells))]

    def get_absolute_row(self, row: int) -> TableRow:
        row = int(row)
        if not 0 <= row < max(self.row_count, self.position + self.visible_row_count):
            raise IndexError(f"Row {row} is out of range")
        return TableRow(self, row)

    def scroll_to(self, position: int) -> None:
        """Set the first visible row. A round trip: earlier references go stale."""
        position = int(position)
        bar = self.vertical_scrollbar
        if not bar.minimum <= position <= bar.maximum:
            raise ValueError(f"Scrollbar position {position} is out of range "
                             f"{bar.minimum}..{bar.maximum}")
        self.position = position
        self.generation += 1
        self._build_cells()
        self.trigger("scroll", self)

    def _column(self, col: int) -> tuple[dict, str, type[TableCell]]:
        spec = self.columns[col] if col < len(self.columns) else {}
        prefix = spec.get("prefix", "txt")
        field = spec.get("field", spec.get("name", str(col)))
        cls = TableCTextCell if prefix == "ctxt" else TableCell
        return spec, f"{prefix}{field}", cls

    def _build_cells(self) -> None:
        for row in self.visible_cells:
            for cell in row:
                cell.detached = True
                if cell.parent is self:
                    self.remove_child(cell)
        self.visible_cells = []
        width = max([len(self.columns)] + [len(r) for r in self.data[:1]])
        for r in range(self.visible_row_count):
            absolute = self.position + r
            values = self.data[absolute] if absolute < len(self.data) else None
            row: list[TableCell] = []
            for c in range(width):
                spec, name, cls = self._column(c)
                cell = cls(
                    f"{self.id}/{name}[{c},{r}]",
                    name=name,
                    row=r, col=c, col_name=spec.get("name", str(c)),
                    table=self, absolute_row=absolute,
                    text=values[c] if values is not None and c < len(values) else "",
                    changeable=self.changeable and values is not None
                    and bool(spec.get("changeable", True)),
                )
                self.add_child(cell)
                row.append(cell)
            self.visible_cells.append(row)
        root = _registry_root(self)
        if root is not None:
            root._reindex(self)  # type: ignore[attr-defined]


def _parse_rows(spec: str) -> set[int]:
    """"0,2-4" -> {0, 2, 3, 4}, the format of GuiGridView.SelectedRows."""
    rows: set[int] = set()
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            low, high = part.split("-", 1)
            rows.update(range(int(low), int(high) + 1))
        else:
            rows.add(int(part))
    return rows


def _format_rows(rows: set[int]) -> str:
    out, ordered = [], sorted(rows)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        out.append(str(ordered[i]) if i == j else f"{ordered[i]}-{ordered[j]}")
        i = j + 1
    return ",".join(out)


class GridView(Container):
    """ALV Grid control (GuiGridView) — modern SAP grid.

    The grid scrolls on the client: ``first_visible_row`` moves without a
    round trip, so references stay valid. With ``lazy_load`` on, a row's
    values are only known once it has been on screen, the way SAP GUI loads
    ALV rows in blocks as you scroll: reading a row never shown returns "".
    """
    sap_type = "GuiGridView"

    def __init__(
        self,
        control_id: str,
        *,
        columns: list[dict] | None = None,
        visible_rows: int = 0,
        lazy_load: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(control_id, **kwargs)
        self.columns: list[dict] = columns or []   # [{"name": str, "title": str}]
        self._rows: list[dict]   = []              # [{"COL1": val, ...}]
        self.visible_row_count = _visible_rows_for(self.height, visible_rows)
        self.lazy_load = lazy_load
        self._first_visible_row = 0
        self._loaded: set[int] = set()
        self.current_cell_row = -1
        self.current_cell_column = ""
        self.selected_rows: set[int] = set()

    def add_row(self, row_dict: dict) -> None:
        self._rows.append(row_dict)
        index = len(self._rows) - 1
        if index < self._first_visible_row + self.visible_row_count:
            self._loaded.add(index)

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def column_order(self) -> list[str]:
        return [c.get("name", "") for c in self.columns]

    def is_loaded(self, row: int) -> bool:
        return not self.lazy_load or row in self._loaded

    def get_cell_value(self, row: int, col_name: str) -> str:
        if 0 <= row < len(self._rows) and self.is_loaded(row):
            return str(self._rows[row].get(col_name, ""))
        return ""

    def check_cell(self, row: int, col_name: str) -> None:
        """Raise, as SAP GUI does, for a row or column the grid doesn't have."""
        if not 0 <= int(row) < len(self._rows):
            raise IndexError(f"Row {row} is out of range 0..{len(self._rows) - 1}")
        if col_name not in self.column_order:
            raise KeyError(f"Column {col_name!r} does not exist")

    @property
    def rows(self) -> list[dict]:
        return list(self._rows)

    # ── scrolling and current cell ───────────────────────────────────────────

    @property
    def first_visible_row(self) -> int:
        return self._first_visible_row

    @first_visible_row.setter
    def first_visible_row(self, row: int) -> None:
        row = int(row)
        if not 0 <= row < max(1, len(self._rows)):
            raise IndexError(f"Row {row} is out of range 0..{len(self._rows) - 1}")
        self._loaded.update(range(row, min(len(self._rows), row + self.visible_row_count)))
        if row != self._first_visible_row:
            self._first_visible_row = row
            self.trigger("scroll", self)

    def set_current_cell(self, row: int, col_name: str) -> None:
        """Move the current cell, scrolling it into view as SAP GUI does."""
        row = int(row)
        self.check_cell(row, col_name)
        self.current_cell_row = row
        self.current_cell_column = col_name
        first = self._first_visible_row
        if not first <= row < first + self.visible_row_count:
            self.first_visible_row = row
        self.trigger("current_cell", self)

    @property
    def selected_rows_text(self) -> str:
        return _format_rows(self.selected_rows)

    @selected_rows_text.setter
    def selected_rows_text(self, spec: str) -> None:
        rows = _parse_rows(spec)
        bad = sorted(r for r in rows if not 0 <= r < len(self._rows))
        if bad:
            raise IndexError(f"Row {bad[0]} is out of range 0..{len(self._rows) - 1}")
        self.selected_rows = rows
        self.trigger("selection", self)
