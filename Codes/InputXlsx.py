from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill, Border, Side, Alignment

from .PipetG import PipetG
from .Rack import Rack


_THIN = Side(style="thin")
_THIN_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_CENTER = Alignment(horizontal="center", vertical="center")

# NOTE (openpyxl colors):
# - "00000000" is often "no fill" (transparent), not black.
# - The fills below are ARGB (FF = opaque).
_VIAL_FILL = PatternFill(fill_type="solid", fgColor="FFD9E1F2")     # light blue
_SOLV_FILL = PatternFill(fill_type="solid", fgColor="FFFCE4D6")     # light orange


class InputXlsx(BaseModel):
    pipet: PipetG

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def create_empty_table(self, out_path: Path) -> Path:
        """
        Create an .xlsx template for the racks in `self.pipet.setup.racks`.

        Sheets (order):
          1) <rack.name>_solvents for each rack in order
          2) <rack.name>_vials    for each rack in order

        - Solvent sheets: orange grid, index stored as COMMENT (cell value left empty).
        - Vial sheets: blue grid, index stored as CELL VALUE (no comments).
                     + below the grid: a 3-column table:
                        [vial_index | volume_uL | solvent_index]
                       with borders and no special coloring.
        - Numbering continues across racks (1..N) in rack order, column-wise inside each rack.
        """
        racks = self.pipet.setup.racks
        if not racks:
            raise ValueError("No racks in pipet.setup.racks")

        wb = Workbook()
        # remove default sheet
        wb.remove(wb.active)

        # ---- 1) solvents first (as requested) ----
        solvent_start = 1
        for rack in racks:
            ws = wb.create_sheet(title=f"{rack.name}_solvents")
            solvent_start = self._write_solvent_sheet(ws, rack, start_index=solvent_start)

        # ---- 2) vials afterwards ----
        vial_start = 1
        for rack in racks:
            ws = wb.create_sheet(title=f"{rack.name}_vials")
            vial_start = self._write_vial_sheet(ws, rack, start_index=vial_start)

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(out_path))
        return out_path

    # ---------------- helpers ----------------

    def _write_solvent_sheet(self, ws, rack: Rack, *, start_index: int) -> int:
        n_rows = int(rack.solvent_rows)
        n_cols = int(rack.solvent_columns)
        n = n_rows * n_cols

        for local_idx in range(n):
            global_idx = start_index + local_idx

            col = local_idx // n_rows          # 0..n_cols-1
            row = local_idx % n_rows           # 0..n_rows-1

            cell = ws.cell(row=row + 1, column=col + 1)

            # leave value empty, store index as comment
            cell.value = None
            cell.comment = Comment(str(global_idx), "index")

            cell.fill = _SOLV_FILL
            cell.border = _THIN_BORDER
            cell.alignment = _CENTER

        return start_index + n

    def _write_vial_sheet(self, ws, rack: Rack, *, start_index: int) -> int:
        n_rows = int(rack.vial_rows)
        n_cols = int(rack.vial_columns)
        n = n_rows * n_cols

        # --- main blue grid with vial indices in cells ---
        for local_idx in range(n):
            global_idx = start_index + local_idx

            col = local_idx // n_rows
            row = local_idx % n_rows

            cell = ws.cell(row=row + 1, column=col + 1)
            cell.value = global_idx

            cell.fill = _VIAL_FILL
            cell.border = _THIN_BORDER
            cell.alignment = _CENTER

        # --- below: index table (A:C) ---
        # one blank row between grid and table
        table_top = n_rows + 2

        # header row
        ws.cell(row=table_top, column=1, value="vial_index").border = _THIN_BORDER
        ws.cell(row=table_top, column=2, value="volume_uL").border = _THIN_BORDER
        ws.cell(row=table_top, column=3, value="solvent_index").border = _THIN_BORDER

        # data rows (no fill, just borders)
        for i in range(n):
            r = table_top + 1 + i

            c1 = ws.cell(row=r, column=1, value=start_index + i)
            c2 = ws.cell(row=r, column=2, value=None)
            c3 = ws.cell(row=r, column=3, value=None)

            c1.border = _THIN_BORDER
            c2.border = _THIN_BORDER
            c3.border = _THIN_BORDER

        return start_index + n
