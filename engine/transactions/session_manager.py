# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — SESSION_MANAGER transaction: Easy Access main menu.
"""
from __future__ import annotations

from engine.control import Tree
from .base import BaseTransaction, _WND0_ID


class SessionManagerScreen(BaseTransaction):
    """
    Easy Access / Main Menu (SESSION_MANAGER).

    The usr area contains a GuiTree with the favourites / SAP menu navigation.

    Usage::

        screen = SessionManagerScreen(user="USER_STANDARD")
        tree = screen.find("wnd[0]/usr/shellcont/shell")
    """

    tcode = "SESSION_MANAGER"

    def __init__(self, user: str = "DEVELOPER") -> None:
        self._user = user
        super().__init__()
        self.session.info.user = user

    @property
    def title(self) -> str:  # type: ignore[override]
        return f"Easy Access - Menu for {self._user}"

    def _build(self) -> None:
        usr_id = f"{_WND0_ID}/usr"

        from engine.control import Container
        shellcont = Container(f"{usr_id}/shellcont", name="shellcont")
        nav_tree  = Tree(
            f"{usr_id}/shellcont/shell",
            name="shell",
            text="",
        )
        shellcont.add_child(nav_tree)
        self.usr.add_child(shellcont)
