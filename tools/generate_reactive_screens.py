# SPDX-License-Identifier: Apache-2.0
"""Screens for reactive flows (engine/reactive.py), added to the sample screens by
``tools/generate_screens.py``. Data fields are left blank here: the flow fills
them at runtime from the matching record. All data is fictional.
"""
from __future__ import annotations

try:
    from tools.generate_screens import labelled, screen
except ModuleNotFoundError:  # run as a script from tools/
    from generate_screens import labelled, screen


def xd03_screens():
    """XD03 Display Customer: initial screen, then General Data for the customer entered."""
    menu = {"Customer": ["Display", "Exit"], "Edit": ["Find"], "Goto": ["Back"]}
    initial = labelled("RF02D-KUNNR", "Customer", 1, width=120, max_len=10)
    initial += labelled("RF02D-BUKRS", "Company Code", 2, width=60, max_len=4)

    general = []
    for row, (name, caption, width) in enumerate([
        ("RF02D-KUNNR", "Customer", 120),
        ("RF02D-BUKRS", "Company Code", 60),
        ("KNA1-NAME1", "Name", 320),
        ("KNA1-STRAS", "Street/House Number", 320),
        ("KNA1-PSTLZ", "Postal Code", 100),
        ("KNA1-ORT01", "City", 240),
        ("KNA1-LAND1", "Country", 40),
        ("KNA1-SPRAS", "Language", 40),
    ]):
        general += labelled(name, caption, row, kind="txt", width=width, changeable=False)

    return [
        screen("16_XD03_initial.json", "XD03", "ZSBX_XD03", 100, "Display Customer: Initial Screen",
               menu, [], initial),
        screen("17_XD03_general_data.json", "XD03", "ZSBX_XD03", 110, "Display Customer: General Data",
               menu, [], general),
    ]


def reactive_screens():
    return xd03_screens()
