# SPDX-License-Identifier: Apache-2.0
"""XD03 Display Customer: a reactive flow that shows the customer you enter."""
import json
import threading
import time

import pytest
from PySide6.QtWidgets import QLineEdit, QWidget

from engine.customers import (
    COMPANY_CODE_FIELD, CUSTOMER_FIELD, CustomerDisplayFlow, load_customers, lookup, normalize,
)
from engine.navigation import TRANSACTIONS, Navigator
from engine.reactive import REACTIVE_FLOWS

NAME_FIELD = "wnd[0]/usr/txtKNA1-NAME1"
CITY_FIELD = "wnd[0]/usr/txtKNA1-ORT01"
SHOWN_CUSTOMER = "wnd[0]/usr/txtRF02D-KUNNR"
SHOWN_COMPANY = "wnd[0]/usr/txtRF02D-BUKRS"


def enter(session, customer, company_code=""):
    session.findById(CUSTOMER_FIELD).value = customer
    session.findById(COMPANY_CODE_FIELD).value = company_code
    session.findById("wnd[0]").send_vkey(0)


def customer_input(window):
    """The Customer entry: a field with a value-help button, so the QLineEdit sits inside it."""
    container = window.findChild(QWidget, "/app/con[0]/ses[0]/" + CUSTOMER_FIELD)
    return container.findChild(QLineEdit)


def status(nav):
    return nav.session.findById("wnd[0]/sbar").text


@pytest.fixture
def nav():
    n = Navigator()
    n.start_transaction("XD03")
    return n


# ── Data and lookup ───────────────────────────────────────────────────────────

class TestLookup:
    def test_registered(self):
        assert "XD03" in REACTIVE_FLOWS
        assert TRANSACTIONS["XD03"] == REACTIVE_FLOWS["XD03"].screens

    def test_sample_data_loads(self):
        customers = load_customers()
        assert len(customers) >= 5
        assert customers["1000"].name == "Sample Customer Inc."

    @pytest.mark.parametrize("raw, expected", [
        ("1000", "1000"), ("0000001000", "1000"), (" 1000 ", "1000"), ("", ""), ("000", "0"),
    ])
    def test_normalize(self, raw, expected):
        assert normalize(raw) == expected

    @pytest.mark.parametrize("number, company, expected", [
        ("", "", "Fill in all required entry fields"),
        ("9999", "", "Customer 9999 has not been created"),
        ("1002", "1000", "Customer 1002 has not been created for company code 1000"),
    ])
    def test_errors(self, number, company, expected):
        error, customer = lookup(load_customers(), number, company)
        assert error == expected and customer is None

    def test_found_in_company_code(self):
        error, customer = lookup(load_customers(), "1001", "2000")
        assert error is None and customer.city == "London"

    def test_duplicate_customer_rejected(self, tmp_path):
        path = tmp_path / "customers.json"
        entry = {"customer": "1", "name": "A", "street": "", "postal_code": "", "city": "",
                 "country": "", "language": "", "company_codes": []}
        path.write_text(json.dumps([entry, {**entry, "customer": "0001"}]), encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate"):
            load_customers(path)


# ── Flow through the Navigator (no UI) ────────────────────────────────────────

class TestFlow:
    def test_known_customer_opens_general_data(self, nav):
        enter(nav.session, "1003")
        assert nav.step == 1
        s = nav.session
        assert s.findById(NAME_FIELD).text == "Test Logistics SA"
        assert s.findById(CITY_FIELD).text == "Paris"
        assert s.findById(SHOWN_CUSTOMER).text == "1003"

    def test_different_customers_show_different_data(self, nav):
        enter(nav.session, "1000")
        first = nav.session.findById(NAME_FIELD).text
        nav.go_back()
        enter(nav.session, "1004")
        assert nav.session.findById(NAME_FIELD).text != first
        assert nav.session.findById(NAME_FIELD).text == "Fictional Foods BV"

    def test_leading_zeros(self, nav):
        enter(nav.session, "0000001002")
        assert nav.session.findById(SHOWN_CUSTOMER).text == "1002"

    def test_company_code_is_shown(self, nav):
        enter(nav.session, "1001", "2000")
        assert nav.session.findById(SHOWN_COMPANY).text == "2000"

    @pytest.mark.parametrize("number, company, expected", [
        ("", "", "Fill in all required entry fields"),
        ("9999", "", "Customer 9999 has not been created"),
        ("1002", "1000", "Customer 1002 has not been created for company code 1000"),
    ])
    def test_wrong_input_stays_with_error(self, nav, number, company, expected):
        enter(nav.session, number, company)
        assert nav.tcode == "XD03" and nav.step == 0
        assert status(nav) == expected
        assert nav.session.findById(CUSTOMER_FIELD).text == number  # input is kept

    def test_back_keeps_what_was_typed(self, nav):
        enter(nav.session, "0000001001", "1000")
        nav.session.findById("wnd[0]").send_vkey(3)  # F3 Back
        assert nav.step == 0
        assert nav.session.findById(CUSTOMER_FIELD).text == "0000001001"
        assert nav.session.findById(COMPANY_CODE_FIELD).text == "1000"

    def test_new_start_forgets_previous_customer(self, nav):
        enter(nav.session, "1000")
        nav.start_transaction("XD03")
        assert nav.session.findById(CUSTOMER_FIELD).text == ""

    def test_enter_on_general_data_does_nothing(self, nav):
        enter(nav.session, "1000")
        nav.session.findById("wnd[0]").send_vkey(0)
        assert nav.step == 1

    def test_command_field_still_navigates(self, nav):
        nav.session.findById("wnd[0]/tbar[0]/okcd").text = "/nSE16"
        nav.session.findById("wnd[0]").send_vkey(0)
        assert nav.tcode == "SE16"

    def test_flow_with_custom_data_file(self, tmp_path):
        path = tmp_path / "customers.json"
        path.write_text(json.dumps([{
            "customer": "42", "name": "Answer Ltd", "street": "", "postal_code": "", "city": "Nowhere",
            "country": "XX", "language": "EN", "company_codes": ["1000"],
        }]), encoding="utf-8")
        flow = CustomerDisplayFlow(path)
        n = Navigator()
        n.start_transaction("XD03")
        enter(n.session, "42")
        error, _ = flow.check(n.session, 0)  # the registered flow doesn't know 42
        assert error is None
        assert n.step == 0 and "has not been created" in status(n)


# ── Live window ───────────────────────────────────────────────────────────────

class TestWindow:
    def test_easy_access_lists_xd03(self, main_window):
        from PySide6.QtWidgets import QTreeWidget
        main_window.load_initial_screen()
        tree = main_window.findChild(QTreeWidget, "nav_tree")
        labels = []

        def walk(item):
            labels.append(item.text(0))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(i))
        assert any(label.startswith("XD03") for label in labels)

    def test_typing_and_enter_shows_customer(self, main_window):
        main_window.router.navigate("XD03")
        field = customer_input(main_window)
        field.setText("1002")
        field.returnPressed.emit()
        shown = main_window.findChild(QLineEdit, "/app/con[0]/ses[0]/" + NAME_FIELD)
        assert shown is not None and shown.text() == "Demo Retail GmbH"
        assert shown.isReadOnly()

    def test_unknown_customer_message_in_window(self, main_window):
        main_window.router.navigate("XD03")
        field = customer_input(main_window)
        field.setText("4711")
        field.returnPressed.emit()
        assert "4711 has not been created" in main_window.statusBar().currentMessage()

    def test_script_thread_enter(self, main_window, qapp):
        """A COM/HTTP script presses Enter from its own thread and sees the new screen."""
        session = main_window.router.navigate("XD03")
        done, errors = threading.Event(), []

        def script():
            try:
                enter(session, "1004")
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(exc)
            finally:
                done.set()

        threading.Thread(target=script, daemon=True).start()
        deadline = time.monotonic() + 5
        while not done.is_set() and time.monotonic() < deadline:
            qapp.processEvents()
        assert done.is_set() and not errors
        current = main_window.renderer.session
        assert current.findById(CITY_FIELD).text == "Amsterdam"
