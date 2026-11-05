# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""End-to-end integration tests for the GUI Sandbox.

Tests full flows: MainWindow → TransactionRouter → ScreenRenderer → widgets.
Covers navigation, transaction flows, toolbar buttons, and session manager.
"""
import pytest
from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QToolButton, QTreeWidget, QTableView,
    QPlainTextEdit, QToolBar, QSplitter,
)

from ui.transaction_router import TransactionRouter, TRANSACTIONS, SCREEN_DIR


# ── Transaction Router (headless, no Qt) ──────────────────────────────────────

class TestTransactionRouterNavigation:
    """Tests for TransactionRouter without full MainWindow rendering."""

    @pytest.fixture
    def router(self, main_window):
        return main_window.router

    def test_navigate_se16(self, router):
        session = router.navigate("SE16")
        assert session is not None
        assert router.current_tcode == "SE16"
        assert router._current_step == 0

    def test_navigate_se38(self, router):
        session = router.navigate("SE38")
        assert session is not None
        assert router.current_tcode == "SE38"

    def test_navigate_unknown(self, router):
        session = router.navigate("ZZ_FAKE")
        assert session is None

    def test_navigate_case_insensitive(self, router):
        session = router.navigate("se16")
        assert session is not None
        assert router.current_tcode == "SE16"

    def test_handle_command_slash_n(self, router):
        session = router.handle_command("/nSE16")
        assert session is not None
        assert router.current_tcode == "SE16"

    def test_handle_command_slash_o(self, router):
        session = router.handle_command("/oSE38")
        assert session is not None
        assert router.current_tcode == "SE38"

    def test_handle_command_bare_tcode(self, router):
        session = router.handle_command("SU01")
        assert session is not None
        assert router.current_tcode == "SU01"

    def test_handle_command_slash_n_alone_goes_home(self, router):
        router.navigate("SE16")
        session = router.handle_command("/n")
        assert session is not None
        assert router.current_tcode == "SESSION_MANAGER"

    def test_handle_command_empty(self, router):
        session = router.handle_command("")
        assert session is None

    def test_available_transactions(self):
        tcodes = TransactionRouter.available_transactions()
        assert "SE16" in tcodes
        assert "SE38" in tcodes
        assert "SU01" in tcodes
        assert "SESSION_MANAGER" in tcodes


# ── Transaction Flows ─────────────────────────────────────────────────────────

class TestSE16Flow:
    """SE16 has 3 steps: initial → selection → results."""

    @pytest.fixture
    def router(self, main_window):
        return main_window.router

    def test_se16_initial_screen(self, router):
        session = router.navigate("SE16")
        assert router._current_step == 0
        wnd = session.get_window(0)
        assert wnd is not None
        assert wnd.user_area is not None

    def test_se16_next_step_to_selection(self, router):
        router.navigate("SE16")
        session = router.next_step()
        assert session is not None
        assert router._current_step == 1

    def test_se16_next_step_to_results(self, router):
        router.navigate("SE16")
        router.next_step()
        session = router.next_step()
        assert session is not None
        assert router._current_step == 2

    def test_se16_no_step_beyond_last(self, router):
        router.navigate("SE16")
        router.next_step()
        router.next_step()
        session = router.next_step()
        assert session is None

    def test_se16_go_back_from_results(self, router):
        router.navigate("SE16")
        router.next_step()
        router.next_step()
        assert router._current_step == 2
        session = router.go_back()
        assert session is not None
        assert router._current_step == 1

    def test_se16_go_back_to_home_from_initial(self, router):
        router.navigate("SE16")
        assert router._current_step == 0
        router.go_back()
        assert router.current_tcode == "SESSION_MANAGER"


class TestSE38Flow:
    """SE38 has 3 steps: initial → source → attributes."""

    @pytest.fixture
    def router(self, main_window):
        return main_window.router

    def test_se38_full_flow(self, router):
        router.navigate("SE38")
        assert router._current_step == 0

        session = router.next_step()
        assert session is not None
        assert router._current_step == 1

        session = router.next_step()
        assert session is not None
        assert router._current_step == 2


class TestSE16NFlow:
    """SE16N has 2 steps: initial → selection."""

    @pytest.fixture
    def router(self, main_window):
        return main_window.router

    def test_se16n_flow(self, router):
        router.navigate("SE16N")
        assert router._current_step == 0

        session = router.next_step()
        assert session is not None
        assert router._current_step == 1

        session = router.next_step()
        assert session is None


class TestSU01Flow:
    """SU01 has 1 step (initial only)."""

    @pytest.fixture
    def router(self, main_window):
        return main_window.router

    def test_su01_single_step(self, router):
        router.navigate("SU01")
        assert router._current_step == 0
        session = router.next_step()
        assert session is None


# ── MainWindow Integration ────────────────────────────────────────────────────

class TestMainWindowSetup:
    def test_window_created(self, main_window):
        assert main_window.windowTitle() == "GUI Sandbox"

    def test_command_field_exists(self, main_window):
        cmd = main_window.findChild(QLineEdit, "cmd_field")
        assert cmd is not None

    def test_main_toolbar_exists(self, main_window):
        tb = main_window.findChild(QToolBar, "toolbar_main")
        assert tb is not None

    def test_context_toolbar_exists(self, main_window):
        tb = main_window.findChild(QToolBar, "toolbar_context")
        assert tb is not None

    def test_workspace_panel_exists(self, main_window):
        wp = main_window.findChild(QWidget, "workspace_panel")
        assert wp is not None

    def test_status_bar_exists(self, main_window):
        assert main_window.statusBar() is not None

    def test_nav_buttons_exist(self, main_window):
        for name in ["btn_back", "btn_exit", "btn_cancel",
                      "btn_save", "btn_print", "btn_find"]:
            btn = main_window.findChild(QToolButton, name)
            assert btn is not None, f"Missing button: {name}"


class TestToolbarNavigation:
    """Test that Back/Exit/Cancel toolbar buttons work."""

    def test_back_button_goes_back(self, main_window):
        main_window.router.navigate("SE16")
        main_window.router.next_step()
        assert main_window.router._current_step == 1
        btn = main_window.findChild(QToolButton, "btn_back")
        btn.click()
        assert main_window.router._current_step == 0

    def test_back_button_goes_home_from_initial(self, main_window):
        main_window.router.navigate("SE16")
        assert main_window.router._current_step == 0
        btn = main_window.findChild(QToolButton, "btn_back")
        btn.click()
        assert main_window.router.current_tcode == "SESSION_MANAGER"

    def test_exit_button_goes_home(self, main_window):
        main_window.router.navigate("SE38")
        btn = main_window.findChild(QToolButton, "btn_exit")
        btn.click()
        assert main_window.router.current_tcode == "SESSION_MANAGER"

    def test_cancel_button_goes_home(self, main_window):
        main_window.router.navigate("SU01")
        btn = main_window.findChild(QToolButton, "btn_cancel")
        btn.click()
        assert main_window.router.current_tcode == "SESSION_MANAGER"


class TestCommandFieldNavigation:
    """Test that typing in the command field navigates."""

    def test_command_field_navigates(self, main_window):
        cmd = main_window.findChild(QLineEdit, "cmd_field")
        cmd.setText("SE16")
        cmd.returnPressed.emit()
        assert main_window.router.current_tcode == "SE16"

    def test_command_field_slash_n(self, main_window):
        cmd = main_window.findChild(QLineEdit, "cmd_field")
        cmd.setText("/nSE38")
        cmd.returnPressed.emit()
        assert main_window.router.current_tcode == "SE38"

    def test_command_field_clears_after_enter(self, main_window):
        cmd = main_window.findChild(QLineEdit, "cmd_field")
        cmd.setText("SE16")
        cmd.returnPressed.emit()
        assert cmd.text() == ""


# ── Screen Rendering ──────────────────────────────────────────────────────────

class TestSessionManagerRendering:
    """Test that the session manager home screen renders correctly."""

    def test_home_screen_has_nav_tree(self, main_window):
        main_window.router.go_home()
        tree = main_window.findChild(QTreeWidget, "nav_tree")
        assert tree is not None

    def test_home_screen_has_splitter(self, main_window):
        main_window.router.go_home()
        splitter = main_window.findChild(QSplitter, "home_splitter")
        assert splitter is not None

    def test_home_nav_tree_has_categories(self, main_window):
        main_window.router.go_home()
        tree = main_window.findChild(QTreeWidget, "nav_tree")
        top_items = [tree.topLevelItem(i).text(0)
                     for i in range(tree.topLevelItemCount())]
        assert "Favorites" in top_items
        assert "Main Menu" in top_items


class TestTransactionScreenRendering:
    """Test that transaction screens render with correct widgets."""

    def test_se16_initial_has_fields(self, main_window):
        main_window.router.navigate("SE16")
        workspace = main_window.findChild(QWidget, "workspace_panel")
        fields = workspace.findChildren(QLineEdit)
        assert len(fields) >= 1, "SE16 initial should have text fields"

    def test_se16_results_has_grid(self, main_window):
        main_window.router.navigate("SE16")
        main_window.router.next_step()
        main_window.router.next_step()
        workspace = main_window.findChild(QWidget, "workspace_panel")
        tables = workspace.findChildren(QTableView)
        assert len(tables) >= 1, "SE16 results should have a grid/table"

    def test_se38_source_has_editor(self, main_window):
        main_window.router.navigate("SE38")
        main_window.router.next_step()
        workspace = main_window.findChild(QWidget, "workspace_panel")
        editors = workspace.findChildren(QPlainTextEdit)
        assert len(editors) >= 1, "SE38 source should have an ABAP editor"

    def test_se38_initial_has_radio_buttons(self, main_window):
        from PySide6.QtWidgets import QRadioButton as QtRadioButton
        main_window.router.navigate("SE38")
        workspace = main_window.findChild(QWidget, "workspace_panel")
        radios = workspace.findChildren(QtRadioButton)
        assert len(radios) >= 4, "SE38 initial should have radio buttons"

    def test_banner_updates_on_navigate(self, main_window):
        main_window.router.navigate("SE16")
        banner = main_window.findChild(QLabel, "header_title")
        assert banner is not None
        assert banner.text() != ""

    def test_context_toolbar_populated(self, main_window):
        main_window.router.navigate("SE16")
        ctx_tb = main_window.findChild(QToolBar, "toolbar_context")
        buttons = ctx_tb.findChildren(QToolButton)
        assert len(buttons) >= 1, "Context toolbar should have buttons"


class TestNavigateCallback:
    """Test that the navigate callback fires."""

    def test_callback_called(self, main_window):
        calls = []
        main_window.router.set_navigate_callback(
            lambda session, tcode: calls.append(tcode)
        )
        main_window.router.navigate("SE16")
        assert "SE16" in calls

    def test_callback_updates_title(self, main_window):
        main_window.router.navigate("SE16")
        assert "SE16" in main_window.windowTitle()


# ── Flow Button Wiring ────────────────────────────────────────────────────────

class TestFlowButtonWiring:
    """Test that _wire_flow_buttons connects advance/back handlers."""

    def test_se16_initial_has_advance_button(self, main_window):
        session = main_window.router.navigate("SE16")
        wnd = session.get_window(0)
        advance_wired = False
        for ctrl in wnd.all_controls():
            if "press" in ctrl.events:
                advance_wired = True
                break
        assert advance_wired, "SE16 initial should have at least one wired button"

    def test_se16_advance_button_changes_step(self, main_window):
        session = main_window.router.navigate("SE16")
        wnd = session.get_window(0)
        for ctrl in wnd.all_controls():
            tooltip = (ctrl.tooltip or "").lower()
            if "(f7)" in tooltip or "table contents" in tooltip:
                ctrl.press()
                break
        assert main_window.router._current_step == 1


# ── All Screens Load & Render ─────────────────────────────────────────────────

class TestAllTransactionsRender:
    """Smoke test: every transaction in the registry renders without error."""

    @pytest.mark.parametrize("tcode", sorted(TRANSACTIONS.keys()))
    def test_transaction_renders(self, main_window, tcode):
        screens = TRANSACTIONS[tcode]
        first_screen = SCREEN_DIR / screens[0]
        if not first_screen.exists():
            pytest.skip(f"Screen file missing: {screens[0]}")
        session = main_window.router.navigate(tcode)
        assert session is not None, f"Failed to navigate to {tcode}"

    @pytest.mark.parametrize("tcode", ["SE16", "SE38"])
    def test_full_flow_renders(self, main_window, tcode):
        """Navigate through all steps of a multi-step transaction."""
        main_window.router.navigate(tcode)
        screens = TRANSACTIONS[tcode]
        for i in range(1, len(screens)):
            path = SCREEN_DIR / screens[i]
            if not path.exists():
                pytest.skip(f"Missing: {screens[i]}")
            session = main_window.router.next_step()
            assert session is not None, f"Step {i} of {tcode} failed"


# ── Screen Renderer Clear ────────────────────────────────────────────────────

class TestRendererClear:
    """Test that switching screens properly clears previous content."""

    def test_switch_from_se16_to_se38(self, main_window):
        main_window.router.navigate("SE16")
        main_window.router.navigate("SE38")
        assert main_window.router.current_tcode == "SE38"

    def test_switch_to_home_clears_transaction(self, main_window):
        main_window.router.navigate("SE16")
        main_window.router.go_home()
        assert main_window.router.current_tcode == "SESSION_MANAGER"
        tree = main_window.findChild(QTreeWidget, "nav_tree")
        assert tree is not None
