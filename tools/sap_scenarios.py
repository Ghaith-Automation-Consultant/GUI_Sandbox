# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
SAP scenario runner — navigates through key transactions, captures every screen,
and writes structured JSON + a human-readable scenario log.

Each scenario mimics a real RPA developer workflow:
  1. Navigate to transaction
  2. Fill fields
  3. Step through screens
  4. Capture control tree at each step
  5. Return to main menu

Run:
    python tools/sap_scenarios.py --scenario all --out screens/
    python tools/sap_scenarios.py --scenario VA01
    python tools/sap_scenarios.py --scenario ME21N
    python tools/sap_scenarios.py --scenario SE16 --table MARA
"""

import json
import time
import argparse
from pathlib import Path
from tools.sap_connect import get_session
from tools.sap_inspect import inspect_session


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _snap(session, label: str, out_dir: Path, scenario_log: list):
    """Capture current screen and append to scenario log."""
    data = inspect_session(session)
    data["_step"] = label

    file_name = label.replace(" ", "_").replace("/", "-") + ".json"
    out_path = out_dir / file_name
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Short summary for the log
    entry = {
        "step":        label,
        "transaction": data.get("transaction"),
        "screen":      data.get("screen"),
        "status":      data.get("status_bar", {}).get("text", ""),
        "file":        str(out_path),
    }
    scenario_log.append(entry)
    print(f"  ✔  {label:40s}  →  {data.get('transaction','?')} / screen {data.get('screen','?')}")
    return data


def _field(session, path: str) -> object:
    try:
        return session.findById(path)
    except Exception:
        return None


def _set(session, path: str, value: str):
    elem = _field(session, path)
    if elem:
        elem.text = value


def _press(session, path: str):
    elem = _field(session, path)
    if elem:
        elem.press()


def _vkey(session, key: int):
    """Send a VKey to the main window. Common: 0=Enter 3=F3 8=F8 11=F11."""
    session.findById("wnd[0]").sendVKey(key)


def _goto(session, tcode: str):
    session.findById("wnd[0]/tbar[0]/okcd").text = f"/n{tcode}"
    _vkey(session, 0)
    time.sleep(1)


# ─────────────────────────────────────────────────────────────────────────────
#  Scenario: VA01 — Create Sales Order
# ─────────────────────────────────────────────────────────────────────────────

def scenario_VA01(session, out_dir: Path, log: list):
    print("\n▶  VA01  —  Create Sales Order")
    _goto(session, "VA01")

    # Initial screen: order type / sales org
    _snap(session, "VA01_01_initial", out_dir, log)

    _set(session, "wnd[0]/usr/ctxtVBAK-AUART", "OR")      # Order type: Standard Order
    _set(session, "wnd[0]/usr/ctxtVBAK-VKORG", "1000")    # Sales org
    _set(session, "wnd[0]/usr/ctxtVBAK-VTWEG", "10")      # Distribution channel
    _set(session, "wnd[0]/usr/ctxtVBAK-SPART", "00")      # Division
    _snap(session, "VA01_02_order_type_filled", out_dir, log)

    _vkey(session, 0)  # Enter → item overview
    time.sleep(1)
    _snap(session, "VA01_03_item_overview", out_dir, log)

    # Header data: sold-to party
    try:
        _set(session, "wnd[0]/usr/subSUBSCREEN_HEADER:SAPMV45A:4021/txtKUNNR", "10000")
        _set(session, "wnd[0]/usr/subSUBSCREEN_HEADER:SAPMV45A:4021/txtVDAT",
             time.strftime("%d.%m.%Y"))
    except Exception:
        pass
    _snap(session, "VA01_04_header_data", out_dir, log)

    # Line items
    try:
        session.findById("wnd[0]/usr/subSUBSCREEN_TC:SAPMV45A:4900/subSUBSCREEN_BUTTONS_AND_OVERVIEW:SAPMV45A:4050/subSUBSCREEN_OVERVIEW:SAPMV45A:4401/tblSAPMV45ATCTRL_U_ERF_AUFTRAG")
        _snap(session, "VA01_05_line_items_table", out_dir, log)
    except Exception:
        _snap(session, "VA01_05_overview_screen", out_dir, log)

    # Back to main
    _goto(session, "SESSION_MANAGER")
    time.sleep(0.5)
    return log


# ─────────────────────────────────────────────────────────────────────────────
#  Scenario: ME21N — Create Purchase Order
# ─────────────────────────────────────────────────────────────────────────────

def scenario_ME21N(session, out_dir: Path, log: list):
    print("\n▶  ME21N  —  Create Purchase Order")
    _goto(session, "ME21N")
    time.sleep(1)

    _snap(session, "ME21N_01_initial", out_dir, log)

    # Vendor / document date
    try:
        _set(session, "wnd[0]/usr/subSUB0:SAPLMEGUI:0013/subSUB1:SAPLMEGUI:1211/subSUB2:SAPLMEGUI:1212/ctxtMEPO_TOPLINE-LLIEF", "100000")
    except Exception:
        pass
    _snap(session, "ME21N_02_vendor_filled", out_dir, log)

    # Item table
    _snap(session, "ME21N_03_items_area", out_dir, log)

    # Check for item details tabs
    try:
        session.findById("wnd[0]/usr/subSUB0:SAPLMEGUI:0013/subSUB3:SAPLMEGUI:3120")
        _snap(session, "ME21N_04_item_detail_tabs", out_dir, log)
    except Exception:
        pass

    _goto(session, "SESSION_MANAGER")
    return log


# ─────────────────────────────────────────────────────────────────────────────
#  Scenario: SE16 — Table Browser
# ─────────────────────────────────────────────────────────────────────────────

def scenario_SE16(session, out_dir: Path, log: list, table_name: str = "MARA"):
    print(f"\n▶  SE16  —  Table Browser  ({table_name})")
    _goto(session, "SE16")
    time.sleep(1)

    _snap(session, "SE16_01_initial", out_dir, log)

    _set(session, "wnd[0]/usr/ctxtDATABROWSE-TABLENAME", table_name)
    _vkey(session, 0)
    time.sleep(1)
    _snap(session, f"SE16_02_{table_name}_selection_screen", out_dir, log)

    # Execute (F8)
    _vkey(session, 8)
    time.sleep(2)
    _snap(session, f"SE16_03_{table_name}_results", out_dir, log)

    # Inspect the grid / table
    try:
        grid = session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell")
        print(f"    Grid columns: {list(grid.ColumnOrder)[:10]}")
    except Exception:
        pass

    _goto(session, "SESSION_MANAGER")
    return log


# ─────────────────────────────────────────────────────────────────────────────
#  Scenario: MM03 — Display Material
# ─────────────────────────────────────────────────────────────────────────────

def scenario_MM03(session, out_dir: Path, log: list):
    print("\n▶  MM03  —  Display Material Master")
    _goto(session, "MM03")
    time.sleep(1)

    _snap(session, "MM03_01_initial", out_dir, log)

    # Select views dialog often appears — accept defaults
    try:
        _vkey(session, 0)  # Enter to accept all views
        time.sleep(1)
        _snap(session, "MM03_02_select_views", out_dir, log)
        _vkey(session, 0)
        time.sleep(1)
    except Exception:
        pass

    _snap(session, "MM03_03_basic_data", out_dir, log)
    _goto(session, "SESSION_MANAGER")
    return log


# ─────────────────────────────────────────────────────────────────────────────
#  Scenario: XD03 — Display Customer
# ─────────────────────────────────────────────────────────────────────────────

def scenario_XD03(session, out_dir: Path, log: list):
    print("\n▶  XD03  —  Display Customer Master")
    _goto(session, "XD03")
    time.sleep(1)

    _snap(session, "XD03_01_initial", out_dir, log)
    _snap(session, "XD03_02_general_data", out_dir, log)
    _goto(session, "SESSION_MANAGER")
    return log


# ─────────────────────────────────────────────────────────────────────────────
#  Scenario: VA03 — Display Sales Order (with popup/navigation demo)
# ─────────────────────────────────────────────────────────────────────────────

def scenario_VA03(session, out_dir: Path, log: list):
    print("\n▶  VA03  —  Display Sales Order")
    _goto(session, "VA03")
    time.sleep(1)

    _snap(session, "VA03_01_initial", out_dir, log)
    _goto(session, "SESSION_MANAGER")
    return log


# ─────────────────────────────────────────────────────────────────────────────
#  Scenario: MAIN MENU — capture the Easy Access tree
# ─────────────────────────────────────────────────────────────────────────────

def scenario_main_menu(session, out_dir: Path, log: list):
    print("\n▶  SESSION_MANAGER  —  Easy Access / Main Menu")
    _goto(session, "SESSION_MANAGER")
    time.sleep(1)
    _snap(session, "MAIN_MENU_01", out_dir, log)
    return log


# ─────────────────────────────────────────────────────────────────────────────
#  Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

SCENARIOS = {
    "main_menu": scenario_main_menu,
    "VA01":      scenario_VA01,
    "VA03":      scenario_VA03,
    "ME21N":     scenario_ME21N,
    "SE16":      scenario_SE16,
    "MM03":      scenario_MM03,
    "XD03":      scenario_XD03,
}


def run_all(session, out_dir: Path, table_name: str = "MARA") -> list:
    log = []
    scenario_main_menu(session, out_dir, log)
    scenario_VA01(session, out_dir, log)
    scenario_ME21N(session, out_dir, log)
    scenario_SE16(session, out_dir, table_name=table_name, log=log)
    scenario_MM03(session, out_dir, log)
    scenario_XD03(session, out_dir, log)
    scenario_VA03(session, out_dir, log)
    return log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SAP inspection scenarios")
    parser.add_argument("--scenario", "-s", default="main_menu",
                        choices=list(SCENARIOS.keys()) + ["all"],
                        help="Which scenario to run")
    parser.add_argument("--out", "-o", default="screens",
                        help="Output directory for JSON snapshots")
    parser.add_argument("--table", default="MARA",
                        help="Table name for SE16 scenario")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = get_session()
    log = []

    if args.scenario == "all":
        log = run_all(session, out_dir, table_name=args.table)
    elif args.scenario == "SE16":
        log = scenario_SE16(session, out_dir, log, table_name=args.table)
    else:
        log = SCENARIOS[args.scenario](session, out_dir, log)

    # Write summary log
    summary_path = out_dir / "_scenario_log.json"
    summary_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[scenarios] Done. {len(log)} snapshots → {out_dir}")
    print(f"[scenarios] Summary log → {summary_path}")
