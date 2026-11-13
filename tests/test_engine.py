# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the engine layer (control, session, loader)."""
import pytest
from pathlib import Path

from engine.control import (
    Control, Container, TextField, ComboTextField, PasswordField,
    Label, Button, RadioButton, CheckBox, ComboBox, CommandField,
    StatusBar, UserArea, Menubar, TabStrip, Tab, Box, TableControl, GridView,
)
from engine.session import Session, Window
from engine.loader import load_screen, build_tree, _build_control


SCREENS_DIR = Path(__file__).resolve().parent.parent / "screens"


# ── Control basics ────────────────────────────────────────────────────────────

class TestControl:
    def test_init_defaults(self):
        c = Control("id1")
        assert c.id == "id1"
        assert c.text == ""
        assert c.enabled is True
        assert c.visible is True
        assert c.changeable is True
        assert c.children == []
        assert c.parent is None

    def test_init_kwargs(self):
        c = Control("id2", name="foo", text="bar", tooltip="tip",
                     enabled=False, visible=False, left=10, top=20,
                     width=100, height=50, required=True, max_length=40)
        assert c.name == "foo"
        assert c.text == "bar"
        assert c.tooltip == "tip"
        assert c.enabled is False
        assert c.left == 10
        assert c.width == 100
        assert c.required is True
        assert c.max_length == 40

    def test_add_remove_child(self):
        parent = Container("p")
        child = Control("c")
        parent.add_child(child)
        assert child in parent.children
        assert child.parent is parent
        parent.remove_child(child)
        assert child not in parent.children
        assert child.parent is None

    def test_find_control_depth_first(self):
        root = Container("root")
        a = Container("a")
        b = Control("b")
        c = Control("c")
        root.add_child(a)
        a.add_child(b)
        root.add_child(c)
        assert root.find_control("b") is b
        assert root.find_control("c") is c
        assert root.find_control("missing") is None

    def test_all_controls(self):
        root = Container("root")
        a = Control("a")
        b = Control("b")
        root.add_child(a)
        root.add_child(b)
        all_c = root.all_controls()
        assert len(all_c) == 3
        assert all_c[0] is root
        assert a in all_c
        assert b in all_c


class TestEvents:
    def test_on_and_trigger(self):
        c = Control("c")
        result = []
        c.on("test", lambda *args: result.append(args))
        c.trigger("test", "x", "y")
        assert result == [("x", "y")]

    def test_handler_replaced_not_appended(self):
        c = Control("c")
        calls = []
        c.on("e", lambda: calls.append("first"))
        c.on("e", lambda: calls.append("second"))
        c.trigger("e")
        assert calls == ["second"]

    def test_trigger_no_handler(self):
        c = Control("c")
        assert c.trigger("missing") is None


class TestValue:
    def test_value_getter(self):
        c = Control("c", text="hello")
        assert c.value == "hello"

    def test_value_setter_fires_change(self):
        c = Control("c", text="old")
        changes = []
        c.on("change", lambda ctrl, val: changes.append(val))
        c.value = "new"
        assert c.text == "new"
        assert changes == ["new"]

    def test_value_setter_no_event_if_same(self):
        c = Control("c", text="same")
        changes = []
        c.on("change", lambda ctrl, val: changes.append(val))
        c.value = "same"
        assert changes == []


class TestPress:
    def test_button_press(self):
        b = Button("btn1", text="OK")
        presses = []
        b.on("press", lambda ctrl: presses.append(ctrl.text))
        b.press()
        assert presses == ["OK"]


# ── Typed controls ────────────────────────────────────────────────────────────

class TestTypedControls:
    def test_radio_button(self):
        r = RadioButton("r1", selected=True, text="Option A")
        assert r.selected is True
        assert r.sap_type == "GuiRadioButton"

    def test_checkbox(self):
        cb = CheckBox("cb1", selected=False, text="Active")
        assert cb.selected is False
        cb.selected = True
        assert cb.selected is True

    def test_combobox(self):
        c = ComboBox("combo", options=["A", "B", "C"])
        assert c.options == ["A", "B", "C"]

    def test_password_field(self):
        p = PasswordField("pw", text="secret")
        assert p.sap_type == "GuiPasswordField"
        assert p.text == "secret"

    def test_statusbar(self):
        s = StatusBar("sbar")
        s.show("Success message", "S")
        assert s.text == "Success message"
        assert s.message_type == "S"

    def test_tabstrip_active_tab(self):
        ts = TabStrip("tabs")
        t1 = Tab("t1", text="Tab 1", selected=False)
        t2 = Tab("t2", text="Tab 2", selected=True)
        ts.add_child(t1)
        ts.add_child(t2)
        assert ts.active_tab is t2


# ── TableControl ──────────────────────────────────────────────────────────────

class TestTableControl:
    def test_add_row(self):
        t = TableControl("tbl", columns=[{"name": "A"}, {"name": "B"}])
        t.add_row(["val1", "val2"])
        assert t.row_count == 1
        assert t.get_cell_value(0, 0) == "val1"
        assert t.get_cell_value(0, 1) == "val2"

    def test_get_cell_out_of_range(self):
        t = TableControl("tbl", columns=[{"name": "X"}], visible_rows=3)
        assert t.get_cell(0, 0).text == ""          # empty rows still have cells, as in SAP
        assert not t.get_cell(0, 0).changeable
        assert t.get_cell(3, 0) is None              # below the visible area
        assert t.get_cell_value(5, 5) == ""

    def test_multiple_rows(self):
        t = TableControl("tbl", columns=[{"name": "N"}])
        t.add_row(["r0"])
        t.add_row(["r1"])
        t.add_row(["r2"])
        assert t.row_count == 3
        assert t.get_cell_value(2, 0) == "r2"


class TestGridView:
    def test_add_row(self):
        g = GridView("grid", columns=[{"name": "COL1", "title": "Column 1"}])
        g.add_row({"COL1": "hello"})
        assert g.row_count == 1
        assert g.get_cell_value(0, "COL1") == "hello"

    def test_column_order(self):
        g = GridView("grid", columns=[{"name": "A"}, {"name": "B"}, {"name": "C"}])
        assert g.column_order == ["A", "B", "C"]


# ── Session ───────────────────────────────────────────────────────────────────

class TestSession:
    def test_create_session(self):
        s = Session()
        assert s.info.system_name == "SIM"
        assert s.info.client == "000"

    def test_add_window(self):
        s = Session()
        w = Window("wnd[0]", index=0, text="Main")
        s.add_window(w)
        assert s.get_window(0) is w
        assert s.get_window(1) is None

    def test_close_window(self):
        s = Session()
        w = Window("/app/con[0]/ses[0]/wnd[0]", index=0)
        ctrl = Control("/app/con[0]/ses[0]/wnd[0]/usr/field1")
        w.add_child(ctrl)
        s.add_window(w)
        assert s.findById("wnd[0]/usr/field1") is ctrl
        s.close_window(0)
        assert s.get_window(0) is None
        with pytest.raises(RuntimeError):
            s.findById("wnd[0]/usr/field1")

    def test_find_by_id_full_path(self):
        s = Session()
        w = Window("/app/con[0]/ses[0]/wnd[0]", index=0)
        f = TextField("/app/con[0]/ses[0]/wnd[0]/usr/txtFIELD", text="test")
        w.add_child(f)
        s.add_window(w)
        assert s.findById("/app/con[0]/ses[0]/wnd[0]/usr/txtFIELD") is f

    def test_find_by_id_short_path(self):
        s = Session()
        w = Window("/app/con[0]/ses[0]/wnd[0]", index=0)
        f = TextField("/app/con[0]/ses[0]/wnd[0]/usr/txtFIELD", text="val")
        w.add_child(f)
        s.add_window(w)
        assert s.findById("wnd[0]/usr/txtFIELD") is f

    def test_find_by_id_not_found(self):
        s = Session()
        with pytest.raises(RuntimeError, match="Control not found"):
            s.findById("wnd[0]/usr/nonexistent")

    def test_active_window(self):
        s = Session()
        w0 = Window("wnd[0]", index=0)
        w1 = Window("wnd[1]", index=1)
        s.add_window(w0)
        s.add_window(w1)
        assert s.active_window is w1

    def test_window_properties(self):
        s = Session()
        w = Window("/app/con[0]/ses[0]/wnd[0]", index=0)
        okcd = CommandField("/app/con[0]/ses[0]/wnd[0]/tbar[0]/okcd")
        sbar = StatusBar("/app/con[0]/ses[0]/wnd[0]/sbar")
        usr = UserArea("/app/con[0]/ses[0]/wnd[0]/usr")
        w.add_child(okcd)
        w.add_child(sbar)
        w.add_child(usr)
        s.add_window(w)
        assert w.command_field is okcd
        assert w.status_bar is sbar
        assert w.user_area is usr

    def test_send_vkey(self):
        s = Session()
        w = Window("/app/con[0]/ses[0]/wnd[0]", index=0)
        s.add_window(w)
        vkeys = []
        w.on("vkey", lambda wnd, key, label: vkeys.append(key))
        s.send_vkey(8)
        assert vkeys == [8]

    def test_set_status(self):
        s = Session()
        w = Window("/app/con[0]/ses[0]/wnd[0]", index=0)
        sbar = StatusBar("/app/con[0]/ses[0]/wnd[0]/sbar")
        w.add_child(sbar)
        s.add_window(w)
        s.set_status("Error occurred", "E")
        assert sbar.text == "Error occurred"
        assert sbar.message_type == "E"


# ── Loader ────────────────────────────────────────────────────────────────────

class TestLoader:
    def test_build_control_textfield(self):
        node = {"id": "f1", "type": "GuiTextField", "name": "FIELD",
                "text": "hello", "changeable": True}
        ctrl = _build_control(node)
        assert isinstance(ctrl, TextField)
        assert ctrl.text == "hello"

    def test_build_control_button(self):
        node = {"id": "b1", "type": "GuiButton", "name": "BTN",
                "text": "Press Me", "tooltip": "Do it (F8)"}
        ctrl = _build_control(node)
        assert isinstance(ctrl, Button)
        assert ctrl.tooltip == "Do it (F8)"

    def test_build_control_checkbox(self):
        node = {"id": "cb1", "type": "GuiCheckBox", "name": "CHK",
                "text": "Active", "selected": True}
        ctrl = _build_control(node)
        assert isinstance(ctrl, CheckBox)
        assert ctrl.selected is True

    def test_build_control_radiobutton(self):
        node = {"id": "rb1", "type": "GuiRadioButton", "name": "RB",
                "text": "Option", "selected": False}
        ctrl = _build_control(node)
        assert isinstance(ctrl, RadioButton)
        assert ctrl.selected is False

    def test_build_control_with_children(self):
        node = {
            "id": "box1", "type": "GuiBox", "name": "GRP", "text": "Group",
            "children": [
                {"id": "lbl", "type": "GuiLabel", "text": "Label"},
                {"id": "fld", "type": "GuiTextField", "text": "Val"},
            ]
        }
        ctrl = _build_control(node)
        assert isinstance(ctrl, Box)
        assert len(ctrl.children) == 2
        assert isinstance(ctrl.children[0], Label)
        assert isinstance(ctrl.children[1], TextField)

    def test_build_control_unknown_type(self):
        node = {"id": "x", "type": "GuiCustomControl", "name": "CUSTOM",
                "children": [{"id": "y", "type": "GuiLabel", "text": "child"}]}
        ctrl = _build_control(node)
        assert isinstance(ctrl, Container)
        assert len(ctrl.children) == 1

    def test_build_control_unknown_leaf(self):
        node = {"id": "x", "type": "GuiStatusPane", "name": "pane"}
        ctrl = _build_control(node)
        assert isinstance(ctrl, Control)

    def test_build_tree(self):
        data = {
            "system": "TST", "client": "100", "user": "ADMIN",
            "transaction": "SE16", "program": "SAPLSETB",
            "tree": {
                "type": "GuiMainWindow",
                "id": "/app/con[0]/ses[0]/wnd[0]",
                "name": "wnd[0]",
                "children": [
                    {"id": "/app/con[0]/ses[0]/wnd[0]/usr",
                     "type": "GuiUserArea", "name": "usr",
                     "children": [
                         {"id": "/app/con[0]/ses[0]/wnd[0]/usr/txtFLD",
                          "type": "GuiTextField", "name": "FLD", "text": "val"}
                     ]},
                ]
            }
        }
        session = build_tree(data)
        assert session.info.system_name == "TST"
        assert session.info.transaction == "SE16"
        wnd = session.get_window(0)
        assert wnd is not None
        assert wnd.user_area is not None
        fld = session.findById("wnd[0]/usr/txtFLD")
        assert fld.text == "val"


class TestLoadScreenFiles:
    """Test that all screen JSON files load without errors."""

    @pytest.fixture
    def screen_files(self):
        return sorted(SCREENS_DIR.glob("*.json"))

    def test_screens_directory_exists(self):
        assert SCREENS_DIR.exists()

    def test_at_least_10_screens(self, screen_files):
        assert len(screen_files) >= 10, f"Only {len(screen_files)} screen files found"

    @pytest.mark.parametrize("screen_name", [
        "01_SESSION_MANAGER.json",
        "02_SE16_initial.json",
        "03_SE16_SFLIGHT_selection_screen.json",
        "04_SE16_SFLIGHT_results.json",
        "11_SU01_initial.json",
        "05_SE16N_initial.json",
        "10_SM37_initial.json",
        "07_SE38_initial.json",
        "08_SE38_source_ZSBX_DEMO.json",
        "09_SE38_attributes_ZSBX_DEMO.json",
    ])
    def test_load_specific_screen(self, screen_name):
        path = SCREENS_DIR / screen_name
        if not path.exists():
            pytest.skip(f"{screen_name} not found")
        session = load_screen(path)
        wnd = session.get_window(0)
        assert wnd is not None, f"No window in {screen_name}"

    @pytest.mark.parametrize("screen_name", [
        "02_SE16_initial.json",
        "07_SE38_initial.json",
        "11_SU01_initial.json",
        "05_SE16N_initial.json",
        "10_SM37_initial.json",
    ])
    def test_screens_have_user_area(self, screen_name):
        path = SCREENS_DIR / screen_name
        if not path.exists():
            pytest.skip(f"{screen_name} not found")
        session = load_screen(path)
        wnd = session.get_window(0)
        assert wnd.user_area is not None, f"No user area in {screen_name}"

    @pytest.mark.parametrize("screen_name", [
        "01_SESSION_MANAGER.json",
        "02_SE16_initial.json",
        "07_SE38_initial.json",
    ])
    def test_screens_have_menubar(self, screen_name):
        path = SCREENS_DIR / screen_name
        if not path.exists():
            pytest.skip(f"{screen_name} not found")
        session = load_screen(path)
        wnd = session.get_window(0)
        menus = [c for c in wnd.children if isinstance(c, Menubar)]
        assert len(menus) >= 1, f"No menubar in {screen_name}"

    def test_se16_initial_has_table_name_field(self):
        path = SCREENS_DIR / "02_SE16_initial.json"
        if not path.exists():
            pytest.skip("SE16 initial not found")
        session = load_screen(path)
        field = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")
        assert isinstance(field, ComboTextField)

    def test_se38_initial_has_program_field(self):
        path = SCREENS_DIR / "07_SE38_initial.json"
        if not path.exists():
            pytest.skip("SE38 initial not found")
        session = load_screen(path)
        wnd = session.get_window(0)
        usr = wnd.user_area
        combo_fields = [c for c in usr.all_controls()
                        if isinstance(c, ComboTextField)]
        assert len(combo_fields) >= 1, "No ComboTextField in SE38 initial"

    def test_se38_initial_has_radio_buttons(self):
        path = SCREENS_DIR / "07_SE38_initial.json"
        if not path.exists():
            pytest.skip("SE38 initial not found")
        session = load_screen(path)
        wnd = session.get_window(0)
        radios = [c for c in wnd.all_controls()
                  if isinstance(c, RadioButton)]
        assert len(radios) >= 4, f"Expected >=4 radio buttons, got {len(radios)}"

    def test_all_screens_load(self, screen_files):
        """Smoke test: every screen JSON loads without exception."""
        for path in screen_files:
            if path.name == "_manifest.json":
                continue
            session = load_screen(path)
            assert session is not None, f"Failed to load {path.name}"
