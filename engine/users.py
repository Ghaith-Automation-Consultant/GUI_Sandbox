# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — test users per environment, from ``users.json`` (repo root).

The file maps an environment id to its users. These are test values for the
simulator only; never put credentials from a real system there.

Password changes and resets made while the app runs are kept in memory and
never written back, so every run starts from the same known users.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Optional

USERS_FILE = Path(__file__).resolve().parent.parent / "users.json"
DEFAULT_ENVIRONMENT = "WL"

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 40


def validate_new_password(old: Optional[str], new: str, repeat: str) -> Optional[str]:
    """Check a new password against the sandbox rules. Returns an error, or None."""
    if not new:
        return "Enter a new password"
    if new != repeat:
        return "The new passwords do not match"
    if old is not None and new == old:
        return "Choose a password that is different from your current password"
    if len(new) < MIN_PASSWORD_LENGTH:
        return f"The password must have at least {MIN_PASSWORD_LENGTH} characters"
    if len(new) > MAX_PASSWORD_LENGTH:
        return f"Password can have at most {MAX_PASSWORD_LENGTH} characters"
    return None


class UserStore:
    """The test users of every environment, held in memory."""

    def __init__(self, data: dict[str, list[dict]]) -> None:
        # environment id -> user name (upper case) -> {"user", "password", "initial"}
        self._envs: dict[str, dict[str, dict]] = {}
        for env_id, users in data.items():
            if not isinstance(users, list):
                raise ValueError(f"users for {env_id} must be a list")
            by_name: dict[str, dict] = {}
            for i, entry in enumerate(users):
                if not isinstance(entry.get("user"), str) or not entry["user"].strip():
                    raise ValueError(f"{env_id} user {i} needs a 'user' name")
                if not isinstance(entry.get("password"), str):
                    raise ValueError(f"{env_id} user {i} needs a 'password'")
                key = entry["user"].strip().upper()
                if key in by_name:
                    raise ValueError(f"duplicate user {key} in {env_id}")
                by_name[key] = {"user": key, "password": entry["password"],
                                "initial": bool(entry.get("initial", False))}
            self._envs[env_id.upper()] = by_name

    @classmethod
    def load(cls, path: Optional[Path] = None, environment_ids=None) -> "UserStore":
        """Read users.json. With environment_ids, reject environments that don't exist."""
        path = Path(path) if path else USERS_FILE
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: expected an object keyed by environment id")
        if environment_ids is not None:
            known = {e.upper() for e in environment_ids}
            unknown = [e for e in data if e.upper() not in known]
            if unknown:
                raise ValueError(f"{path.name}: unknown environment {unknown[0]}")
        return cls(copy.deepcopy(data))

    # ── queries ───────────────────────────────────────────────────────────────

    def _user(self, env_id: str, user: str) -> Optional[dict]:
        return self._envs.get((env_id or "").upper(), {}).get((user or "").strip().upper())

    def users(self, env_id: str) -> list[str]:
        return [u["user"] for u in self._envs.get((env_id or "").upper(), {}).values()]

    def exists(self, env_id: str, user: str) -> bool:
        return self._user(env_id, user) is not None

    def check(self, env_id: str, user: str, password: str) -> bool:
        entry = self._user(env_id, user)
        return entry is not None and entry["password"] == password

    def is_initial(self, env_id: str, user: str) -> bool:
        entry = self._user(env_id, user)
        return bool(entry and entry["initial"])

    # ── changes (in memory only) ──────────────────────────────────────────────

    def change_password(self, env_id: str, user: str, old: str, new: str, repeat: str) -> Optional[str]:
        """A user sets their own password. Returns an error, or None."""
        entry = self._user(env_id, user)
        if entry is None or entry["password"] != old:
            return "Name or password is incorrect (repeat logon)"
        error = validate_new_password(old, new, repeat)
        if error:
            return error
        entry["password"] = new
        entry["initial"] = False
        return None

    def reset_password(self, env_id: str, user: str, new: str, repeat: str) -> Optional[str]:
        """An administrator sets an initial password, to be changed at next logon."""
        entry = self._user(env_id, user)
        if entry is None:
            return f"User {(user or '').strip().upper()} does not exist"
        error = validate_new_password(None, new, repeat)
        if error:
            return error
        entry["password"] = new
        entry["initial"] = True
        return None
