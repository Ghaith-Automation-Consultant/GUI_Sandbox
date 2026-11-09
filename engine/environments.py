# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — the environments listed in the SAP Logon pad.

Each entry in ``environments.json`` (repo root) is one system a user or a
script can open, like a connection entry in SAP Logon. Scripts open one with
``application.OpenConnection("<description>", True)``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

ENVIRONMENTS_FILE = Path(__file__).resolve().parent.parent / "environments.json"

_FIELDS = {"id": str, "description": str, "system": str, "client": str, "logon": bool}


@dataclass(frozen=True)
class Environment:
    id: str
    description: str
    system: str
    client: str
    logon: bool


def load_environments(path: Optional[Path] = None) -> list[Environment]:
    """Read and validate the environment list."""
    path = Path(path) if path else ENVIRONMENTS_FILE
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{path.name}: expected a non-empty list of environments")

    envs = []
    for i, entry in enumerate(entries):
        for field, kind in _FIELDS.items():
            if not isinstance(entry.get(field), kind):
                raise ValueError(f"{path.name}: entry {i} needs '{field}' ({kind.__name__})")
        envs.append(Environment(**{field: entry[field] for field in _FIELDS}))

    for field in ("id", "description"):
        values = [getattr(env, field).upper() for env in envs]
        if len(values) != len(set(values)):
            raise ValueError(f"{path.name}: duplicate {field}")
    return envs


def find_environment(envs: Iterable[Environment], name: str) -> Optional[Environment]:
    """Find an environment by id or description, ignoring case."""
    name = (name or "").strip().upper()
    for env in envs:
        if name in (env.id.upper(), env.description.upper()):
            return env
    return None
