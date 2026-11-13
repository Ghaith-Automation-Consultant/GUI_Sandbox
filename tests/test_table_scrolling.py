# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""Table control and ALV grid scrolling, the way scripts meet it in a real system.

A table control only has cells for its visible rows; scrolling is a round trip
after which the script finds the table again. An ALV grid scrolls on the client
and, with lazy loading, only knows the rows that have been on screen.
"""
import pytest
from PySide6.QtWidgets import QTableView

from bridge import RemoteSession, SandboxSession, start_server
from engine import load_screen
from engine.navigation import SCREEN_DIR

from .test_navigation import run_in_thread

TABLE = "wnd[0]/usr/tabsTAXI_TABSTRIP/tabpT02/tblITEMS"
GRID = "wnd[0]/usr/cntlGRID1/shellcont/shell"
ITEMS = [str(10 * (i + 1)) for i in range(25)]


def home():
    return load_screen(SCREEN_DIR / "01_SESSION_MANAGER.json")


def flight_rows():
    """Every SFLIGHT row, read from the screen file, loaded or not."""
    return load_screen(SCREEN_DIR / "04_SE16_SFLIGHT_results.json").findById(GRID).rows


def open_order(session):
    session.StartTransaction("VA03")
    session.findById("wnd[0]").sendVKey(0)
    return session


def open_flights(session):
    session.StartTransaction("SE16")
    session.findById("wnd[0]").sendVKey(7)
    session.findById("wnd[0]").sendVKey(8)
    return session


def read_all_items(session):
    """The classic script: page through the table, finding it again after each scroll."""
    table = session.findById(TABLE)
    total, page = table.RowCount, table.VisibleRowCount
    values = []
    for start in range(0, total, page):
        table.VerticalScrollbar.Position = start
        table = session.findById(TABLE)
        for row in range(min(page, total - start)):
            values.append(table.GetCell(row, 0).Text)
    return values


# ── Table control, in-process ────────────────────────────────────────────────

class TestTableControl:
    @pytest.fixture
    def session(self):
        return open_order(SandboxSession(home()))

    def test_sizes_and_scrollbar(self, session):
        table = session.findById(TABLE)
        assert table.RowCount == 25
        assert table.VisibleRowCount == 9
        bar = table.VerticalScrollbar
        assert (bar.Minimum, bar.Maximum, bar.PageSize, bar.Position) == (0, 24, 9, 0)

    def test_cells_have_sap_ids(self, session):
        cell = session.findById(f"{TABLE}/txtVBAP-POSNR[0,0]")
        assert cell.Text == "10"
        material = session.findById(f"{TABLE}/ctxtVBAP-MATNR[1,2]")
        assert material.Type == "GuiCTextField"
        assert session.findById(TABLE).GetCell(2, 1).Id == material.Id

    def test_rows_below_the_screen_do_not_exist(self, session):
        with pytest.raises(RuntimeError):
            session.findById(f"{TABLE}/txtVBAP-POSNR[0,9]")
        with pytest.raises(RuntimeError, match="visible area"):
            session.findById(TABLE).GetCell(9, 0)

    def test_paging_reads_every_row(self, session):
        assert read_all_items(session) == ITEMS

    def test_reading_without_scrolling_misses_rows(self, session):
        """What passes on a short dev table and fails on QA data."""
        table = session.findById(TABLE)
        with pytest.raises(RuntimeError):
            [table.GetCell(row, 0).Text for row in range(table.RowCount)]

    def test_scroll_makes_old_references_stale(self, session):
        table = session.findById(TABLE)
        cell = table.GetCell(0, 0)
        bar = table.VerticalScrollbar
        table.VerticalScrollbar.Position = 9
        for stale in (lambda: table.RowCount, lambda: cell.Text, lambda: bar.Position):
            with pytest.raises(RuntimeError, match="find it again"):
                stale()
        assert session.findById(TABLE).GetCell(0, 0).Text == "100"
        assert session.findById(f"{TABLE}/txtVBAP-POSNR[0,0]").Text == "100"

    def test_position_out_of_range(self, session):
        with pytest.raises(RuntimeError, match="out of range"):
            session.findById(TABLE).VerticalScrollbar.Position = 25

    def test_last_page_has_empty_rows(self, session):
        session.findById(TABLE).VerticalScrollbar.Position = 24
        table = session.findById(TABLE)
        assert table.GetCell(0, 0).Text == "250"
        assert table.GetCell(1, 0).Text == ""
        assert not table.GetCell(1, 0).Changeable

    def test_edits_survive_scrolling(self, session):
        session.findById(TABLE).VerticalScrollbar.Position = 18
        session.findById(TABLE).GetCell(2, 2).Text = "99"   # item 210
        session.findById(TABLE).VerticalScrollbar.Position = 0
        session.findById(TABLE).VerticalScrollbar.Position = 20
        assert session.findById(TABLE).GetCell(0, 2).Text == "99"

    def test_rows_and_selection(self, session):
        table = session.findById(TABLE)
        assert table.Rows.Count == 9
        assert table.Rows(1).Item(0).Text == "20"
        table.GetAbsoluteRow(20).Selected = True
        table = session.findById(TABLE)
        assert table.GetAbsoluteRow(20).Selected
        assert not table.Rows(0).Selected
        table.VerticalScrollbar.Position = 18
        assert session.findById(TABLE).Rows(2).Selected

    def test_names_ignore_case_as_in_com(self, session):
        session.findById(TABLE).verticalScrollbar.position = 9
        assert session.findById(TABLE).getCell(0, 0).text == "100"


# ── ALV grid, in-process ─────────────────────────────────────────────────────

class TestGrid:
    @pytest.fixture
    def session(self):
        return open_flights(SandboxSession(home()))

    def test_sizes(self, session):
        grid = session.findById(GRID)
        assert grid.RowCount == 120
        assert grid.VisibleRowCount == 24
        assert grid.FirstVisibleRow == 0

    def test_rows_never_shown_read_empty(self, session):
        """Lazy loading: the trap of reading a big grid without scrolling."""
        rows = flight_rows()
        grid = session.findById(GRID)
        assert grid.GetCellValue(5, "CONNID") == rows[5]["CONNID"]
        assert grid.GetCellValue(100, "CONNID") == ""
        grid.FirstVisibleRow = 96
        assert grid.GetCellValue(100, "CONNID") == rows[100]["CONNID"]
        assert grid.FirstVisibleRow == 96            # the grid reference stays valid

    def test_set_current_cell_scrolls_into_view(self, session):
        grid = session.findById(GRID)
        grid.SetCurrentCell(110, "CONNID")
        assert (grid.CurrentCellRow, grid.CurrentCellColumn) == (110, "CONNID")
        assert grid.FirstVisibleRow == 110
        assert grid.GetCellValue(110, "CONNID") == flight_rows()[110]["CONNID"]

    def test_selected_rows(self, session):
        grid = session.findById(GRID)
        grid.SelectedRows = "0,2-4,7"
        assert grid.SelectedRows == "0,2-4,7"

    def test_bad_row_or_column_raises(self, session):
        grid = session.findById(GRID)
        with pytest.raises(RuntimeError):
            grid.GetCellValue(120, "CARRID")
        with pytest.raises(RuntimeError):
            grid.GetCellValue(0, "NOPE")
        with pytest.raises(RuntimeError):
            grid.FirstVisibleRow = 500


# ── COM wrappers, called the way VBScript does ───────────────────────────────

class TestCom:
    @pytest.fixture
    def session(self):
        win32com_client = pytest.importorskip("win32com.client")
        from bridge.com_server import ComSession, SessionHolder, _wrap
        from engine.navigation import Navigator
        holder = SessionHolder(open_order(SandboxSession(home())).session)
        # The app's ComBridge follows navigation the same way.
        Navigator.for_session(holder.session).subscribe(
            lambda session, _tcode: setattr(holder, "session", session))
        return win32com_client.Dispatch(_wrap(ComSession(holder)))

    def test_paging_over_com(self, session):
        assert read_all_items(session) == ITEMS

    def test_stale_table_raises_com_error(self, session):
        import pywintypes
        table = session.findById(TABLE)
        table.VerticalScrollbar.Position = 9
        with pytest.raises(pywintypes.com_error):
            table.GetCell(0, 0)
        assert session.findById(TABLE).GetCell(0, 0).Text == "100"

    def test_rows_and_absolute_row(self, session):
        from .test_com_collections import vbs_index
        table = session.findById(TABLE)
        assert vbs_index(table, "Rows", 1).Item(0).Text == "20"
        row = table.GetAbsoluteRow(3)
        row.Selected = True
        assert session.findById(TABLE).GetAbsoluteRow(3).Selected

    def test_grid_over_com(self, session):
        session.StartTransaction("SE16")
        session.findById("wnd[0]").sendVKey(7)
        session.findById("wnd[0]").sendVKey(8)
        grid = session.findById(GRID)
        assert grid.GetCellValue(100, "CARRID") == ""
        grid.FirstVisibleRow = 100
        assert grid.GetCellValue(100, "CARRID") == flight_rows()[100]["CARRID"]
        grid.SetCurrentCell(5, "PRICE")
        assert grid.CurrentCellRow == 5 and grid.FirstVisibleRow == 5


# ── HTTP bridge ──────────────────────────────────────────────────────────────

class TestHttp:
    @pytest.fixture
    def remote(self):
        server = start_server(home(), port=0)
        yield RemoteSession(server.url)
        server.shutdown()
        server.server_close()

    def test_paging_over_http(self, remote):
        open_order(remote)
        assert read_all_items(remote) == ITEMS

    def test_row_outside_the_screen_is_refused(self, remote):
        open_order(remote)
        with pytest.raises(RuntimeError, match="visible area"):
            remote.findById(TABLE).GetCellValue(9, 0)

    def test_grid_over_http(self, remote):
        open_flights(remote)
        grid = remote.findById(GRID)
        assert grid.GetCellValue(100, "CARRID") == ""
        grid.FirstVisibleRow = 96
        assert grid.FirstVisibleRow == 96
        assert grid.GetCellValue(100, "CARRID") == flight_rows()[100]["CARRID"]
        grid.SelectedRows = "1-3"
        assert grid.SelectedRows == "1-3"


# ── The live window follows, and drives, the engine ──────────────────────────

class TestLiveWindow:
    @pytest.fixture
    def ready(self, qapp, main_window):
        main_window.load_initial_screen()
        return main_window

    def _view(self, window, object_name):
        return window.findChild(QTableView, object_name)

    def test_script_scroll_updates_the_table(self, qapp, ready):
        nav = ready.router.navigator
        run_in_thread(qapp, lambda: open_order(SandboxSession(nav.session)))
        table = nav.session.findById(TABLE)
        view = self._view(ready, table.id)
        assert view.model().rowCount() == 9
        assert view.model().item(0, 0).text() == "10"

        run_in_thread(qapp, lambda: setattr(table.vertical_scrollbar, "position", 9))
        qapp.processEvents()
        assert view.model().item(0, 0).text() == "100"
        assert view.pager.value() == 9

    def test_user_scroll_moves_the_engine(self, qapp, ready):
        nav = ready.router.navigator
        open_order(SandboxSession(nav.session))
        table = nav.session.findById(TABLE)
        view = self._view(ready, table.id)
        view.pager.setValue(18)
        qapp.processEvents()
        assert table.position == 18
        assert nav.session.findById(f"{TABLE}/txtVBAP-POSNR[0,0]").text == "190"
        assert view.model().item(0, 0).text() == "190"

    def test_script_grid_scroll_moves_the_view(self, qapp, ready):
        nav = ready.router.navigator
        run_in_thread(qapp, lambda: open_flights(SandboxSession(nav.session)))
        grid = nav.session.findById(GRID)
        view = self._view(ready, grid.id)
        run_in_thread(qapp, lambda: setattr(grid, "first_visible_row", 60))
        qapp.processEvents()
        assert view.verticalScrollBar().value() == 60
        view.verticalScrollBar().setValue(80)
        qapp.processEvents()
        assert grid.first_visible_row == 80
