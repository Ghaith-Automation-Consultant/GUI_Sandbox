# API Reference

This document covers all three scripting interfaces exposed by the GUI Sandbox:
the COM/ROT bridge, the HTTP JSON API, and the in-process Python API.

---

## 1. COM Object Hierarchy

External scripts connect via `GetObject("SAPGUI")`, which returns the ROT entry
point. The object graph mirrors real SAP GUI Scripting:

```
GetObject("SAPGUI")          →  ComSapGui
  .GetScriptingEngine         →  ComApplication
    .Children(0)              →  ComConnection
      .Children(0)            →  ComSession
        .findById(path)       →  ComControl
          .Children           →  ComCollection
        .Info                 →  ComSessionInfo
```

### ComSapGui

| Member                | Kind   | Returns         | Description                              |
|-----------------------|--------|-----------------|------------------------------------------|
| `GetScriptingEngine`  | Method | ComApplication  | Top-level application object             |
| `Id`                  | Prop   | `"SAPGUI"`      | Moniker identifier                       |

### ComApplication

| Member            | Kind     | Returns        | Description                          |
|-------------------|----------|----------------|--------------------------------------|
| `Children`        | Prop     | ComCollection  | Same as `Connections`                |
| `Connections`     | Prop     | ComCollection  | Collection of ComConnection (1 item) |
| `Id`              | Prop     | `"/app"`       | Application path                     |
| `Type`            | Prop     | `"GuiApplication"` |                                 |
| `MajorVersion`    | Prop     | `770`          | SAP GUI version (emulated)           |
| `MinorVersion`    | Prop     | `0`            |                                      |
| `PatchLevel`      | Prop     | `0`            |                                      |
| `Revision`        | Prop     | `0`            |                                      |
| `HistoryEnabled`  | Prop R/W | bool           | Defaults to `True`                   |

### ComConnection

| Member             | Kind | Returns        | Description                        |
|--------------------|------|----------------|------------------------------------|
| `Children`         | Prop | ComCollection  | Same as `Sessions`                 |
| `Sessions`         | Prop | ComCollection  | Collection of ComSession (1 item)  |
| `Id`               | Prop | `"/app/con[0]"`|                                    |
| `Type`             | Prop | `"GuiConnection"` |                                |
| `Description`      | Prop | str            | e.g. `"SIM SBX"`                   |
| `DisabledByServer` | Prop | `False`        | Always false in the sandbox        |

### ComSession

| Member              | Kind   | Returns        | Description                          |
|---------------------|--------|----------------|--------------------------------------|
| `findById(path)`    | Method | ComControl     | Locate a control by SAP ID path      |
| `StartTransaction(tcode)` | Method | —       | Load a transaction's first screen; an unknown code sets a status bar error |
| `sendVKey(key)`     | Method | —              | Send a virtual key to `wnd[0]`       |
| `Info`              | Prop   | ComSessionInfo | Session metadata                     |
| `ActiveWindow`      | Prop   | ComControl     | The active `wnd[0]` control          |
| `Children`          | Prop   | ComCollection  | Top-level controls (windows)         |
| `Id`                | Prop   | str            | e.g. `"/app/con[0]/ses[0]"`          |
| `Type`              | Prop   | `"GuiSession"` |                                      |
| `Name`              | Prop   | `"ses[0]"`     |                                      |
| `Busy`              | Prop   | `False`        | Always false in the sandbox          |

---

## 2. findById()

`findById(path)` is the primary control lookup method. It accepts two path formats:

| Format    | Example                                              | Description                   |
|-----------|------------------------------------------------------|-------------------------------|
| Short     | `wnd[0]/usr/ctxtDATABROWSE-TABLENAME`                | Relative from the session     |
| Full      | `/app/con[0]/ses[0]/wnd[0]/usr/ctxtDATABROWSE-TABLENAME` | Absolute path             |

Both formats resolve to the same control. The engine uses an O(1) dictionary
lookup internally — paths are registered at load time.

### Path segments

| Segment     | Meaning                                  |
|-------------|------------------------------------------|
| `wnd[N]`    | Window — `wnd[0]` main, `wnd[1]+` modals |
| `usr`       | User area (main content)                 |
| `tbar[N]`   | Toolbar — `tbar[0]` main, `tbar[1]` app  |
| `mbar`      | Menu bar                                 |
| `titl`      | Title bar                                |
| `sbar`      | Status bar                               |
| `shellcont` | Shell container                          |
| `shell`     | Shell (tree, ALV grid)                   |
| `tabsN`     | TabStrip                                 |
| `btnX`      | Button                                   |
| `ctxtX`     | Input field with F4 help (CTextField)    |
| `txtX`      | Text field                               |
| `lblX`      | Label                                    |
| `chkX`      | Checkbox                                 |
| `radX`      | Radio button                             |

### Examples

```python
import win32com.client

sap = win32com.client.GetObject("SAPGUI")
session = sap.GetScriptingEngine.Children(0).Children(0)

# Read a field
field = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")
print(field.Text)

# Write a field
field.Text = "SFLIGHT"

# Press Enter
session.findById("wnd[0]").sendVKey(0)

# Navigate the window tree
wnd = session.findById("wnd[0]")
usr = session.findById("wnd[0]/usr")
tbar = session.findById("wnd[0]/tbar[0]")
sbar = session.findById("wnd[0]/sbar")
```

---

## 3. Control Properties

All properties exposed by `ComControl`:

### Identity

| Property       | Type | Access | Description                                    |
|----------------|------|--------|------------------------------------------------|
| `Id`           | str  | R      | Full SAP path, e.g. `/app/con[0]/ses[0]/wnd[0]/usr/ctxtFOO` |
| `Type`         | str  | R      | SAP type name, e.g. `"GuiTextField"`           |
| `TypeAsNumber` | int  | R      | Numeric type code (see section 7)              |
| `Name`         | str  | R      | Short name segment, e.g. `ctxtFOO`             |

### Text / Value

| Property | Type | Access | Description                                |
|----------|------|--------|--------------------------------------------|
| `Text`   | str  | R/W    | Current text or value. Writing fires the `change` event on the underlying control. |

### State

| Property     | Type | Access | Description                              |
|--------------|------|--------|------------------------------------------|
| `Enabled`    | bool | R      | Whether the control accepts interaction  |
| `Changeable` | bool | R      | Whether the value can be modified        |
| `Visible`    | bool | R      | Whether the control is rendered          |
| `Required`   | bool | R      | Whether input is mandatory               |
| `Tooltip`    | str  | R      | Tooltip text                             |
| `DefaultTooltip` | str | R   | Same as `Tooltip`                        |
| `MaxLength`  | int  | R      | Maximum input length (0 = unlimited)     |

### Position / Size

| Property     | Type | Access | Description              |
|--------------|------|--------|--------------------------|
| `Left`       | int  | R      | X offset in pixels       |
| `Top`        | int  | R      | Y offset in pixels       |
| `Width`      | int  | R      | Width in pixels          |
| `Height`     | int  | R      | Height in pixels         |
| `ScreenLeft` | int  | R      | Same as `Left`           |
| `ScreenTop`  | int  | R      | Same as `Top`            |

### Table / Grid (GridView and TableControl only)

| Property          | Type | Access | Description                               |
|-------------------|------|--------|-------------------------------------------|
| `RowCount`        | int  | R      | Total number of rows, on screen or not    |
| `VisibleRowCount` | int  | R      | Rows that fit on screen (from the control's height, or `visible_rows` in the screen JSON) |
| `ColumnCount`     | int  | R      | Number of columns                         |
| `ColumnOrder`     | list | R      | Column order list (GridView only)         |

### Table control scrolling (GuiTableControl)

SAP GUI only sends a table control the rows on screen, and the sandbox does the same:

- **Cells exist for visible rows only.** Their IDs are `<prefix><field>[column,row]`, such as `txtVBAP-POSNR[0,3]` or `ctxtVBAP-MATNR[1,3]`, where `row` counts from the top of the screen. Rows past the end of the data have empty cells that can't be changed.
- **Scrolling is a round trip.** After `VerticalScrollbar.Position` changes, the table, its cells, rows and scrollbar taken before the scroll raise "The control could not be found by id" (`RuntimeError` in-process). Call `findById` again.
- **Edits are kept.** Text written to a cell stays in the table when it scrolls away and back.

| Member                    | Type | Access | Description |
|---------------------------|------|--------|-------------|
| `VerticalScrollbar`       | GuiScrollbar | R | `Position` (R/W), `Minimum` (0), `Maximum` (`RowCount - 1`), `PageSize` (`VisibleRowCount`), `Range` |
| `GetCell(row, col)`       | method | — | The cell at a visible row and a column index. Raises for a row outside the screen. |
| `Rows` / `Rows(i)`        | collection | R | The visible rows (`GuiTableRow`): `Count`, `Item(i)` for a cell, `Selected` (R/W), `Selectable` |
| `GetAbsoluteRow(n)`       | method | — | The `GuiTableRow` at an absolute index, to select rows that are off screen |

### ALV grid scrolling (GuiGridView)

The grid scrolls on the client, so a grid reference stays valid. A grid with `"lazy_load": true` in its screen JSON (the SE16 results) behaves like a large grid in SAP GUI, which loads rows in blocks as you scroll: `GetCellValue` on a row that has never been on screen returns `""`.

| Member                    | Type | Access | Description |
|---------------------------|------|--------|-------------|
| `FirstVisibleRow`         | int  | R/W    | Top row on screen. Setting it scrolls and loads that page. |
| `CurrentCellRow`          | int  | R/W    | Row of the current cell, `-1` if none |
| `CurrentCellColumn`       | str  | R/W    | Column name of the current cell |
| `SetCurrentCell(row, col)`| method | —    | Moves the current cell and scrolls it into view |
| `SelectedRows`            | str  | R/W    | Selected rows, such as `"0,2-4"` |
| `GetCellValue(row, col)`  | method | —    | Absolute row and column name. Raises for an unknown row or column. |

### Selection (CheckBox / RadioButton only)

| Property   | Type | Access | Description                              |
|------------|------|--------|------------------------------------------|
| `Selected` | bool | R      | Whether the control is selected/checked  |

### Status Bar

| Property      | Type | Access | Description                               |
|---------------|------|--------|-------------------------------------------|
| `MessageType` | str  | R      | Message type: `"S"` success, `"W"` warning, `"E"` error, `"A"` abort, `"I"` information. Empty when there is no message, and for other controls. |
| `MessageId`   | str  | R      | Message class, such as `"00"` on a real system. Always empty in the sandbox for now. |
| `MessageNumber` | str | R     | Message number. The sandbox sets `"343"` (transaction does not exist) and `"190"` (password can't be changed); other messages leave it empty. |

```python
sbar = session.findById("wnd[0]/sbar")
if sbar.MessageType == "E":
    print("Error:", sbar.Text)
```

---

## 4. Control Actions

| Method                    | Applies to           | Description                                |
|---------------------------|----------------------|--------------------------------------------|
| `Press()`                 | Button               | Triggers the `press` event                 |
| `Select()`                | Tab, RadioButton     | Triggers the `select` event                |
| `sendVKey(key)`           | Window, any control  | Sends a virtual key. If called on a non-Window control, walks up the tree to find the parent Window. |
| `GetCellValue(row, col)`  | GridView, TableControl | Returns cell text. GridView: absolute row and column name (str). TableControl: visible row and column index (int), a sandbox shortcut for `GetCell(row, col).Text`. |
| `GetCell(row, col)`       | TableControl         | Returns the cell control at a visible row |
| `GetAbsoluteRow(row)`     | TableControl         | Returns the row at an absolute index |
| `SetCurrentCell(row, col)`| GridView             | Moves the current cell and scrolls to it |

### Virtual Key Codes

| Code | Key              |
|------|------------------|
| 0    | Enter            |
| 2    | F2               |
| 3    | F3 (Back)        |
| 4    | F4 (Value Help)  |
| 5    | F5               |
| 6    | F6               |
| 7    | F7               |
| 8    | F8 (Execute)     |
| 9    | F9               |
| 11   | F11 (Save)       |
| 12   | F12 (Cancel)     |
| 14   | Shift+F2         |
| 15   | Shift+F3         |

---

## 5. Session.Info (ComSessionInfo)

Read-only session metadata, accessed via `session.Info`:

| Property              | Type | Description                              |
|-----------------------|------|------------------------------------------|
| `Transaction`         | str  | Current transaction code, e.g. `"SE16"`  |
| `Program`             | str  | Running ABAP program name                |
| `ScreenNumber`        | int  | Dynpro screen number                     |
| `SystemName`          | str  | SAP system ID, e.g. `"SBX"`             |
| `Client`              | str  | SAP client number, e.g. `"200"`          |
| `User`                | str  | Logged-in user, e.g. `"USER_STANDARD"`  |
| `Language`            | str  | Logon language, defaults to `"EN"`       |
| `IsLowSpeedConnection` | bool | Always `False` in the sandbox          |

```python
info = session.Info
print(f"{info.SystemName}/{info.Client} - {info.User}")
print(f"Transaction: {info.Transaction} Screen: {info.ScreenNumber}")
```

---

## 6. Collections (ComCollection)

Collections are returned by `.Children`, `.Connections`, and `.Sessions` properties.

| Member      | Kind     | Description                                     |
|-------------|----------|-------------------------------------------------|
| `Count`     | Property | Number of items. **This is a property, not a method** — use `coll.Count`, not `coll.Count()`. |
| `Item(i)`   | Method   | Returns the item at zero-based index `i`        |
| `coll(i)`   | Default  | Same as `Item(i)` — default item access via DISPID_VALUE |

### Default item access

The sandbox implements DISPID_VALUE (dispatch ID 0) via the `_value_` method
on `ComCollection`. This means `coll(i)` works in both VBScript and Python
COM clients — no need to call `.Item(i)` explicitly.

```python
children = session.findById("wnd[0]").Children
count = children.Count          # property, not method
first = children(0)             # default item access
also_first = children.Item(0)   # explicit — same result
```

```vbscript
Set children = session.findById("wnd[0]").Children
n = children.Count
Set first = children(0)
Set also_first = children.Item(0)
```

---

## 7. SAP Type Numbers

The `TypeAsNumber` property returns a numeric code matching the real SAP GUI
Scripting type identifiers:

| SAP Type              | TypeAsNumber |
|-----------------------|--------------|
| `GuiControl`          | 0            |
| `GuiApplication`      | 10           |
| `GuiConnection`       | 11           |
| `GuiSession`          | 12           |
| `GuiMainWindow`       | 21           |
| `GuiModalWindow`      | 22           |
| `GuiLabel`            | 30           |
| `GuiTextField`        | 31           |
| `GuiCTextField`       | 32           |
| `GuiPasswordField`    | 33           |
| `GuiComboBox`         | 34           |
| `GuiOkCodeField`      | 35           |
| `GuiButton`           | 40           |
| `GuiCheckBox`         | 42           |
| `GuiRadioButton`      | 43           |
| `GuiBox`              | 62           |
| `GuiSimpleContainer`  | 71           |
| `GuiScrollContainer`  | 72           |
| `GuiUserArea`         | 74           |
| `GuiSplitterContainer`| 75           |
| `GuiTableControl`     | 80           |
| `GuiTabStrip`         | 90           |
| `GuiTab`              | 91           |
| `GuiToolbar`          | 101          |
| `GuiTitlebar`         | 102          |
| `GuiStatusbar`        | 103          |
| `GuiMenubar`          | 110          |
| `GuiMenu`             | 111          |
| `GuiMenuItem`         | 112          |
| `GuiShell`            | 122          |
| `GuiTree`             | 200          |
| `GuiGridView`         | 201          |

---

## 8. HTTP API Endpoints

The HTTP bridge runs on `http://127.0.0.1:7654` by default (configurable via
the `port` argument to `start_server()`).

### Read endpoints

| Method | Path        | Response                                       |
|--------|-------------|------------------------------------------------|
| GET    | `/info`     | Session metadata (transaction, user, screen, system, client) |
| GET    | `/tree`     | Full control tree as nested JSON               |
| GET    | `/controls` | Flat list of all controls with properties       |
| GET    | `/log`      | Action recorder entries                        |

### Write endpoints

| Method | Path          | Body                                            | Response              |
|--------|---------------|------------------------------------------------|-----------------------|
| POST   | `/findById`   | `{"path": "wnd[0]/usr/ctxtFOO"}`               | Control JSON          |
| POST   | `/action`     | `{"path": "...", "action": "...", ...}`          | `{"result": ...}`     |
| POST   | `/loadScreen` | `{"file": "screens/02_SE16_initial.json"}`       | Loads a new screen    |

### Supported actions (POST /action)

| Action             | Extra fields          | Description                          |
|--------------------|-----------------------|--------------------------------------|
| `getText`          | —                     | Returns `{"result": "current text"}` |
| `setText`          | `value: "new value"`  | Sets the control's text              |
| `press`            | —                     | Triggers press/click                 |
| `select`           | —                     | Triggers select (tab/radio)          |
| `sendVKey`         | `key: <int>`          | Sends a virtual key                  |
| `getInfo`          | —                     | Full control dict including children |
| `getChildren`      | —                     | List of direct child control dicts   |
| `getCellValue`     | `row: int, col: int\|str` | Cell value (grid: absolute row; table control: visible row) |
| `scroll`           | `value: <int>`        | Table control: `VerticalScrollbar.Position`; grid: `FirstVisibleRow` |
| `setCurrentCell`   | `row: int, col: str`  | Grid current cell                    |
| `setSelectedRows`  | `value: "0,2-4"`      | Grid selected rows                   |
| `selectRow`        | `row: int, value: bool` | Selects an absolute table control row |
| `startTransaction` | `value: "SE16"`       | Navigate to a transaction            |

### Example (curl)

```bash
# Read session info
curl http://127.0.0.1:7654/info

# Find a control
curl -X POST http://127.0.0.1:7654/findById \
  -H "Content-Type: application/json" \
  -d '{"path": "wnd[0]/usr/ctxtDATABROWSE-TABLENAME"}'

# Set a field value
curl -X POST http://127.0.0.1:7654/action \
  -H "Content-Type: application/json" \
  -d '{"path": "wnd[0]/usr/ctxtDATABROWSE-TABLENAME", "action": "setText", "value": "SFLIGHT"}'

# Press Enter
curl -X POST http://127.0.0.1:7654/action \
  -H "Content-Type: application/json" \
  -d '{"path": "wnd[0]", "action": "sendVKey", "key": 0}'
```

---

## 9. In-Process Python API

For scripts running in the same Python process, wrap any `Session` in a
`SandboxSession` for a SAP COM-compatible API without COM overhead.

```python
from bridge import SandboxSession
from engine import load_screen

session = SandboxSession(load_screen("screens/02_SE16_initial.json"))
```

### Dual-case property access

Both PascalCase (SAP COM convention) and snake_case (Pythonic) are supported
on `ControlProxy` objects:

```python
ctrl = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")

# PascalCase (matches SAP COM scripts)
ctrl.Text = "SFLIGHT"
print(ctrl.Text)

# snake_case (Pythonic)
ctrl.text = "SFLIGHT"
print(ctrl.text)
```

### SandboxSession methods

| Method / Property            | Description                             |
|------------------------------|-----------------------------------------|
| `findById(path)`             | Returns a `ControlProxy`                |
| `Info`                       | `SessionInfoProxy` with session metadata|
| `recorder`                   | `ActionRecorder` instance               |
| `recorder.entries()`         | List of recorded action dicts           |
| `recorder.save(path)`        | Persist log to a JSON file              |
| `recorder.filter(action)`    | Filter entries by action name           |

### ControlProxy methods

| Method / Property  | Description                                        |
|--------------------|----------------------------------------------------|
| `.Text` / `.text`  | Read/write the control's text value                |
| `.Id` / `.id`      | Control's SAP path                                 |
| `.Type` / `.type`  | SAP type string                                    |
| `.Name` / `.name`  | Short name segment                                 |
| `.Children`        | `ChildrenCollection` of child `ControlProxy` objects |
| `.Press()` / `.press()` | Trigger press event                           |
| `.Select()` / `.select()` | Trigger select event                       |
| `.sendVKey(key)`   | Send virtual key                                   |
| `.GetCellValue(row, col)` | Cell value (GridView/TableControl)          |
| `.VerticalScrollbar.Position` | Scroll a table control; find the table again afterwards |
| `.FirstVisibleRow` / `.SetCurrentCell(row, col)` / `.SelectedRows` | Scroll and select in an ALV grid |

Member names also ignore case, as in COM: `table.verticalScrollbar.position = 9` works.

### ActionRecorder

Every scripting operation across all three mechanisms (in-process, HTTP, COM)
is logged with:

- UTC ISO-8601 timestamp
- Action name (`findById`, `setText`, `press`, `sendVKey`, etc.)
- Target control path
- Value written or returned

```python
for entry in session.recorder.entries():
    print(f"{entry['timestamp']} {entry['action']} {entry['path']}")

session.recorder.save("session_log.json")
```

### HTTP client (RemoteSession)

`RemoteSession` provides the same API as `SandboxSession` over HTTP:

```python
from bridge import RemoteSession

session = RemoteSession("http://127.0.0.1:7654")
assert session.ping()

session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
session.findById("wnd[0]").sendVKey(0)

# Load a different screen on the server
session.load_screen("screens/03_SE16_SFLIGHT_selection_screen.json")
```
