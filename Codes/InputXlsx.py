from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill, Border, Side, Alignment

from .PipetG import PipetG


class InputXlsx(BaseModel):
    pipet: PipetG

    # runtime-only
    xlsx_path: Path | None = Field(default=None, exclude=True, repr=False)
    wb: Workbook | None = Field(default=None, exclude=True, repr=False)

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    # ---------- template creation ----------
    def create_empty_table(self, out_path: Path) -> Path:
        wb = Workbook()
        wb.remove(wb.active)

        vial_start_idx = 1
        solvent_start_idx = 1

        for rack in self.pipet.setup.racks:
            solvent_start_idx = self._write_solvent_sheet(wb, rack, solvent_start_idx)
            vial_start_idx = self._write_vial_sheet(wb, rack, vial_start_idx)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(out_path)
        return out_path

    def _write_solvent_sheet(self, wb: Workbook, rack, start_index: int) -> int:
        ws = wb.create_sheet(f"{rack.name}_solvents")

        n_rows = int(rack.solvent_rows)
        n_cols = int(rack.solvent_columns)

        dx = float(rack.solvent_dx or 0.0)
        dy = float(rack.solvent_dy or 0.0)

        fill = PatternFill("solid", fgColor="FFF2CC")  # light orange
        thin = Side(style="thin")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        align = Alignment(horizontal="center", vertical="center")

        idx = start_index
        for col in range(n_cols):
            for row in range(n_rows):
                r = 1 + row
                c = 1 + col

                cell = ws.cell(row=r, column=c, value=None)  # user writes solvent_id here
                cell.fill = fill
                cell.border = border
                cell.alignment = align

                # comment shows global solvent-slot index
                cell.comment = Comment(f"{idx}", "index")
                idx += 1

        ws.freeze_panes = "A1"
        return start_index + (n_rows * n_cols)

    def _write_vial_sheet(self, wb: Workbook, rack, start_index: int) -> int:
        ws = wb.create_sheet(f"{rack.name}_vials")

        n_rows = int(rack.vial_rows)
        n_cols = int(rack.vial_columns)
        n = n_rows * n_cols

        fill = PatternFill("solid", fgColor="DDEBF7")  # light blue
        thin = Side(style="thin")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        align = Alignment(horizontal="center", vertical="center")
        white = PatternFill("solid", fgColor="FFFFFF")

        # --- vial grid with global vial indices (not editable meaningfully, but you can overwrite) ---
        idx = start_index
        for col in range(n_cols):
            for row in range(n_rows):
                r = 1 + row
                c = 1 + col
                cell = ws.cell(row=r, column=c, value=idx)
                cell.fill = fill
                cell.border = border
                cell.alignment = align
                idx += 1

        # make the rest of the visible region clean white (prevents “dirty white”)
        for r in range(1, n_rows + 20):
            for c in range(1, n_cols + 10):
                cell = ws.cell(row=r, column=c)
                if cell.fill is None or cell.fill.patternType is None:
                    cell.fill = white

        # --- program table below: A=index, B=volume_uL, C=solvent_index ---
        table_top = n_rows + 2
        ws.cell(row=table_top, column=1, value="index").border = border
        ws.cell(row=table_top, column=2, value="volume_uL").border = border
        ws.cell(row=table_top, column=3, value="solvent_index").border = border

        for i in range(n):
            r = table_top + 1 + i
            ws.cell(row=r, column=1, value=start_index + i).border = border
            ws.cell(row=r, column=2, value=None).border = border
            ws.cell(row=r, column=3, value=None).border = border

        ws.freeze_panes = "A1"
        return start_index + n

    # ------------------------------------------------------------------
    # Loading / validation
    # ------------------------------------------------------------------

    def load(self, xlsx_path: str | Path, **wb_kwargs: Any) -> "InputXlsx":
        """Load an existing Excel file into this instance.

        Assigning `self.wb` triggers model validators (validate_assignment=True).
        """
        path = Path(xlsx_path)
        self.xlsx_path = path
        self.wb = load_workbook(filename=str(path), **wb_kwargs)
        return self

    @classmethod
    def from_excel(cls, xlsx_path: str | Path, pipet: PipetG, **wb_kwargs: Any) -> "InputXlsx":
        obj = cls(pipet=pipet)
        obj.load(xlsx_path, **wb_kwargs)  # triggers validation
        return obj

    @classmethod
    def write_gcode_from_excel(
        cls,
        xlsx_path: str | Path,
        pipet: PipetG,
        *,
        do_home: bool = True,
        do_finish: bool = True,
        **g_kwargs: Any,
    ) -> Path:
        obj = cls.from_excel(xlsx_path, pipet=pipet)
        return obj.generate_gcode(do_home=do_home, do_finish=do_finish, **g_kwargs)

    @model_validator(mode="after")
    def _validate_solvent_ids_in_solvent_grids(self) -> "InputXlsx":
        if self.wb is None:
            return self
        self._validate_solvent_ids_in_solvent_grids_impl()
        return self

    @model_validator(mode="after")
    def _validate_solvent_index_in_vial_program(self) -> "InputXlsx":
        if self.wb is None:
            return self
        self._validate_vial_solvent_idx_bounds_impl()
        return self

    # ---------------- validation helpers ----------------

    def _as_int(self, v: Any, *, where: str) -> int | None:
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError(f"{where}: boolean is not a valid integer")
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            if v.is_integer():
                return int(v)
            raise ValueError(f"{where}: expected integer, got float {v}")
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return None
            try:
                f = float(s)
            except ValueError as e:
                raise ValueError(f"{where}: cannot parse '{v}' as number") from e
            if f.is_integer():
                return int(f)
            raise ValueError(f"{where}: expected integer, got '{v}'")
        raise ValueError(f"{where}: unsupported type {type(v).__name__}")

    def _allowed_solvent_ids(self) -> set[int]:
        ids = []
        for s in self.pipet.setup.solvents:
            if s.id is None:
                raise ValueError("Setup contains a Solvent with id=None; cannot validate solvent IDs.")
            ids.append(int(s.id))
        return set(ids)

    def _total_solvent_slots(self) -> int:
        return sum(int(r.solvent_rows) * int(r.solvent_columns) for r in self.pipet.setup.racks)

    def _validate_solvent_ids_in_solvent_grids_impl(self) -> None:
        assert self.wb is not None
        allowed = self._allowed_solvent_ids()

        for rack in self.pipet.setup.racks:
            name = f"{rack.name}_solvents"
            if name not in self.wb.sheetnames:
                raise ValueError(f"Missing sheet '{name}' in workbook.")

            ws = self.wb[name]
            n_rows = int(rack.solvent_rows)
            n_cols = int(rack.solvent_columns)

            for col in range(n_cols):
                for row in range(n_rows):
                    r = 1 + row
                    c = 1 + col
                    val = ws.cell(row=r, column=c).value
                    sid = self._as_int(val, where=f"{name}!{ws.cell(r,c).coordinate}")
                    if sid is None:
                        continue
                    if sid not in allowed:
                        raise ValueError(
                            f"{name}!{ws.cell(r,c).coordinate}: solvent_id={sid} not in setup.solvents ids={sorted(allowed)}"
                        )

    def _validate_vial_solvent_idx_bounds_impl(self) -> None:
        assert self.wb is not None
        total_slots = self._total_solvent_slots()

        for rack in self.pipet.setup.racks:
            name = f"{rack.name}_vials"
            if name not in self.wb.sheetnames:
                raise ValueError(f"Missing sheet '{name}' in workbook.")

            ws = self.wb[name]
            n_rows = int(rack.vial_rows)
            n_cols = int(rack.vial_columns)
            n = n_rows * n_cols

            table_top = n_rows + 2
            # data rows: table_top+1 .. table_top+n
            for i in range(n):
                r = table_top + 1 + i
                cell = ws.cell(row=r, column=3)  # solvent_index column
                sval = cell.value
                sidx = self._as_int(sval, where=f"{name}!{cell.coordinate}")
                if sidx is None:
                    continue
                if not (1 <= sidx <= total_slots):
                    raise ValueError(
                        f"{name}!{cell.coordinate}: solvent_index={sidx} out of bounds (allowed 1..{total_slots})"
                    )

    # ------------------------------------------------------------------
    # G-code generation
    # ------------------------------------------------------------------

    def _solvent_id_by_global_solvent_index(self) -> list[int | None]:
        """Returns a 1-based mapping stored as a 0-based list:
        mapping[solvent_index-1] -> solvent_id or None (if not assigned in grid).
        """
        assert self.wb is not None

        mapping: list[int | None] = []
        for rack in self.pipet.setup.racks:
            ws = self.wb[f"{rack.name}_solvents"]
            n_rows = int(rack.solvent_rows)
            n_cols = int(rack.solvent_columns)

            for col in range(n_cols):
                for row in range(n_rows):
                    r = 1 + row
                    c = 1 + col
                    cell = ws.cell(row=r, column=c)
                    sid = self._as_int(cell.value, where=f"{rack.name}_solvents!{cell.coordinate}")
                    mapping.append(sid)
        return mapping

    def generate_gcode(self, *, do_home: bool = True, do_finish: bool = True, **g_kwargs: Any) -> Path:
        """Read the workbook program and emit gcode using the provided PipetG."""
        if self.wb is None:
            raise RuntimeError("No workbook loaded. Use InputXlsx.from_excel(...) or .load(...) first.")

        solvent_id_map = self._solvent_id_by_global_solvent_index()

        def run(pg: PipetG) -> None:
            if do_home:
                pg.home()

            # rack order matters (matches your setup concatenation logic)
            for rack in pg.setup.racks:
                ws = self.wb[f"{rack.name}_vials"]
                n_rows = int(rack.vial_rows)
                n_cols = int(rack.vial_columns)
                n = n_rows * n_cols
                table_top = n_rows + 2

                for i in range(n):
                    r = table_top + 1 + i
                    vial_cell = ws.cell(row=r, column=1)
                    vol_cell = ws.cell(row=r, column=2)
                    sidx_cell = ws.cell(row=r, column=3)

                    vial_index = self._as_int(vial_cell.value, where=f"{rack.name}_vials!{vial_cell.coordinate}")
                    solvent_index = self._as_int(sidx_cell.value, where=f"{rack.name}_vials!{sidx_cell.coordinate}")
                    volume_val = vol_cell.value

                    # skip completely empty lines
                    if (solvent_index is None) and (volume_val is None):
                        continue

                    if (vial_index is None) and (solvent_index is None) and (volume_val is None):
                        continue

                    if vial_index is None:
                        raise ValueError(f"{rack.name}_vials!{vial_cell.coordinate}: vial index is empty.")
                    if solvent_index is None:
                        raise ValueError(f"{rack.name}_vials!{sidx_cell.coordinate}: solvent_index is empty.")
                    if volume_val is None:
                        raise ValueError(f"{rack.name}_vials!{vol_cell.coordinate}: volume_uL is empty.")

                    volume_ul = float(volume_val)

                    # Excel indices are 1-based; PipetG expects 0-based indices
                    vial_idx0 = vial_index - 1
                    solvent_idx0 = solvent_index - 1

                    if not (0 <= solvent_idx0 < len(solvent_id_map)):
                        raise ValueError(
                            f"{rack.name}_vials row {r}: solvent_index={solvent_index} out of mapping range."
                        )

                    solvent_id = solvent_id_map[solvent_idx0]
                    if solvent_id is None:
                        raise ValueError(
                            f"{rack.name}_vials row {r}: solvent_index={solvent_index} has no solvent_id assigned "
                            f"in solvent grids."
                        )

                    pg.process_vial(
                        vial_idx=vial_idx0,
                        solvent_idx=solvent_idx0,
                        solvent_id=int(solvent_id),
                        volume_ul=volume_ul,
                        slow=False,
                        flush_repeats=0,
                    )

            if do_finish:
                pg.finish()

        # If PipetG already started, don't restart it.
        if self.pipet.g is None:
            with self.pipet:
                run(self.pipet)
        else:
            run(self.pipet)

        return self.pipet.outfile
