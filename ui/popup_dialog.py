# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer A — a modal popup (wnd[1], wnd[2]) shown as a Qt dialog.

The dialog is drawn from the engine window, so scripts and users act on the
same controls. It never runs its own event loop (open(), not exec()), so a
script waiting on the GUI thread can't deadlock. Closing it with X or Esc
sends F12 to the window, and the Navigator decides what happens.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from engine.control import Button, Toolbar, UserArea
from engine.session import ModalWindow

from .styles import SAP
from .widget_factory import _build_children_into

_VKEY_CANCEL = 12


class PopupDialog(QDialog):
    def __init__(self, window: ModalWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.window = window
        self._closing = False
        self.setObjectName(window.id)
        self.setWindowTitle(window.text)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
        self.setStyleSheet(f"QDialog {{ background: {SAP.PANEL_BG}; }}")

        layout = QVBoxLayout(self)
        usr = next((c for c in window.children if isinstance(c, UserArea)), None)
        area = QWidget(self)
        if usr is not None:
            area.setObjectName(usr.id)
            area.setFixedSize(max(usr.width, 300), max(usr.height, 40))
            _build_children_into(usr, area)
        layout.addWidget(area)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        toolbar = next((c for c in window.children if isinstance(c, Toolbar)), None)
        for ctrl in (toolbar.children if toolbar else []):
            if isinstance(ctrl, Button):
                btn = QPushButton(ctrl.text or ctrl.tooltip, self)
                btn.setObjectName(ctrl.id)
                btn.setToolTip(ctrl.tooltip)
                btn.setAutoDefault(False)
                btn.clicked.connect(lambda _checked=False, c=ctrl: c.press())
                buttons.addWidget(btn)
        layout.addLayout(buttons)

    def close_from_engine(self) -> None:
        """The engine closed this window: close without sending F12."""
        self._closing = True
        self.done(QDialog.Rejected)
        self.deleteLater()

    def reject(self) -> None:
        # Esc or the window's X button: let the engine decide, as F12 would.
        if self._closing:
            super().reject()
        else:
            self.window.send_vkey(_VKEY_CANCEL)

    def closeEvent(self, event) -> None:
        if self._closing:
            super().closeEvent(event)
        else:
            event.ignore()
            self.window.send_vkey(_VKEY_CANCEL)
