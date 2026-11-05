# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer C — ActionRecorder.

Logs every scripting operation performed against a sandbox session.
Each entry records: timestamp (UTC ISO-8601), action name, target path,
value written (if any), and the returned result.

The log is the primary mechanism for automated test validation and
script replay debugging.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ActionRecorder:
    """
    Append-only log of scripting operations.

    Usage::

        recorder = ActionRecorder()
        recorder.log("setText", path="wnd[0]/usr/ctxtFOO", value="SFLIGHT")
        recorder.log("sendVKey", value=0)
        recorder.save("out/session_log.json")
    """

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    # ── logging ───────────────────────────────────────────────────────────────

    def log(
        self,
        action: str,
        path: str | None = None,
        value: Any = None,
        result: Any = None,
    ) -> None:
        entry: dict[str, Any] = {
            "ts":     datetime.now(timezone.utc).isoformat(),
            "action": action,
        }
        if path is not None:
            entry["path"] = path
        if value is not None:
            entry["value"] = value
        if result is not None:
            entry["result"] = result
        self._entries.append(entry)

    # ── access ────────────────────────────────────────────────────────────────

    def entries(self) -> list[dict[str, Any]]:
        """Return a copy of all logged entries."""
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def filter(self, action: str) -> list[dict[str, Any]]:
        """Return only entries matching a specific action name."""
        return [e for e in self._entries if e["action"] == action]

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Write the full log to a JSON file."""
        Path(path).write_text(
            json.dumps(self._entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "ActionRecorder":
        """Reconstruct a recorder from a previously saved log file."""
        recorder = cls()
        recorder._entries = json.loads(Path(path).read_text(encoding="utf-8"))
        return recorder

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"<ActionRecorder entries={len(self._entries)}>"
