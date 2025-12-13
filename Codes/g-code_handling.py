from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, PositiveInt, PositiveFloat
from mecode import G

from .Setup import Setup
from .Syringe import Syringe
from .SyringeSolventLink import SyringeSolventLink

#TODO rewrite all functions
class PipetG(BaseModel):
    outfile: Path
    setup: Setup
    syringe_id: PositiveInt  # required

    # runtime-only (underscore attrs are NOT pydantic fields in v2)
    g: G | None = None

    max_volume_ul: float | None = None
    waste_pos: tuple[float, float] | None = None
    solvent_positions: tuple[float, float] | None = None
    vial_positions: tuple[float, float] | None = None
    syringe_solvents: list[SyringeSolventLink] | None = None

    Z_min: float | None = None
    Z_max: float | None = None
    Z_slow: float | None = None
    Fz: float | None = None
    Fxy: float | None = None
    Fa_push: float | None = None
    Fa_push_slow: float | None = None
    Fa_pull: float | None = None
    Rest_x: float | None = None
    Rest_y: float | None = None

    # ---------- lifecycle ----------
    def start(self, **g_kwargs: Any) -> None:
        self.g = G(outfile=str(self.outfile), **g_kwargs)
        self._init_from_setup()

    def stop(self) -> None:
        if self.g is None:
            return
        g = self.g
        if hasattr(g, "teardown"):
            try:
                g.teardown()
            except Exception:
                pass
        self.g = None

    def __enter__(self) -> "PipetG":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def _require_g(self) -> G:
        if self.g is None:
            raise RuntimeError("PipetG is not started. Call .start() or use `with PipetG(...) as g:`.")
        return self.g

    def _require_ready(self) -> None:
        if (
            self.max_volume_ul is None
            or self.waste_pos is None
            or self.solvent_positions is None
            or self.cal_by_solvent is None
            or self.Z_min is None
            or self.Z_max is None
            or self.Z_slow is None
            or self.Fz is None
            or self.Fxy is None
            or self.Fa_push is None
            or self.Fa_push_slow is None
            or self.Fa_pull is None
            or self.Rest_x is None
            or self.Rest_y is None
        ):
            raise RuntimeError("PipetG not initialized. Call start() first.")

    def __getattr__(self, name: str):
        # forward unknown attributes to mecode.G once started
        g = object.__getattribute__(self, "g")
        if g is None:
            raise AttributeError(name)
        return getattr(g, name)

    # ---------- setup picking ----------
    def _pick_syringe(self):
        s = next((x for x in self.setup.syringes if x.id == self.syringe_id), None)
        if s is None:
            raise ValueError(f"No syringe with id={self.syringe_id} in setup.")
        if s.id is None:
            raise ValueError("Selected syringe has id=None (not saved to DB?).")
        return s

    # ---------- init ----------
    def _init_from_setup(self) -> None:
        rack = self.setup.racks[0]
        machine = self.setup.machine
        syringe = Syringe.get_by_id(self.syringe_id) 

        # syringe
        self.max_volume_ul = syringe.nominal_volume_ul

        # machine
        self.Z_min =   machine.Z_min
        self.Z_max =   machine.Z_max
        self.Z_slow =  machine.Z_slow
        self.Fz =      machine.Fz
        self.Fxy =     machine.Fxy
        self.Fa_push = machine.Fa_push
        self.Fa_push_slow = machine.Fa_push_slow
        self.Fa_pull = machine.Fa_pull
        self.Rest_x =  machine.Rest_x
        self.Rest_y =  machine.Rest_y

        # rack
        self.waste_pos = (rack.waste_x, rack.waste_y)

        # derived
        self.solvent_positions = rack.solvent_positions
        self.vial_positions = rack.vial_positions
        self.syringe_solvents = self.setup.syringe_solvents
        
        self._require_ready()

    # ---------- displacement ----------
    def displacement(self, volume_ul: PositiveFloat, solvent_id: PositiveInt) -> float:
        self._require_ready()

        v = volume_ul

        if v > self.max_volume_ul:  # type: ignore[arg-type]
            raise ValueError(f"Volume too large: {v} µL (max {self.max_volume_ul}).")

        #link = self.syringe_solvents.get_link()

        factor, backlash = cal[solvent_id]
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
        g.move(z=self.Z_max, F=self.Fz)
        g.move(self.Rest_x, self.Rest_y, F=self.Fxy)
        g.move(z=self.Z_min, F=self.Fz)
        g.write("M84")

    def remove_from_vial(self, x: float, y: float, volume_ul: float, solvent_number: str) -> None:
        self._require_ready()
        g = self._require_g()

        g.write("remove_from_vial")
        g.absolute()

        disp = self.displacement(volume_ul, solvent_number)

        g.move(z=self.Z_max, F=self.Fz)
        g.move(x, y, F=self.Fxy)
        g.move(z=self.Z_min, F=self.Fz)

        g.relative()
        g.move(A=disp, F=self.Fa_pull)
        g.absolute()

        g.move(z=self.Z_max, F=self.Fz)

    def fill_vial(self, x: float, y: float, slow_push: bool = False) -> None:
        self._require_ready()
        g = self._require_g()

        g.write("fill_vial")
        g.absolute()

        g.move(z=self.Z_max, F=self.Fz)
        g.move(x, y, F=self.Fxy)

        if slow_push:
            g.move(z=self.Z_slow, F=self.Fz)
            g.move(A=0, F=self.Fa_push_slow)
        else:
            g.move(z=self.Z_min, F=self.Fz)
            g.move(A=0, F=self.Fa_push)

        g.move(z=self.Z_max, F=self.Fz)

    def flush(self, volume_ul: float, *, repeats: int = 1, solvent_name: str) -> None:
        self._require_ready()
        g = self._require_g()

        pos = self.solvent_positions  # type: ignore[assignment]
        if solvent_name not in pos:
            raise KeyError(f"Unknown solvent '{solvent_name}'. Known: {list(pos)}")

        g.write("flush")
        sx, sy = pos[solvent_name]

        for _ in range(int(repeats)):
            self.remove_from_vial(sx, sy, volume_ul, solvent_name)

            wx, wy = self.waste_pos  # type: ignore[misc]
            g.write("fill_vial")
            g.absolute()
            g.move(**{self.Z_AXIS: self.Z_max}, F=self.Fz)
            g.move(wx, wy, F=self.Fxy)
            g.move(**{self.Z_AXIS: self.Z_min}, F=self.Fz)
            g.move(**{self.P_AXIS: 0}, F=self.Fa_push)
            g.move(**{self.Z_AXIS: self.Z_max}, F=self.Fz)

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

        pos = self.solvent_positions  # type: ignore[assignment]
        sx, sy = pos[solvent_name]
        self.remove_from_vial(sx, sy, volume_ul, solvent_name)

        vx, vy = self.vial_position(vial_index_1based)
        self.fill_vial(vx, vy, slow_push=slow_push)
