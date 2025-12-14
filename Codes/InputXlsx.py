from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from openpyxl import Workbook
from openpyxl.styles import Border, Side

from .PipetG import PipetG


_THIN = Side(style="thin")
_GRID_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


class InputXlsx(BaseModel):
    pipet: PipetG
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @staticmethod
    def _validate_sheet_name(name: str) -> None:
        if not name:
            raise ValueError("Excel sheet name must not be empty.")
        if len(name) > 31:
            raise ValueError(f"Excel sheet name too long (>31): '{name}'")
        forbidden = set(r'[]:*?/\\')
        if any(ch in forbidden for ch in name):
            raise ValueError(f"Excel sheet name contains forbidden characters: '{name}'")

    @staticmethod
    def _make_numbered_grid(ws, *, n_rows: int, n_cols: int) -> None:
        ws.sheet_view.showGridLines = True

        k = 1
        # columnwise: A1..A(n), then B1..B(n), ...
        for c in range(1, n_cols + 1):
            for r in range(1, n_rows + 1):
                cell = ws.cell(row=r, column=c)
                cell.value = k
                cell.border = _GRID_BORDER
                k += 1

    def create_empty_table(self, out_path: Path) -> Path:
        racks = self.pipet.setup.racks
        if not racks:
            raise ValueError("setup.racks is empty; cannot create Excel template.")

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        wb.remove(wb.active)  # remove default sheet

        # validate sheet names
        sheet_names: list[str] = []
        for r in racks:
            sheet_names.append(f"{r.name}_solvents")
            sheet_names.append(f"{r.name}_vials")

        if len(sheet_names) != len(set(sheet_names)):
            raise ValueError("Duplicate sheet names detected (rack names may not be unique).")

        for sname in sheet_names:
            self._validate_sheet_name(sname)

        # create sheets + fill
        for rack in racks:
            ws_sol = wb.create_sheet(f"{rack.name}_solvents")
            self._make_numbered_grid(
                ws_sol,
                n_rows=int(rack.solvent_rows),
                n_cols=int(rack.solvent_columns),
            )

            ws_vial = wb.create_sheet(f"{rack.name}_vials")
            self._make_numbered_grid(
                ws_vial,
                n_rows=int(rack.vial_rows),
                n_cols=int(rack.vial_columns),
            )

        wb.save(out_path)
        return out_path
