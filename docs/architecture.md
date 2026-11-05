# GUI Sandbox — Technical Architecture

## 1. Architecture Overview

The sandbox mirrors SAP GUI's internal architecture with three independent layers.
Each layer has no upward dependency: Layer B can run headless, Layer C can expose
a bare Session without any Qt window.

```
┌──────────────────────────────────────────────────────────────────┐
│  External Scripts  (Python, VBScript, UiPath, …)                │
│                                                                  │
│  sap = GetObject("SAPGUI")                                       │
│  session = sap.GetScriptingEngine.Children(0).Children(0)        │
│  session.findById("wnd[0]/usr/ctxtFOO").Text = "SFLIGHT"            │
└─────────────────────────┬────────────────────────────────────────┘
                          │
         ┌────────────────▼────────────────┐
         │     Layer C: Scripting Bridge   │
         │                                 │
         │  COM/ROT ─ HTTP API ─ In-Proc   │
         │  bridge/                        │
         └────────────────┬────────────────┘
                          │  delegates to
         ┌────────────────▼────────────────┐
         │   Layer B: Control Tree Engine  │
         │                                 │
         │  Session ─ Window ─ Controls    │
         │  findById() ─ O(1) registry     │
         │  engine/                        │
         └────────────────┬────────────────┘
                          │  renders
         ┌────────────────▼────────────────┐
         │     Layer A: Visual Shell       │
         │                                 │
         │  PySide6/Qt ─ classic-style UI     │
         │  main.py + ui/                  │
         └─────────────────────────────────┘
```

**Design principle:** Layer B is the source of truth. Layer A renders it visually.
Layer C exposes it to external scripts. All three operate on the same in-memory
control tree.

---

## 2. Layer A — Visual Shell

**Files:** `main.py`, `ui/__init__.py`, `ui/screen_renderer.py`,
`ui/transaction_router.py`, `ui/widget_factory.py`, `ui/styles.py`

### MainWindow (`main.py`)

`MainWindow(QMainWindow)` builds the classic-style window chrome. Six horizontal
zones are stacked top to bottom:

```
┌─────────────────────────────────────────────┐
│  Menu Bar     Menu │ Traiter │ Favoris │ …  │
├─────────────────────────────────────────────┤
│  Main Toolbar  ✓  [command field ▼]  Save   │
├─────────────────────────────────────────────┤
│  Title Banner  GUI Sandbox - User Menu      │  gradient
├─────────────────────────────────────────────┤
│  Context Toolbar  Open │ Create │ Delete    │
├─────────────┬───────────────────────────────┤
│  Nav Tree   │  Workspace Panel              │
│  Favoris    │       (content area)          │
│  Menu SAP   │                               │
├─────────────┴───────────────────────────────┤
│  Status Bar   Ready                         │
└─────────────────────────────────────────────┘
```

Key implementation details:

- `app.setStyle("Fusion")` is called before showing the window — required for the
  SAP color palette to render correctly on Windows.
- Toolbars are **removed from Qt's native toolbar system** and re-parented into a
  `QVBoxLayout`. Without this, Qt may reorder toolbars or let the user drag them.
- Every Qt widget gets a stable `objectName` matching SAP-like IDs (e.g.
  `cmd_field.setObjectName("wnd[0]/tbar[0]/okcd")`). This makes RPA selectors work.

### ScreenRenderer (`ui/screen_renderer.py`)

Renders a full `engine.Session` into the MainWindow's content areas:

1. Populates the menu bar from `mbar` children
2. Rebuilds toolbar buttons from `tbar[0]` and `tbar[1]`
3. Updates the title banner from the `titl` control
4. Renders the user area (`usr`) recursively via the widget factory
5. Updates the status bar from `sbar`

### TransactionRouter (`ui/transaction_router.py`)

Maps SAP transaction codes to screen JSON files and handles navigation via the
command field.

- Supports `/nTCODE`, `/oTCODE`, bare `TCODE`, and `/n` (go home)
- Maintains a `TRANSACTIONS` dict mapping tcodes to lists of screen JSON files
  (multi-step flows: initial → selection → results)
- Wires flow-advance buttons (F7 → content, F8 → execute) and Back (F3) buttons
  to navigate between steps
- Home transaction: `SESSION_MANAGER`

Available transactions: `SESSION_MANAGER`, `SE16`, `SE16N`, `SE38`, `SM37`,
`SU01`, `VA03`, `MM03`.

### WidgetFactory (`ui/widget_factory.py`)

Converts `engine.Control` instances into PySide6 widgets. Each SAP type maps to a
Qt widget constructor. Recursively builds the widget tree for container controls.

### Styles (`ui/styles.py`)

Centralizes the SAP color palette as constants:

| Element            | Hex                    |
|--------------------|------------------------|
| Window / Menu bg   | `#E6EEF7`              |
| Toolbar bg         | `#D5DEE8`              |
| Banner gradient    | `#DCE6F2` → `#B7C9DC`  |
| Panel bg           | `#F4F6F9`              |
| Selected item      | `#C7D6EA`              |
| Borders            | `#9FB2C6`              |

Font: Segoe UI / Arial, 12px for UI chrome, 14px bold for the title banner.

---

## 3. Layer B — Control Tree Engine

**Files:** `engine/__init__.py`, `engine/control.py`, `engine/session.py`,
`engine/loader.py`, `engine/transactions/`

### Control Class Hierarchy (`engine/control.py`)

The base `Control` class holds the properties every SAP element has. Each subclass
sets a `sap_type` class attribute matching the real SAP GUI Scripting COM type name.

```
Control (base)  sap_type="GuiControl"
│
├── Container  "GuiContainerShell"
│   ├── UserArea           "GuiUserArea"
│   ├── Menubar            "GuiMenubar"
│   ├── Menu               "GuiMenu"
│   ├── Toolbar            "GuiToolbar"
│   ├── TabStrip           "GuiTabStrip"     + active_tab property
│   ├── Tab                "GuiTab"          + selected
│   ├── Shell              "GuiShell"
│   ├── Splitter           "GuiSplitterContainer"
│   ├── ScrollContainer    "GuiScrollContainer"
│   ├── SimpleContainer    "GuiSimpleContainer"
│   ├── Box                "GuiBox"
│   ├── TableControl       "GuiTableControl"  (classic ABAP tables)
│   └── GridView           "GuiGridView"      (ALV grids)
│
├── Leaf controls
│   ├── TextField          "GuiTextField"
│   ├── ComboTextField     "GuiCTextField"      (with F4 help)
│   ├── PasswordField      "GuiPasswordField"
│   ├── Label              "GuiLabel"
│   ├── Button             "GuiButton"
│   ├── RadioButton        "GuiRadioButton"     + selected
│   ├── CheckBox           "GuiCheckBox"        + selected
│   ├── ComboBox           "GuiComboBox"        + options
│   ├── CommandField       "GuiOkCodeField"     (transaction field)
│   ├── StatusBar          "GuiStatusbar"       + message_type, show()
│   ├── Titlebar           "GuiTitlebar"
│   ├── MenuItem           "GuiMenuItem"
│   ├── Tree               "GuiTree"
│   └── Chart              "GuiSAPChart"
│
└── Table internals
    ├── TableRow           "TableRow"           + index, cells
    └── TableCell          "TableCell"          + row, col, col_name
```

### Base Control Properties and Methods

**Properties:**

| Property     | Type   | Description                                      |
|-------------|--------|--------------------------------------------------|
| `id`        | str    | Full SAP path, e.g. `/app/con[0]/ses[0]/wnd[0]/usr/ctxtFOO` |
| `name`      | str    | Short name segment, e.g. `ctxtFOO`                |
| `text`      | str    | Current display text / value                      |
| `tooltip`   | str    | Tooltip text                                      |
| `enabled`   | bool   | Whether the control is active                     |
| `changeable`| bool   | Whether the value can be modified                 |
| `visible`   | bool   | Whether the control is rendered                   |
| `required`  | bool   | Whether the field is mandatory                    |
| `max_length`| int    | Maximum input length (0 = unlimited)              |
| `left`, `top`, `width`, `height` | int | Position/size in pixels     |
| `parent`    | Control | Parent in the tree                               |
| `children`  | list   | Direct child controls                             |
| `events`    | dict   | Event handlers: `{"change": fn, "press": fn}`     |

**Methods:**

| Method                    | Description                              |
|--------------------------|------------------------------------------|
| `find_control(id)`       | Depth-first search by full SAP ID path   |
| `all_controls()`         | Flat list of self + all descendants       |
| `value` (property)       | Read/write alias for `text`; setter fires `change` event |
| `press()`                | Trigger the `press` event                |
| `select()`               | Trigger the `select` event               |
| `on(event, handler)`     | Register an event callback               |
| `trigger(event, *args)`  | Fire an event                            |

### Session & Window (`engine/session.py`)

`Session` is the top-level object (mirrors `GuiSession`). It holds:

- `info: SessionInfo` — read-only metadata (system_name, client, user,
  transaction, program, screen_number)
- `_registry: dict[str, Control]` — O(1) lookup index built by `_reindex()`
- Windows as children (instances of `Window`)

**Key methods:**

```python
session = load_screen("screens/02_SE16_initial.json")

# O(1) lookup via internal registry
field = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")

# Both full and short paths work
session.findById("/app/con[0]/ses[0]/wnd[0]/usr/ctxtFOO")   # full
session.findById("wnd[0]/usr/ctxtFOO")                       # short

# VKeys, transactions, status bar
session.send_vkey(0)                   # Enter
session.start_transaction("SE16")
session.set_status("Saved.", "S")
```

`Window` extends `Container` and represents a top-level SAP window (`wnd[0]` is
the main window, `wnd[1..N]` are modal popups). It exposes convenience properties:
`command_field`, `status_bar`, `user_area`, `send_vkey(key)`.

### JSON Loader (`engine/loader.py`)

Reconstructs a full `Session` from a screen JSON file.

- `_TYPE_MAP`: 30+ entries mapping SAP COM type strings to Python classes
- `_build_control(node)`: recursive builder with special handling for:
  - `TableControl`: pre-parsed rows from JSON `rows` field
  - `GridView`: rows as dicts from JSON `rows` field
  - `RadioButton` / `CheckBox` / `Tab`: carry `selected` state
- `_populate_session()`: fills `SessionInfo` and builds the window tree
- Falls back to `Container` for unknown types with children, `Control` otherwise

**Public API:**

```python
from engine import load_screen, build_tree

session = load_screen("screens/02_SE16_initial.json")   # from file
session = build_tree(json_data)                          # from dict
```

### Transaction Screens (`engine/transactions/`)

Hand-authored screen classes that build control trees programmatically:

| File                  | Class                   | Transaction       |
|-----------------------|-------------------------|-------------------|
| `base.py`             | `BaseTransaction`       | (base class)      |
| `se16.py`             | `SE16InitialScreen`     | SE16 initial      |
| `se16.py`             | `SE16SelectionScreen`   | SE16 selection    |
| `se16.py`             | `SE16ResultsScreen`     | SE16 results      |
| `session_manager.py`  | `SessionManagerScreen`  | SESSION_MANAGER   |

`BaseTransaction` provides the standard window chrome (toolbar with command field,
status bar) and convenience methods (`find()`, `set_field()`, `press()`,
`send_vkey()`).

---

## 4. Layer C — Scripting Bridge

**Files:** `bridge/__init__.py`, `bridge/proxy.py`, `bridge/server.py`,
`bridge/client.py`, `bridge/recorder.py`, `bridge/com_server.py`,
`bridge/com_thread.py`

Three complementary mechanisms expose the control tree. All three share the same
`ActionRecorder` for logging.

### 4.1 In-Process Python Proxy (`bridge/proxy.py`)

Wraps any `Session` in a `SandboxSession` (aliased as `SessionProxy`) for a
SAP COM-compatible Python API. Both PascalCase (`.Text`) and snake_case (`.text`)
are supported.

```python
from bridge import SandboxSession
from engine import load_screen

session = SandboxSession(load_screen("screens/02_SE16_initial.json"))

session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
session.findById("wnd[0]").sendVKey(0)
print(session.Info.Transaction)       # "SE16"
print(session.recorder.entries())     # action log
```

Key classes:
- `SessionProxy` (`SandboxSession`) — wraps `Session`
- `ControlProxy` — wraps any `Control`
- `SessionInfoProxy` — wraps `SessionInfo`
- `ChildrenCollection`, `ColumnsCollection`, `ColumnTitlesCollection` — list wrappers

### 4.2 HTTP JSON API (`bridge/server.py`, `bridge/client.py`)

For cross-process / cross-language access.

**Server:**

```python
from bridge import start_server
from engine import load_screen

server = start_server(load_screen("screens/02_SE16_initial.json"), port=7654)
```

**Endpoints:**

| Endpoint       | Method | Description                                      |
|---------------|--------|--------------------------------------------------|
| `/info`       | GET    | Session metadata (transaction, user, screen)      |
| `/tree`       | GET    | Full control tree as nested JSON                  |
| `/controls`   | GET    | Flat list of all controls                         |
| `/log`        | GET    | Action recorder entries                           |
| `/findById`   | POST   | `{"path": "wnd[0]/usr/ctxtFOO"}` → control JSON  |
| `/action`     | POST   | `{"path": "…", "action": "setText", "value": "X"}` |
| `/loadScreen` | POST   | `{"file": "screens/02_SE16_initial.json"}`        |

**Supported actions** (POST `/action`):
`getText`, `setText`, `press`, `select`, `sendVKey`, `getInfo`, `getChildren`,
`getCellValue`, `startTransaction`

**Client:**

```python
from bridge import RemoteSession

session = RemoteSession("http://localhost:7654")
session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
```

### 4.3 COM/ROT Bridge (`bridge/com_server.py`, `bridge/com_thread.py`)

The flagship mechanism. A background STA thread registers COM objects in the
Windows Running Object Table (ROT), so external scripts connect via
`GetObject("SAPGUI")` — exactly how real SAP works.

#### COM Object Hierarchy

```
GetObject("SAPGUI")
  │
  ├── .GetScriptingEngine  →  ComApplication
  │     ├── .Children(0)   →  ComConnection
  │     │     └── .Children(0)  →  ComSession
  │     │           ├── .findById(path)  →  ComControl
  │     │           │     ├── .Text  (read/write)
  │     │           │     ├── .Press()
  │     │           │     ├── .sendVKey(key)
  │     │           │     ├── .Children  →  ComCollection
  │     │           │     └── .Id, .Type, .Name, .Enabled, …
  │     │           ├── .Info  →  ComSessionInfo
  │     │           │     └── .Transaction, .User, .SystemName, …
  │     │           ├── .ActiveWindow  →  ComControl
  │     │           └── .sendVKey(key)
  │     ├── .Connections   →  ComCollection
  │     └── .MajorVersion, .MinorVersion, …
  └── .Id  →  "SAPGUI"
```

#### COM Wrapper Classes (`bridge/com_server.py`)

Each class declares `_public_methods_`, `_public_attrs_`, and `_readonly_attrs_`
for pywin32's `DesignatedWrapPolicy`.

| Class            | Wraps              | Key Members                              |
|------------------|--------------------|------------------------------------------|
| `ComSapGui`      | ROT entry point    | `GetScriptingEngine()` → `ComApplication`|
| `ComApplication` | Application root   | `Children`/`Connections`, version props   |
| `ComConnection`  | SAP connection     | `Children`/`Sessions`, `Description`      |
| `ComSession`     | `Session`          | `findById()`, `sendVKey()`, `Info`, `ActiveWindow` |
| `ComControl`     | Any `Control`      | All SAP properties + `Press()`, `Select()`, `Children` |
| `ComSessionInfo` | `SessionInfo`      | `Transaction`, `User`, `SystemName`, etc. |
| `ComCollection`  | Indexed list       | `Count`, `Item(i)`, default item access   |

#### DISPID_VALUE and `_value_`

`ComCollection` supports default-index access (`coll(0)` in VBScript/Python)
through the `_value_` method. pywin32's `DesignatedWrapPolicy` maps
`DISPID_VALUE` (dispatch ID 0) to `_value_` via its `_dispid_to_get_` table.

```python
class ComCollection:
    _public_methods_ = ["Item"]
    _public_attrs_ = ["Count"]
    _readonly_attrs_ = ["Count"]

    def _value_(self, index: int) -> Any:
        return self._items[int(index)]

    @property
    def Count(self) -> int:
        return len(self._items)
```

`_com_default_method_` is **not** supported by pywin32 — only `_value_` works for
DISPID_VALUE dispatch.

#### `_wrap()` Helper

All COM objects returned to clients are wrapped with
`win32com.server.util.wrap(obj)`, which produces an `IDispatch` pointer suitable
for cross-process COM calls.

#### `SessionHolder` — Thread Safety

`SessionHolder` guards the active `Session` reference with a `threading.Lock()`,
allowing `ComBridge.update_session()` to swap the exposed session safely from the
main thread while the COM STA thread serves requests.

#### STA Thread Lifecycle (`bridge/com_thread.py`)

`ComBridge` manages the COM server lifecycle:

1. **`start()`** spawns a daemon thread (`COM-STA`) that calls
   `pythoncom.CoInitialize()` (Single-Threaded Apartment).
2. Creates a `ComSapGui` instance, wraps it, and registers it in the ROT via
   `pythoncom.CreateFileMoniker(name)` for two monikers: `"SAPGUI"` and
   `"SAPGUISERVER"`.
3. Enters a message pump loop using Win32 events:

```python
while WaitForSingleObject(stop_handle, 0) != WAIT_OBJECT_0:
    pythoncom.PumpWaitingMessages()
    MsgWaitForMultipleObjects([stop_handle], False, 50, QS_ALLINPUT)
```

This pumps COM messages every 50ms while simultaneously watching a stop event.
The `MsgWaitForMultipleObjects` pattern is more responsive than
`sleep()`-based polling and ensures cross-process COM calls are dispatched
promptly (~3ms per call).

4. **`stop()`** signals the stop event via `win32event.SetEvent()`, the thread
   revokes from the ROT and calls `CoUninitialize()`.

#### ROT Registration

Two file monikers are registered so that both standard scripting tools (which use
`GetObject("SAPGUI")`) and tracker tools (which use `GetObject("SAPGUISERVER")`)
can discover the sandbox.

The `MK_S_MONIKERALREADYREGISTERED` success code (0x000401E7) is handled
gracefully — it means the entry replaced a stale one from a previous crash.

### 4.4 Action Recorder (`bridge/recorder.py`)

Append-only log shared by all three mechanisms. Every scripting operation is
recorded with:
- UTC ISO-8601 timestamp
- Action name (`setText`, `press`, `sendVKey`, etc.)
- Target control path
- Value written or returned

```python
recorder.log("setText", path="wnd[0]/usr/ctxtFOO", value="SFLIGHT")
recorder.entries()                   # list of dicts
recorder.filter("sendVKey")          # filter by action
recorder.save("session_log.json")    # persist to file
```

---

## 5. Screen JSON Format

Screen JSON files in `screens/` are fictional samples generated by
`tools/generate_screens.py`. Each file describes one screen.

### Structure

```json
{
  "_label": "02_SE16_initial",
  "system": "SBX",
  "client": "000",
  "user": "USER_STANDARD",
  "transaction": "SE16",
  "program": "SAPLSETB",
  "screen": 230,
  "status": "",
  "tree": {
    "id": "/app/con[0]/ses[0]",
    "type": "GuiSession",
    "name": "ses[0]",
    "children": [
      {
        "id": "/app/con[0]/ses[0]/wnd[0]",
        "type": "GuiMainWindow",
        "name": "wnd[0]",
        "text": "Data Browser: Initial Screen",
        "changeable": true,
        "left": -9, "top": -9, "width": 1938, "height": 1048,
        "children": [ … ]
      }
    ]
  }
}
```

### Metadata Fields

| Field         | Description                                |
|---------------|--------------------------------------------|
| `_label`      | Human-readable identifier for the screen   |
| `system`      | SAP system ID (SID)                        |
| `client`      | SAP client number                          |
| `user`        | SAP username                               |
| `transaction` | Transaction code                           |
| `program`     | ABAP program name                          |
| `screen`      | Dynpro screen number                       |
| `status`      | Status bar message (if any)                |

### Control Node Fields

| Field        | Type    | Description                              |
|-------------|---------|------------------------------------------|
| `id`        | string  | Full SAP path                            |
| `type`      | string  | SAP COM type name (e.g. `GuiTextField`)  |
| `name`      | string  | Short name segment                       |
| `text`      | string  | Display text / value                     |
| `tooltip`   | string  | Tooltip text                             |
| `changeable`| boolean | Whether the control is editable          |
| `required`  | boolean | Whether the field is mandatory           |
| `max_len`   | integer | Maximum input length                     |
| `left`, `top`, `width`, `height` | integer | Position/size  |
| `children`  | array   | Child control nodes                      |
| `selected`  | boolean | Selection state (radio/checkbox/tab)     |
| `columns`   | array   | Column definitions (table/grid controls) |
| `rows`      | array   | Row data (table/grid controls)           |

### Captured Screens

22 screen files covering 10+ transactions:

| Transaction      | Screens | Description                                   |
|------------------|---------|-----------------------------------------------|
| SESSION_MANAGER  | 1       | Easy Access (main menu)                        |
| SE16             | 3       | Data Browser: initial, selection, results      |
| SE16N            | 2       | General Table Display                          |
| SE38             | 3       | ABAP Editor: initial, source, attributes       |
| SM37             | 1       | Job Overview                                   |
| SU01             | 1       | User Maintenance                               |
| VA03             | 2       | Display Sales Order: initial, overview         |
| MM03             | 1       | Display Material                               |

---

## 6. Testing

**Framework:** pytest

**Run all tests:**

```bash
python -m pytest tests/ -q
```

### Test Files

| File                    | Scope                                     |
|-------------------------|-------------------------------------------|
| `tests/conftest.py`     | Shared fixtures                           |
| `tests/test_engine.py`  | Layer B: control tree, session, loader     |
| `tests/test_ui.py`      | Layer A: Qt widgets, screen renderer       |
| `tests/test_e2e.py`     | End-to-end: JSON → Session → bridge       |
| `tests/test_com_bridge.py` | Layer C: COM wrapper classes            |

### Fixtures (`tests/conftest.py`)

```python
@pytest.fixture(scope="session")
def qapp():
    """Single QApplication for the entire test session."""
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    yield app

@pytest.fixture
def main_window(qapp):
    """Fresh MainWindow for each test."""
    win = MainWindow()
    yield win
    win.close()
    win.deleteLater()
```

The `qapp` fixture is session-scoped to avoid creating multiple `QApplication`
instances (Qt enforces a singleton). `main_window` is function-scoped for test
isolation.

### Additional Test Artifacts

- `tests/test_com_bridge.vbs` — VBScript COM smoke test (run with `cscript`)

---

## 7. Directory Structure

```
gui_sandbox/
├── main.py                          # App entry point + MainWindow (Layer A)
├── requirements.txt                 # PySide6, pywin32, pandas
├── run_sandbox.bat                      # CLI dispatcher for tools
├── .gitignore
│
├── engine/                          # Layer B: Control Tree Engine
│   ├── __init__.py                  # Public exports
│   ├── control.py                   # Control base + 30+ subclasses
│   ├── session.py                   # Session, Window, SessionInfo
│   ├── loader.py                    # JSON → Session reconstruction
│   └── transactions/
│       ├── __init__.py
│       ├── base.py                  # BaseTransaction
│       ├── se16.py                  # SE16 Initial / Selection / Results
│       └── session_manager.py       # SESSION_MANAGER main menu
│
├── ui/                              # Layer A: Dynamic UI rendering
│   ├── __init__.py                  # ScreenRenderer, TransactionRouter
│   ├── screen_renderer.py           # Session → Qt widgets
│   ├── transaction_router.py        # Tcode → screen navigation
│   ├── widget_factory.py            # Control → QWidget mapping
│   └── styles.py                    # SAP color palette constants
│
├── bridge/                          # Layer C: Scripting Bridge
│   ├── __init__.py                  # Public exports (all 3 mechanisms)
│   ├── proxy.py                     # In-process: SandboxSession, ControlProxy
│   ├── server.py                    # HTTP: SandboxServer, REST endpoints
│   ├── client.py                    # HTTP: RemoteSession client
│   ├── recorder.py                  # ActionRecorder (shared logging)
│   ├── com_server.py                # COM: 7 wrapper classes
│   └── com_thread.py                # COM: STA thread, ROT lifecycle
│
├── screens/                         # Generated sample screen JSONs (14 + manifest)
│   ├── _manifest.json               # Screen inventory metadata
│   ├── 01_SESSION_MANAGER.json
│   ├── 02_SE16_initial.json
│   ├── …
│
├── tools/                           # SAP connection & capture scripts
│   ├── sap_connect.py               # COM connection to real SAP
│   ├── sap_inspect.py               # Screen tree walker → JSON
│   ├── sap_scenarios.py             # Multi-screen automated capture
│   ├── sap_launch.py                # SAP Logon launcher
│   ├── generate_screens.py          # Generates the sample screens
│   ├── diag_rot.py                  # ROT diagnostics
│   └── capture_flows.py             # Screenshots of each flow
│
├── tests/                           # pytest test suite
│   ├── conftest.py                  # Shared fixtures (qapp, main_window)
│   ├── test_engine.py               # Layer B tests
│   ├── test_ui.py                   # Layer A tests
│   ├── test_e2e.py                  # End-to-end tests
│   ├── test_com_bridge.py           # Layer C COM tests
│   └── test_com_bridge.vbs          # VBScript COM smoke test
│
├── docs/                            # Documentation
│   ├── architecture.md              # This file
│   ├── user_guide.md                # User guide (French)
│   ├── api_reference.md             # API reference
│   └── project_documentation.html   # Full HTML documentation
│
└── specs/                           # Design specifications
    ├── spec_tech.md                 # High-level architecture
    ├── 1_spec_visual_shell.md       # UI shell spec
    ├── 2_spec_logical_model.md      # Control Tree class design
    └── UI_detailed.md               # Pixel-level layout & colors
```

---

## 8. SAP Type Number Map

The `_SAP_TYPE_NUMBERS` dict in `bridge/com_server.py` maps SAP COM type names to
their numeric type codes (used by `TypeAsNumber` property):

| Type                    | Number |
|------------------------|--------|
| GuiApplication          | 10     |
| GuiConnection           | 11     |
| GuiSession              | 12     |
| GuiMainWindow           | 21     |
| GuiModalWindow          | 22     |
| GuiLabel                | 30     |
| GuiTextField            | 31     |
| GuiCTextField           | 32     |
| GuiPasswordField        | 33     |
| GuiComboBox             | 34     |
| GuiOkCodeField          | 35     |
| GuiButton               | 40     |
| GuiCheckBox             | 42     |
| GuiRadioButton          | 43     |
| GuiBox                  | 62     |
| GuiSimpleContainer      | 71     |
| GuiScrollContainer      | 72     |
| GuiUserArea             | 74     |
| GuiSplitterContainer    | 75     |
| GuiTableControl         | 80     |
| GuiTabStrip             | 90     |
| GuiTab                  | 91     |
| GuiToolbar              | 101    |
| GuiTitlebar             | 102    |
| GuiStatusbar            | 103    |
| GuiMenubar              | 110    |
| GuiMenu                 | 111    |
| GuiMenuItem             | 112    |
| GuiShell                | 122    |
| GuiTree                 | 200    |
| GuiGridView             | 201    |
| GuiControl              | 0      |
