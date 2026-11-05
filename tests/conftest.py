# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for the GUI Sandbox test suite."""
import sys
import pytest
from pathlib import Path

# Ensure the project root is on the path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def qapp():
    """Create a single QApplication for the entire test session."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        app.setStyle("Fusion")
    yield app


@pytest.fixture
def main_window(qapp):
    """Create a fresh MainWindow for each test."""
    from main import MainWindow
    win = MainWindow()
    yield win
    win.close()
    win.deleteLater()
