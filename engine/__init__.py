# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — Control Tree Engine.

Public API::

    # Load a sample screen
    from engine import load_screen
    session = load_screen("screens/02_SE16_initial.json")
    field = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")

    # Build a screen programmatically
    from engine.transactions import SE16InitialScreen
    screen = SE16InitialScreen()
    screen.set_field("wnd[0]/usr/ctxtDATABROWSE-TABLENAME", "SFLIGHT")
    screen.send_vkey(0)   # Enter

    # Core control classes
    from engine import Control, Container, TextField, Button, Table, GridView
"""

from .control import (
    Control, Container,
    TextField, ComboTextField, PasswordField, Label, Button,
    RadioButton, CheckBox, ComboBox, CommandField, StatusBar,
    UserArea, Menubar, Menu, MenuItem, Toolbar, TabStrip, Tab,
    Shell, Splitter, ScrollContainer, SimpleContainer, Box,
    Titlebar, Tree, Chart,
    TableCell, TableRow, TableControl, GridView,
)
from .session import Session, Window, SessionInfo, VKEY_LABELS
from .loader import load_screen, build_tree
from .navigation import Navigator

__all__ = [
    # Base
    "Control", "Container",
    # Leaf controls
    "TextField", "ComboTextField", "PasswordField", "Label", "Button",
    "RadioButton", "CheckBox", "ComboBox", "CommandField", "StatusBar",
    # Structural containers
    "UserArea", "Menubar", "Menu", "MenuItem", "Toolbar",
    "TabStrip", "Tab", "Shell", "Splitter", "ScrollContainer",
    "SimpleContainer", "Box", "Titlebar", "Tree", "Chart",
    # Table controls
    "TableCell", "TableRow", "TableControl", "GridView",
    # Session
    "Session", "Window", "SessionInfo", "VKEY_LABELS",
    # Navigation
    "Navigator",
    # Loader
    "load_screen", "build_tree",
]
