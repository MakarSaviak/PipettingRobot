from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, PositiveInt
from mecode import G

from .Setup import Setup

#TODO rewrite all functions
class PipetG(BaseModel):
    Z_AXIS: str = "z"
    P_AXIS: str = "A"

    outfile: Path
    setup: Setup
    syringe_id: PositiveInt  # required

    # runtime-only (underscore attrs are NOT pydantic fields in v2)
    _g: G | None = None

    _max_volume_ul: float | None = None
    _waste_pos: tuple[float, float] | None = None
    _solvent_positions: dict[str, tuple[float, float]] | None = None
    _cal_by_solvent: dict[str, tuple[float, float]] | None = None

    _Z_min: float | None = None
    _Z_max: float | None = None
    _Z_slow: float | None = None
    _Fz: float | None = None
    _Fxy: float | None = None
    _Fa_push: float | None = None
    _Fa_push_slow: float | None = None
    _Fa_pull: float | None = None
    _Rest_x: float | None = None
    _Rest_y: float | None = None

    # ---------- lifecycle ----------
    def start(self, **g_kwargs: Any) -> None:
        self._g = G(outfile=str(self.outfile), **g_kwargs)
        self._init_from_setup()

    def stop(self) -> None:
        if self._g is None:
            return
        g = self._g
        if hasattr(g, "teardown"):
            try:
                g.teardown()
            except Exception:
                pass
        self._g = None

    def __enter__(self) -> "PipetG":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def _require_g(self) -> G:
        if self._g is None:
            raise RuntimeError("PipetG is not started. Call .start() or use `with PipetG(...) as g:`.")
        return self._g

    def _require_ready(self) -> None:
        if (
            self._max_volume_ul is None
            or self._waste_pos is None
            or self._solvent_positions is None
            or self._cal_by_solvent is None
            or self._Z_min is None
            or self._Z_max is None
            or self._Z_slow is None
            or self._Fz is None
            or self._Fxy is None
            or self._Fa_push is None
            or self._Fa_push_slow is None
            or self._Fa_pull is None
            or self._Rest_x is None
            or self._Rest_y is None
        ):
            raise RuntimeError("PipetG not initialized. Call start() first.")

    def __getattr__(self, name: str):
        # forward unknown attributes to mecode.G once started
        g = object.__getattribute__(self, "_g")
        if g is None:
            raise AttributeError(name)
        return getattr(g, name)

    # ---------- setup picking ----------
    def _pick_single_rack(self):
        if len(self.setup.racks) != 1:
            raise ValueError(f"Expected exactly 1 rack in setup, got {len(self.setup.racks)}.")
        return self.setup.racks[0]

    def _pick_single_machine(self):
        if len(self.setup.machines) != 1:
            raise ValueError(f"Expected exactly 1 machine in setup, got {len(self.setup.machines)}.")
        return self.setup.machines[0]

    def _pick_syringe(self):
        s = next((x for x in self.setup.syringes if x.id == self.syringe_id), None)
        if s is None:
            raise ValueError(f"No syringe with id={self.syringe_id} in setup.")
        if s.id is None:
            raise ValueError("Selected syringe has id=None (not saved to DB?).")
        return s

    # ---------- init ----------
    def _init_from_setup(self) -> None:
        rack = self._pick_single_rack()
        machine = self._pick_single_machine()
        syringe = self._pick_syringe()

        # syringe
        self._max_volume_ul = float(syringe.nominal_volume_ul)

        # machine
        self._Z_min = float(machine.Z_min)
        self._Z_max = float(machine.Z_max)
        self._Z_slow = float(machine.Z_slow)
        self._Fz = float(machine.Fz)
        self._Fxy = float(machine.Fxy)
        self._Fa_push = float(machine.Fa_push)
        self._Fa_push_slow = float(machine.Fa_push_slow)
        self._Fa_pull = float(machine.Fa_pull)
        self._Rest_x = float(machine.Rest_x)
        self._Rest_y = float(machine.Rest_y)

        # rack
        self._waste_pos = (float(rack.waste_x), float(rack.waste_y))

        # derived
        self._solvent_positions = self._build_solvent_positions(rack)
        self._cal_by_solvent = self._build_calibration(syringe)

        self._require_ready()

    def _build_solvent_positions(self, rack) -> dict[str, tuple[float, float]]:
        rows = int(rack.solvent_rows)
        cols = int(rack.solvent_columns)
        cap = rows * cols

        solvents = list(self.setup.solvents)
        if len(solvents) > cap:
            raise ValueError(f"Rack solvent grid capacity is {cap}, but setup has {len(solvents)} solvents.")

        dx = rack.solvent_dx
        dy = rack.solvent_dy

        # if grid needs spacing, spacing must be provided
        if cols > 1 and dx is None:
            raise ValueError("rack.solvent_dx is None but solvent_columns > 1.")
        if rows > 1 and dy is None:
            raise ValueError("rack.solvent_dy is None but solvent_rows > 1.")

        dx_f = 0.0 if dx is None else float(dx)
        dy_f = 0.0 if dy is None else float(dy)

        x0 = float(rack.solvent1_x)
        y0 = float(rack.solvent1_y)

        out: dict[str, tuple[float, float]] = {}
        for i, sol in enumerate(solvents):
            r = i // cols
            c = i % cols
            out[sol.name] = (x0 + c * dx_f, y0 + r * dy_f)
        return out

    def _build_calibration(self, syringe) -> dict[str, tuple[float, float]]:
        default_factor = float(syringe.theoretical_correlation_factor)
        out: dict[str, tuple[float, float]] = {}

        for sol in self.setup.solvents:
            # best: match by ids (what you actually use in DB)
            link = None
            if sol.id is not None:
                link = next(
                    (
                        l for l in self.setup.syringe_solvents
                        if l.syringe_id == syringe.id and l.solvent_id == sol.id
                    ),
                    None,
                )

            if link is None:
                out[sol.name] = (default_factor, 0.0)
                continue

            factor = float(link.real_correlation_factor) if link.real_correlation_factor is not None else default_factor
            backlash = float(link.backlash_correction) if link.backlash_correction is not None else 0.0
            out[sol.name] = (factor, backlash)

        return out

    # ---------- geometry ----------
    def vial_position(self, vial_index_1based: int) -> tuple[float, float]:
        rack = self._pick_single_rack()

        i = int(vial_index_1based) - 1
        rows = int(rack.vial_rows)
        cols = int(rack.vial_columns)
        total = rows * cols
        if not (0 <= i < total):
            raise IndexError(f"Vial index out of bounds: {vial_index_1based} (rack has {total} vials).")

        col = i // rows  # column-by-column
        row = i % rows

        x = float(rack.vial1_x) + col * float(rack.vial_dx)
        y = float(rack.vial1_y) + row * float(rack.vial_dy)
        return x, y

    # ---------- displacement ----------
    def displacement(self, volume_ul: float, solvent_name: str) -> float:
        self._require_ready()

        v = float(volume_ul)
        if v < 0:
            raise ValueError(f"Volume must be >= 0 µL, got {v}.")
        if v > float(self._max_volume_ul):  # type: ignore[arg-type]
            raise ValueError(f"Volume too large: {v} µL (max {self._max_volume_ul}).")

        cal = self._cal_by_solvent  # type: ignore[assignment]
        if solvent_name not in cal:
            raise KeyError(f"Unknown solvent '{solvent_name}'. Known: {list(cal)}")

        factor, backlash = cal[solvent_name]
        return v * factor + backlash

    # ---------- gcode blocks ----------
    def prologue(self) -> None:
        g = self._require_g()
        g.write("G21")     # mm
        g.write("G28 Z")   # home Z
        g.write("G28 Y X A")

    def home(self) -> None:
        self._require_ready()
        g = self._require_g()

        g.absolute()
        g.move(**{self.Z_AXIS: self._Z_max}, F=self._Fz)
        g.move(self._Rest_x, self._Rest_y, F=self._Fxy)
        g.move(**{self.Z_AXIS: self._Z_min}, F=self._Fz)
        g.write("M84")

    def remove_from_vial(self, x: float, y: float, volume_ul: float, solvent_name: str) -> None:
        self._require_ready()
        g = self._require_g()

        g.write("remove_from_vial")
        g.absolute()

        disp = self.displacement(volume_ul, solvent_name)

        g.move(**{self.Z_AXIS: self._Z_max}, F=self._Fz)
        g.move(float(x), float(y), F=self._Fxy)
        g.move(**{self.Z_AXIS: self._Z_min}, F=self._Fz)

        g.relative()
        g.move(**{self.P_AXIS: disp}, F=self._Fa_pull)
        g.absolute()

        g.move(**{self.Z_AXIS: self._Z_max}, F=self._Fz)

    def fill_vial(self, x: float, y: float, *, slow_push: bool = False) -> None:
        self._require_ready()
        g = self._require_g()

        g.write("fill_vial")
        g.absolute()

        g.move(**{self.Z_AXIS: self._Z_max}, F=self._Fz)
        g.move(float(x), float(y), F=self._Fxy)

        if slow_push:
            g.move(**{self.Z_AXIS: self._Z_slow}, F=self._Fz)
            g.move(**{self.P_AXIS: 0}, F=self._Fa_push_slow)
        else:
            g.move(**{self.Z_AXIS: self._Z_min}, F=self._Fz)
            g.move(**{self.P_AXIS: 0}, F=self._Fa_push)

        g.move(**{self.Z_AXIS: self._Z_max}, F=self._Fz)

    def flush(self, volume_ul: float, *, repeats: int = 1, solvent_name: str) -> None:
        self._require_ready()
        g = self._require_g()

        pos = self._solvent_positions  # type: ignore[assignment]
        if solvent_name not in pos:
            raise KeyError(f"Unknown solvent '{solvent_name}'. Known: {list(pos)}")

        g.write("flush")
        sx, sy = pos[solvent_name]

        for _ in range(int(repeats)):
            self.remove_from_vial(sx, sy, volume_ul, solvent_name)

            wx, wy = self._waste_pos  # type: ignore[misc]
            g.write("fill_vial")
            g.absolute()
            g.move(**{self.Z_AXIS: self._Z_max}, F=self._Fz)
            g.move(wx, wy, F=self._Fxy)
            g.move(**{self.Z_AXIS: self._Z_min}, F=self._Fz)
            g.move(**{self.P_AXIS: 0}, F=self._Fa_push)
            g.move(**{self.Z_AXIS: self._Z_max}, F=self._Fz)

    def process_vial(
        self,
        *,
        vial_index_1based: int,
        solvent_name: str,
        volume_ul: float,
        flush_required: bool,
        slow_push: bool = False,
        flush_repeats: int = 1,
    ) -> None:
        if flush_required:
            self.flush(volume_ul, repeats=flush_repeats, solvent_name=solvent_name)

        pos = self._solvent_positions  # type: ignore[assignment]
        sx, sy = pos[solvent_name]
        self.remove_from_vial(sx, sy, volume_ul, solvent_name)

        vx, vy = self.vial_position(vial_index_1based)
        self.fill_vial(vx, vy, slow_push=slow_push)
