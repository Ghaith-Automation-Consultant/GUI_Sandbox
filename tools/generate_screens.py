# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""Generate the sample screen files in screens/.

Every screen is written by hand here. All data is fictional.

Usage::

    python tools/generate_screens.py          # write screens/
    python tools/generate_screens.py --check  # exit 1 if screens/ is out of date
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "screens"
WND = "/app/con[0]/ses[0]/wnd[0]"
SYSTEM, CLIENT, USER = "SBX", "000", "USER_STANDARD"

LABEL_X, FIELD_X, ROW_H = 16, 220, 30
SAMPLE_PROGRAM = "ZSBX_DEMO"


def node(cid, ctype, name, *, children=None, **props):
    """Build one control node, with an absolute ID derived from its parent path."""
    result = {"id": cid, "type": ctype, "name": name, **props}
    if children:
        result["children"] = children
    return result


def box(left, top, width, height):
    return {"left": left, "top": top, "width": width, "height": height}


# ── Window chrome ─────────────────────────────────────────────────────────────

def menubar(menus):
    """Build the menu bar from {menu title: [item titles]}; System and Help are always added."""
    menus = {**menus, "System": ["User Profile", "Services", "Status..."], "Help": ["Application Help"]}
    children = []
    for i, (title, items) in enumerate(menus.items()):
        mid = f"{WND}/mbar/menu[{i}]"
        subs = [
            node(f"{mid}/menu[{j}]", "GuiMenu", item, text=item, changeable=True)
            for j, item in enumerate(items)
        ]
        children.append(node(mid, "GuiMenu", title, text=title, changeable=True, children=subs))
    return node(f"{WND}/mbar", "GuiMenubar", "mbar", children=children)


def main_toolbar():
    buttons = [
        (0, "Enter   (Enter)"), (11, "Save   (Ctrl+S)"), (3, "Back   (F3)"),
        (15, "Exit   (Shift+F3)"), (12, "Cancel   (F12)"), (86, "Print   (Ctrl+P)"),
        (71, "Find   (Ctrl+F)"),
    ]
    children = [node(f"{WND}/tbar[0]/okcd", "GuiOkCodeField", "okcd", changeable=True, max_len=132)]
    children += [
        node(f"{WND}/tbar[0]/btn[{n}]", "GuiButton", f"btn[{n}]", tooltip=tip, changeable=True)
        for n, tip in buttons
    ]
    return node(f"{WND}/tbar[0]", "GuiToolbar", "tbar[0]", changeable=True, children=children)


def app_toolbar(buttons):
    children = [
        node(f"{WND}/tbar[1]/btn[{n}]", "GuiButton", f"btn[{n}]", tooltip=tip, changeable=True)
        for n, tip in buttons
    ]
    return node(f"{WND}/tbar[1]", "GuiToolbar", "tbar[1]", changeable=True, children=children)


def status_bar(message):
    panes = ["", f"{SYSTEM} (1) {CLIENT}", "sandbox", "INS"]
    children = [
        node(f"{WND}/sbar/pane[{i}]", "GuiStatusPane", f"pane[{i}]", **({"text": t} if t else {}))
        for i, t in enumerate(panes)
    ]
    props = {"text": message} if message else {}
    return node(f"{WND}/sbar", "GuiStatusbar", "sbar", children=children, **props)


def screen(file, tcode, program, number, title, menus, buttons, usr, status=""):
    """Assemble a full screen file from its parts."""
    window = node(
        WND, "GuiMainWindow", "wnd[0]", text=title, changeable=True,
        children=[
            menubar(menus),
            main_toolbar(),
            node(f"{WND}/titl", "GuiTitlebar", "titl", text=title),
            app_toolbar(buttons),
            node(f"{WND}/usr", "GuiUserArea", "usr", changeable=True, children=usr),
            status_bar(status),
        ],
        **box(0, 0, 1280, 800),
    )
    return file, {
        "_label": file.removesuffix(".json"),
        "system": SYSTEM, "client": CLIENT, "user": USER,
        "transaction": tcode, "program": program, "screen": number, "status": status,
        "tree": node("/app/con[0]/ses[0]", "GuiSession", "ses[0]", children=[window]),
    }


# ── User-area helpers ─────────────────────────────────────────────────────────

def usr_id(cid):
    return f"{WND}/usr/{cid}"


def label(field, text, row, parent=usr_id):
    return node(parent(f"lbl{field}"), "GuiLabel", field, text=text, **box(LABEL_X, 20 + row * ROW_H, 200, 24))


def field(field_name, row, *, kind="ctxt", text="", width=240, left=FIELD_X, changeable=True, max_len=40,
          parent=usr_id):
    ctype = {"ctxt": "GuiCTextField", "txt": "GuiTextField", "pwd": "GuiPasswordField"}[kind]
    props = {"text": text} if text else {}
    return node(
        parent(f"{kind}{field_name}"), ctype, field_name, changeable=changeable, max_len=max_len,
        **props, **box(left, 20 + row * ROW_H, width, 24),
    )


def labelled(field_name, caption, row, *, parent=usr_id, **kwargs):
    return [label(field_name, caption, row, parent), field(field_name, row, parent=parent, **kwargs)]


def checkbox(field_name, text, row, left, selected=True):
    return node(
        usr_id(f"chk{field_name}"), "GuiCheckBox", field_name, text=text, selected=selected,
        changeable=True, **box(left, 20 + row * ROW_H, 110, 24),
    )


def radio(field_name, text, row, selected=False):
    return node(
        usr_id(f"rad{field_name}"), "GuiRadioButton", field_name, text=text, selected=selected,
        changeable=True, **box(LABEL_X + 12, 20 + row * ROW_H, 240, 24),
    )


# ── Standard menus and sample data ────────────────────────────────────────────

SE16_MENU = {"Table Entry": ["Display", "Print", "Exit"], "Edit": ["Select All", "Find"], "Goto": ["Back"]}

FLIGHT_FIELDS = [
    ("CARRID", "Airline"), ("CONNID", "Flight Number"), ("FLDATE", "Flight Date"),
    ("PRICE", "Fare"), ("CURRENCY", "Currency"), ("PLANETYPE", "Aircraft Type"),
    ("SEATSMAX", "Maximum Seats"), ("SEATSOCC", "Occupied Seats"),
]

FLIGHT_ROWS = [
    ("SX", "0101", "20260112", "420.00", "EUR", "A320", "180", "152"),
    ("SX", "0101", "20260119", "435.00", "EUR", "A320", "180", "167"),
    ("SX", "0205", "20260114", "610.50", "EUR", "A350", "300", "241"),
    ("SY", "0310", "20260115", "289.90", "USD", "B737", "160", "98"),
    ("SY", "0310", "20260122", "305.00", "USD", "B737", "160", "143"),
    ("SY", "0412", "20260118", "780.00", "USD", "B787", "280", "266"),
    ("SZ", "0550", "20260120", "198.00", "GBP", "A220", "130", "77"),
    ("SZ", "0550", "20260127", "212.50", "GBP", "A220", "130", "121"),
]

ABAP_SOURCE_NOTE = "SAPGUI.AbapEditor.1"


def se16_screens():
    selection = []
    for i, (name, _title) in enumerate(FLIGHT_FIELDS):
        selection.append(node(usr_id(f"txt%_I{i + 1}_%_APP_%-TEXT"), "GuiTextField", f"%_I{i + 1}_%_APP_%-TEXT",
                              text=name, **box(LABEL_X, 20 + i * ROW_H, 200, 24)))
        selection.append(field(f"I{i + 1}-LOW", i, width=180))
        selection.append(field(f"I{i + 1}-HIGH", i, width=180, left=FIELD_X + 200))
    selection += labelled("MAX_SEL", "Maximum Hits", 9, kind="txt", text="500", width=100)

    grid = node(
        usr_id("cntlGRID1/shellcont/shell"), "GuiGridView", "shell", changeable=True,
        columns=[{"name": n, "title": t} for n, t in FLIGHT_FIELDS],
        rows=[dict(zip((n for n, _ in FLIGHT_FIELDS), row)) for row in FLIGHT_ROWS],
        **box(8, 8, 1200, 560),
    )
    return [
        screen("02_SE16_initial.json", "SE16", "ZSBX_SE16", 230, "Data Browser: Initial Screen", SE16_MENU,
               [(7, "Table Contents   (F7)"), (5, "Create Entries   (F5)"), (6, "User Parameters...   (F6)")],
               labelled("DATABROWSE-TABLENAME", "Table Name", 1)),
        screen("03_SE16_SFLIGHT_selection_screen.json", "SE16", "ZSBX_SE16", 1000,
               "Data Browser: Table SFLIGHT: Selection Screen", SE16_MENU,
               [(8, "Execute   (F8)"), (31, "Number of Entries   (Ctrl+F7)"), (14, "Delete Selection   (Shift+F2)")],
               selection),
        screen("04_SE16_SFLIGHT_results.json", "SE16", "ZSBX_SE16", 500,
               f"Data Browser: Table SFLIGHT Select Entries   {len(FLIGHT_ROWS)}", SE16_MENU,
               [(7, "Display   (F7)"), (28, "Sort Ascending   (Ctrl+F4)"), (40, "Sort Descending   (Ctrl+Shift+F4)")],
               [grid], status=f"{len(FLIGHT_ROWS)} entries displayed"),
    ]


def se16n_screens():
    menu = {"Table": ["Display", "Exit"], "Edit": ["Delete Row"], "Goto": ["Back"]}
    buttons = [(8, "Online   (F8)"), (7, "Number of Entries   (F7)"), (32, "Background   (Ctrl+F8)")]
    table = node(
        usr_id("tblSE16NSELFIELDS_TC"), "GuiTableControl", "SELFIELDS_TC", text="Selection Criteria",
        changeable=True,
        columns=[{"name": "FIELDNAME", "title": "Field Name"}, {"name": "SCRTEXT", "title": "Description"},
                 {"name": "LOW", "title": "From"}, {"name": "HIGH", "title": "To"}],
        rows=[[name, title, "", ""] for name, title in FLIGHT_FIELDS],
        **box(LABEL_X, 110, 800, 320),
    )
    return [
        screen("05_SE16N_initial.json", "SE16N", "ZSBX_SE16N", 100, "General Table Display", menu, buttons,
               labelled("GD-TAB", "Table", 0) + labelled("GD-MAX_LINES", "Maximum Hits", 1, kind="txt", text="500")),
        screen("06_SE16N_SFLIGHT_selection.json", "SE16N", "ZSBX_SE16N", 100, "General Table Display", menu, buttons,
               labelled("GD-TAB", "Table", 0, text="SFLIGHT")
               + labelled("GD-MAX_LINES", "Maximum Hits", 1, kind="txt", text="500") + [table]),
    ]


def se38_screens():
    menu = {"Program": ["Check", "Activate", "Execute"], "Edit": ["Find"], "Goto": ["Attributes", "Variants"],
            "Utilities": ["Settings"]}
    initial = labelled("RS38M-PROGRAMM", "Program", 0)
    initial.append(node(usr_id("boxSUBOBJECTS"), "GuiBox", "SUBOBJECTS", text="Subobjects", **box(LABEL_X, 56, 520, 190)))
    initial += [
        radio("RS38M-FUNC_EDIT", "Source Code", 2, selected=True),
        radio("RS38M-FUNC_VARI", "Variants", 3),
        radio("RS38M-FUNC_HEAD", "Attributes", 4),
        radio("RS38M-FUNC_DOCU", "Documentation", 5),
        radio("RS38M-FUNC_TEXT", "Text Elements", 6),
    ]
    initial.append(node(usr_id("btnSHOP"), "GuiButton", "SHOP", text="Display", tooltip="Display   (F7)",
                        changeable=True, **box(LABEL_X, 260, 120, 28)))
    initial.append(node(usr_id("btnCHAP"), "GuiButton", "CHAP", text="Change", tooltip="Change   (F6)",
                        changeable=True, **box(LABEL_X + 130, 260, 120, 28)))

    editor = node(usr_id("cntlEDITOR/shellcont/shell"), "GuiShell", "shell", text=ABAP_SOURCE_NOTE,
                  **box(8, 44, 1200, 520))
    source_usr = labelled("SOURCE_ID", "Program", 0, kind="txt", text=SAMPLE_PROGRAM, changeable=False) + [editor]

    attributes = []
    for i, (name, text, value) in enumerate([
        ("RS38M-PROGRAMM", "Program", SAMPLE_PROGRAM),
        ("RS38M-REPTI", "Title", "Sandbox demo report"),
        ("TRDIR-SUBC", "Type", "Executable Program"),
        ("TRDIR-RSTAT", "Status", "Test Program"),
        ("TRDIR-APPL", "Application", "Cross-Application"),
    ]):
        attributes += labelled(name, text, i, kind="txt", text=value, changeable=False, width=320)

    return [
        screen("07_SE38_initial.json", "SE38", "ZSBX_SE38", 100, "ABAP Editor: Initial Screen", menu,
               [(8, "Direct Processing   (F8)"), (17, "Debugging   (Shift+F5)"), (18, "With Variant   (Shift+F6)")],
               initial),
        screen(f"08_SE38_source_{SAMPLE_PROGRAM}.json", "SE38", "ZSBX_SE38", 500,
               f"ABAP Editor: Display Report {SAMPLE_PROGRAM}", menu,
               [(8, "Attributes   (F8)"), (26, "Check   (Ctrl+F2)")], source_usr),
        screen(f"09_SE38_attributes_{SAMPLE_PROGRAM}.json", "SE38", "ZSBX_SE38", 120,
               f"ABAP Editor: Attributes of {SAMPLE_PROGRAM}", menu, [(5, "Source Code   (F5)")], attributes),
    ]


def sm37_screen():
    menu = {"Program": ["Execute", "Exit"], "Edit": ["Select All"], "Goto": ["Extended Job Selection"]}
    usr = labelled("BTCH2170-JOBNAME", "Job Name", 0, kind="txt", text="*")
    usr += labelled("BTCH2170-USERNAME", "User Name", 1, kind="txt", text=USER)
    usr.append(node(usr_id("boxSTATUS"), "GuiBox", "STATUS", text="Job Status", **box(LABEL_X, 76, 760, 60)))
    states = [("PRELIM", "Scheduled"), ("SCHEDUL", "Released"), ("READY", "Ready"),
              ("RUNNING", "Active"), ("FINISHED", "Finished"), ("ABORTED", "Canceled")]
    usr += [checkbox(f"BTCH2170-{n}", t, 3, LABEL_X + 12 + i * 122) for i, (n, t) in enumerate(states)]
    usr += labelled("BTCH2170-FROM_DATE", "From Date", 5, text="01.01.2026", width=120)
    usr += labelled("BTCH2170-TO_DATE", "To Date", 6, text="31.12.2026", width=120)
    return [screen("10_SM37_initial.json", "SM37", "ZSBX_SM37", 2170, "Simple Job Selection", menu,
                   [(8, "Execute   (F8)"), (6, "Extended Job Selection   (F6)")], usr)]


def su01_screen():
    menu = {"Users": ["Create", "Change", "Display", "Exit"], "Edit": ["Lock/Unlock"], "Goto": ["Back"]}
    return [screen("11_SU01_initial.json", "SU01", "ZSBX_SU01", 1050, "User Maintenance: Initial Screen", menu,
                   [(8, "Create   (F8)"), (18, "Change   (Shift+F6)"), (7, "Display   (F7)"),
                    (14, "Delete   (Shift+F2)"), (29, "Lock/Unlock   (Ctrl+F5)")],
                   labelled("SUID_ST_BNAME-BNAME", "User", 1))]


def va03_screens():
    menu = {"Sales Document": ["Display", "Exit"], "Edit": ["Find"], "Goto": ["Header", "Item"]}

    def tab_id(tab):
        return lambda cid: usr_id(f"tabsTAXI_TABSTRIP/tabp{tab}/{cid}")

    sales_tab = node(
        usr_id("tabsTAXI_TABSTRIP/tabpT01"), "GuiTab", "T01", text="Sales", selected=True,
        children=labelled("VBAK-AUDAT", "Order Date", 0, kind="txt", text="12.01.2026", changeable=False, parent=tab_id("T01"))
        + labelled("VBAK-WAERK", "Currency", 1, kind="txt", text="EUR", changeable=False, parent=tab_id("T01"))
        + labelled("VBAK-NETWR", "Net Value", 2, kind="txt", text="1,250.00", changeable=False, parent=tab_id("T01")),
    )
    items_tab = node(
        usr_id("tabsTAXI_TABSTRIP/tabpT02"), "GuiTab", "T02", text="Item Overview",
        children=[node(
            tab_id("T02")("tblITEMS"), "GuiTableControl", "ITEMS", changeable=True,
            columns=[{"name": "POSNR", "title": "Item"}, {"name": "MATNR", "title": "Material"},
                     {"name": "KWMENG", "title": "Quantity"}, {"name": "NETWR", "title": "Net Value"}],
            rows=[["10", "SBX-1000", "5", "750.00"], ["20", "SBX-2000", "2", "500.00"]],
            **box(8, 8, 800, 240),
        )],
    )
    overview = labelled("VBAK-VBELN", "Standard Order", 0, kind="txt", text="1000000001", changeable=False)
    overview += labelled("KUAGV-TXTPA", "Sold-To Party", 1, kind="txt", text="Sample Customer Inc.", changeable=False, width=320)
    overview.append(node(usr_id("tabsTAXI_TABSTRIP"), "GuiTabStrip", "TAXI_TABSTRIP", changeable=True,
                         children=[sales_tab, items_tab], **box(LABEL_X, 90, 900, 320)))
    return [
        screen("12_VA03_initial.json", "VA03", "ZSBX_VA03", 102, "Display Sales Order: Initial Screen", menu,
               [(8, "Display Order   (F8)"), (6, "Search   (F6)")], labelled("VBAK-VBELN", "Order", 1)),
        screen("13_VA03_overview.json", "VA03", "ZSBX_VA03", 4001, "Standard Order 1000000001: Overview", menu,
               [(5, "Item Details   (F5)")], overview),
    ]


def mm03_screen():
    menu = {"Material": ["Display", "Exit"], "Edit": ["Find"], "Goto": ["Back"]}
    return [screen("14_MM03_initial.json", "MM03", "ZSBX_MM03", 60, "Display Material: Initial Screen", menu,
                   [(5, "Select Views   (F5)")], labelled("RMMG1-MATNR", "Material", 1, text="SBX-1000"))]


def logon_screen():
    """Logon screen, shown before Easy Access. Field IDs match the standard SAP GUI logon screen."""
    menu = {"Logon": ["New Password", "Exit"]}
    usr = labelled("RSYST-MANDT", "Client", 1, kind="txt", text=CLIENT, width=60, max_len=3)
    # SAP user names are at most 12 characters; widen so the sample user fits
    usr += labelled("RSYST-BNAME", "User", 2, kind="txt", width=180, max_len=max(12, len(USER)))
    usr += labelled("RSYST-BCODE", "Password", 3, kind="pwd", width=180, max_len=40)
    usr += labelled("RSYST-LANGU", "Logon Language", 5, kind="txt", text="EN", width=40, max_len=2)
    usr.append(node(usr_id("boxINFO"), "GuiBox", "INFO", text="Information", **box(560, 20, 420, 160)))
    usr.append(node(usr_id("lblINFO_TEXT"), "GuiLabel", "INFO_TEXT",
                    text="Welcome to GUI Sandbox. All data is fictional.", **box(576, 56, 390, 24)))
    return [screen("00_LOGON.json", "S000", "ZSBX_LOGON", 20, "Logon", menu, [], usr)]


def home_screen():
    image = node(usr_id("IMAGE_CONTAINER"), "GuiContainerShell", "IMAGE_CONTAINER",
                 children=[node(usr_id("IMAGE_CONTAINER/shellcont"), "GuiContainerShell", "shellcont")],
                 **box(0, 0, 800, 600))
    menu = {"Menu": ["Log Off"], "Edit": ["Execute"], "Favorites": ["Add Transaction"], "Extras": ["Settings"]}
    return [screen("01_SESSION_MANAGER.json", "SESSION_MANAGER", "ZSBX_HOME", 100,
                   f"Easy Access - Menu for {USER}", menu, [(36, "Workplace   (Ctrl+F12)")], [image])]


def all_screens():
    return dict(
        logon_screen() + home_screen() + se16_screens() + se16n_screens() + se38_screens()
        + sm37_screen() + su01_screen() + va03_screens() + mm03_screen()
    )


def render(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def expected_files() -> dict[str, str]:
    screens = all_screens()
    manifest = [
        {"label": d["_label"], "transaction": d["transaction"], "program": d["program"],
         "screen": d["screen"], "status": d["status"], "file": name}
        for name, d in screens.items()
    ]
    return {**{name: render(d) for name, d in screens.items()}, "_manifest.json": render(manifest)}


def main() -> int:
    files = expected_files()
    if "--check" in sys.argv:
        stale = [n for n, text in files.items()
                 if not (OUT_DIR / n).exists() or (OUT_DIR / n).read_text(encoding="utf-8") != text]
        print("Out of date: " + ", ".join(stale) if stale else "screens/ is up to date")
        return 1 if stale else 0
    OUT_DIR.mkdir(exist_ok=True)
    for name, text in files.items():
        (OUT_DIR / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {len(files)} files to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
