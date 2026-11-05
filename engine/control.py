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

    def show(self, message: str, message_type: str = "S") -> None:
        self.text = message
        self.message_type = message_type


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
# ──────────────────────────────────────────────────────────────────────────────

class TableCell(Control):
    """Single cell in a TableControl or GridView."""
    sap_type = "TableCell"

    def __init__(
        self,
        control_id: str,
        *,
        row: int = 0,
        col: int = 0,
        col_name: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(control_id, **kwargs)
        self.row      = row
        self.col      = col
        self.col_name = col_name


class TableRow(Container):
    """One row in a TableControl."""
    sap_type = "TableRow"

    def __init__(self, control_id: str, *, index: int = 0, **kwargs: Any) -> None:
        super().__init__(control_id, **kwargs)
        self.index = index

    @property
    def cells(self) -> list[TableCell]:
        return [c for c in self.children if isinstance(c, TableCell)]


class TableControl(Container):
    """Classic ABAP table control (GuiTableControl)."""
    sap_type = "GuiTableControl"

    def __init__(
        self,
        control_id: str,
        *,
        columns: list[dict] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(control_id, **kwargs)
        self.columns: list[dict] = columns or []   # [{"name": str, "title": str}]
        self.rows: list[TableRow] = []

    def add_row(self, values: list[str]) -> TableRow:
        idx    = len(self.rows)
        row_id = f"{self.id}/row[{idx}]"
        row    = TableRow(row_id, index=idx)
        for i, val in enumerate(values):
            col_name = self.columns[i]["name"] if i < len(self.columns) else str(i)
            cell = TableCell(
                f"{row_id}/cell[{i}]",
                row=idx, col=i, col_name=col_name, text=str(val),
            )
            row.add_child(cell)
        self.rows.append(row)
        self.add_child(row)
        return row

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def get_cell(self, row: int, col: int) -> Optional[TableCell]:
        if 0 <= row < len(self.rows):
            cells = self.rows[row].cells
            if 0 <= col < len(cells):
                return cells[col]
        return None

    def get_cell_value(self, row: int, col: int) -> str:
        cell = self.get_cell(row, col)
        return cell.text if cell else ""


class GridView(Container):
    """ALV Grid control (GuiGridView) — modern SAP grid."""
    sap_type = "GuiGridView"

    def __init__(
        self,
        control_id: str,
        *,
        columns: list[dict] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(control_id, **kwargs)
        self.columns: list[dict] = columns or []   # [{"name": str, "title": str}]
        self._rows: list[dict]   = []              # [{"COL1": val, ...}]

    def add_row(self, row_dict: dict) -> None:
        self._rows.append(row_dict)

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def column_order(self) -> list[str]:
        return [c.get("name", "") for c in self.columns]

    def get_cell_value(self, row: int, col_name: str) -> str:
        if 0 <= row < len(self._rows):
            return str(self._rows[row].get(col_name, ""))
        return ""

    @property
    def rows(self) -> list[dict]:
        return list(self._rows)
