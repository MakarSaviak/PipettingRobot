from __future__ import annotations

from pathlib import Path
from typing import Any
from itertools import chain

from pydantic import BaseModel, ConfigDict, Field, model_validator
from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill, Border, Side, Alignment, NamedStyle, Font

from .PipetG import PipetG

# --- Table Design Constants ---
THIN_SIDE = Side(style="thin")
GRID_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
CENTER_ALIGN = Alignment(horizontal="center", vertical="center")
# --- Colors ---
LIGHT_ORANGE = PatternFill("solid", fgColor="FFF2CC")
LIGHT_BLUE = PatternFill("solid", fgColor="DDEBF7")
WHITE = PatternFill("solid", fgColor="FFFFFF")
HEADER_ORANGE = PatternFill("solid", fgColor="FFA62B")
VIAL_IDX_FILL = PatternFill("solid", fgColor="16697A")
HEADER_BOLD = Font(bold=True)


class InputXlsx(BaseModel):
    pipet: PipetG

    xlsx_path: Path | None = Field(default=None, exclude=True, repr=False)
    wb: Workbook | None = Field(default=None, exclude=True, repr=False)

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    # ---------- template creation ----------
    def create_empty_table(self, out_path: Path, *, stages: int = 3) -> Path:
        wb = Workbook()
        wb.remove(wb.active)

        vial_start_idx = 1
        solvent_start_idx = 1

        for rack in self.pipet.setup.racks:
            solvent_start_idx = self._write_solvent_sheet(wb, rack, solvent_start_idx)
            vial_start_idx = self._write_vial_sheet(wb, rack, vial_start_idx, stages=stages)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(out_path)
        return out_path

    def _write_solvent_sheet(self, wb: Workbook, rack, start_index: int) -> int:
        ws = wb.create_sheet(f"{rack.name}_solvents")

        n_rows = int(rack.solvent_rows)
        n_cols = int(rack.solvent_columns)

        idx = start_index
        for col in range(1, n_cols + 1):
            for row in range(1, n_rows + 1):
                cell = ws.cell(row=row, column=col, value=None)  # user writes solvent_id here

                cell.fill = LIGHT_ORANGE
                cell.border = GRID_BORDER
                cell.alignment = CENTER_ALIGN

                cell.comment = Comment(f"{idx}", "index") # comment shows global solvent-slot index
                idx += 1

        return start_index + (n_rows * n_cols)

    def _write_vial_sheet(self, wb: Workbook, rack, start_index: int, *, stages: int = 3) -> int:
        ws = wb.create_sheet(f"{rack.name}_vials")

        n_rows = int(rack.vial_rows)
        n_cols = int(rack.vial_columns)
        n = n_rows * n_cols # total number of vials

        # make the rest of the visible region white
        table_top = n_rows + 2
        header_max_col = 1 + (3 * stages)

        rows = chain(ws.iter_rows(min_row=1, max_row=n_rows + 1, min_col=1, max_col=37),
            ws.iter_rows(min_row=table_top + n + 1, max_row=table_top + n + 30, min_col=1, max_col=37))
        for row in rows:
            for cell in row:
                cell.fill = WHITE

        # --- vial grid with global vial indices ---
        idx = start_index
        for col in range(1, n_cols + 1):
            for row in range(1, n_rows + 1):
                cell = ws.cell(row=row, column=col, value=idx)
                cell.fill = LIGHT_BLUE
                cell.border = GRID_BORDER
                cell.alignment = CENTER_ALIGN
                idx += 1

        # --- the program table below: A=index, then (volume_uL, solvent_index, flush)*stages ---

        # headers for stages
        for col in ws.iter_cols(min_row=table_top, max_row=table_top, min_col=1, max_col=header_max_col):
            for cell in col:
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.fill = HEADER_ORANGE
                cell.font = HEADER_BOLD
        ws.row_dimensions[table_top].height = 30

        ws.cell(row=table_top, column=1, value="index") # the vial index header
        for i in range(n):
            r = table_top + 1 + i
            cell = ws.cell(row=r, column=1, value=start_index + i)
            cell.fill = VIAL_IDX_FILL
            cell.font = Font(color="FFFFFF")

        for col in range(2, 1 + header_max_col, 3): # range(start, end, stepsize)
            ws.cell(row=table_top, column=col + 0, value="volume\nµL")
            ws.cell(row=table_top, column=col + 1, value="solvent\nindex")

            ws.cell(row=table_top, column=col + 2, value="flush")
            for i in range(n): # FALSE in every Flush cell
                r = table_top + 1 + i
                ws.cell(row=r, column=col + 2, value=False)

        # rows and borders for the program table
        for row in ws.iter_rows(min_row=table_top, max_row=table_top + n, min_col=1, max_col=header_max_col):
            for cell in row:
                cell.border = GRID_BORDER

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
        self._validate_vial_program_bounds_impl()
        return self

    # ---------------- validation helpers ----------------

    def _is_empty(self, v: Any) -> bool:
        return v is None or (isinstance(v, str) and v.strip() == "")

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

    def _parse_flush_spec(self, v: Any, *, where: str) -> bool | int | None:
        """Flush cell can be:
        - empty -> None (no flush)
        - TRUE/FALSE -> bool
        - integer k:
            - 0 -> False (no flush)
            - k>=1 -> flush with global solvent_index=k
        """
        if v is None:
            return None

        if isinstance(v, bool):
            return v

        if isinstance(v, int):
            if v == 0:
                return False
            if v >= 1:
                return v
            raise ValueError(f"{where}: flush integer must be >=0, got {v}")

        if isinstance(v, float):
            if not v.is_integer():
                raise ValueError(f"{where}: flush must be TRUE/FALSE or an integer solvent index, got {v}")
            iv = int(v)
            if iv == 0:
                return False
            if iv >= 1:
                return iv
            raise ValueError(f"{where}: flush integer must be >=0, got {iv}")

        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return None

            s_low = s.lower()
            if s_low in {"true", "t", "yes", "y"}:
                return True
            if s_low in {"false", "f", "no", "n"}:
                return False

            try:
                f = float(s_low)
            except ValueError as e:
                raise ValueError(f"{where}: flush cannot parse '{v}' (use TRUE/FALSE or a solvent index)") from e
            if not f.is_integer():
                raise ValueError(f"{where}: flush must be TRUE/FALSE or integer solvent index, got '{v}'")
            iv = int(f)
            if iv == 0:
                return False
            if iv >= 1:
                return iv
            raise ValueError(f"{where}: flush integer must be >=0, got {iv}")

        raise ValueError(f"{where}: unsupported type {type(v).__name__} for flush")

    def _allowed_solvent_ids(self) -> set[int]:
        ids = []
        for s in self.pipet.setup.solvents:
            if s.id is None:
                raise ValueError("Setup contains a Solvent with id=None; cannot validate solvent IDs.")
            ids.append(int(s.id))
        return set(ids)

    def _total_solvent_slots(self) -> int:
        return sum(int(r.solvent_rows) * int(r.solvent_columns) for r in self.pipet.setup.racks)

    # ---------- program table parsing (multi-stage) ----------

    def _program_header_last_col(self, ws, *, header_row: int) -> int:
        """Last column (in header_row) that has a non-empty header value."""
        last = 1
        max_c = ws.max_column or 1
        for c in range(1, max_c + 1):
            if not self._is_empty(ws.cell(row=header_row, column=c).value):
                last = c
        return last

    def _parse_program_stages(self, ws, *, sheet_name: str, header_row: int) -> list[tuple[int, int, int | None]]:
        """Return list of stages as tuples: (vol_col, solvent_col, flush_col|None)

        Expected layout (after col A=index):
            [volume_uL, solvent_index] OR [volume_uL, solvent_index, flush]
        repeated as many times as the user adds.
        """
        last_col = self._program_header_last_col(ws, header_row=header_row)
        if last_col < 3:
            raise ValueError(f"{sheet_name}: program header row {header_row} is missing required columns.")

        def norm(x: Any) -> str:
            if x is None:
                return ""
            return str(x).strip().lower().replace(" ", "")

        def is_volume(h: str) -> bool:
            return h.startswith("volume")

        def is_solvent(h: str) -> bool:
            return h.startswith("solvent")

        def is_flush(h: str) -> bool:
            return h.startswith("flush")

        stages: list[tuple[int, int, int | None]] = []
        col = 2  # after index
        while col <= last_col:
            h_vol = norm(ws.cell(row=header_row, column=col).value)
            h_sol = norm(ws.cell(row=header_row, column=col + 1).value) if (col + 1) <= last_col else ""

            # stop when user didn't define more stages
            if h_vol == "" and h_sol == "":
                break

            if not is_volume(h_vol):
                raise ValueError(
                    f"{sheet_name}!{ws.cell(row=header_row, column=col).coordinate}: "
                    f"expected a volume header (e.g. 'volume_uL'), got '{ws.cell(row=header_row, column=col).value}'."
                )
            if not is_solvent(h_sol):
                raise ValueError(
                    f"{sheet_name}!{ws.cell(row=header_row, column=col+1).coordinate}: "
                    f"expected a solvent header (e.g. 'solvent_index'), got '{ws.cell(row=header_row, column=col+1).value}'."
                )

            vol_col = col
            sol_col = col + 1
            flush_col: int | None = None

            if (col + 2) <= last_col:
                h_f = norm(ws.cell(row=header_row, column=col + 2).value)
                if is_flush(h_f):
                    flush_col = col + 2
                    col += 3
                else:
                    col += 2
            else:
                col += 2

            stages.append((vol_col, sol_col, flush_col))

        if not stages:
            raise ValueError(f"{sheet_name}: no program stages found in header row {header_row}.")
        return stages

    # ---------------- validation impl ----------------

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
                    cell = ws.cell(row=r, column=c)
                    sid = self._as_int(cell.value, where=f"{name}!{cell.coordinate}")
                    if sid is None:
                        continue
                    if sid not in allowed:
                        raise ValueError(
                            f"{name}!{cell.coordinate}: solvent_id={sid} not in setup.solvents ids={sorted(allowed)}"
                        )

    def _validate_vial_program_bounds_impl(self) -> None:
        """Validate solvent_index (all stages) + flush integer bounds (all stages)."""
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

            header_row = n_rows + 2
            stages = self._parse_program_stages(ws, sheet_name=name, header_row=header_row)

            for i in range(n):
                r = header_row + 1 + i

                for (vol_col, sol_col, flush_col) in stages:
                    sol_cell = ws.cell(row=r, column=sol_col)
                    sidx = self._as_int(sol_cell.value, where=f"{name}!{sol_cell.coordinate}")
                    if sidx is not None:
                        if not (1 <= sidx <= total_slots):
                            raise ValueError(
                                f"{name}!{sol_cell.coordinate}: solvent_index={sidx} out of bounds (allowed 1..{total_slots})"
                            )

                    if flush_col is not None:
                        f_cell = ws.cell(row=r, column=flush_col)
                        spec = self._parse_flush_spec(f_cell.value, where=f"{name}!{f_cell.coordinate}")
                        if isinstance(spec, int):
                            if not (1 <= spec <= total_slots):
                                raise ValueError(
                                    f"{name}!{f_cell.coordinate}: flush solvent_index={spec} out of bounds (allowed 1..{total_slots})"
                                )

    # ------------------------------------------------------------------
    # G-code generation
    # ------------------------------------------------------------------

    def _solvent_id_by_global_solvent_index(self) -> list[int | None]:
        """mapping[solvent_index-1] -> solvent_id or None (if not assigned in grid)."""
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

    def _split_volume_ul(self, total_ul: float, max_ul: float, *, eps: float = 1e-9) -> list[float]:
        """Split total volume into chunks <= max_ul."""
        if total_ul <= 0:
            raise ValueError(f"volume_uL must be > 0, got {total_ul}")
        if max_ul <= 0:
            raise ValueError(f"max_volume_ul must be > 0, got {max_ul}")

        parts: list[float] = []
        remaining = float(total_ul)

        while remaining > max_ul + eps:
            parts.append(float(max_ul))
            remaining -= float(max_ul)

        if remaining > eps:
            parts.append(float(remaining))

        return parts

    def generate_gcode(self, *, do_home: bool = True, do_finish: bool = True, **g_kwargs: Any) -> Path:
        """Read the workbook program and emit gcode using the provided PipetG.

        Multi-stage handling:
          - You can add as many stage groups as you want:
              volume_uL | solvent_index | [flush]
            repeated to the right.
          - Execution is stage-wise:
              stage1 over all vials -> stage2 over all vials -> ...
        """
        if self.wb is None:
            raise RuntimeError("No workbook loaded. Use InputXlsx.from_excel(...) or .load(...) first.")

        solvent_id_map = self._solvent_id_by_global_solvent_index()

        pg = self.pipet
        started_here = False
        if getattr(pg, "g", None) is None:
            pg.start(**g_kwargs)
            started_here = True

        try:
            max_ul = float(pg.max_volume_ul)  # type: ignore[arg-type]

            if do_home:
                pg.home()

            for rack in pg.setup.racks:
                sheet_name = f"{rack.name}_vials"
                ws = self.wb[sheet_name]
                n_rows = int(rack.vial_rows)
                n_cols = int(rack.vial_columns)
                n = n_rows * n_cols

                header_row = n_rows + 2
                stages = self._parse_program_stages(ws, sheet_name=sheet_name, header_row=header_row)

                # stage-wise execution (what you asked for)
                for stage_i, (vol_col, sol_col, flush_col) in enumerate(stages, start=1):
                    for i in range(n):
                        r = header_row + 1 + i

                        vial_cell = ws.cell(row=r, column=1)  # index
                        vol_cell = ws.cell(row=r, column=vol_col)
                        sidx_cell = ws.cell(row=r, column=sol_col)
                        flush_cell = ws.cell(row=r, column=flush_col) if flush_col is not None else None

                        vial_index = self._as_int(vial_cell.value, where=f"{sheet_name}!{vial_cell.coordinate}")
                        if vial_index is None:
                            raise ValueError(f"{sheet_name}!{vial_cell.coordinate}: vial index is empty.")

                        volume_val = vol_cell.value
                        sidx_raw = sidx_cell.value
                        flush_raw = flush_cell.value if flush_cell is not None else None

                        # skip empty stage instruction for this vial
                        if self._is_empty(volume_val) and self._is_empty(sidx_raw) and self._is_empty(flush_raw):
                            continue

                        solvent_index = self._as_int(sidx_raw, where=f"{sheet_name}!{sidx_cell.coordinate}")
                        if solvent_index is None:
                            raise ValueError(
                                f"{sheet_name}!{sidx_cell.coordinate}: solvent_index is empty "
                                f"(stage {stage_i})."
                            )
                        if self._is_empty(volume_val):
                            raise ValueError(
                                f"{sheet_name}!{vol_cell.coordinate}: volume_uL is empty "
                                f"(stage {stage_i})."
                            )

                        volume_ul_total = float(volume_val)
                        chunks = self._split_volume_ul(volume_ul_total, max_ul)

                        # Excel indices are 1-based; PipetG expects 0-based indices
                        vial_idx0 = vial_index - 1
                        solvent_idx0 = solvent_index - 1

                        if not (0 <= solvent_idx0 < len(solvent_id_map)):
                            raise ValueError(
                                f"{sheet_name} row {r} stage {stage_i}: solvent_index={solvent_index} out of mapping range."
                            )

                        dispense_solvent_id = solvent_id_map[solvent_idx0]
                        if dispense_solvent_id is None:
                            raise ValueError(
                                f"{sheet_name} row {r} stage {stage_i}: solvent_index={solvent_index} has no solvent_id assigned in solvent grids."
                            )

                        # flush spec (optional column)
                        spec = None
                        if flush_cell is not None:
                            spec = self._parse_flush_spec(flush_raw, where=f"{sheet_name}!{flush_cell.coordinate}")

                        flush_idx0: int | None = None
                        flush_solvent_id: int | None = None

                        if spec is True:
                            flush_idx0 = solvent_idx0
                            flush_solvent_id = int(dispense_solvent_id)
                        elif isinstance(spec, int):
                            flush_idx0 = spec - 1
                            if not (0 <= flush_idx0 < len(solvent_id_map)):
                                raise ValueError(
                                    f"{sheet_name}!{flush_cell.coordinate}: flush solvent_index={spec} out of mapping range."
                                )
                            _sid = solvent_id_map[flush_idx0]
                            if _sid is None:
                                raise ValueError(
                                    f"{sheet_name}!{flush_cell.coordinate}: flush solvent_index={spec} has no solvent_id assigned in solvent grids."
                                )
                            flush_solvent_id = int(_sid)

                        # flush only ONCE per stage-row, and never more than max_volume_ul per repeat
                        if flush_idx0 is not None and flush_solvent_id is not None:
                            flush_vol = min(volume_ul_total, max_ul)
                            pg.flush(
                                volume_ul=flush_vol,
                                repeats=1,
                                solvent_idx=flush_idx0,
                                solvent_id=flush_solvent_id,
                            )

                        # dispense total amount (chunked)
                        for v_chunk in chunks:
                            pg.process_vial(
                                vial_idx=vial_idx0,
                                solvent_idx=solvent_idx0,
                                solvent_id=int(dispense_solvent_id),
                                volume_ul=v_chunk,
                                slow=False,
                                flush_repeats=0,
                            )

            if do_finish:
                pg.finish()

            return Path(pg.outfile)

        finally:
            if started_here:
                pg.stop()
