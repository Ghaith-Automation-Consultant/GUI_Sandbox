# GUI Sandbox: Architecture Specification

This document outlines the architecture for a desktop application that emulates the SAP GUI, focusing on its control hierarchy and scripting interface for automation purposes.

## Table of Contents
1.  [Core Architecture](#1-core-architecture)
2.  [Recommended Technology Stack](#2-recommended-technology-stack)
3.  [Control Model Implementation](#3-control-model-implementation)
4.  [Keyboard & Focus Engine](#4-keyboard--focus-engine)
5.  [Table Control Implementation](#5-table-control-implementation)
6.  [Popup Window System](#6-popup-window-system)
7.  [Status Bar Engine](#7-status-bar-engine)
8.  [Transaction Engine](#8-transaction-engine)
9.  [Automation Interface Strategy](#9-automation-interface-strategy)
10. [Development Phases](#10-development-phases)
11. [MVP Deliverables](#11-mvp-deliverables)

---

## 1. Core Architecture

The system is designed with three distinct internal layers, mirroring core SAP concepts.

### Layer A: Visual Shell
This is the front-end layer that the user interacts with. Its responsibilities are limited to rendering the main UI chrome.
-   **Window Management:** Main application window.
-   **Menus:** Top-level menu bar (e.g., File, Edit, System).
-   **Toolbar:** Main application toolbar with action buttons.
-   **Command Field:** The input field for transaction codes.
-   **Status Bar:** The area at the bottom for displaying system messages.
-   **Container Layout:** The primary area where transaction-specific screens are displayed.

### Layer B: Control Tree Engine (Logical Model)
This is the most critical layer. It defines an internal, hierarchical object model that represents the UI controls, independent of the front-end framework. This abstraction is key to enabling robust scripting.

**Example Hierarchy:**
```
App
 └─ Connection
     └─ Session
         └─ wnd[0] (Main Window)
             └─ usr (User Area)
                 ├─ ctxtKUNNR (GuiTextField)
                 ├─ txtVBELN (GuiTextField)
                 ├─ tblVBAK (GuiTableControl)
                 └─ btnSAVE (GuiButton)
```

**Node Properties:**
Each node in this logical tree must store metadata such as:
-   `id` (e.g., `ctxtKUNNR`)
-   `type` (e.g., `GuiTextField`)
-   `parent` reference
-   `children` list
-   `text` or `value`
-   `state` (e.g., enabled, visible, read-only)
-   `position` (screen coordinates)

### Layer C: Scripting Bridge
This layer exposes the Control Tree Engine to external automation tools (e.g., RPA bots, Python scripts). It provides an API for interacting with the application programmatically.

**Core Functions:**
-   **Element Search:** Find a control by its unique hierarchical ID (e.g., `session.findById("wnd[0]/usr/ctxtKUNNR")`).
-   **Hierarchical Navigation:** Traverse the control tree.
-   **Actions:** Perform operations on controls (e.g., `press`, `setText`, `select`).
-   **Session Management:** Access to the main session object.

**Exposure Options:**
-   **Option 1: COM Interface:** (Windows-only) Provides the most realistic simulation of the actual SAP GUI Scripting Engine.
-   **Option 2: Local HTTP API:** (Cross-platform) Easier to implement and consume from various languages.
    -   `POST /session/find` with `{"id": "wnd[0]/usr/ctxtKUNNR"}`
    -   `POST /session/action` with `{"id": "...", "action": "setText", "value": "1000"}`

---

## 2. Recommended Technology Stack

A desktop application framework with deep control over the widget tree and event handling is required.

**Recommended Choice: Qt (via PySide6 or C++ Qt)**

**Justification:**
-   **Native Widgets:** Provides a look and feel closer to the real SAP GUI compared to web-based frameworks like Electron.
-   **Hierarchy Control:** Allows for the creation and management of a widget tree that can be mapped to the logical `SapControl` tree.
-   **Event System:** Offers fine-grained control over keyboard and focus events, which is critical for realism.
-   **Mature Controls:** Includes robust, native table controls suitable for emulating SAP tables.
-   **Extensibility:** Can be extended to expose a COM interface or a local socket/HTTP server for the scripting bridge.

---

## 3. Control Model Implementation

### Step 1: Define the Base Control Class
All logical controls should inherit from a common base class.

**Pseudo-code:**
```python
class SapControl:
    def __init__(self, id, type, parent):
        self.id = id
        self.type = type
        self.parent = parent
        self.children = []
        self.value = ""
        self.enabled = True
        self.visible = True

    def set_value(self, v):
        self.value = v

    def press(self):
        # Trigger associated action
        pass
```

### Step 2: Map UI Widgets to Logical Controls
A direct mapping must exist between the UI widgets (e.g., Qt) and the logical `SapControl` objects.

**Mapping Examples:**
-   `QLineEdit` → `GuiTextField`
-   `QComboBox` → `GuiComboBox`
-   `QTableView` → `GuiTableControl`
-   `QPushButton` → `GuiButton`

Each UI widget should hold a reference to its corresponding logical control object (e.g., `widget.sap_control_ref`) to keep the two models synchronized.

### Step 3: Implement the Hierarchical ID Resolver
A function is needed to parse an ID path and traverse the logical tree to find the corresponding control.

**Pseudo-code:**
```python
def find_by_id(root_node, path):
    """Finds a control in the tree by its SAP-like ID path."""
    parts = path.split("/")
    current_node = root_node
    for part in parts:
        # This logic needs to handle indices like wnd[0]
        # and find the child with the matching ID part.
        current_node = current_node.find_child_by_id_part(part)
        if not current_node:
            return None
    return current_node
```

---

## 4. Keyboard & Focus Engine
SAP navigation is heavily keyboard-driven. The application must replicate this behavior precisely.
-   **Tab Order:** `Tab` and `Shift+Tab` must cycle through interactive fields in a predefined, stable order.
-   **Enter Key:** Should trigger a validation event or default action for the active control.
-   **Function Keys:** `F8` should execute a common action, `F1` for help, etc.
-   **Escape Key:** `Esc` should close popups or cancel the current action.

This can be achieved by centrally intercepting key events in the main window.

---

## 5. Table Control Implementation
Tables are a complex but essential part of the SAP UI.
-   **Control:** Use a native `QTableView` and wrap it in a custom `GuiTableControl` logical object.
-   **Functionality:** The wrapper must expose high-level automation methods.
-   **API:**
    -   `getCell(row, col)`
    -   `setCell(row, col, value)`
    -   `selectRow(row)`
    -   `getRowCount()`

---

## 6. Popup Window System
Modal dialogs and popups must be handled as separate windows in the control hierarchy (e.g., `wnd[1]`, `wnd[2]`). The engine must:
-   Stack windows and manage their numbering.
-   Enforce modality, blocking interaction with underlying windows.
-   Allow the scripting bridge to find and interact with controls in popups.

---

## 7. Status Bar Engine
The status bar provides critical feedback.
-   A global session method should be available to update it: `session.set_status("Document 12345 saved.", type="success")`.
-   Automation scripts must be able to read the current message and its type (success, warning, error).

---

## 8. Transaction Engine
A simple router to manage which screen to display.
-   The command field input (e.g., "VA01") maps to a specific screen layout.
-   Initially, this can just load a predefined UI file (e.g., `sales_order_screen.ui`).
-   **MVP Transactions:** `VA01` (Sales Order), `ME21N` (Purchase Order), `SE16` (Table Viewer).

---

## 9. Automation Interface Strategy

Three levels of automation interaction are possible:

-   **Level 1: UI Automation (Basic):** Relies on standard OS-level accessibility APIs or image recognition. Stable control IDs and layout make this more reliable than in typical apps.
-   **Level 2: Exposed Scripting API (Recommended):** A custom API (HTTP or otherwise) that allows direct querying and interaction with the logical control tree. This is the primary goal.
-   **Level 3: SAP-like Object Model (Advanced):** Exposing a complete object model (`Application -> Connection -> Session -> findById()`) that perfectly mimics the VBScript/COM engine for maximum compatibility with existing SAP automation scripts.

---

## 10. Development Phases

A realistic, phased approach to development is recommended.

1.  **Phase 1: Shell & Control Tree (2-3 Weeks)**
    -   Implement the main window, menus, toolbar, command field, and status bar.
    -   Build the fundamental internal `SapControl` tree structure.
    -   Establish the mapping between visual widgets and the logical tree.

2.  **Phase 2: Scripting Bridge (1-2 Weeks)**
    -   Implement the `findById` function.
    -   Expose basic actions like `setText`, `press`, and `getText` through the bridge.

3.  **Phase 3: Core Transactions (2 Weeks)**
    -   Build the UI for `VA01`, `ME21N`, and `SE16`.
    -   Implement the popup window system.

4.  **Phase 4: Polish & Realism (1-2 Weeks)**
    -   Implement the detailed keyboard focus and event engine.
    -   Ensure the status bar is fully functional and scriptable.
    -   Refine modality logic.

---

## 11. MVP Deliverables
-   Installable desktop application for Windows.
-   Main SAP-like shell with menu, command field, and status bar.
-   Scriptable control hierarchy mimicking SAP (`wnd[0]/usr/...`).
-   Three functional transaction screens (UI only): `VA01`, `ME21N`, `SE16`.
-   Table, form, and popup controls that behave like their SAP counterparts.
-   Deterministic validation and status messages for reliable automation.
-   A scripting API compatible with Python or RPA tools like UiPath.
-   Realistic keyboard navigation and focus engine.
