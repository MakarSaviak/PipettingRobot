from __future__ import annotations

from pathlib import Path
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Border, Side, Alignment, PatternFill, Font
from openpyxl.utils import get_column_letter

from .PipetG import PipetG
from .Rack import Rack


class InputXlsx(BaseModel):
    pipet: PipetG = Field(exclude=True)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Light fills (ARGB)
    _VIAL_FILL = PatternFill(fill_type="solid", fgColor="FFDDEBF7")     # light blue
    _SOLVENT_FILL = PatternFill(fill_type="solid", fgColor="FFFCE4D6")  # light orange

    # Simple visible borders
    _THIN = Side(style="thin")
    _BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

    _CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
    _BOLD = Font(bold=True)
    _NOFILL = PatternFill()

    def create_empty_table(self, out_path: Union[str, Path]) -> Path:
        """
        Create an Excel workbook formatted for the racks in pipet.setup.
        - For each rack: sheets <rack.name>_vials and <rack.name>_solvents
        - Vials: filled with indices (columnwise), blue
        - Solvents: empty cells but with index in comment, orange
        """
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        # remove default sheet
        wb.remove(wb.active)

        racks = self.pipet.setup.racks
        if not racks:
            raise ValueError("No racks in setup; cannot create Excel template.")

        for rack in racks:
            self._add_rack_sheets(wb, rack)

        wb.save(path)
        return path

    # ----------------- internals -----------------

    def _add_rack_sheets(self, wb: Workbook, rack: Rack) -> None:
        vials_name = f"{rack.name}_vials"
        solvents_name = f"{rack.name}_solvents"

        for nm in (vials_name, solvents_name):
            if len(nm) > 31:
                raise ValueError(
                    f"Excel sheet name too long ({len(nm)}): '{nm}'. "
                    f"Please shorten Rack.name so that '<name>_vials' and '<name>_solvents' fit into 31 chars."
                )

        ws_v = wb.create_sheet(vials_name)
        ws_s = wb.create_sheet(solvents_name)

        n_vial_rows = int(rack.vial_rows)
        n_vial_cols = int(rack.vial_columns)

        self._fill_grid(
            ws_v,
            n_rows=n_vial_rows,
            n_cols=n_vial_cols,
            mode="value",
        )
        # NEW: add the long index column under the vial grid
        self._add_vial_index_column(
            ws_v,
            n_rows=n_vial_rows,
            n_cols=n_vial_cols,
        )

        self._fill_grid(
            ws_s,
            n_rows=int(rack.solvent_rows),
            n_cols=int(rack.solvent_columns),
            mode="comment",
        )

    def _fill_grid(
        self,
        ws,
        *,
        n_rows: int,
        n_cols: int,
        mode: Literal["value", "comment"],
    ) -> None:
        # make the grid look like a grid in Excel
        ws.sheet_view.showGridLines = False

        # sizing: tweak if you want
        for c in range(1, n_cols + 1):
            ws.column_dimensions[get_column_letter(c)].width = 6
        for r in range(1, n_rows + 1):
            ws.row_dimensions[r].height = 18

        k = 1  # index starting at 1
        for col in range(1, n_cols + 1):          # columnwise
            for row in range(1, n_rows + 1):      # down the column
                cell = ws.cell(row=row, column=col)

                cell.border = self._BORDER
                cell.alignment = self._CENTER

                if mode == "value":
                    cell.fill = self._VIAL_FILL
                    cell.value = k
                else:
                    cell.fill = self._SOLVENT_FILL
                    cell.value = None
                    com = Comment(str(k), "idx")
                    com.width = 60
                    com.height = 25
                    cell.comment = com

                k += 1

    def _add_vial_index_column(self, ws, *, n_rows: int, n_cols: int) -> None:
        """
        Adds a single-column table below the vial grid:
        header 'index' + 1..N with borders, no special coloring.
        """
        n = int(n_rows) * int(n_cols)

        start_row = n_rows + 3  # "below" with a little vertical indent
        start_col = 1  # horizontal indent (column A)

        # header
        h = ws.cell(row=start_row, column=start_col)
        h.value = "index"
        h.font = self._BOLD
        h.border = self._BORDER
        h.alignment = self._CENTER
        h.fill = self._NOFILL

        # values 1..N
        for i in range(1, n + 1):
            c = ws.cell(row=start_row + i, column=start_col)
            c.value = i
            c.border = self._BORDER
            c.alignment = self._CENTER
            c.fill = self._NOFILL

        # make that column readable
        ws.column_dimensions[get_column_letter(start_col)].width = max(
            ws.column_dimensions[get_column_letter(start_col)].width or 0,
            10,
        )
