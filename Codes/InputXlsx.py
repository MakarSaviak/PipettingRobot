from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from openpyxl import Workbook

from .PipetG import PipetG


class InputXlsx(BaseModel):
    pipet: PipetG
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def create_empty_table(self, outpath: str | Path, *, overwrite: bool = True) -> Path:
        outpath = Path(outpath)
        if outpath.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {outpath} (use overwrite=True)")

        wb = Workbook()
        # Remove the default sheet created by openpyxl
        wb.remove(wb.active)

        racks = self.pipet.setup.racks  # order here defines sheet order :contentReference[oaicite:1]{index=1}

        # 1) solvent sheets first: <Rack.name>_solvents
        for rack in racks:
            ws = wb.create_sheet(self._safe_sheet_name(f"{rack.name}_solvents"))
            self._make_blank_grid(ws, n_rows=int(rack.solvent_rows), n_cols=int(rack.solvent_columns))

        # 2) vial sheets: <Rack.name>_vials
        for rack in racks:
            ws = wb.create_sheet(self._safe_sheet_name(f"{rack.name}_vials"))
            self._make_blank_grid(ws, n_rows=int(rack.vial_rows), n_cols=int(rack.vial_columns))

        wb.save(outpath)
        return outpath

    @staticmethod
    def _make_blank_grid(ws, *, n_rows: int, n_cols: int) -> None:
        # Create an explicitly-sized empty table (cells exist, values are empty strings).
        for r in range(1, n_rows + 1):
            for c in range(1, n_cols + 1):
                ws.cell(row=r, column=c, value="")

    @staticmethod
    def _safe_sheet_name(name: str) -> str:
        # Excel rules: max 31 chars, and cannot contain: : \ / ? * [ ]
        bad = ':\\/?*[]'
        cleaned = "".join("_" if ch in bad else ch for ch in name).strip()
        return cleaned[:31] if len(cleaned) > 31 else cleaned
