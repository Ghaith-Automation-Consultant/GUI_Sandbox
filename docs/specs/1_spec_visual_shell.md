1. General Requirements

Objective: Provide a fully functional, visually identical GUI Sandbox for testing automation scripts (SAPscript, RPA, etc.) without connecting to any real backend.

Scope:

Visual Layer (UI shell, screens, menus)

Simulated transactions with forms, tables, popups

Command field and toolbar simulation

Fully automatable (supports SAPscript-like scripts or RPA)

Technology stack for MVP:

Python 3.12+

PySide6 (Qt6 bindings for Python)

Optional: QML for rich UI components

SQLite or in-memory JSON for temporary data storage

Python scripting API to simulate transactions and data input

2. Architecture Overview
2.1 Layered Architecture

UI Layer (Qt/PySide6)

SAP GUI shell simulation

Menus, status bar, toolbars

Windows, dialogs, forms, popups

Tables and grids with editable cells

Command field simulation

Controller Layer

Handles user input

Manages screen navigation (transaction flow)

Provides API hooks for automation (scriptable commands)

State management for transactions

Data Layer (Simulated)

Lightweight SQLite or JSON for storing temporary transaction data

Predefined datasets to populate forms and tables

Optional: simulate BAPI responses for advanced automation

3. UI Shell Specification
3.1 Main Window

Title bar: "GUI Sandbox"

Menu bar: replicate SAP standard menus

System, Edit, Goto, Favorites, Extras, Help

Toolbar:

Standard SAP buttons: Enter, Save, Back, Cancel, Exit, Print, Find, First Page, Previous Page, Next Page, Last Page

Status icons

Command field: single-line input

Supports transaction codes (e.g., VA01, ME21N)

Triggers corresponding transaction screens

Status bar: bottom of the window

Displays message area, system info, user info, client

Supports message types: Success, Error, Warning, Info

3.2 Transaction Screen Shell

Layout:

Title/header

Tabs if needed

Forms with labels and fields

Tables (editable/non-editable)

Field types:

Text fields, numeric fields, dropdowns, checkboxes, date pickers

Search helps (simulated popup list selection)

Popups:

Modal windows for alerts, confirmations, value help, selection screens

Fully stylable to match SAP theme

Message area inside screens

Show info/warning/error messages

3.3 Tables

SAP-like ALV grid simulation

Features:

Column headers, sorting, filtering

Row selection, multiple selection

Editable and read-only cells

Support for checkboxes, combo-boxes, hyperlinks

4. Automation / SAPscript Compatibility

Scriptable API Layer:

Each UI component (fields, tables, buttons) exposes an automation ID

Sample API:

sap_ui.find_element("BILL_TO_FIELD").set_text("12345")
sap_ui.find_element("SAVE_BUTTON").click()

Simulated command field execution

Accept transaction codes, trigger screen rendering

Events

Button clicks, field input, table row selection trigger Python events

Logging

All actions logged (timestamp, element, action) to allow automated testing

5. Visual Fidelity Requirements

SAP Blue Crystal theme

Font: SAP UI5 default font (e.g., 72dpi, 10pt)

Colors, icons, and layout match SAP GUI Windows version

Optional: support for scaling (high-DPI displays)

Mouse hover highlights and keyboard navigation

Tooltip support

6. Transaction Flow Simulation

Each transaction is a Python class:

Example:

class VA01Transaction:
    def __init__(self, ui_shell):
        self.ui_shell = ui_shell

    def render_screen(self):
        # Create header fields
        # Create tables
        # Bind buttons to event handlers

Screens can be chained, simulating real SAP navigation

Save/cancel/back buttons trigger events, not actual DB operations

Predefined datasets simulate responses

7. Data Layer Specification

For MVP:

In-memory JSON or SQLite for transaction data

Supports:

Customer master

Material master

Sales order / Purchase order sample tables

Optional import/export of CSV/Excel

Data operations

CRUD operations on tables/forms

Transaction-specific validation (required fields, data type checks)

8. Input Simulation

Keyboard shortcuts:

F1–F12 mapped to SAP actions

Ctrl+F, Ctrl+S, etc.

Mouse support:

Click, double-click, drag & drop (for tables)

Optional: touch support (if using QML)

9. Logging & Debugging

Event log: captures all user interactions

Transaction log: shows screen navigation and actions

Error simulation: allow test errors/messages as in real SAP (e.g., “Material does not exist”)

10. Deployment & Packaging

Standalone desktop app

PyInstaller / Nuitka for building executable

Configurable themes and data sets

Optional: Portable (no installation needed)

Runs on Windows primarily (to match SAP GUI environment)