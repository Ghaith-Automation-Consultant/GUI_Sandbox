# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the UI layer (widget factory, screen renderer, styles)."""
import pytest
from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QCheckBox as QtCheckBox,
    QRadioButton as QtRadioButton, QComboBox as QtComboBox,
    QGroupBox, QTabWidget, QTreeWidget, QTableView, QScrollArea,
    QPlainTextEdit,
)

from engine.control import (
    Control, Container, TextField, ComboTextField, PasswordField,
    Label, Button, RadioButton, CheckBox, ComboBox, CommandField,
    UserArea, Menubar, Toolbar,
    TabStrip, Tab, Shell, Box, Tree, Titlebar, ScrollContainer,
    TableControl, GridView,
)
from ui.widget_factory import build_widget, _build_children_into
from ui.styles import SAP


# ── Widget Factory ─────────────────────────────────────────────────────────────

class TestBuildWidget:
    """Tests for the widget factory dispatcher."""

    @pytest.fixture
    def parent(self, qapp):
        w = QWidget()
        yield w
        w.deleteLater()

    def test_label(self, parent):
        ctrl = Label("lbl1", text="Description")
        w = build_widget(ctrl, parent)
        assert isinstance(w, QLabel)
        assert w.text() == "Description"
        assert w.objectName() == "lbl1"

    def test_textfield_editable(self, parent):
        ctrl = TextField("fld1", text="hello", changeable=True)
        w = build_widget(ctrl, parent)
        assert isinstance(w, QLineEdit)
        assert w.text() == "hello"
        assert not w.isReadOnly()

    def test_textfield_readonly(self, parent):
        ctrl = TextField("fld2", text="locked", changeable=False)
        w = build_widget(ctrl, parent)
        assert isinstance(w, QLineEdit)
        assert w.isReadOnly()

    def test_textfield_max_length(self, parent):
        ctrl = TextField("fld3", text="", max_length=10, changeable=True)
        w = build_widget(ctrl, parent)
        assert isinstance(w, QLineEdit)
        assert w.maxLength() == 10

    def test_textfield_bidirectional_qt_to_engine(self, parent):
        ctrl = TextField("fld4", text="old", changeable=True)
        w = build_widget(ctrl, parent)
        w.setText("new")
        assert ctrl.value == "new"

    def test_textfield_bidirectional_engine_to_qt(self, parent):
        ctrl = TextField("fld5", text="old", changeable=True)
        w = build_widget(ctrl, parent)
        ctrl.value = "updated"
        assert w.text() == "updated"

    def test_combo_textfield(self, parent):
        ctrl = ComboTextField("ctxt1", text="SFLIGHT", changeable=True)
        w = build_widget(ctrl, parent)
        assert w.objectName() == "ctxt1"
        inner_field = w.findChild(QLineEdit)
        assert inner_field is not None
        assert inner_field.text() == "SFLIGHT"

    def test_password_field(self, parent):
        ctrl = PasswordField("pw1", text="secret", changeable=True)
        w = build_widget(ctrl, parent)
        assert isinstance(w, QLineEdit)
        assert w.echoMode() == QLineEdit.EchoMode.Password

    def test_button(self, parent):
        ctrl = Button("btn1", text="OK")
        w = build_widget(ctrl, parent)
        assert isinstance(w, QPushButton)
        assert w.text() == "OK"

    def test_button_press_triggers_engine(self, parent):
        ctrl = Button("btn2", text="Submit")
        presses = []
        ctrl.on("press", lambda c: presses.append(c.text))
        w = build_widget(ctrl, parent)
        w.click()
        assert presses == ["Submit"]

    def test_checkbox(self, parent):
        ctrl = CheckBox("cb1", text="Active", selected=True)
        w = build_widget(ctrl, parent)
        assert isinstance(w, QtCheckBox)
        assert w.isChecked()

    def test_checkbox_toggle_updates_engine(self, parent):
        ctrl = CheckBox("cb2", text="Flag", selected=False)
        w = build_widget(ctrl, parent)
        w.setChecked(True)
        assert ctrl.selected is True

    def test_radiobutton(self, parent):
        ctrl = RadioButton("rb1", text="Option A", selected=True)
        w = build_widget(ctrl, parent)
        assert isinstance(w, QtRadioButton)
        assert w.isChecked()

    def test_combobox(self, parent):
        ctrl = ComboBox("cbo1", options=["A", "B", "C"], text="B")
        w = build_widget(ctrl, parent)
        assert isinstance(w, QtComboBox)
        assert w.count() == 3
        assert w.currentText() == "B"

    def test_button_disabled(self, parent):
        ctrl = Button("btn3", text="Disabled", enabled=False)
        w = build_widget(ctrl, parent)
        assert not w.isEnabled()

    def test_box_groupbox(self, parent):
        box = Box("box1", text="Group Title")
        box.add_child(Label("lbl_inner", text="Inside"))
        w = build_widget(box, parent)
        assert isinstance(w, QGroupBox)
        assert w.title() == "Group Title"

    def test_tabstrip(self, parent):
        ts = TabStrip("tabs1")
        t1 = Tab("t1", text="Tab 1", selected=True)
        t2 = Tab("t2", text="Tab 2", selected=False)
        t1.add_child(Label("lbl_t1", text="Content 1"))
        ts.add_child(t1)
        ts.add_child(t2)
        w = build_widget(ts, parent)
        assert isinstance(w, QTabWidget)
        assert w.count() == 2
        assert w.currentIndex() == 0

    def test_tree_widget(self, parent):
        ctrl = Tree("tree1", text="Root Node")
        w = build_widget(ctrl, parent)
        assert isinstance(w, QTreeWidget)

    def test_scroll_container(self, parent):
        ctrl = ScrollContainer("scroll1")
        ctrl.add_child(Label("inner_lbl", text="Scrollable"))
        w = build_widget(ctrl, parent)
        assert isinstance(w, QScrollArea)

    def test_titlebar(self, parent):
        ctrl = Titlebar("titl", text="Screen Title")
        w = build_widget(ctrl, parent)
        assert isinstance(w, QLabel)
        assert w.text() == "Screen Title"

    def test_skip_menubar(self, parent):
        ctrl = Menubar("mbar")
        w = build_widget(ctrl, parent)
        assert w is None

    def test_skip_toolbar(self, parent):
        ctrl = Toolbar("tbar")
        w = build_widget(ctrl, parent)
        assert w is None

    def test_skip_command_field(self, parent):
        ctrl = CommandField("okcd")
        w = build_widget(ctrl, parent)
        assert w is None

    def test_container_recurse(self, parent):
        c = Container("cnt1")
        c.add_child(Label("lbl_a", text="A", left=0, top=0, width=50, height=20))
        c.add_child(Label("lbl_b", text="B", left=0, top=25, width=50, height=20))
        w = build_widget(c, parent)
        assert w is not None
        labels = w.findChildren(QLabel)
        assert len(labels) >= 2

    def test_shell_abap_editor(self, parent):
        ctrl = Shell("shell1", text="SAPGUI.AbapEditor.1",
                     left=0, top=0, width=600, height=400)
        w = build_widget(ctrl, parent)
        assert isinstance(w, QPlainTextEdit)
        assert "REPORT" in w.toPlainText()

    def test_shell_gridview(self, parent):
        ctrl = Shell("shell2", text="SAPGUI.GridViewCtrl.1",
                     left=0, top=0, width=600, height=400)
        w = build_widget(ctrl, parent)
        assert isinstance(w, QTableView)
        assert w.model().rowCount() == 8

    def test_shell_unknown_falls_through(self, parent):
        ctrl = Shell("shell3", text="")
        w = build_widget(ctrl, parent)
        assert w is not None  # becomes a container widget

    def test_table_control(self, parent):
        ctrl = TableControl("tbl1", columns=[
            {"name": "A", "title": "Col A"},
            {"name": "B", "title": "Col B"},
        ])
        ctrl.add_row(["val1", "val2"])
        ctrl.add_row(["val3", "val4"])
        w = build_widget(ctrl, parent)
        assert isinstance(w, QTableView)
        assert w.model().rowCount() == 2
        assert w.model().columnCount() == 2

    def test_gridview_widget(self, parent):
        ctrl = GridView("grid1", columns=[
            {"name": "X", "title": "Column X"},
        ])
        ctrl.add_row({"X": "hello"})
        w = build_widget(ctrl, parent)
        assert isinstance(w, QTableView)
        assert w.model().rowCount() == 1

    def test_positioning(self, parent):
        ctrl = Label("pos_lbl", text="Placed", left=50, top=100, width=200, height=30)
        w = build_widget(ctrl, parent)
        assert w.x() == 50
        assert w.y() == 100
        assert w.width() == 200
        assert w.height() == 30

    def test_unknown_leaf_with_text(self, parent):
        ctrl = Control("unknown1", text="Fallback text")
        w = build_widget(ctrl, parent)
        assert isinstance(w, QLabel)
        assert w.text() == "Fallback text"

    def test_unknown_leaf_no_text(self, parent):
        ctrl = Control("unknown2")
        w = build_widget(ctrl, parent)
        assert w is None


class TestBuildChildrenInto:
    """Tests for recursive child building."""

    @pytest.fixture
    def parent(self, qapp):
        w = QWidget()
        yield w
        w.deleteLater()

    def test_builds_all_children(self, parent):
        usr = UserArea("usr")
        usr.add_child(Label("l1", text="A", left=0, top=0, width=50, height=20))
        usr.add_child(TextField("f1", text="B", left=0, top=25, width=100, height=20))
        usr.add_child(Button("b1", text="C", left=0, top=50, width=80, height=25))
        _build_children_into(usr, parent)
        labels = parent.findChildren(QLabel)
        assert len(labels) >= 1
        fields = parent.findChildren(QLineEdit)
        assert len(fields) >= 1
        buttons = parent.findChildren(QPushButton)
        assert len(buttons) >= 1


# ── Styles ─────────────────────────────────────────────────────────────────────

class TestStyles:
    def test_sap_colors_defined(self):
        assert SAP.PANEL_BG.startswith("#")
        assert SAP.TOOLBAR_BG.startswith("#")
        assert SAP.BORDER_COLOR.startswith("#")
        assert SAP.SELECTED_BG.startswith("#")
        assert SAP.BANNER_START.startswith("#")
        assert SAP.BANNER_END.startswith("#")

    def test_sap_font(self):
        assert isinstance(SAP.FONT_FAMILY, str)
        assert SAP.FONT_SIZE > 0

    def test_sap_icons(self):
        assert "save" in SAP.ICONS
        assert "back" in SAP.ICONS
        assert "cancel" in SAP.ICONS
        assert "enter" in SAP.ICONS

    def test_sap_status_colors(self):
        assert SAP.STATUS_SUCCESS.startswith("#")
        assert SAP.STATUS_WARNING.startswith("#")
        assert SAP.STATUS_ERROR.startswith("#")
        assert SAP.STATUS_INFO.startswith("#")
