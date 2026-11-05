# GUI Sandbox

A standalone Windows desktop application that simulates the SAP GUI scripting environment for RPA development, test automation, and training. It needs no SAP system or SAP software.

The sandbox rebuilds a control tree from JSON screen files and exposes it through the same `GetObject("SAPGUI")` entry point as SAP GUI Scripting, so automation scripts can be developed and tested against it.

> **Disclaimer:** This is an independent project, not affiliated with, endorsed by, or sponsored by SAP SE. See [NOTICE](NOTICE) for trademark details.

## Features

- **14 sample screens**: SE16, SE16N, SE38, SM37, SU01, VA03, and MM03, in English with fictional data
- **COM/ROT bridge**: connect through `GetObject("SAPGUI")` from VBScript, Python, or RPA tools
- **HTTP JSON API**: REST endpoints for cross-process and cross-language automation
- **In-process Python API**: `SandboxSession`, with both PascalCase and snake_case names
- **Action recorder**: logs every `findById`, `setText`, `press`, and `sendVKey` with timestamps
- **Qt UI**: a PySide6 visual shell

## Prerequisites

- Windows 10 or later
- Python 3.10 or later

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

The sandbox opens on the home screen and registers itself in the Windows Running Object Table. You'll see `COM bridge started` in the terminal.

### Connect from a script

```python
import win32com.client

sap = win32com.client.GetObject("SAPGUI")
app = sap.GetScriptingEngine
session = app.Children(0).Children(0)

print(session.Info.Transaction)  # "SESSION_MANAGER"
```

### Run the tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

## Architecture

```
Layer A: Visual Shell      main.py, ui/    PySide6/Qt UI
Layer B: Control Tree      engine/         Session, Window, Controls, findById()
Layer C: Scripting Bridge  bridge/         COM/ROT, HTTP API, in-process Python
```

Layer B is the source of truth. Layer A renders it, and Layer C exposes it to scripts.

## Project Structure

```
├── main.py          # Entry point and Qt main window
├── engine/          # Layer B: control classes, session, JSON loader, transactions
├── bridge/          # Layer C: COM, HTTP, and in-process Python APIs
├── ui/              # Layer A: screen rendering and navigation
├── screens/         # Sample screen JSON files
├── tools/           # Screen capture and diagnostic scripts
├── tests/           # pytest suite
└── docs/            # User, API, and architecture docs; design specs in docs/specs/
```

## Documentation

| Document | Description |
|---|---|
| [User Guide](docs/user_guide.md) | Installation and usage (French) |
| [Technical Documentation](docs/DOCUMENTATION_TECHNIQUE.md) | Architecture, data model, COM bridge (French) |
| [Architecture](docs/architecture.md) | Layer-by-layer design |
| [API Reference](docs/api_reference.md) | COM, HTTP, and Python APIs |

## Adding Screens

The sample screens are defined in `tools/generate_screens.py`, so extend that script and rerun it to add more.

`tools/sap_inspect.py` can also capture screens from a SAP system you are authorised to access. Captures contain system identifiers, usernames, hostnames, and business data, so **never commit a capture or a screenshot of a live system**. `tests/test_screens_sanitized.py` checks for placeholder identities, email addresses, IP addresses, and non-English text, but it cannot detect every kind of sensitive value.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE) for attributions.
