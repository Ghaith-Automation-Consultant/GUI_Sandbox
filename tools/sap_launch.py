# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
SAP GUI launcher — opens SAP Logon and waits for you to log in,
then hands control to the inspector / scenarios.

Run:
    python tools/sap_launch.py
        → launches SAP Logon, waits for you to log in, then prints the session info

    python tools/sap_launch.py --inspect --tree
        → after login, dumps the full control tree

    python tools/sap_launch.py --inspect --out screens/main_menu.json
        → captures main menu screen to JSON

    python tools/sap_launch.py --scenarios all --out screens/
        → runs all scenarios after you log in
"""

import subprocess
import time
import argparse
from tools.sap_connect import get_sap_app, list_connections, SAP_LOGON_EXE
from tools.sap_inspect import print_tree, inspect_session
from tools.sap_scenarios import run_all, SCENARIOS

import json
from pathlib import Path


def ensure_sap_running(timeout: int = 60):
    """Launch SAP Logon if not running, wait until at least one session is logged in."""
    app = get_sap_app()
    if app is None:
        print(f"Launching SAP Logon: {SAP_LOGON_EXE}")
        subprocess.Popen([SAP_LOGON_EXE])
    else:
        connections = app.Connections.Count
        print(f"SAP GUI already running — {connections} connection(s) open")

    print("Waiting for an active SAP session (log in via the SAP Logon window)…")
    for _ in range(timeout):
        try:
            app = get_sap_app()
            if app and app.Connections.Count > 0:
                conn = app.Connections.Item(0)
                if conn.Sessions.Count > 0:
                    session = conn.Sessions.Item(0)
                    # Check we're past the logon screen (transaction is not empty)
                    info = session.Info
                    if info.Transaction and info.Transaction.strip():
                        print(f"\nSession detected: {info.SystemName} / {info.User} / T:{info.Transaction}")
                        return session
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(1)

    raise RuntimeError(f"No SAP session appeared within {timeout} seconds.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAP GUI launcher + inspector")
    parser.add_argument("--inspect", action="store_true", help="Inspect active screen after login")
    parser.add_argument("--tree", action="store_true", help="Print control tree")
    parser.add_argument("--out", "-o", help="Output path / directory")
    parser.add_argument("--scenarios", "-s", help="Run scenarios: all or a scenario name",
                        choices=list(SCENARIOS.keys()) + ["all"])
    parser.add_argument("--table", default="MARA", help="Table name for SE16")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds to wait for login")
    args = parser.parse_args()

    session = ensure_sap_running(timeout=args.timeout)
    list_connections()

    if args.scenarios:
        out_dir = Path(args.out or "screens")
        out_dir.mkdir(parents=True, exist_ok=True)
        if args.scenarios == "all":
            log = run_all(session, out_dir, table_name=args.table)
        else:
            log = SCENARIOS[args.scenarios](session, out_dir, [])
        summary = out_dir / "_scenario_log.json"
        summary.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nDone. {len(log)} snapshots in {out_dir}")

    elif args.inspect:
        data = inspect_session(session)
        if args.tree:
            for wnd in data.get("windows", []):
                print_tree(wnd)
        if args.out:
            Path(args.out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Saved → {args.out}")
        elif not args.tree:
            print(json.dumps(data, indent=2, ensure_ascii=False))

    else:
        print("\nSAP session is ready. Options:")
        print("  Inspect current screen : python tools/sap_inspect.py --tree")
        print("  Run all scenarios       : python tools/sap_scenarios.py --scenario all --out screens/")
