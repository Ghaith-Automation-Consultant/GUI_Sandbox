# SPDX-License-Identifier: Apache-2.0
"""
Layer B — logon rules for the sandbox logon screen (transaction S000).

The sandbox has one client. The test users of each environment live in
``users.json`` (see engine/users.py); never put credentials from a real
system there.
"""
from __future__ import annotations

from typing import Optional

from .users import DEFAULT_ENVIRONMENT, UserStore

SANDBOX_CLIENT = "000"
SANDBOX_LANGUAGES = {"EN"}


def check_logon(client: str, user: str, password: str, language: str = "",
                users: Optional[UserStore] = None,
                environment: str = DEFAULT_ENVIRONMENT) -> str | None:
    """Validate a logon attempt. Returns an error message, or None on success.

    User names are case-insensitive, passwords are not.
    """
    users = users or UserStore.load()
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
    if not users.check(environment, user, password):
        return "Name or password is incorrect (repeat logon)"
    return None
