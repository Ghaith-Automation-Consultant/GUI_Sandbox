# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — modal popups (wnd[1], wnd[2]) built at runtime.

A popup has the parts scripts expect on an SAP dialog box::

    wnd[n]/titl            title
    wnd[n]/usr/...         labels and fields (optionally inside a subscreen)
    wnd[n]/tbar[0]/btn[0]  Continue (Enter)
    wnd[n]/tbar[0]/btn[12] Cancel (F12)
    wnd[n]/sbar            status bar

The Navigator decides what Continue and Cancel do.
"""
from __future__ import annotations

from typing import Optional

from .control import (
    Button, Label, PasswordField, SimpleContainer, StatusBar, Titlebar, Toolbar, UserArea,
)
from .session import ModalWindow, Session

POPUP_INDEX = 1
MESSAGE_INDEX = 2
BTN_CONTINUE = 0
BTN_CANCEL = 12

_LABEL_X, _FIELD_X, _ROW_H = 16, 200, 30


def _frame(session: Session, index: int, title: str, height: int) -> tuple[ModalWindow, UserArea]:
    close_popup(session, index)
    wnd_id = f"{session.id}/wnd[{index}]"
    wnd = ModalWindow(wnd_id, index=index, name=f"wnd[{index}]", text=title, width=440, height=height)
    wnd.add_child(Titlebar(f"{wnd_id}/titl", name="titl", text=title))
    usr = wnd.add_child(UserArea(f"{wnd_id}/usr", name="usr", width=440, height=height - 80))
    return wnd, usr


def _finish(session: Session, wnd: ModalWindow, cancel: bool = True) -> ModalWindow:
    tbar = wnd.add_child(Toolbar(f"{wnd.id}/tbar[0]", name="tbar[0]"))
    tbar.add_child(Button(f"{wnd.id}/tbar[0]/btn[{BTN_CONTINUE}]", name=f"btn[{BTN_CONTINUE}]",
                          text="Continue", tooltip="Continue (Enter)"))
    if cancel:
        tbar.add_child(Button(f"{wnd.id}/tbar[0]/btn[{BTN_CANCEL}]", name=f"btn[{BTN_CANCEL}]",
                              text="Cancel", tooltip="Cancel (F12)"))
    wnd.add_child(StatusBar(f"{wnd.id}/sbar", name="sbar"))
    return session.add_window(wnd)


def open_popup(session: Session, title: str, fields: list[tuple[str, str]], message: str = "",
               index: int = POPUP_INDEX, subscreen: str = "") -> ModalWindow:
    """Add wnd[index] with password fields, given as (field name, label) pairs.

    Field IDs are ``wnd[index]/usr/pwd<name>``, or with a subscreen such as
    ``SAPMSYST:0043``, ``wnd[index]/usr/subSUBSCREEN:SAPMSYST:0043/pwd<name>``.
    ``message`` is an optional line shown above the fields.
    """
    height = 130 + _ROW_H * (len(fields) + (1 if message else 0))
    wnd, usr = _frame(session, index, title, height)
    top = 12
    if message:
        usr.add_child(Label(f"{usr.id}/lblMESSAGE", name="MESSAGE", text=message,
                            left=_LABEL_X, top=top, width=400, height=22))
        top += _ROW_H
    parent = usr
    if subscreen:
        parent = usr.add_child(SimpleContainer(f"{usr.id}/subSUBSCREEN:{subscreen}",
                                               name=f"SUBSCREEN:{subscreen}", left=0, top=top,
                                               width=440, height=_ROW_H * len(fields)))
        top = 0
    for name, label in fields:
        parent.add_child(Label(f"{parent.id}/lbl{name}", name=name, text=label,
                               left=_LABEL_X, top=top, width=180, height=22))
        parent.add_child(PasswordField(f"{parent.id}/pwd{name}", name=name, changeable=True,
                                       max_length=40, left=_FIELD_X, top=top, width=200, height=22))
        top += _ROW_H
    return _finish(session, wnd)


def open_message(session: Session, text: str, title: str = "Information",
                 index: int = MESSAGE_INDEX) -> ModalWindow:
    """Add an information popup with one line of text and a Continue button."""
    wnd, usr = _frame(session, index, title, 140)
    usr.add_child(Label(f"{usr.id}/txtMESSTXT1", name="MESSTXT1", text=text,
                        left=_LABEL_X, top=12, width=400, height=22))
    return _finish(session, wnd, cancel=False)


def popup(session: Optional[Session], index: int = POPUP_INDEX) -> Optional[ModalWindow]:
    """The popup at wnd[index], if open."""
    if session is None:
        return None
    wnd = session.get_window(index)
    return wnd if isinstance(wnd, ModalWindow) else None


def close_popup(session: Session, index: int = POPUP_INDEX) -> None:
    """Close wnd[index] and any popup above it."""
    for i in sorted((w.index for w in session.children if isinstance(w, ModalWindow)), reverse=True):
        if i >= index:
            session.close_window(i)


def field_text(wnd: ModalWindow, name: str) -> str:
    """The text of password field <name> in a popup, inside a subscreen or not."""
    for ctrl in wnd.all_controls():
        if isinstance(ctrl, PasswordField) and ctrl.id.endswith(f"/pwd{name}"):
            return ctrl.text or ""
    return ""


def clear_fields(wnd: ModalWindow) -> None:
    for ctrl in wnd.all_controls():
        if isinstance(ctrl, PasswordField):
            ctrl.value = ""
