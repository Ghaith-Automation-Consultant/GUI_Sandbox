# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — JSON loader.

Reconstructs a full Control tree from a screen JSON file
(as written by tools/generate_screens.py or tools/sap_inspect.py).

Usage::

    from engine.loader import load_screen
    session = load_screen("screens/02_SE16_initial.json")
    field = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")
    print(field.text)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .control import (
    Control, Container,
    TextField, ComboTextField, PasswordField, Label, Button,
    RadioButton, CheckBox, ComboBox, CommandField, StatusBar,
    UserArea, Menubar, Menu, MenuItem, Toolbar,
    TabStrip, Tab, Shell, Splitter, ScrollContainer, SimpleContainer,
    Box, Titlebar, Tree, Chart,
    TableControl, GridView,
)
from .session import ModalWindow, Session, Window


# SAP COM type string → Python class
_TYPE_MAP: dict[str, type[Control]] = {
    "GuiTextField":         TextField,
    "GuiCTextField":        ComboTextField,
    "GuiPasswordField":     PasswordField,
    "GuiLabel":             Label,
    "GuiButton":            Button,
    "GuiRadioButton":       RadioButton,
    "GuiCheckBox":          CheckBox,
    "GuiComboBox":          ComboBox,
    "GuiOkCodeField":       CommandField,
    "GuiStatusbar":         StatusBar,
    "GuiUserArea":          UserArea,
    "GuiMenubar":           Menubar,
    "GuiMenu":              Menu,
    "GuiMenuItem":          MenuItem,
    "GuiToolbar":           Toolbar,
    "GuiTabStrip":          TabStrip,
    "GuiTab":               Tab,
    "GuiShell":             Shell,
    "GuiContainerShell":    Container,
    "GuiSplitterContainer": Splitter,
    "GuiScrollContainer":   ScrollContainer,
    "GuiSimpleContainer":   SimpleContainer,
    "GuiBox":               Box,
    "GuiTitlebar":          Titlebar,
    "GuiTree":              Tree,
    "GuiSAPChart":          Chart,
    "GuiTableControl":      TableControl,
    "GuiGridView":          GridView,
}


def _coerce_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _build_control(node: dict[str, Any]) -> Control:
    """Recursively build a Control (and its children) from a JSON node."""
    sap_type   = node.get("type", "")
    ctrl_id    = node.get("id", "")
    name       = node.get("name", "") or ""
    text       = node.get("text", "") or ""
    tooltip    = node.get("tooltip", "") or ""
    changeable = bool(node.get("changeable", False))
    required   = bool(node.get("required", False))
    max_length = _coerce_int(node.get("max_len") or node.get("maxlength") or node.get("MaxLength"))
    left       = _coerce_int(node.get("left"))
    top        = _coerce_int(node.get("top"))
    width      = _coerce_int(node.get("width"))
    height     = _coerce_int(node.get("height"))

    common = dict(
        name=name, text=text, tooltip=tooltip,
        changeable=changeable, required=required, max_length=max_length,
        left=left, top=top, width=width, height=height,
    )

    # ── TableControl: use pre-parsed columns / rows if present ───────────────
    if sap_type == "GuiTableControl":
        ctrl = TableControl(ctrl_id, columns=node.get("columns", []),
                            visible_rows=int(node.get("visible_rows", 0)), **common)
        for row_vals in node.get("rows", []):
            # rows may be a list of dicts {0: val, 1: val} or {col: val}
            if isinstance(row_vals, dict):
                row_vals = list(row_vals.values())
            ctrl.add_row([str(v) for v in row_vals])
        # If no rows/columns were pre-parsed, recurse into children normally
        if not node.get("rows") and not node.get("columns"):
            for child_node in node.get("children", []):
                ctrl.add_child(_build_control(child_node))
        return ctrl

    # ── GridView: use pre-parsed columns / rows if present ───────────────────
    if sap_type == "GuiGridView":
        ctrl = GridView(ctrl_id, columns=node.get("columns", []),
                        visible_rows=int(node.get("visible_rows", 0)),
                        lazy_load=bool(node.get("lazy_load", False)), **common)
        for row_dict in node.get("rows", []):
            if isinstance(row_dict, dict):
                ctrl.add_row(row_dict)
        if not node.get("rows") and not node.get("columns"):
            for child_node in node.get("children", []):
                ctrl.add_child(_build_control(child_node))
        return ctrl

    # ── RadioButton / CheckBox: carry selection state ────────────────────────
    if sap_type == "GuiRadioButton":
        ctrl = RadioButton(ctrl_id, selected=bool(node.get("selected", False)), **common)
        return ctrl

    if sap_type == "GuiCheckBox":
        ctrl = CheckBox(ctrl_id, selected=bool(node.get("selected", False)), **common)
        return ctrl

    # ── Tab: carry selection state ────────────────────────────────────────────
    if sap_type == "GuiTab":
        ctrl = Tab(ctrl_id, selected=bool(node.get("selected", False)), **common)
        for child_node in node.get("children", []):
            ctrl.add_child(_build_control(child_node))
        return ctrl

    # ── Generic: look up class, fall back to Container/Control ───────────────
    cls = _TYPE_MAP.get(sap_type)
    if cls is None:
        cls = Container if node.get("children") else Control

    ctrl = cls(ctrl_id, **common)

    for child_node in node.get("children", []):
        ctrl.add_child(_build_control(child_node))

    return ctrl


def _extract_window_index(wnd_id: str) -> int:
    m = re.search(r"wnd\[(\d+)\]", wnd_id)
    return int(m.group(1)) if m else 0


def _attach_window(session: Session, wnd_node: dict[str, Any]) -> Window:
    wnd_id = wnd_node.get("id", "")
    index  = _extract_window_index(wnd_id)

    cls = ModalWindow if wnd_node.get("type") == "GuiModalWindow" else Window
    wnd = cls(
        wnd_id,
        index=index,
        name=wnd_node.get("name", f"wnd[{index}]"),
        text=wnd_node.get("text", ""),
        changeable=bool(wnd_node.get("changeable", True)),
        left=_coerce_int(wnd_node.get("left")),
        top=_coerce_int(wnd_node.get("top")),
        width=_coerce_int(wnd_node.get("width")),
        height=_coerce_int(wnd_node.get("height")),
    )

    for child_node in wnd_node.get("children", []):
        wnd.add_child(_build_control(child_node))

    session.add_window(wnd)
    return wnd


def _populate_session(session: Session, data: dict[str, Any]) -> None:
    """Fill session.info and build the window tree from a parsed JSON dict."""
    session.info.system_name   = data.get("system") or "SIM"
    session.info.client        = data.get("client") or "000"
    session.info.user          = data.get("user") or ""
    session.info.transaction   = data.get("transaction") or ""
    session.info.program       = data.get("program") or ""
    session.info.screen_number = _coerce_int(data.get("screen"))

    tree = data.get("tree", {})
    sap_type = tree.get("type", "")

    if sap_type == "GuiSession":
        # Top level is a session node; its children are windows
        for wnd_node in tree.get("children", []):
            if wnd_node.get("type") in ("GuiMainWindow", "GuiFrameWindow", "GuiModalWindow"):
                _attach_window(session, wnd_node)
    elif sap_type in ("GuiMainWindow", "GuiFrameWindow"):
        _attach_window(session, tree)
    else:
        # Fallback: treat the root as the session node itself
        for child_node in tree.get("children", []):
            ctrl = _build_control(child_node)
            session.add_child(ctrl)
            session._reindex(ctrl)


def load_screen(path: str | Path) -> Session:
    """
    Load a screen JSON file and return a ready-to-use Session.

    All controls are registered so that session.findById() works immediately.

    Example::

        session = load_screen("screens/02_SE16_initial.json")
        field = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")
        print(field.text)        # ""
        field.value = "SFLIGHT"
        session.send_vkey(0)    # Enter
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    session = Session()
    _populate_session(session, data)
    session.source = Path(path).name
    return session


def build_tree(data: dict[str, Any]) -> Session:
    """Like load_screen() but accepts a pre-parsed dict instead of a file path."""
    session = Session()
    _populate_session(session, data)
    return session
