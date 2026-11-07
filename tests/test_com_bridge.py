# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
COM bridge smoke test — run while main.py is running.

Usage:
    1. Start the sandbox:   python main.py
    2. In another terminal:  python tests/test_com_bridge.py
"""
import sys
import win32com.client


def main():
    print("Connecting to SAPGUI via COM...")
    try:
        sap = win32com.client.GetObject("SAPGUI")
    except Exception as exc:
        print(f"FAILED — could not connect: {exc}")
        print("Make sure main.py is running first.")
        sys.exit(1)

    print(f"  Root ID: {sap.Id}")

    app = sap.GetScriptingEngine
    print(f"  App Type: {app.Type}")

    conn = app.Children.Item(0)
    print(f"  Connection: {conn.Description}")
    print(f"  Connection Type: {conn.Type}")

    session = conn.Children.Item(0)
    print(f"  Session ID: {session.Id}")
    print(f"  Session Type: {session.Type}")

    info = session.Info
    print(f"  Transaction: {info.Transaction}")
    print(f"  System: {info.SystemName}")
    print(f"  Client: {info.Client}")
    print(f"  User: {info.User}")
    print(f"  Screen: {info.ScreenNumber}")

    if info.Transaction == "S000":
        print("\nLogging on with the sandbox test user...")
        session.findById("wnd[0]/usr/txtRSYST-MANDT").Text = "000"
        session.findById("wnd[0]/usr/txtRSYST-BNAME").Text = "USER_STANDARD"
        session.findById("wnd[0]/usr/pwdRSYST-BCODE").Text = "sandbox"
        session.findById("wnd[0]").sendVKey(0)
        print(f"  User: {session.Info.User}")

    print("\nTesting StartTransaction...")
    session.StartTransaction("SE16")
    print(f"  Transaction: {session.Info.Transaction}")

    print("\nTesting findById...")
    field = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")
    print(f"  Field ID: {field.Id}")
    print(f"  Field Type: {field.Type}")
    print(f"  Field Text (before): '{field.Text}'")

    field.Text = "SFLIGHT"
    print(f"  Field Text (after setText): '{field.Text}'")

    print("\nTesting sendVKey...")
    wnd = session.findById("wnd[0]")
    print(f"  Window Type: {wnd.Type}")
    wnd.sendVKey(0)
    print("  sendVKey(0) — OK")

    print("\nTesting ActiveWindow...")
    active = session.ActiveWindow
    if active:
        print(f"  ActiveWindow Type: {active.Type}")
    else:
        print("  ActiveWindow: None")

    print("\nTesting Children collection...")
    children = session.Children
    count = children.Count
    print(f"  Session has {count} child(ren)")
    if count > 0:
        first = children(0)
        print(f"  First child Type: {first.Type}")

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
