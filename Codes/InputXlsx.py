from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill, Border, Side, Alignment

from .PipetG import PipetG
from .Rack import Rack


_THIN = Side(style="thin")
_THIN_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_CENTER = Alignment(horizontal="center", vertical="center")

# ARGB (FF = opaque)
_VIAL_FILL = PatternFill(fill_type="solid", fgColor="FFD9E1F2")  # light blue
_SOLV_FILL = PatternFill(fill_type="solid", fgColor="FFFCE4D6")  # light orange


class InputXlsx(BaseModel):
    pipet: PipetG

    # runtime-only caches
    xlsx_path: Path | None = Field(default=None, exclude=True, repr=False)
    wb: Workbook | None = Field(default=None, exclude=True, repr=False)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,  # <- re-run validation on every .load()
    )

    # ---------------- I/O ----------------

    def load(self, xlsx_path: str | Path, **wb_kwargs: Any) -> None:
        """
        Load an existing workbook and trigger validators (via validate_assignment).
        """
        path = Path(xlsx_path)
        if not path.is_file():
            raise FileNotFoundError(path)

        # set path first (nice for error messages), then wb to trigger validation
        self.xlsx_path = path
        self.wb = load_workbook(filename=str(path), **wb_kwargs)

    @classmethod
    def from_excel(cls, xlsx_path: str | Path, pipet: PipetG, **wb_kwargs: Any) -> "InputXlsx":
        obj = cls(pipet=pipet)
        obj.load(xlsx_path, **wb_kwargs)  # triggers validation
        return obj

    # ------------- validators -------------

    @model_validator(mode="after")
    def _validate_solvent_ids_in_solvent_grids(self) -> "InputXlsx":
        """
        In each <Rack.name>_solvents sheet:
        - user writes SOLVENT_IDs into the grid cells (values, not comments)
        - validate each non-empty value is an int and exists in setup.solvents ids
        """
        if self.wb is None:
            return self

        allowed = {int(s.id) for s in self.pipet.setup.solvents if s.id is not None}
        if not allowed:
            raise ValueError("setup.solvents contains no valid ids; cannot validate solvent IDs.")

        for rack in self.pipet.setup.racks:
            sheet = f"{rack.name}_solvents"
            if sheet not in self.wb.sheetnames:
                raise ValueError(f"Missing sheet '{sheet}' in {self.xlsx_path or 'workbook'}.")

            ws = self.wb[sheet]
            n_rows = int(rack.solvent_rows)
            n_cols = int(rack.solvent_columns)
            n = n_rows * n_cols

            for local_idx in range(n):
                col = local_idx // n_rows
                row = local_idx % n_rows
                cell = ws.cell(row=row + 1, column=col + 1)

                val = cell.value
                if val is None or val == "":
                    continue

                try:
                    solvent_id = int(val)
                except Exception:
                    raise ValueError(
                        f"{sheet}!{cell.coordinate}: solvent_id must be an integer, got {val!r}."
                    )

                if solvent_id not in allowed:
                    raise ValueError(
                        f"{sheet}!{cell.coordinate}: solvent_id={solvent_id} not found in setup.solvents."
                    )

        return self

    @model_validator(mode="after")
    def _validate_vial_program_solvent_index_bounds(self) -> "InputXlsx":
        """
        In each <Rack.name>_vials sheet, below-table column 'solvent_index' (col C):
        validate each non-empty solvent_index is within 1..N where
        N = total solvent slots across ALL racks in setup order.
        """
        if self.wb is None:
            return self

        total_slots = len(self.pipet.setup.solvent_positions)
        if total_slots <= 0:
            raise ValueError("setup.solvent_positions is empty; cannot validate solvent_index bounds.")

        for rack in self.pipet.setup.racks:
            sheet = f"{rack.name}_vials"
            if sheet not in self.wb.sheetnames:
                raise ValueError(f"Missing sheet '{sheet}' in {self.xlsx_path or 'workbook'}.")

            ws = self.wb[sheet]
            n_rows = int(rack.vial_rows)
            n_cols = int(rack.vial_columns)
            n = n_rows * n_cols

            # must match your template writer
            table_top = n_rows + 2
            solvent_index_col = 3  # "solvent_index" is column C

            for i in range(n):
                r = table_top + 1 + i
                cell = ws.cell(row=r, column=solvent_index_col)
                val = cell.value
                if val is None or val == "":
                    continue

                try:
                    solvent_index = int(val)
                except Exception:
                    raise ValueError(
                        f"{sheet}!{cell.coordinate}: solvent_index must be an integer, got {val!r}."
                    )

                # IMPORTANT: this assumes your Excel indices are 1-based (as in your template).
                if not (1 <= solvent_index <= total_slots):
                    raise ValueError(
                        f"{sheet}!{cell.coordinate}: solvent_index={solvent_index} out of bounds "
                        f"(allowed 1..{total_slots})."
                    )

        return self

    # ---------------- template writing ----------------

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
        wb.remove(wb.active)

        solvent_start = 1
        for rack in racks:
            ws = wb.create_sheet(title=f"{rack.name}_solvents")
            solvent_start = self._write_solvent_sheet(ws, rack, start_index=solvent_start)

        vial_start = 1
        for rack in racks:
            ws = wb.create_sheet(title=f"{rack.name}_vials")
            vial_start = self._write_vial_sheet(ws, rack, start_index=vial_start)

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(out_path))
        return out_path

    def _write_solvent_sheet(self, ws, rack: Rack, *, start_index: int) -> int:
        n_rows = int(rack.solvent_rows)
        n_cols = int(rack.solvent_columns)
        n = n_rows * n_cols

        for local_idx in range(n):
            global_idx = start_index + local_idx

            col = local_idx // n_rows
            row = local_idx % n_rows

            cell = ws.cell(row=row + 1, column=col + 1)
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

        for local_idx in range(n):
            global_idx = start_index + local_idx

            col = local_idx // n_rows
            row = local_idx % n_rows

            cell = ws.cell(row=row + 1, column=col + 1)
            cell.value = global_idx
            cell.fill = _VIAL_FILL
            cell.border = _THIN_BORDER
            cell.alignment = _CENTER

        table_top = n_rows + 2

        ws.cell(row=table_top, column=1, value="vial_index").border = _THIN_BORDER
        ws.cell(row=table_top, column=2, value="volume_uL").border = _THIN_BORDER
        ws.cell(row=table_top, column=3, value="solvent_index").border = _THIN_BORDER

        for i in range(n):
            r = table_top + 1 + i

            c1 = ws.cell(row=r, column=1, value=start_index + i)
            c2 = ws.cell(row=r, column=2, value=None)
            c3 = ws.cell(row=r, column=3, value=None)

            c1.border = _THIN_BORDER
            c2.border = _THIN_BORDER
            c3.border = _THIN_BORDER

        return start_index + n
