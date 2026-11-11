# SPDX-License-Identifier: Apache-2.0
"""
Layer B — XD03 (Display Customer): a reactive flow over fictional customers.

The initial screen asks for a customer number and an optional company code.
Enter looks the customer up in ``customers.json`` (repo root): a known customer
opens the General Data screen filled with its address, anything else stays on
the initial screen with an error in the status bar. All data is fictional.

Customer numbers behave as in SAP: leading zeros don't matter, so ``1000`` and
``0000001000`` are the same customer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .control import Control
from .reactive import ReactiveFlow, get_text, register, set_text
from .session import Session

CUSTOMERS_FILE = Path(__file__).resolve().parent.parent / "customers.json"

CUSTOMER_FIELD = "wnd[0]/usr/ctxtRF02D-KUNNR"
COMPANY_CODE_FIELD = "wnd[0]/usr/ctxtRF02D-BUKRS"

# Fields on the General Data screen (step 1) → Customer attribute
DETAIL_FIELDS = {
    "wnd[0]/usr/txtRF02D-KUNNR": "customer",
    "wnd[0]/usr/txtRF02D-BUKRS": "company_code",
    "wnd[0]/usr/txtKNA1-NAME1": "name",
    "wnd[0]/usr/txtKNA1-STRAS": "street",
    "wnd[0]/usr/txtKNA1-PSTLZ": "postal_code",
    "wnd[0]/usr/txtKNA1-ORT01": "city",
    "wnd[0]/usr/txtKNA1-LAND1": "country",
    "wnd[0]/usr/txtKNA1-SPRAS": "language",
}

_REQUIRED = "Fill in all required entry fields"


@dataclass(frozen=True)
class Customer:
    customer: str
    name: str
    street: str
    postal_code: str
    city: str
    country: str
    language: str
    company_codes: tuple[str, ...]


def normalize(number: str) -> str:
    """SAP-style number: ignore surrounding blanks and leading zeros."""
    number = (number or "").strip().upper()
    return number.lstrip("0") or ("0" if number else "")


def load_customers(path: Optional[Path] = None) -> dict[str, Customer]:
    """Read customers.json, keyed by normalized customer number."""
    path = Path(path) if path else CUSTOMERS_FILE
    entries = json.loads(path.read_text(encoding="utf-8"))
    customers: dict[str, Customer] = {}
    for i, entry in enumerate(entries):
        try:
            customer = Customer(**{**entry, "company_codes": tuple(entry["company_codes"])})
        except (TypeError, KeyError) as exc:
            raise ValueError(f"{path.name}: entry {i} is invalid ({exc})") from None
        key = normalize(customer.customer)
        if key in customers:
            raise ValueError(f"{path.name}: duplicate customer {customer.customer}")
        customers[key] = customer
    return customers


def lookup(customers: dict[str, Customer], number: str, company_code: str = "") -> tuple[Optional[str], Optional[Customer]]:
    """Find a customer. Returns (error, None) or (None, customer)."""
    key = normalize(number)
    company_code = (company_code or "").strip().upper()
    if not key:
        return _REQUIRED, None
    customer = customers.get(key)
    if customer is None:
        return f"Customer {key} has not been created", None
    if company_code and company_code not in customer.company_codes:
        return f"Customer {key} has not been created for company code {company_code}", None
    return None, customer


class CustomerDisplayFlow(ReactiveFlow):
    tcode = "XD03"
    screens = ["16_XD03_initial.json", "17_XD03_general_data.json"]
    advance_keys = {0: {0}}  # Enter on the initial screen

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path
        self._customers: Optional[dict[str, Customer]] = None

    @property
    def customers(self) -> dict[str, Customer]:
        if self._customers is None:
            self._customers = load_customers(self._path)
        return self._customers

    def check(self, session: Session, step: int) -> tuple[Optional[str], Any]:
        if step != 0:
            return None, None
        number = get_text(session, CUSTOMER_FIELD)
        company_code = get_text(session, COMPANY_CODE_FIELD).upper()
        error, customer = lookup(self.customers, number, company_code)
        if error:
            return error, None
        return None, {"entered": number, "company_code": company_code, "customer": customer}

    def fill(self, session: Session, step: int, context: Any) -> None:
        if not context:
            return
        if step == 0:  # Back from General Data keeps what was typed
            set_text(session, CUSTOMER_FIELD, context["entered"])
            set_text(session, COMPANY_CODE_FIELD, context["company_code"])
            return
        customer: Customer = context["customer"]
        values = {**customer.__dict__, "customer": normalize(customer.customer),
                  "company_code": context["company_code"]}
        for path, attr in DETAIL_FIELDS.items():
            set_text(session, path, str(values[attr]))

    def advance_button(self, ctrl: Control, step: int) -> bool:
        return False  # XD03 moves on with Enter only


FLOW = register(CustomerDisplayFlow())
