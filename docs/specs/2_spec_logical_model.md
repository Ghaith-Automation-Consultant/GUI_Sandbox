Layer B: Control Tree Engine (Logical Model)
1. Overview

Purpose: Represent all UI elements as hierarchical objects with metadata, properties, events, and relationships.

Goals:

Abstract the UI from the front-end rendering (PySide6/Qt).

Enable automation and scripting without relying on coordinates or platform-specific details.

Support dynamic transactions, popups, tables, and forms with hierarchical relationships.

Track state changes for logging and test validation.

2. Core Concepts
Concept	Description
Control	Base object representing any UI element (field, button, table, etc.).
Container	Control that can hold child controls (e.g., screen, tab, popup, panel).
Leaf Control	Control without children (e.g., text field, checkbox, button).
Properties	Metadata: ID, type, label, value, visibility, enabled/disabled.
Events	Actions like click, change, double-click, enter-key pressed.
Hierarchy / Tree	Each screen or transaction is a tree of containers and leaf controls.
Binding	Links logical control to front-end widget (optional, can be null if only logical simulation).
3. Control Class Specification
3.1 Base Class: Control
class Control:
    def __init__(self, control_id: str, control_type: str, label: str = "", value=None):
        self.control_id = control_id        # Unique identifier
        self.control_type = control_type    # e.g., "Button", "Table", "Field"
        self.label = label                  # Visible label
        self.value = value                  # Current value (if applicable)
        self.enabled = True                 # Is control active
        self.visible = True                 # Is control shown
        self.parent = None                  # Parent control (container)
        self.children = []                  # Child controls if any
        self.events = {}                    # Event handlers: {"click": func, "change": func}

    def add_child(self, child: "Control"):
        child.parent = self
        self.children.append(child)

    def remove_child(self, child: "Control"):
        self.children.remove(child)
        child.parent = None

    def trigger_event(self, event_name: str, *args, **kwargs):
        if event_name in self.events:
            self.events[event_name](*args, **kwargs)
3.2 Container Controls

Containers include:

Screens

Tabs

Popups

Panels

Containers can have any number of child controls, forming the tree structure.

class Container(Control):
    def __init__(self, control_id, label="", children=None):
        super().__init__(control_id, "Container", label)
        if children:
            for child in children:
                self.add_child(child)
3.3 Leaf Controls

Examples: Button, TextField, Checkbox, Dropdown, TableCell.

Each leaf control has:

Value (text, number, selection)

Validation rules (required, type, length)

Events (click, enter, selection changed)

class TextField(Control):
    def __init__(self, control_id, label="", value="", required=False):
        super().__init__(control_id, "TextField", label, value)
        self.required = required
4. Table & Grid Model

ALV-style tables are hierarchical controls: Table → Rows → Cells

Cell Control is a leaf node; Table is a container for rows

class Table(Control):
    def __init__(self, control_id, columns, rows=None):
        super().__init__(control_id, "Table")
        self.columns = columns
        self.rows = rows or []

    def add_row(self, row_values):
        row = [TableCell(f"{self.control_id}_cell_{i}", val) for i, val in enumerate(row_values)]
        self.rows.append(row)
        for cell in row:
            self.add_child(cell)

class TableCell(Control):
    def __init__(self, control_id, value):
        super().__init__(control_id, "TableCell", value=value)
5. Control Tree Operations

Traversal

Depth-first or breadth-first search to locate controls by ID, type, label

def find_control(self, control_id):
    if self.control_id == control_id:
        return self
    for child in self.children:
        found = child.find_control(control_id)
        if found:
            return found
    return None

Property Binding

Read/write values, enable/disable, show/hide independent of UI

Event Dispatching

Trigger events programmatically for automation

Simulate user interactions in a deterministic way

Validation

Before “Save” or “Submit,” traverse tree to check required fields, data types

6. Transaction Example Using Control Tree
class VA01Transaction(Container):
    def __init__(self):
        super().__init__("VA01_screen", "Create Sales Order")

        # Header
        self.add_child(TextField("sold_to_party", "Sold-To Party", required=True))
        self.add_child(TextField("order_type", "Order Type"))

        # Table
        table = Table("item_table", columns=["Material", "Quantity", "Plant"])
        table.add_row(["MAT001", 10, "PL01"])
        table.add_row(["MAT002", 5, "PL01"])
        self.add_child(table)

        # Buttons
        save_button = Control("save_btn", "Button", "Save")
        save_button.events["click"] = self.on_save
        self.add_child(save_button)

    def on_save(self):
        print("Saving transaction…")

This shows how each screen is a tree of controls.

Automation scripts can call:

screen = VA01Transaction()
sold_to = screen.find_control("sold_to_party")
sold_to.value = "12345"
screen.find_control("save_btn").trigger_event("click")
7. Key Benefits

Framework-agnostic: Control tree logic is independent of PySide6 or any other UI toolkit.

Automation-ready: Every control can be accessed programmatically.

Hierarchical structure: Mirrors actual SAP UI screen flow.

Dynamic validation & event handling: Can simulate realistic SAP errors, warnings, and info messages.

Extensible: New transactions or control types can be added by extending base classes.

8. Optional Advanced Features

Control Metadata

help_text, tooltip, visible_condition (dynamic visibility)

Data Binding

Connect control values to in-memory or simulated datasets

Undo/Redo

Maintain a history stack in the tree

Event Propagation

Bubble events from child → parent → container

Virtual Transactions

Dynamically generate screens from JSON or XML definitions