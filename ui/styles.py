# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
SAP Blue Crystal theme constants and stylesheet generation.
"""


class SAP:
    """Color palette and font specs."""

    # Backgrounds
    MENU_BG         = "#E6EEF7"
    TOOLBAR_BG      = "#D5DEE8"
    BANNER_START    = "#DCE6F2"
    BANNER_END      = "#B7C9DC"
    PANEL_BG        = "#F4F6F9"
    SELECTED_BG     = "#C7D6EA"
    CONTENT_BG      = "#FFFFFF"

    # Borders
    BORDER_COLOR    = "#9FB2C6"

    # Fields
    FIELD_BORDER    = "#A0B0C0"
    FIELD_REQUIRED_BORDER = "#E8A000"
    FIELD_FOCUS_BORDER    = "#4A90D9"
    FIELD_TEXT_COLOR      = "#000000"
    FIELD_READONLY_BG     = "#EEF2F6"

    # Labels
    LABEL_COLOR     = "#333333"

    # Status bar
    STATUS_SUCCESS  = "#2E7D32"
    STATUS_WARNING  = "#F9A825"
    STATUS_ERROR    = "#C62828"
    STATUS_INFO     = "#1565C0"

    # Fonts (pt for QFont, px for stylesheets — 9pt ≈ 12px at 96dpi)
    FONT_FAMILY     = "Segoe UI"
    FONT_SIZE       = 9       # point size for QFont()
    FONT_SIZE_PX    = 12      # pixel size for stylesheets
    FONT_SIZE_BANNER = 11     # point size for QFont()
    FONT_SIZE_BANNER_PX = 14  # pixel size for stylesheets

    # Toolbar icons (Unicode approximations of SAP icons)
    ICONS = {
        "enter":      "✔",   # ✔ green check
        "save":       "\U0001F4BE",  # 💾
        "back":       "←",   # ←
        "exit":       "✖",   # ✖
        "cancel":     "❌",   # ❌
        "print":      "\U0001F5A8",  # 🖨
        "find":       "\U0001F50D",  # 🔍
        "first":      "⏮",   # ⏮
        "prev":       "◀",   # ◀
        "next":       "▶",   # ▶
        "last":       "⏭",   # ⏭
        "new_session": "➕",  # ➕
        "help":       "❓",   # ❓
        "execute":    "⏵",   # ⏵ (F8)
    }


def sap_global_stylesheet() -> str:
    """Return the global application stylesheet."""
    return f"""
        QMainWindow {{
            background-color: {SAP.MENU_BG};
        }}

        QMenuBar {{
            background-color: {SAP.MENU_BG};
            border-bottom: 1px solid {SAP.BORDER_COLOR};
            font-family: "{SAP.FONT_FAMILY}";
            font-size: {SAP.FONT_SIZE}pt;
            padding: 1px;
        }}
        QMenuBar::item {{
            padding: 3px 8px;
            background: transparent;
        }}
        QMenuBar::item:selected {{
            background: {SAP.SELECTED_BG};
        }}
        QMenu {{
            background: {SAP.MENU_BG};
            border: 1px solid {SAP.BORDER_COLOR};
            font-family: "{SAP.FONT_FAMILY}";
            font-size: {SAP.FONT_SIZE}pt;
        }}
        QMenu::item:selected {{
            background: {SAP.SELECTED_BG};
        }}

        QToolBar {{
            background-color: {SAP.TOOLBAR_BG};
            border: none;
            border-bottom: 1px solid {SAP.BORDER_COLOR};
            spacing: 2px;
            padding: 2px 4px;
        }}
        QToolButton {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 2px;
            padding: 2px 4px;
            font-family: "{SAP.FONT_FAMILY}";
            font-size: {SAP.FONT_SIZE}pt;
        }}
        QToolButton:hover {{
            background: {SAP.SELECTED_BG};
            border: 1px solid {SAP.BORDER_COLOR};
        }}
        QToolButton:pressed {{
            background: {SAP.BORDER_COLOR};
        }}

        QStatusBar {{
            background-color: {SAP.TOOLBAR_BG};
            border-top: 1px solid {SAP.BORDER_COLOR};
            font-family: "{SAP.FONT_FAMILY}";
            font-size: {SAP.FONT_SIZE}pt;
        }}

        QSplitter::handle {{
            background: {SAP.BORDER_COLOR};
            width: 3px;
        }}

        QScrollBar:vertical {{
            background: {SAP.PANEL_BG};
            width: 14px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {SAP.BORDER_COLOR};
            min-height: 20px;
            border-radius: 3px;
            margin: 2px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {SAP.PANEL_BG};
            height: 14px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {SAP.BORDER_COLOR};
            min-width: 20px;
            border-radius: 3px;
            margin: 2px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
    """
