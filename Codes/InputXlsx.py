from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill, Border, Side, Alignment, Font
from openpyxl.utils import get_column_letter

from .PipetG import PipetG


def _safe_sheet_name(name: str) -> str:
    # Excel sheet name rules:
    # - max 31 chars
    # - cannot contain: : \ / ? * [ ]
    bad = r'[]:*?/\\'
    out = "".join("_" if ch in bad else ch for ch in name)
    out = out.strip() or "Sheet"
    return out[:31]


class InputXlsx(BaseModel):
    pipet: PipetG = Field(exclude=True)
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Colors
    _FILL_BG: Final = PatternFill("solid", fgColor="FFFFFF")      # off-white background
    _FILL_VIAL: Final = PatternFill("solid", fgColor="D9E8FF")    # light blue
    _FILL_SOLV: Final = PatternFill("solid", fgColor="FFE7CC")    # light orange

    # Borders / formatting
    _SIDE: Final = Side(style="thin", color="BFBFBF")
    _BORDER: Final = Border(left=_SIDE, right=_SIDE, top=_SIDE, bottom=_SIDE)
    _CENTER: Final = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def create_empty_table(self, out_path: Path) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        # remove default sheet
        wb.remove(wb.active)

        vial_global = 1
        solvent_global = 1

        for rack in self.pipet.setup.racks:
            # ---- solvents sheet ----
            ws_s = wb.create_sheet(_safe_sheet_name(f"{rack.name}_solvents"))
            r_rows = int(rack.solvent_rows)
            r_cols = int(rack.solvent_columns)

            # paint a "work area" (bg) slightly larger than the grid
            self._paint_bg(ws_s, rows=max(r_rows, 1) + 2, cols=max(r_cols, 1) + 2)
            self._format_grid(ws_s, rows=r_rows, cols=r_cols)

            solvent_global = self._fill_solvent_grid_with_comments(
                ws_s,
                n_rows=r_rows,
                n_cols=r_cols,
                start_index=solvent_global,
            )

            # ---- vials sheet ----
            ws_v = wb.create_sheet(_safe_sheet_name(f"{rack.name}_vials"))
            v_rows = int(rack.vial_rows)
            v_cols = int(rack.vial_columns)
            n_vials = v_rows * v_cols

            # we need space below the grid for the index column table:
            index_header_row = v_rows + 3               # 2-row gap
            index_last_row = index_header_row + n_vials  # header + n_vials

            # paint bg for grid + index table area (a bit wider than needed)
            self._paint_bg(ws_v, rows=max(index_last_row, 1) + 2, cols=max(v_cols, 1) + 2)
            self._format_grid(ws_v, rows=v_rows, cols=v_cols)

            vial_global = self._fill_vial_grid_with_numbers(
                ws_v,
                n_rows=v_rows,
                n_cols=v_cols,
                start_index=vial_global,
            )

            self._add_vial_index_column_table(
                ws_v,
                start_row=index_header_row,
                start_index=vial_global - n_vials,  # indices we just wrote into the grid
                count=n_vials,
            )

        wb.save(out_path)
        return out_path

    # ---------------- helpers ----------------

    def _paint_bg(self, ws, *, rows: int, cols: int) -> None:
        """Fill a finite 'work area' with off-white so the nice background stays."""
        for r in range(1, rows + 1):
            for c in range(1, cols + 1):
                cell = ws.cell(r, c)
                cell.fill = self._FILL_BG

    def _format_grid(self, ws, *, rows: int, cols: int) -> None:
        # make columns a bit readable
        for c in range(1, cols + 1):
            ws.column_dimensions[get_column_letter(c)].width = 5.0
        for r in range(1, rows + 1):
            ws.row_dimensions[r].height = 18.0

        # hide default gridlines; we draw borders instead
        ws.sheet_view.showGridLines = False

    def _fill_solvent_grid_with_comments(self, ws, *, n_rows: int, n_cols: int, start_index: int) -> int:
        """Orange grid, empty values, comment contains global solvent index."""
        idx = start_index
        for k in range(n_rows * n_cols):
            col = (k // n_rows) + 1  # column-wise fill
            row = (k % n_rows) + 1

            cell = ws.cell(row=row, column=col)
            cell.fill = self._FILL_SOLV
            cell.border = self._BORDER
            cell.alignment = self._CENTER
            cell.value = None

            # comment shows index, cell remains editable
            cell.comment = Comment(f"{idx}", "index")
            idx += 1
        return idx

    def _fill_vial_grid_with_numbers(self, ws, *, n_rows: int, n_cols: int, start_index: int) -> int:
        """Blue grid, values are global vial indices, column-wise fill."""
        idx = start_index
        for k in range(n_rows * n_cols):
            col = (k // n_rows) + 1
            row = (k % n_rows) + 1

            cell = ws.cell(row=row, column=col)
            cell.fill = self._FILL_VIAL
            cell.border = self._BORDER
            cell.alignment = self._CENTER
            cell.value = idx
            idx += 1
        return idx

    def _add_vial_index_column_table(self, ws, *, start_row: int, start_index: int, count: int) -> None:
        """
        Below the vial grid:
        Column A only, header 'index' + [start_index .. start_index+count-1]
        Borders yes, no special coloring (background stays off-white).
        """
        # header in A
        h = ws.cell(row=start_row, column=1)
        h.value = "index"
        h.font = Font(bold=True)
        h.alignment = self._CENTER
        h.border = self._BORDER

        # values
        for i in range(count):
            c = ws.cell(row=start_row + 1 + i, column=1)
            c.value = start_index + i
            c.alignment = self._CENTER
            c.border = self._BORDER

        # make column A readable
        ws.column_dimensions["A"].width = 10.0
