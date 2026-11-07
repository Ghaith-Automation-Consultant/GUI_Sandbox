# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Widget Factory — maps engine.Control subclasses to PySide6 widgets.

Each factory function:
  1. Creates the Qt widget
  2. Sets objectName to the control's SAP ID (for automation selectors)
  3. Applies SAP-accurate styling
  4. Binds control properties <-> widget state bidirectionally
  5. Positions using the control's absolute coordinates
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QCheckBox as QtCheckBox,
    QRadioButton as QtRadioButton, QComboBox as QtComboBox,
    QGroupBox, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QTableView, QHeaderView, QScrollArea, QFrame, QToolButton,
    QHBoxLayout, QPlainTextEdit,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont

from . import gui_thread
from engine.control import (
    Control, Container,
    TextField, ComboTextField, PasswordField, Label, Button,
    RadioButton, CheckBox, ComboBox, CommandField, StatusBar,
    UserArea, Menubar, Menu, MenuItem, Toolbar, Titlebar,
    TabStrip, Tab, Shell, Splitter as EngineSplitter,
    ScrollContainer, SimpleContainer, Box, Tree,
    TableControl, GridView,
)
from engine.session import Window
from .styles import SAP


def _set_common(widget: QWidget, ctrl: Control) -> None:
    """Apply properties common to all widgets."""
    widget.setObjectName(ctrl.id)
    if ctrl.tooltip:
        widget.setToolTip(ctrl.tooltip)
    widget.setEnabled(ctrl.enabled)
    widget.setVisible(ctrl.visible)
    widget.setProperty("sap_control", ctrl)


def _sync_from_engine(field: QLineEdit, ctrl: Control) -> None:
    """Show the engine value in the widget, on the GUI thread.

    Scripts set values from the COM or HTTP thread, where touching Qt widgets
    is unsafe. The update reads the engine value when it runs, so a later
    change (such as the logon screen clearing the password) is never
    overwritten by an older one.
    """
    def apply() -> None:
        try:
            if field.text() != ctrl.text:
                field.setText(ctrl.text)
        except RuntimeError:
            pass  # The screen was replaced before this change arrived.

    gui_thread.invoker().post(apply)


def _position(widget: QWidget, ctrl: Control, parent: QWidget) -> None:
    """Position widget using absolute coordinates from the SAP capture.
    SAP controls use -1 to mean 'no position data'."""
    if ctrl.left >= 0 and ctrl.top >= 0:
        widget.setParent(parent)
        widget.move(ctrl.left, ctrl.top)
    if ctrl.width > 0 and ctrl.height > 0:
        widget.resize(ctrl.width, ctrl.height)
    elif ctrl.width > 0:
        widget.setFixedWidth(ctrl.width)


# ── Individual widget builders ──────────────────────────────────────────────

def build_label(ctrl: Label, parent: QWidget) -> QLabel:
    w = QLabel(ctrl.text, parent)
    _set_common(w, ctrl)
    w.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    w.setStyleSheet(f"color: {SAP.LABEL_COLOR}; background: transparent;")
    return w


def build_textfield(ctrl: TextField, parent: QWidget) -> QLineEdit:
    w = QLineEdit(ctrl.text, parent)
    _set_common(w, ctrl)
    w.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    w.setReadOnly(not ctrl.changeable)
    if ctrl.max_length > 0:
        w.setMaxLength(ctrl.max_length)

    bg = "white" if ctrl.changeable else SAP.FIELD_READONLY_BG
    border_color = SAP.FIELD_REQUIRED_BORDER if ctrl.required else SAP.FIELD_BORDER
    w.setStyleSheet(f"""
        QLineEdit {{
            background: {bg};
            border: 1px solid {border_color};
            padding: 1px 3px;
            color: {SAP.FIELD_TEXT_COLOR};
        }}
        QLineEdit:focus {{
            border: 1px solid {SAP.FIELD_FOCUS_BORDER};
        }}
        QLineEdit:read-only {{
            background: {SAP.FIELD_READONLY_BG};
        }}
    """)

    def on_text_changed(text):
        ctrl.value = text

    w.textChanged.connect(on_text_changed)
    w.returnPressed.connect(lambda: _send_enter(ctrl))

    ctrl.on("change", lambda c, new_val: _sync_from_engine(w, ctrl))
    return w


def _send_enter(ctrl: Control) -> None:
    """Enter in a field sends VKey 0 to its window, as in SAP GUI."""
    node = ctrl.parent
    while node is not None:
        if isinstance(node, Window):
            node.send_vkey(0)
            return
        node = node.parent


def build_combo_textfield(ctrl: ComboTextField, parent: QWidget) -> QWidget:
    container = QWidget(parent)
    container.setObjectName(ctrl.id)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    field = QLineEdit(ctrl.text, container)
    field.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    field.setReadOnly(not ctrl.changeable)
    if ctrl.max_length > 0:
        field.setMaxLength(ctrl.max_length)

    bg = "white" if ctrl.changeable else SAP.FIELD_READONLY_BG
    border_color = SAP.FIELD_REQUIRED_BORDER if ctrl.required else SAP.FIELD_BORDER
    field.setStyleSheet(f"""
        QLineEdit {{
            background: {bg};
            border: 1px solid {border_color};
            border-right: none;
            padding: 1px 3px;
            color: {SAP.FIELD_TEXT_COLOR};
        }}
        QLineEdit:focus {{
            border: 1px solid {SAP.FIELD_FOCUS_BORDER};
        }}
    """)

    dropdown = QToolButton(container)
    dropdown.setText("▼")
    dropdown.setFixedSize(18, field.sizeHint().height())
    dropdown.setStyleSheet(f"""
        QToolButton {{
            background: {SAP.TOOLBAR_BG};
            border: 1px solid {SAP.FIELD_BORDER};
            font-size: 8px;
        }}
        QToolButton:hover {{
            background: {SAP.SELECTED_BG};
        }}
    """)

    layout.addWidget(field)
    layout.addWidget(dropdown)
    container.setProperty("sap_control", ctrl)

    def on_text_changed(text):
        ctrl.value = text

    field.textChanged.connect(on_text_changed)
    field.returnPressed.connect(lambda: _send_enter(ctrl))

    ctrl.on("change", lambda c, new_val: _sync_from_engine(field, ctrl))
    return container


def build_password_field(ctrl: PasswordField, parent: QWidget) -> QLineEdit:
    w = build_textfield(ctrl, parent)
    w.setEchoMode(QLineEdit.EchoMode.Password)
    return w


def build_button(ctrl: Button, parent: QWidget) -> QPushButton:
    w = QPushButton(ctrl.text, parent)
    _set_common(w, ctrl)
    w.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    w.setStyleSheet(f"""
        QPushButton {{
            background: {SAP.TOOLBAR_BG};
            border: 1px solid {SAP.BORDER_COLOR};
            padding: 2px 8px;
            color: {SAP.FIELD_TEXT_COLOR};
        }}
        QPushButton:hover {{
            background: {SAP.SELECTED_BG};
        }}
        QPushButton:pressed {{
            background: {SAP.BORDER_COLOR};
        }}
        QPushButton:disabled {{
            color: #999;
        }}
    """)
    w.clicked.connect(lambda: ctrl.press())
    return w


def build_checkbox(ctrl: CheckBox, parent: QWidget) -> QtCheckBox:
    w = QtCheckBox(ctrl.text, parent)
    _set_common(w, ctrl)
    w.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    w.setChecked(ctrl.selected)
    w.setStyleSheet("QCheckBox { background: transparent; }")

    def on_toggled(checked):
        ctrl.selected = checked

    w.toggled.connect(on_toggled)
    return w


def build_radiobutton(ctrl: RadioButton, parent: QWidget) -> QtRadioButton:
    w = QtRadioButton(ctrl.text, parent)
    _set_common(w, ctrl)
    w.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    w.setChecked(ctrl.selected)
    w.setStyleSheet("QRadioButton { background: transparent; }")

    def on_toggled(checked):
        ctrl.selected = checked

    w.toggled.connect(on_toggled)
    return w


def build_combobox(ctrl: ComboBox, parent: QWidget) -> QtComboBox:
    w = QtComboBox(parent)
    _set_common(w, ctrl)
    w.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    w.addItems(ctrl.options)
    if ctrl.text:
        idx = w.findText(ctrl.text)
        if idx >= 0:
            w.setCurrentIndex(idx)
    w.setStyleSheet(f"""
        QComboBox {{
            background: white;
            border: 1px solid {SAP.FIELD_BORDER};
            padding: 1px 3px;
        }}
    """)
    return w


def build_statusbar(ctrl: StatusBar, parent: QWidget) -> QWidget:
    container = QWidget(parent)
    container.setObjectName(ctrl.id)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 2, 4, 2)
    layout.setSpacing(6)

    icon_label = QLabel("", container)
    icon_label.setFixedWidth(16)
    icon_label.setObjectName(f"{ctrl.id}_icon")

    msg_label = QLabel(ctrl.text or "", container)
    msg_label.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    msg_label.setObjectName(f"{ctrl.id}_text")

    layout.addWidget(icon_label)
    layout.addWidget(msg_label, 1)
    container.setProperty("sap_control", ctrl)

    _update_statusbar_style(icon_label, msg_label, ctrl.message_type)
    return container


def _update_statusbar_style(icon: QLabel, msg: QLabel, msg_type: str) -> None:
    colors = {
        "S": ("#2E7D32", "✔"),
        "W": ("#F9A825", "⚠"),
        "E": ("#C62828", "✖"),
        "A": ("#C62828", "✖"),
        "I": ("#1565C0", "ℹ"),
    }
    color, symbol = colors.get(msg_type, ("#333", ""))
    icon.setText(symbol)
    icon.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent;")
    msg.setStyleSheet(f"color: {color}; background: transparent;")


def build_table(ctrl: TableControl, parent: QWidget) -> QTableView:
    model = QStandardItemModel()

    col_names = [c.get("title", c.get("name", f"Col {i}")) for i, c in enumerate(ctrl.columns)]
    model.setHorizontalHeaderLabels(col_names)

    for row in ctrl.rows:
        items = []
        for cell in row.cells:
            item = QStandardItem(cell.text)
            item.setEditable(False)
            items.append(item)
        model.appendRow(items)

    view = QTableView(parent)
    _set_common(view, ctrl)
    view.setModel(model)
    view.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    view.setAlternatingRowColors(True)
    view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
    view.horizontalHeader().setStretchLastSection(True)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    view.verticalHeader().setDefaultSectionSize(22)
    view.verticalHeader().setVisible(False)
    view.setStyleSheet(f"""
        QTableView {{
            background: white;
            gridline-color: {SAP.BORDER_COLOR};
            border: 1px solid {SAP.BORDER_COLOR};
        }}
        QTableView::item:selected {{
            background: {SAP.SELECTED_BG};
            color: black;
        }}
        QHeaderView::section {{
            background: {SAP.TOOLBAR_BG};
            border: 1px solid {SAP.BORDER_COLOR};
            padding: 3px;
            font-weight: bold;
            font-size: {SAP.FONT_SIZE_PX}px;
        }}
    """)
    return view


def build_gridview(ctrl: GridView, parent: QWidget) -> QTableView:
    model = QStandardItemModel()

    col_titles = [c.get("title", c.get("name", "")) for c in ctrl.columns]
    model.setHorizontalHeaderLabels(col_titles)

    for row_data in ctrl.rows:
        items = []
        for col_def in ctrl.columns:
            col_name = col_def.get("name", "")
            val = str(row_data.get(col_name, ""))
            item = QStandardItem(val)
            item.setEditable(False)
            items.append(item)
        model.appendRow(items)

    view = QTableView(parent)
    _set_common(view, ctrl)
    view.setModel(model)
    view.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    view.setAlternatingRowColors(True)
    view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
    view.horizontalHeader().setStretchLastSection(True)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    view.horizontalHeader().setMinimumSectionSize(50)
    view.verticalHeader().setDefaultSectionSize(22)
    view.verticalHeader().setVisible(False)
    view.setStyleSheet(f"""
        QTableView {{
            background: white;
            gridline-color: #C0C0C0;
            border: 1px solid {SAP.BORDER_COLOR};
            alternate-background-color: #F5F8FC;
        }}
        QTableView::item:selected {{
            background: {SAP.SELECTED_BG};
            color: black;
        }}
        QHeaderView::section {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #F0F4FA, stop:1 {SAP.TOOLBAR_BG});
            border: 1px solid {SAP.BORDER_COLOR};
            padding: 3px 6px;
            font-weight: bold;
            font-size: {SAP.FONT_SIZE_PX}px;
        }}
    """)
    return view


def build_tabstrip(ctrl: TabStrip, parent: QWidget) -> QTabWidget:
    tabs = QTabWidget(parent)
    _set_common(tabs, ctrl)
    tabs.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    tabs.setStyleSheet(f"""
        QTabWidget::pane {{
            border: 1px solid {SAP.BORDER_COLOR};
            background: {SAP.PANEL_BG};
        }}
        QTabBar::tab {{
            background: {SAP.TOOLBAR_BG};
            border: 1px solid {SAP.BORDER_COLOR};
            padding: 4px 12px;
            margin-right: 1px;
        }}
        QTabBar::tab:selected {{
            background: {SAP.PANEL_BG};
            border-bottom-color: {SAP.PANEL_BG};
        }}
        QTabBar::tab:hover {{
            background: {SAP.SELECTED_BG};
        }}
    """)

    active_index = 0
    for i, child in enumerate(ctrl.children):
        if isinstance(child, Tab):
            tab_page = QWidget()
            tab_page.setObjectName(child.id)
            _build_children_into(child, tab_page)
            tabs.addTab(tab_page, child.text or child.name or f"Tab {i}")
            if child.selected:
                active_index = i

    tabs.setCurrentIndex(active_index)
    return tabs


def build_box(ctrl: Box, parent: QWidget) -> QGroupBox:
    w = QGroupBox(ctrl.text, parent)
    _set_common(w, ctrl)
    w.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    w.setStyleSheet(f"""
        QGroupBox {{
            border: 1px solid {SAP.BORDER_COLOR};
            margin-top: 12px;
            padding-top: 14px;
            background: transparent;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: {SAP.LABEL_COLOR};
        }}
    """)
    _build_children_into(ctrl, w)
    return w


def build_tree_widget(ctrl: Tree, parent: QWidget) -> QTreeWidget:
    w = QTreeWidget(parent)
    _set_common(w, ctrl)
    w.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
    w.setHeaderHidden(True)
    w.setStyleSheet(f"""
        QTreeWidget {{
            background: white;
            border: 1px solid {SAP.BORDER_COLOR};
        }}
        QTreeWidget::item:selected {{
            background: {SAP.SELECTED_BG};
            color: black;
        }}
        QTreeWidget::item:hover {{
            background: #E0E8F0;
        }}
    """)
    if ctrl.text:
        root = QTreeWidgetItem(w, [ctrl.text])
        root.setExpanded(True)
    return w


def build_container(ctrl: Container, parent: QWidget) -> QWidget:
    w = QWidget(parent)
    _set_common(w, ctrl)
    _build_children_into(ctrl, w)
    return w


def build_scroll_container(ctrl: ScrollContainer, parent: QWidget) -> QScrollArea:
    scroll = QScrollArea(parent)
    _set_common(scroll, ctrl)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    _build_children_into(ctrl, inner)
    scroll.setWidget(inner)
    return scroll


def build_titlebar(ctrl: Titlebar, parent: QWidget) -> QLabel:
    w = QLabel(ctrl.text, parent)
    _set_common(w, ctrl)
    return w


# ── Shell content (ActiveX control placeholders) ──────────────────────────

_SAMPLE_ABAP = """\
*&---------------------------------------------------------------------*
*& Report ZSBX_DEMO
*&---------------------------------------------------------------------*
*& Sandbox demo report: lists flights from the sample table
*&---------------------------------------------------------------------*
REPORT zsbx_demo.

DATA: lt_flights TYPE TABLE OF sflight,
      ls_flight  TYPE sflight.

START-OF-SELECTION.
  SELECT * FROM sflight INTO TABLE lt_flights
    UP TO 500 ROWS.

  LOOP AT lt_flights INTO ls_flight.
    WRITE: / ls_flight-carrid, ls_flight-connid, ls_flight-fldate.
  ENDLOOP.
"""

_SAMPLE_GRID_COLS = ["CARRID", "CONNID", "FLDATE", "PRICE", "CURRENCY"]

_SAMPLE_GRID_ROWS = [
    ["SX", "0101", "20260112", "420.00", "EUR"],
    ["SX", "0101", "20260119", "435.00", "EUR"],
    ["SX", "0205", "20260114", "610.50", "EUR"],
    ["SY", "0310", "20260115", "289.90", "USD"],
    ["SY", "0310", "20260122", "305.00", "USD"],
    ["SY", "0412", "20260118", "780.00", "USD"],
    ["SZ", "0550", "20260120", "198.00", "GBP"],
    ["SZ", "0550", "20260127", "212.50", "GBP"],
]


def _build_shell_content(ctrl: Control, parent: QWidget) -> QWidget | None:
    """Render placeholder content for SAP ActiveX shell controls."""
    shell_type = (ctrl.text or "").lower()

    if "abapeditor" in shell_type or "textedit" in shell_type:
        editor = QPlainTextEdit(parent)
        _set_common(editor, ctrl)
        editor.setFont(QFont("Consolas", SAP.FONT_SIZE))
        editor.setReadOnly(True)
        editor.setPlainText(_SAMPLE_ABAP)
        editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background: white;
                border: 1px solid {SAP.BORDER_COLOR};
                color: #000080;
            }}
        """)
        return editor

    if "gridview" in shell_type:
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(_SAMPLE_GRID_COLS)
        for row_data in _SAMPLE_GRID_ROWS:
            items = []
            for val in row_data:
                item = QStandardItem(val)
                item.setEditable(False)
                items.append(item)
            model.appendRow(items)

        view = QTableView(parent)
        _set_common(view, ctrl)
        view.setModel(model)
        view.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
        view.setAlternatingRowColors(True)
        view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        view.horizontalHeader().setStretchLastSection(True)
        view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        view.horizontalHeader().setMinimumSectionSize(60)
        view.verticalHeader().setDefaultSectionSize(22)
        view.verticalHeader().setVisible(False)
        view.setStyleSheet(f"""
            QTableView {{
                background: white;
                gridline-color: #C0C0C0;
                border: 1px solid {SAP.BORDER_COLOR};
                alternate-background-color: #F5F8FC;
            }}
            QTableView::item:selected {{
                background: {SAP.SELECTED_BG};
                color: black;
            }}
            QHeaderView::section {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F0F4FA, stop:1 {SAP.TOOLBAR_BG});
                border: 1px solid {SAP.BORDER_COLOR};
                padding: 3px 6px;
                font-weight: bold;
                font-size: {SAP.FONT_SIZE_PX}px;
            }}
        """)
        return view

    if "htmlcontrol" in shell_type:
        label = QLabel("", parent)
        _set_common(label, ctrl)
        label.setStyleSheet(f"background: white; border: 1px solid {SAP.BORDER_COLOR};")
        return label

    if "tabletreecontrol" in shell_type or "sapguictrltree" in shell_type:
        tree = QTreeWidget(parent)
        _set_common(tree, ctrl)
        tree.setHeaderHidden(True)
        tree.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
        tree.setStyleSheet(f"""
            QTreeWidget {{
                background: white;
                border: 1px solid {SAP.BORDER_COLOR};
            }}
        """)
        return tree

    return None


# ── Dispatcher ──────────────────────────────────────────────────────────────

_BUILDERS = {
    Label:           build_label,
    TextField:       build_textfield,
    ComboTextField:  build_combo_textfield,
    PasswordField:   build_password_field,
    Button:          build_button,
    CheckBox:        build_checkbox,
    RadioButton:     build_radiobutton,
    ComboBox:        build_combobox,
    StatusBar:       build_statusbar,
    TableControl:    build_table,
    GridView:        build_gridview,
    TabStrip:        build_tabstrip,
    Tab:             build_container,
    Box:             build_box,
    Tree:            build_tree_widget,
    ScrollContainer: build_scroll_container,
    Titlebar:        build_titlebar,
}

# Container types that should recurse into children
_CONTAINER_TYPES = (
    Container, UserArea, Shell, EngineSplitter,
    SimpleContainer,
)


def build_widget(ctrl: Control, parent: QWidget) -> Optional[QWidget]:
    """Build a Qt widget from an engine Control. Returns None for skipped types."""
    # Skip menu/toolbar controls — they're handled separately
    if isinstance(ctrl, (Menubar, Menu, MenuItem, Toolbar, CommandField)):
        return None

    builder = _BUILDERS.get(type(ctrl))
    if builder:
        w = builder(ctrl, parent)
        _position(w, ctrl, parent)
        return w

    if isinstance(ctrl, Shell) and ctrl.text:
        w = _build_shell_content(ctrl, parent)
        if w:
            _position(w, ctrl, parent)
            return w

    if isinstance(ctrl, _CONTAINER_TYPES):
        w = build_container(ctrl, parent)
        _position(w, ctrl, parent)
        return w

    # Fallback for unknown leaf controls: show as a label
    if ctrl.text:
        w = QLabel(ctrl.text, parent)
        _set_common(w, ctrl)
        w.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
        _position(w, ctrl, parent)
        return w

    return None


def _build_children_into(ctrl: Control, parent_widget: QWidget) -> None:
    """Recursively build all children of a control into a parent widget."""
    for child in ctrl.children:
        build_widget(child, parent_widget)
