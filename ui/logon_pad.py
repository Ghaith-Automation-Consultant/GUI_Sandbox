# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer A — the SAP Logon pad: pick an environment and open it.

Like SAP Logon, it lists the connection entries from ``environments.json``.
Double-clicking an entry, pressing Enter on it, or clicking Log On asks to
open it; the pad stays open while the connection window is in use.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout, QMainWindow, QPushButton, QSplitter, QToolBar, QTreeWidget,
    QTreeWidgetItem, QWidget,
)

from engine.environments import Environment
from .styles import SAP

COLUMNS = ["Name", "System ID", "Description"]
FOLDERS = ["Favorites", "Shortcuts", "Connections"]


class LogonPad(QMainWindow):
    """The SAP Logon window. ``on_open(environment)`` runs when an entry is opened."""

    def __init__(self, environments: list[Environment],
                 on_open: Optional[Callable[[Environment], None]] = None) -> None:
        super().__init__()
        self.setObjectName("logon_pad")
        self.setWindowTitle("SAP Logon")
        self.resize(640, 360)
        self._on_open = on_open
        self.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))

        self.addToolBar(self._create_toolbar())

        self.folders = QTreeWidget()
        self.folders.setObjectName("logon_pad/folders")
        self.folders.setHeaderHidden(True)
        for name in FOLDERS:
            QTreeWidgetItem(self.folders, ["📁 " + name])
        self.folders.setCurrentItem(self.folders.topLevelItem(FOLDERS.index("Connections")))

        self.connections = QTreeWidget()
        self.connections.setObjectName("logon_pad/connections")
        self.connections.setColumnCount(len(COLUMNS))
        self.connections.setHeaderLabels(COLUMNS)
        self.connections.setRootIsDecorated(False)
        self.connections.setAlternatingRowColors(True)
        for env in environments:
            item = QTreeWidgetItem(self.connections, ["🖥 " + env.description, env.system, self._describe(env)])
            item.setData(0, Qt.UserRole, env)
        self.connections.setColumnWidth(0, 230)
        self.connections.setColumnWidth(1, 80)
        if self.connections.topLevelItemCount():
            self.connections.setCurrentItem(self.connections.topLevelItem(0))
        self.connections.itemActivated.connect(lambda item, _col: self._open(item))

        splitter = QSplitter()
        splitter.addWidget(self.folders)
        splitter.addWidget(self.connections)
        splitter.setSizes([140, 500])

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.setCentralWidget(central)
        self.setStyleSheet(f"""
            QMainWindow#logon_pad {{ background: {SAP.PANEL_BG}; }}
            QTreeWidget {{ background: white; border: 1px solid {SAP.BORDER_COLOR}; }}
            QTreeWidget::item:selected {{ background: {SAP.SELECTED_BG}; color: black; }}
            QToolBar {{ background: {SAP.TOOLBAR_BG}; border-bottom: 1px solid {SAP.BORDER_COLOR}; }}
        """)

    @staticmethod
    def _describe(env: Environment) -> str:
        return "Logon screen" if env.logon else "Opens Easy Access"

    def _create_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Logon Toolbar")
        toolbar.setObjectName("logon_pad/toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.btn_logon = QPushButton("Log On")
        self.btn_logon.setObjectName("logon_pad/btn_logon")
        self.btn_logon.setToolTip("Log On to the selected entry")
        self.btn_logon.clicked.connect(lambda: self._open(self.connections.currentItem()))
        toolbar.addWidget(self.btn_logon)
        return toolbar

    def selected_environment(self) -> Optional[Environment]:
        item = self.connections.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def select(self, environment_id: str) -> None:
        """Select an entry by id."""
        for i in range(self.connections.topLevelItemCount()):
            item = self.connections.topLevelItem(i)
            if item.data(0, Qt.UserRole).id == environment_id:
                self.connections.setCurrentItem(item)
                return

    def _open(self, item: Optional[QTreeWidgetItem]) -> None:
        if item is None or self._on_open is None:
            return
        self._on_open(item.data(0, Qt.UserRole))
