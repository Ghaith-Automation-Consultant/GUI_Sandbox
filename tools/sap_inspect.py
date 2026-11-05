# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
SAP GUI Screen Inspector — walks the full control tree of the active screen
and exports it as JSON.

Run against a live SAP session:
    python tools/sap_inspect.py
    python tools/sap_inspect.py --transaction SE16 --table MARA
    python tools/sap_inspect.py --out screens/VA01_initial.json
"""

import json
import argparse
import time
from pathlib import Path
from tools.sap_connect import get_session

# SAP control type → friendly name mapping
TYPE_MAP = {
    "GuiTextField":       "TextField",
    "GuiCTextField":      "ComboTextField",
    "GuiPasswordField":   "PasswordField",
    "GuiLabel":           "Label",
    "GuiButton":          "Button",
    "GuiRadioButton":     "RadioButton",
    "GuiCheckBox":        "CheckBox",
    "GuiComboBox":        "ComboBox",
    "GuiTabStrip":        "TabStrip",
    "GuiTab":             "Tab",
    "GuiTableControl":    "TableControl",
    "GuiGridView":        "GridView",
    "GuiStatusbar":       "StatusBar",
    "GuiFrameWindow":     "Window",
    "GuiMainWindow":      "MainWindow",
    "GuiUserArea":        "UserArea",
    "GuiToolbar":         "Toolbar",
    "GuiMenubar":         "Menubar",
    "GuiMenu":            "Menu",
    "GuiMenuItem":        "MenuItem",
    "GuiOkCodeField":     "CommandField",
    "GuiContainerShell":  "ContainerShell",
    "GuiShell":           "Shell",
    "GuiSplitterContainer": "Splitter",
    "GuiScrollContainer": "ScrollContainer",
    "GuiSimpleContainer": "SimpleContainer",
    "GuiBox":             "Box",
    "GuiTitlebar":        "Titlebar",
    "GuiSAPChart":        "Chart",
    "GuiTree":            "Tree",
}

# Properties to extract per control (if they exist)
SCALAR_PROPS = [
    "Id", "Type", "Name", "Text", "Tooltip", "DefaultTooltip",
    "Left", "Top", "Width", "Height",
    "Enabled", "Changeable", "Required",
    "VisibleRowCount", "RowCount", "ColumnCount",
    "MaxLength",
]


def _safe_get(obj, attr):
    try:
        return getattr(obj, attr)
    except Exception:
        return None


def _extract_node(elem, depth=0) -> dict:
    """Recursively extract a GuiComponent into a dict."""
    node = {}

    # Core identity
    node["id"]   = _safe_get(elem, "Id") or ""
    node["type"] = TYPE_MAP.get(_safe_get(elem, "Type") or "", _safe_get(elem, "Type") or "")
    node["name"] = _safe_get(elem, "Name") or ""

    # All available scalar properties
    for prop in SCALAR_PROPS:
        val = _safe_get(elem, prop)
        if val is not None and prop not in ("Id", "Type", "Name"):
            node[prop.lower()] = val

    # Table-specific: extract headers + sample rows
    elem_type = _safe_get(elem, "Type") or ""
    if elem_type == "GuiTableControl":
        node["columns"] = _extract_table_columns(elem)
        node["rows"]    = _extract_table_rows(elem, max_rows=10)

    if elem_type == "GuiGridView":
        node["columns"] = _extract_grid_columns(elem)
        node["rows"]    = _extract_grid_rows(elem, max_rows=10)

    # Recurse into children
    children_obj = _safe_get(elem, "Children")
    if children_obj is not None:
        children = []
        try:
            count = children_obj.Count
            for i in range(count):
                child = children_obj.Item(i)
                children.append(_extract_node(child, depth + 1))
        except Exception:
            pass
        if children:
            node["children"] = children

    return node


def _extract_table_columns(table) -> list:
    cols = []
    try:
        for i in range(table.ColumnCount):
            col = table.Columns.Item(i)
            cols.append({"index": i, "title": _safe_get(col, "Title") or "",
                         "id": _safe_get(col, "Id") or ""})
    except Exception:
        pass
    return cols


def _extract_table_rows(table, max_rows=10) -> list:
    rows = []
    try:
        row_count = min(table.RowCount, max_rows)
        col_count = table.ColumnCount
        for r in range(row_count):
            row = {}
            for c in range(col_count):
                try:
                    cell = table.GetCell(r, c)
                    row[c] = _safe_get(cell, "Text") or ""
                except Exception:
                    row[c] = ""
            rows.append(row)
    except Exception:
        pass
    return rows


def _extract_grid_columns(grid) -> list:
    cols = []
    try:
        titles = grid.ColumnTitles
        col_names = list(grid.ColumnOrder)
        for i, name in enumerate(col_names):
            title = titles.ElementAt(i) if hasattr(titles, "ElementAt") else name
            cols.append({"index": i, "name": name, "title": title})
    except Exception:
        pass
    return cols


def _extract_grid_rows(grid, max_rows=10) -> list:
    rows = []
    try:
        row_count = min(grid.RowCount, max_rows)
        col_names = list(grid.ColumnOrder)
        for r in range(row_count):
            row = {}
            for col in col_names:
                try:
                    row[col] = grid.GetCellValue(r, col)
                except Exception:
                    row[col] = ""
            rows.append(row)
    except Exception:
        pass
    return rows


def inspect_session(session) -> dict:
    """Walk the entire active window and return a structured dict."""
    result = {
        "system":      _safe_get(session.Info, "SystemName"),
        "client":      _safe_get(session.Info, "Client"),
        "user":        _safe_get(session.Info, "User"),
        "transaction": _safe_get(session.Info, "Transaction"),
        "program":     _safe_get(session.Info, "Program"),
        "screen":      _safe_get(session.Info, "ScreenNumber"),
        "status_bar":  {
            "text":       _safe_get(session.findById("wnd[0]/sbar"), "Text"),
            "message_id": _safe_get(session.findById("wnd[0]/sbar"), "MessageId"),
        },
        "windows": [],
    }

    # Inspect all open windows (wnd[0], wnd[1], ...)
    try:
        for i in range(session.Children.Count):
            wnd = session.Children.Item(i)
            result["windows"].append(_extract_node(wnd))
    except Exception as e:
        result["error"] = str(e)

    return result


def run_inspection(out_path: str = None, transaction: str = None,
                   extra_cmds: list = None):
    session = get_session()

    if transaction:
        session.StartTransaction(transaction)
        time.sleep(1)

    if extra_cmds:
        for cmd in extra_cmds:
            exec(cmd)  # e.g. "session.findById('wnd[0]/usr/ctxtDATABROWSE-TABLENAME').text='MARA'"
        time.sleep(0.5)

    data = inspect_session(session)

    out = json.dumps(data, indent=2, ensure_ascii=False)

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(out, encoding="utf-8")
        print(f"[inspect] Saved → {out_path}")
    else:
        print(out)

    return data


def print_tree(node: dict, indent: int = 0):
    """Pretty-print the control tree (id, type, text)."""
    prefix = "  " * indent
    nid   = node.get("id", "?")
    ntype = node.get("type", "")
    ntext = node.get("text", "")
    extra = f'  "{ntext}"' if ntext else ""
    print(f"{prefix}[{ntype}] {nid}{extra}")
    for child in node.get("children", []):
        print_tree(child, indent + 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect the active SAP GUI screen")
    parser.add_argument("--transaction", "-t", help="Navigate to this transaction first")
    parser.add_argument("--out", "-o", help="Save JSON output to this path")
    parser.add_argument("--tree", action="store_true", help="Print control tree to stdout")
    args = parser.parse_args()

    data = run_inspection(out_path=args.out, transaction=args.transaction)

    if args.tree or not args.out:
        for wnd in data.get("windows", []):
            print_tree(wnd)
