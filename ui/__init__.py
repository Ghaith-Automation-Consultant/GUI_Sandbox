# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer A — Dynamic UI rendering: maps Layer B control trees to PySide6 widgets.
"""
from .screen_renderer import ScreenRenderer
from .transaction_router import TransactionRouter

__all__ = ["ScreenRenderer", "TransactionRouter"]
