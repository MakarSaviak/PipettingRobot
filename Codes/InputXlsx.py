from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Border, Side, Alignment

from .PipetG import PipetG
from .Rack import Rack


_THIN = Side(style="thin")
_GRID_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_CENTER = Alignment(horizontal="center", vertical="center")


class InputXlsx(BaseModel):
    pipet: PipetG

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def create_empty_table(self, out_path: Path) -> Path:
        racks = self.pipet.setup.racks
        if not racks:
            raise ValueError("No racks in setup.")

        wb = Workbook()
        # remove the default sheet
        wb.remove(wb.active)

        for rack in racks:
            self._add_rack_sheets(wb, rack)

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(out_path)
        return out_path

    # ----------------- internals -----------------
    def _add_rack_sheets(self, wb: Workbook, rack: Rack) -> None:
        sname_sol = f"{rack.name}_solvents"
        sname_via = f"{rack.name}_vials"

        # Excel sheet name limit
        if len(sname_sol) > 31 or len(sname_via) > 31:
            raise ValueError(
                f"Excel sheet names must be <= 31 chars. Got '{sname_sol}' / '{sname_via}'. "
                f"Shorten Rack.name."
            )

        ws_sol = wb.create_sheet(sname_sol)
        ws_via = wb.create_sheet(sname_via)

        # Solvents: comments only (cells stay empty)
        self._fill_grid(
            ws_sol,
            n_rows=int(rack.solvent_rows),
            n_cols=int(rack.solvent_columns),
            mode="comment",
        )

        # Vials: numbers as actual cell values (no comments)
        self._fill_grid(
            ws_via,
            n_rows=int(rack.vial_rows),
            n_cols=int(rack.vial_columns),
            mode="value",
        )

    def _fill_grid(self, ws, *, n_rows: int, n_cols: int, mode: str) -> None:
        # make it look like a table even if Excel gridlines are off
        ws.sheet_view.showGridLines = True

        # basic sizing so the table is readable
        for c in range(1, n_cols + 1):
            ws.column_dimensions[self._col_letter(c)].width = 6
        for r in range(1, n_rows + 1):
            ws.row_dimensions[r].height = 18

        k = 1
        for c in range(1, n_cols + 1):          # column-wise fill
            for r in range(1, n_rows + 1):
                cell = ws.cell(row=r, column=c)
                cell.border = _GRID_BORDER
                cell.alignment = _CENTER

                if mode == "value":
                    cell.value = k
                elif mode == "comment":
                    cell.value = None  # you type here; index is in the note
                    com = Comment(str(k), "idx")
                    com.width = 60
                    com.height = 25
                    cell.comment = com
                else:
                    raise ValueError(f"Unknown mode: {mode}")

                k += 1

    @staticmethod
    def _col_letter(n: int) -> str:
        # 1 -> A, 26 -> Z, 27 -> AA, ...
        s = ""
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s
