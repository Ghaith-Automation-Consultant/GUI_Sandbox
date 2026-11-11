# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Screen Renderer — renders a full engine.Session into a MainWindow's workspace.

Takes the Session's active Window and:
  1. Populates the menu bar from mbar children
  2. Rebuilds toolbar buttons from tbar[0] and tbar[1]
  3. Updates the title banner from the titl control
  4. Renders the user area (usr) recursively via the widget factory
  5. Updates the status bar from sbar
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QLabel, QScrollArea, QFrame, QVBoxLayout, QToolBar, QToolButton, QMenu, QTreeWidget, QTreeWidgetItem, QSplitter,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from engine.session import Session, Window
from engine.control import (
    Control, Menubar, Menu, MenuItem,
    StatusBar, Button,
)
from .widget_factory import _build_children_into
from .styles import SAP


class ScreenRenderer:
    """Renders an engine Session into a Qt MainWindow's content areas."""

    def __init__(self, main_window):
        self.main_window = main_window
        self._current_session: Session | None = None
        self._usr_scroll: QScrollArea | None = None
        self._usr_widget: QWidget | None = None

    @property
    def session(self) -> Session | None:
        return self._current_session

    def render(self, session: Session) -> None:
        """Render the full session into the main window."""
        self._current_session = session
        wnd = session.get_window(0)
        if not wnd:
            return

        self._render_title_banner(wnd)
        self._render_menu_bar(wnd)
        self._render_toolbar_buttons(wnd)
        self._render_user_area(wnd)
        self._render_status_bar(wnd)

    def clear(self) -> None:
        """Remove all dynamically rendered content."""
        if self._usr_scroll:
            old = self._usr_scroll.takeWidget()
            if old:
                old.deleteLater()
        self._current_session = None

    # ── Title Banner ────────────────────────────────────────────────────────

    def _render_title_banner(self, wnd: Window) -> None:
        banner_label = self.main_window.findChild(QLabel, "header_title")
        if not banner_label:
            return

        titl = _find_child_by_name(wnd, "titl")
        if titl:
            banner_label.setText(titl.text)
        else:
            banner_label.setText(wnd.text or "GUI Sandbox")

    # ── Menu Bar ────────────────────────────────────────────────────────────

    def _render_menu_bar(self, wnd: Window) -> None:
        menu_bar = self.main_window.menuBar()
        menu_bar.clear()

        mbar = _find_child_by_type(wnd, Menubar)
        if not mbar:
            return

        for menu_ctrl in mbar.children:
            if isinstance(menu_ctrl, Menu):
                qt_menu = menu_bar.addMenu(menu_ctrl.text or menu_ctrl.name)
                qt_menu.setObjectName(menu_ctrl.id)
                self._populate_menu(qt_menu, menu_ctrl)

    def _populate_menu(self, qt_menu: QMenu, menu_ctrl: Control) -> None:
        for child in menu_ctrl.children:
            if isinstance(child, (Menu, MenuItem)):
                if child.children:
                    sub = qt_menu.addMenu(child.text or child.name)
                    sub.setObjectName(child.id)
                    self._populate_menu(sub, child)
                else:
                    action = qt_menu.addAction(child.text or child.name)
                    action.setObjectName(child.id)
                    action.setEnabled(child.enabled)

    # ── Toolbars ────────────────────────────────────────────────────────────

    def _render_toolbar_buttons(self, wnd: Window) -> None:
        # Main toolbar (tbar[0]) is kept as static SAP chrome — don't rebuild.
        # Only rebuild the context toolbar (tbar[1]) from engine data.
        ctx_tb = self.main_window.findChild(QToolBar, "toolbar_context")
        tbar1 = _find_child_by_name(wnd, "tbar[1]")
        if tbar1 and ctx_tb:
            self._populate_context_toolbar(ctx_tb, tbar1)

    def _populate_context_toolbar(self, qt_tb: QToolBar, tbar_ctrl: Control) -> None:
        qt_tb.clear()

        for child in tbar_ctrl.children:
            if isinstance(child, Button):
                btn = QToolButton()
                btn.setObjectName(child.id)
                label = child.text or ""
                if not label and child.tooltip:
                    # Extract short label from tooltip (before whitespace padding)
                    label = child.tooltip.split("(")[0].strip()
                    if len(label) > 20:
                        label = label[:18] + "…"
                btn.setText(label or child.name)
                btn.setToolTip(child.tooltip or child.text or "")
                btn.setEnabled(child.enabled)
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                btn.clicked.connect(lambda checked=False, c=child: c.press())
                qt_tb.addWidget(btn)

    # ── User Area ───────────────────────────────────────────────────────────

    def _render_user_area(self, wnd: Window) -> None:
        """Render the usr (user content area) into the workspace panel."""
        workspace = self.main_window.findChild(QWidget, "workspace_panel")
        if not workspace:
            return

        # Clear existing content
        for child_widget in workspace.findChildren(QWidget):
            if child_widget.parent() == workspace:
                child_widget.deleteLater()
        self._usr_scroll = None
        self._usr_widget = None

        usr = wnd.user_area
        if not usr:
            return

        # Check if this is the session manager (user area has only
        # shell/custom controls with no renderable fields)
        if self._is_session_manager(usr):
            self._render_session_manager_home(workspace)
            return

        # Create a scrollable container for the user area
        scroll = QScrollArea(workspace)
        scroll.setObjectName("usr_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {SAP.PANEL_BG};")

        # The inner widget uses absolute positioning (no layout manager)
        inner = QWidget()
        inner.setObjectName(usr.id)
        inner.setStyleSheet(f"background: {SAP.PANEL_BG};")

        # Calculate required size from child control positions
        max_w, max_h = 800, 600
        for ctrl in usr.all_controls():
            if ctrl.left >= 0 and ctrl.top >= 0:
                r = ctrl.left + max(ctrl.width, 0)
                b = ctrl.top + max(ctrl.height, 0)
                if r > max_w:
                    max_w = r
                if b > max_h:
                    max_h = b

        inner.setMinimumSize(max_w + 20, max_h + 20)

        # Build all user area children as Qt widgets with absolute positioning
        _build_children_into(usr, inner)

        scroll.setWidget(inner)
        self._usr_scroll = scroll
        self._usr_widget = inner

        # Make the scroll area fill the workspace
        if workspace.layout():
            workspace.layout().addWidget(scroll)
        else:
            layout = QVBoxLayout(workspace)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(scroll)

    def _is_session_manager(self, usr) -> bool:
        """Detect if user area is the session manager (only shells, no fields)."""
        for child in usr.children:
            if child.name == "IMAGE_CONTAINER":
                return True
        return False

    def _render_session_manager_home(self, workspace: QWidget) -> None:
        """Build a synthetic Easy Access home screen."""

        splitter = QSplitter(Qt.Orientation.Horizontal, workspace)
        splitter.setObjectName("home_splitter")

        # Left pane: navigation tree
        tree = QTreeWidget()
        tree.setObjectName("nav_tree")
        tree.setHeaderHidden(True)
        tree.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
        tree.setStyleSheet(f"""
            QTreeWidget {{
                background: white;
                border: 1px solid {SAP.BORDER_COLOR};
            }}
            QTreeWidget::item {{
                padding: 2px 0;
            }}
            QTreeWidget::item:selected {{
                background: {SAP.SELECTED_BG};
                color: black;
            }}
            QTreeWidget::item:hover {{
                background: #E0E8F0;
            }}
        """)

        favorites = QTreeWidgetItem(tree, ["Favorites"])
        favorites.setExpanded(True)

        sap_menu = QTreeWidgetItem(tree, ["Main Menu"])
        sap_menu.setExpanded(True)

        cat_basis = QTreeWidgetItem(sap_menu, ["Basis"])
        cat_data = QTreeWidgetItem(sap_menu, ["Data Dictionary"])
        cat_dev = QTreeWidgetItem(sap_menu, ["ABAP Development"])
        cat_admin = QTreeWidgetItem(sap_menu, ["Administration"])
        cat_logistics = QTreeWidgetItem(sap_menu, ["Logistics"])

        transactions = {
            "SE16  - Data Browser": ("SE16", cat_data),
            "SE16N - General Table Display": ("SE16N", cat_data),
            "SE38  - ABAP Editor": ("SE38", cat_dev),
            "SU01  - User Maintenance": ("SU01", cat_admin),
            "SM37  - Job Overview": ("SM37", cat_basis),
            "VA03  - Display Sales Order": ("VA03", cat_logistics),
            "MM03  - Display Material": ("MM03", cat_logistics),
            "XD03  - Display Customer": ("XD03", cat_logistics),
        }

        for label, (tcode, parent_item) in transactions.items():
            item = QTreeWidgetItem(parent_item, [label])
            item.setData(0, Qt.ItemDataRole.UserRole, tcode)

        for cat in [cat_basis, cat_data, cat_dev, cat_admin, cat_logistics]:
            cat.setExpanded(True)

        def on_double_click(item, column):
            tcode = item.data(0, Qt.ItemDataRole.UserRole)
            if tcode:
                self.main_window.router.navigate(tcode)

        tree.itemDoubleClicked.connect(on_double_click)

        # Right pane: product name
        right_pane = QWidget()
        right_pane.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {SAP.PANEL_BG}, stop:1 {SAP.BANNER_START});
        """)
        right_layout = QVBoxLayout(right_pane)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_label = QLabel("GUI Sandbox")
        logo_label.setFont(QFont(SAP.FONT_FAMILY, 48, QFont.Weight.Bold))
        logo_label.setStyleSheet("color: #1661BE; background: transparent;")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(logo_label)


        splitter.addWidget(tree)
        splitter.addWidget(right_pane)
        splitter.setSizes([350, 850])

        if workspace.layout():
            workspace.layout().addWidget(splitter)
        else:
            layout = QVBoxLayout(workspace)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(splitter)

    # ── Status Bar ──────────────────────────────────────────────────────────

    def _render_status_bar(self, wnd: Window) -> None:
        status_bar = self.main_window.statusBar()
        if not status_bar:
            return

        status_bar.clearMessage()

        sbar = wnd.status_bar
        if not sbar:
            return

        # Get text from status bar or its first pane child
        text = sbar.text
        msg_type = ""
        if isinstance(sbar, StatusBar):
            msg_type = sbar.message_type

        if not text:
            for child in sbar.children:
                if child.text:
                    text = child.text
                    break

        if text:
            color = {
                "S": SAP.STATUS_SUCCESS,
                "W": SAP.STATUS_WARNING,
                "E": SAP.STATUS_ERROR,
                "A": SAP.STATUS_ERROR,
                "I": SAP.STATUS_INFO,
            }.get(msg_type, "#333")
            status_bar.setStyleSheet(
                f"QStatusBar {{ color: {color}; "
                f"background: {SAP.TOOLBAR_BG}; "
                f"border-top: 1px solid {SAP.BORDER_COLOR}; }}"
            )
            status_bar.showMessage(text)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _find_child_by_name(parent: Control, name: str) -> Control | None:
    for child in parent.children:
        if child.name == name:
            return child
    return None


def _find_child_by_type(parent: Control, ctrl_type: type) -> Control | None:
    for child in parent.children:
        if isinstance(child, ctrl_type):
            return child
    return None
