# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
ROT diagnostic — run from a separate terminal while main.py is running.

Tests every discovery path that SAP scripting tools use:
  1. ROT enumeration (list all registered monikers)
  2. GetObject("SAPGUI")  (VBScript / Python style)
  3. SapROTWr.SapROTWrapper.GetROTEntry("SAPGUI")  (PowerShell 6+ / Tracker.exe style)
  4. GetScriptingEngine via DISPATCH_METHOD and DISPATCH_PROPERTYGET
  5. Full object chain navigation

Usage:
    python tools/diag_rot.py
"""
import pythoncom
import win32com.client


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_rot_enumeration():
    section("1. ROT Enumeration")
    try:
        rot = pythoncom.GetRunningObjectTable(0)
        enum = rot.EnumRunning()
        found_sapgui = False
        count = 0
        for moniker in enum:
            try:
                ctx = pythoncom.CreateBindCtx(0)
                name = moniker.GetDisplayName(ctx, None)
                count += 1
                if "SAP" in name.upper():
                    print(f"  [SAP] {name}")
                    found_sapgui = True
                else:
                    print(f"        {name}")
            except Exception as e:
                print(f"  [error reading moniker] {e}")
        print(f"\n  Total ROT entries: {count}")
        if found_sapgui:
            print("  PASS: SAP-related entry found in ROT")
        else:
            print("  FAIL: No SAP-related entry found in ROT")
            print("  -> Is main.py running? Check for COM bridge startup errors.")
        return found_sapgui
    except Exception as e:
        print(f"  FAIL: Could not enumerate ROT: {e}")
        return False


def test_getobject():
    section("2. GetObject(\"SAPGUI\")")
    try:
        sap = win32com.client.GetObject("SAPGUI")
        print("  PASS: GetObject succeeded")
        print(f"  Root Id: {sap.Id}")
        return sap
    except Exception as e:
        print(f"  FAIL: {e}")
        return None


def test_saprotwrapper():
    section("3. SapROTWr.SapROTWrapper.GetROTEntry(\"SAPGUI\")")
    try:
        wrapper = win32com.client.Dispatch("SapROTWr.SapROTWrapper")
        print("  SapROTWr created OK")
    except Exception as e:
        print(f"  SKIP: SapROTWr not available ({e})")
        return None

    try:
        sap = wrapper.GetROTEntry("SAPGUI")
        if sap is None:
            print("  FAIL: GetROTEntry returned None")
            return None
        print("  PASS: GetROTEntry succeeded")
        return sap
    except Exception as e:
        print(f"  FAIL: GetROTEntry raised: {e}")
        return None


def test_getscriptingengine(sap):
    section("4. GetScriptingEngine Dispatch")
    if sap is None:
        print("  SKIP: no root object available")
        return None

    # Test as property (DISPATCH_PROPERTYGET)
    try:
        app = sap.GetScriptingEngine
        print(f"  PASS (property access): Type={app.Type}, Id={app.Id}")
    except Exception as e:
        print(f"  FAIL (property access): {e}")
        app = None

    # Test as method call (DISPATCH_METHOD) — this is how Tracker.exe calls it
    if app is None:
        try:
            app = sap.GetScriptingEngine()
            print(f"  PASS (method call): Type={app.Type}, Id={app.Id}")
        except Exception as e:
            print(f"  FAIL (method call): {e}")
            print("  -> GetScriptingEngine is likely only in _public_attrs_, not _public_methods_")

    return app


def test_object_chain(app):
    section("5. Full Object Chain")
    if app is None:
        print("  SKIP: no application object")
        return

    try:
        conn = app.Children(0)
        print(f"  Connection: Type={conn.Type}, Id={conn.Id}")
        print(f"  Description: {conn.Description}")
    except Exception as e:
        print(f"  FAIL at Connection: {e}")
        return

    try:
        session = conn.Children(0)
        print(f"  Session: Type={session.Type}, Id={session.Id}")
    except Exception as e:
        print(f"  FAIL at Session: {e}")
        return

    try:
        info = session.Info
        print(f"  Info.Transaction: {info.Transaction}")
        print(f"  Info.SystemName: {info.SystemName}")
        print(f"  Info.User: {info.User}")
        print(f"  Info.Client: {info.Client}")
        print(f"  Info.ScreenNumber: {info.ScreenNumber}")
    except Exception as e:
        print(f"  FAIL at Info: {e}")

    try:
        wnd = session.findById("wnd[0]")
        print(f"  Window: Type={wnd.Type}, Id={wnd.Id}")
    except Exception as e:
        print(f"  findById('wnd[0]'): {e}")

    try:
        children = session.Children
        count = children.Count
        print(f"  Session children: {count}")
    except Exception as e:
        print(f"  Children: {e}")

    print("\n  PASS: Full chain navigated successfully")


def main():
    print("GUI Sandbox — COM Bridge Diagnostic")
    print("Run this while main.py is running in another terminal.")

    pythoncom.CoInitialize()
    try:
        rot_ok = test_rot_enumeration()
        sap = test_getobject()
        sap_rot = test_saprotwrapper()

        root = sap or sap_rot
        app = test_getscriptingengine(root)
        test_object_chain(app)

        section("Summary")
        if rot_ok and root and app:
            print("  ALL CHECKS PASSED — sandbox is detectable")
        else:
            print("  SOME CHECKS FAILED — see details above")
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
