# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""
Layer B — SE16 transaction: Data Browser.

Covers the three screens of a typical SE16 flow:
  1. SE16InitialScreen  — enter a table name
  2. SE16SelectionScreen — filter fields (generic, populated from a column list)
  3. SE16ResultsScreen  — ALV grid with results
"""
from __future__ import annotations

from engine.control import (
    Label, ComboTextField, TextField, GridView,
)
from .base import BaseTransaction, _WND0_ID


class SE16InitialScreen(BaseTransaction):
    """
    SE16 — Data Browser: Initial screen.

    The user types a table name into ctxtDATABROWSE-TABLENAME and presses Enter.

    Control IDs (from screens/02_SE16_initial.json):
        wnd[0]/usr/lblDATABROWSE-TABLENAME  — label "Nom de table"
        wnd[0]/usr/ctxtDATABROWSE-TABLENAME — ComboTextField (table name input)
    """

    tcode = "SE16"
    title = "Data Browser: Initial Screen"

    def _build(self) -> None:
        usr_id = f"{_WND0_ID}/usr"

        self.usr.add_child(Label(
            f"{usr_id}/lblDATABROWSE-TABLENAME",
            name="lblDATABROWSE-TABLENAME",
            text="Nom de table",
        ))
        self.usr.add_child(ComboTextField(
            f"{usr_id}/ctxtDATABROWSE-TABLENAME",
            name="ctxtDATABROWSE-TABLENAME",
            text="",
            tooltip="Nom de table",
            changeable=True,
            required=True,
            max_length=16,
        ))


class SE16SelectionScreen(BaseTransaction):
    """
    SE16 — selection screen for a given table.

    Columns are derived from the table's fields; each becomes a pair of
    range-low / range-high TextField controls, mirroring the real SAP layout.

    Usage::

        screen = SE16SelectionScreen("SFLIGHT", columns=["CARRID", "CONNID", "FLDATE"])
        field = screen.find("wnd[0]/usr/txtSFLIGHT-CARRID_LOW")
        field.value = "SX"
        screen.send_vkey(8)   # F8 = Execute
    """

    tcode = "SE16"

    def __init__(self, table_name: str, columns: list[str] | None = None) -> None:
        self.table_name   = table_name
        self._columns_in  = columns or []
        super().__init__()

    @property
    def title(self) -> str:  # type: ignore[override]
        return f"Data Browser: Table {self.table_name}: Selection Screen"

    def _build(self) -> None:
        usr_id = f"{_WND0_ID}/usr"

        # Max-entries field (always present)
        self.usr.add_child(Label(
            f"{usr_id}/lblMAX_SEL",
            name="lblMAX_SEL",
            text="Nombre max de lignes",
        ))
        self.usr.add_child(TextField(
            f"{usr_id}/txtMAX_SEL",
            name="txtMAX_SEL",
            text="500",
            changeable=True,
            max_length=7,
        ))

        # One low/high pair per column
        for col in self._columns_in:
            col_up = col.upper()
            self.usr.add_child(Label(
                f"{usr_id}/lbl{self.table_name}-{col_up}",
                name=f"lbl{self.table_name}-{col_up}",
                text=col_up,
            ))
            self.usr.add_child(TextField(
                f"{usr_id}/txt{self.table_name}-{col_up}_LOW",
                name=f"txt{self.table_name}-{col_up}_LOW",
                text="",
                changeable=True,
            ))
            self.usr.add_child(TextField(
                f"{usr_id}/txt{self.table_name}-{col_up}_HIGH",
                name=f"txt{self.table_name}-{col_up}_HIGH",
                text="",
                changeable=True,
            ))


class SE16ResultsScreen(BaseTransaction):
    """
    SE16 — results screen with an ALV grid.

    Usage::

        screen = SE16ResultsScreen(
            "SFLIGHT",
            columns=[{"name": "CARRID", "title": "Airline"}, ...],
            rows=[{"CARRID": "SX", ...}, ...],
            total_records=1_000,
        )
        grid = screen.find("wnd[0]/usr/cntlGRID1/shellcont/shell")
        print(grid.row_count)
    """

    tcode = "SE16"

    def __init__(
        self,
        table_name: str,
        columns: list[dict] | None = None,
        rows: list[dict] | None = None,
        total_records: int = 0,
        max_rows: int = 500,
    ) -> None:
        self.table_name    = table_name
        self._cols         = columns or []
        self._rows         = rows or []
        self.total_records = total_records
        self.max_rows      = max_rows
        super().__init__()

    @property
    def title(self) -> str:  # type: ignore[override]
        displayed = len(self._rows)
        return f"Affichage : {displayed:>12} de {self.total_records:>30} occurrences"

    def _build(self) -> None:
        usr_id   = f"{_WND0_ID}/usr"
        grid_id  = f"{usr_id}/cntlGRID1/shellcont/shell"

        grid = GridView(grid_id, name="shell", columns=self._cols)
        for row in self._rows:
            grid.add_row(row)

        # SAP wraps the grid in a ContainerShell hierarchy
        from engine.control import Container
        shell1 = Container(f"{usr_id}/cntlGRID1", name="cntlGRID1")
        shell2 = Container(f"{usr_id}/cntlGRID1/shellcont", name="shellcont")
        shell2.add_child(grid)
        shell1.add_child(shell2)
        self.usr.add_child(shell1)

        # Status bar message
        if self._rows:
            msg = f"Selection limited to {self.max_rows} entries"
            self.session.set_status(msg, "W")
