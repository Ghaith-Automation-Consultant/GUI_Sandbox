# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""Quick capture of all live SAP sessions — run with system Python."""
import win32com.client
import json
from pathlib import Path


def safe(obj, attr, default=""):
    try:
        v = getattr(obj, attr)
        return v if v is not None else default
    except Exception:
        return default


def walk(elem):
    node = {
        "id":         safe(elem, "Id"),
        "type":       safe(elem, "Type"),
        "name":       safe(elem, "Name"),
        "text":       safe(elem, "Text"),
        "changeable": safe(elem, "Changeable", False),
        "tooltip":    safe(elem, "Tooltip"),
        "left":       safe(elem, "Left"),
        "top":        safe(elem, "Top"),
        "width":      safe(elem, "Width"),
        "height":     safe(elem, "Height"),
    }
    # strip empty
    node = {k: v for k, v in node.items() if v != "" and v is not False}
    try:
        kids = elem.Children
        count = kids.Count
        if count:
            node["children"] = [walk(kids(i)) for i in range(count)]
    except Exception:
        pass
    return node


def print_tree(node, indent=0):
    nid   = node.get("id", "?")
    ntype = node.get("type", "")
    ntext = node.get("text", "")
    extra = f'  "{ntext}"' if ntext else ""
    print("  " * indent + f"[{ntype}] {nid}{extra}")
    for child in node.get("children", []):
        print_tree(child, indent + 1)


def main():
    Path("screens").mkdir(exist_ok=True)

    sap = win32com.client.GetObject("SAPGUI")
    app = sap.GetScriptingEngine
    conns = app.Children
    print(f"Connections: {conns.Count}")

    for ci in range(conns.Count):
        conn = conns.Item(ci)
        sessions = conn.Children
        print(f"Connection {ci}: {sessions.Count} session(s)")

        for si in range(sessions.Count):
            s = sessions.Item(si)
            info = s.Info
            sys_name  = info.SystemName
            user      = info.User
            tcode     = info.Transaction
            program   = info.Program
            screen    = info.ScreenNumber

            print(f"\n  Session {si}: {sys_name} | {user} | T:{tcode} | Pgm:{program} | Scr:{screen}")
            print(f"  Status: {safe(s.findById('wnd[0]/sbar'), 'Text')}")

            tree = walk(s)
            label = f"conn{ci}_sess{si}_{sys_name}_{tcode}_{screen}"
            out_path = Path("screens") / f"{label}.json"
            out_path.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  Saved → {out_path}")

            print("\n  Control tree:")
            print_tree(tree, indent=2)


if __name__ == "__main__":
    main()
