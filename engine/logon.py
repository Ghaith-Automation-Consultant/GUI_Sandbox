# SPDX-License-Identifier: Apache-2.0
"""
Layer B — logon rules for the sandbox logon screen (transaction S000).

The sandbox has one client and a fixed set of test users. These are test
values for the simulator only; never put credentials from a real system here.
"""
from __future__ import annotations

SANDBOX_CLIENT = "000"
SANDBOX_LANGUAGES = {"EN"}

# User name → password. User names are case-insensitive, passwords are not.
SANDBOX_USERS: dict[str, str] = {
    "USER_STANDARD": "sandbox",
}


def check_logon(client: str, user: str, password: str, language: str = "") -> str | None:
    """Validate a logon attempt. Returns an error message, or None on success."""
    client = (client or "").strip()
    user = (user or "").strip().upper()
    language = (language or "").strip().upper()

    if not user:
        return "Enter a user name"
    if not password:
        return "Enter a password"
    if client != SANDBOX_CLIENT:
        return f"Client {client or '(blank)'} is not available in this system"
    if language and language not in SANDBOX_LANGUAGES:
        return f"Language {language} is not available; use EN"
    if SANDBOX_USERS.get(user) != password:
        return "Name or password is incorrect (repeat logon)"
    return None
