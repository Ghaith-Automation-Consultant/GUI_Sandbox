# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
import sys
import atexit
import argparse

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QLabel,
    QToolBar, QStatusBar, QFrame, QPushButton, QToolButton, QSizePolicy,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QSize

from bridge import ComBridge
from engine.environments import find_environment, load_environments
from ui import gui_thread
from ui.logon_pad import LogonPad
from ui.screen_renderer import ScreenRenderer
from ui.transaction_router import TransactionRouter
from ui.styles import SAP, sap_global_stylesheet


class MainWindow(QMainWindow):
    def __init__(self, com_bridge=None, require_logon=False):
        super().__init__()
        self.com_bridge = com_bridge
        self.logon_pad = None  # set when the app starts on the SAP Logon pad

        self.setWindowTitle("GUI Sandbox")
        self.setGeometry(100, 100, 1200, 800)
        self.setUnifiedTitleAndToolBarOnMac(False)

        # Main vertical layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # [B] Main Toolbar
        main_toolbar = self._create_main_toolbar()
        self.addToolBar(main_toolbar)

        # [C] Title Banner
        banner = self._create_title_banner()
        main_layout.addWidget(banner)

        # [D] Secondary Toolbar
        secondary_toolbar = self._create_secondary_toolbar()
        self.addToolBar(secondary_toolbar)

        # Re-parent toolbars into the layout to force stacking order
        self.removeToolBar(main_toolbar)
        self.removeToolBar(secondary_toolbar)
        main_toolbar.show()
        secondary_toolbar.show()
        main_layout.insertWidget(0, main_toolbar)
        main_layout.addWidget(secondary_toolbar)

        # [E] Main Content — workspace panel (no nav tree splitter for now)
        self.workspace_panel = QWidget()
        self.workspace_panel.setObjectName("workspace_panel")
        self.workspace_panel.setStyleSheet(f"background: {SAP.PANEL_BG};")
        main_layout.addWidget(self.workspace_panel, 1)

        # [F] Status Bar
        self.setStatusBar(QStatusBar(self))
        self.statusBar().setObjectName("status_bar")
        self.statusBar().showMessage("Ready")

        # Renderer and router
        self.renderer = ScreenRenderer(self)
        self.router = TransactionRouter(self.renderer, require_logon=require_logon)
        self.router.set_navigate_callback(self._on_navigate)

        # Connect command field and toolbar navigation buttons
        self.command_field.returnPressed.connect(self._on_command_enter)
        self._connect_toolbar_buttons()

    def _on_command_enter(self):
        cmd = self.command_field.text().strip()
        if cmd:
            self.router.handle_command(cmd)
            self.command_field.clear()
        elif self.renderer.session:
            # Enter with an empty command field goes to the screen, as in SAP GUI
            self.renderer.session.send_vkey(0)

    def _on_navigate(self, session, tcode):
        self.setWindowTitle(f"GUI Sandbox — {tcode}" if session else "GUI Sandbox")
        if self.com_bridge:
            self.com_bridge.update_session(session, self.router.navigator.environment)

    def load_initial_screen(self):
        """Load the first screen (logon or home) after the window is shown."""
        self.router.go_home()

    def open_environment(self, environment):
        """Open an environment from the SAP Logon pad, replacing any open one."""
        self.router.connect(environment)
        self.show()
        self.raise_()
        self.activateWindow()
        return environment

    def closeEvent(self, event):
        # With the SAP Logon pad open, closing the window closes the connection
        # and returns to the pad, as in SAP GUI.
        if self.logon_pad is not None and self.logon_pad.isVisible():
            event.ignore()
            self.hide()
            self.router.disconnect()
            self.logon_pad.raise_()
            self.logon_pad.activateWindow()
            return
        super().closeEvent(event)

    def _create_main_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("toolbar_main")
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        toolbar.setMovable(False)

        btn_enter = QPushButton(SAP.ICONS["enter"])
        btn_enter.setObjectName("btn_enter")
        btn_enter.setStyleSheet(
            "color: green; font-weight: bold; font-size: 14px; "
            f"background: transparent; border: 1px solid {SAP.BORDER_COLOR}; "
            "border-radius: 2px; padding: 2px 6px;"
        )
        btn_enter.setToolTip("Enter")
        btn_enter.clicked.connect(self._on_command_enter)
        toolbar.addWidget(btn_enter)

        self.command_field = QLineEdit()
        self.command_field.setObjectName("cmd_field")
        self.command_field.setFixedWidth(200)
        self.command_field.setFont(QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE))
        self.command_field.setPlaceholderText("Transaction...")
        self.command_field.setStyleSheet(f"""
            QLineEdit {{
                background: white;
                border: 1px solid {SAP.FIELD_BORDER};
                padding: 2px 4px;
            }}
            QLineEdit:focus {{
                border: 1px solid {SAP.FIELD_FOCUS_BORDER};
            }}
        """)
        toolbar.addWidget(self.command_field)

        btn_dropdown = QToolButton()
        btn_dropdown.setObjectName("cmd_dropdown")
        btn_dropdown.setText("▼")
        btn_dropdown.setFixedSize(18, 24)
        toolbar.addWidget(btn_dropdown)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        toolbar_buttons = [
            ("btn_save",    SAP.ICONS["save"],   "Save (Ctrl+S)"),
            ("btn_back",    SAP.ICONS["back"],   "Back (F3)"),
            ("btn_exit",    SAP.ICONS["exit"],   "Exit (Shift+F3)"),
            ("btn_cancel",  SAP.ICONS["cancel"], "Cancel (F12)"),
            None,
            ("btn_print",   SAP.ICONS["print"],  "Print (Ctrl+P)"),
            ("btn_find",    SAP.ICONS["find"],   "Find (Ctrl+F)"),
            None,
            ("btn_first",   SAP.ICONS["first"],  "First Page (Ctrl+Home)"),
            ("btn_prev",    SAP.ICONS["prev"],   "Previous Page (PgUp)"),
            ("btn_next",    SAP.ICONS["next"],   "Next Page (PgDn)"),
            ("btn_last",    SAP.ICONS["last"],   "Last Page (Ctrl+End)"),
            None,
            ("btn_new",     SAP.ICONS["new_session"], "Create Session"),
            ("btn_help",    SAP.ICONS["help"],   "Help (F1)"),
        ]

        for item in toolbar_buttons:
            if item is None:
                toolbar.addSeparator()
            else:
                obj_name, icon_text, tooltip = item
                btn = QToolButton()
                btn.setObjectName(obj_name)
                btn.setText(icon_text)
                btn.setToolTip(tooltip)
                btn.setFixedSize(28, 24)
                toolbar.addWidget(btn)

        return toolbar

    def _connect_toolbar_buttons(self):
        """Connect toolbar buttons after router is initialized."""
        button_actions = {
            "btn_back":   lambda: self.router.go_back(),
            "btn_exit":   lambda: self.router.go_home(),
            "btn_cancel": lambda: self.router.go_home(),
        }
        for obj_name, action in button_actions.items():
            btn = self.findChild(QToolButton, obj_name)
            if btn:
                btn.clicked.connect(action)

    def _create_title_banner(self):
        banner = QFrame()
        banner.setObjectName("header_banner")
        banner.setFixedHeight(40)
        banner.setStyleSheet(f"""
            QFrame#header_banner {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {SAP.BANNER_START}, stop:1 {SAP.BANNER_END});
                border-bottom: 1px solid {SAP.BORDER_COLOR};
            }}
        """)

        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(12, 0, 12, 0)
        title_label = QLabel("GUI Sandbox")
        title_label.setObjectName("header_title")
        font = QFont(SAP.FONT_FAMILY, SAP.FONT_SIZE_BANNER)
        font.setBold(True)
        font.setItalic(True)
        title_label.setFont(font)
        title_label.setStyleSheet("color: #000; border: none; background: transparent;")
        banner_layout.addWidget(title_label)
        return banner

    def _create_secondary_toolbar(self):
        toolbar = QToolBar("Context Toolbar")
        toolbar.setObjectName("toolbar_context")
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setMovable(False)
        toolbar.setStyleSheet(f"""
            QToolBar#toolbar_context {{
                background-color: {SAP.TOOLBAR_BG};
                border-top: 1px solid #B3C0CF;
                border-bottom: 1px solid {SAP.BORDER_COLOR};
                min-height: 28px;
            }}
        """)
        return toolbar


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(sap_global_stylesheet())

    parser = argparse.ArgumentParser(description="GUI Sandbox: an SAP GUI scripting simulator")
    parser.add_argument("--env", metavar="ID",
                        help="open this environment directly (for example WL or NL) instead of the SAP Logon pad")
    parser.add_argument("--no-logon", action="store_true", help="same as --env NL")
    args, _qt_args = parser.parse_known_args()

    environments = load_environments()
    env_name = "NL" if args.no_logon else args.env
    start_env = find_environment(environments, env_name) if env_name else None
    if env_name and start_env is None:
        known = ", ".join(env.id for env in environments)
        parser.error(f"unknown environment {env_name!r}; choose one of {known}")

    main_win = MainWindow()

    def open_connection(description):
        """OpenConnection from a script: open the entry on the GUI thread and wait."""
        env = find_environment(environments, description)
        if env is None:
            return None
        return gui_thread.invoker().call(lambda: main_win.open_environment(env))

    com_bridge = ComBridge(opener=open_connection)
    try:
        com_bridge.start()
        main_win.com_bridge = com_bridge
        print("COM bridge started — GetObject(\"SAPGUI\") is available")
    except Exception as exc:
        print(f"COM bridge failed to start: {exc}")
        com_bridge = None

    atexit.register(lambda: com_bridge.stop() if com_bridge else None)

    if start_env:
        main_win.open_environment(start_env)
    else:
        main_win.logon_pad = LogonPad(environments, on_open=main_win.open_environment)
        main_win.logon_pad.show()

    sys.exit(app.exec())
