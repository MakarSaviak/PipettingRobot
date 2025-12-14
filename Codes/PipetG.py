from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, PositiveInt, PositiveFloat, NonNegativeInt, NonNegativeFloat, ConfigDict, Field
from mecode import G

from .Setup import Setup

#TODO check for correctness
class PipetG(BaseModel):
    outfile: Path
    setup: Setup
    syringe_id: PositiveInt  # required

    g: G | None = Field(default=None, exclude=True)
    model_config = ConfigDict(arbitrary_types_allowed=True)

    max_volume_ul: PositiveFloat | None = Field(default=None, exclude=True, repr=False)
    waste_pos: tuple[NonNegativeFloat, NonNegativeFloat] | None = Field(default=None, exclude=True, repr=False)
    solvent_positions: list[tuple[NonNegativeFloat, NonNegativeFloat]] | None = Field(default=None, exclude=True,
                                                                                      repr=False)
    vial_positions: list[tuple[NonNegativeFloat, NonNegativeFloat]] | None = Field(default=None, exclude=True,
                                                                                   repr=False)
    Z_min: float | None = Field(default=None, exclude=True, repr=False)
    Z_max: float | None = Field(default=None, exclude=True, repr=False)
    Z_slow: float | None = Field(default=None, exclude=True, repr=False)
    Fz: float | None = Field(default=None, exclude=True, repr=False)
    Fxy: float | None = Field(default=None, exclude=True, repr=False)
    Fa_push: float | None = Field(default=None, exclude=True, repr=False)
    Fa_push_slow: float | None = Field(default=None, exclude=True, repr=False)
    Fa_pull: float | None = Field(default=None, exclude=True, repr=False)
    Rest_x: float | None = Field(default=None, exclude=True, repr=False)
    Rest_y: float | None = Field(default=None, exclude=True, repr=False)

    # ---------- lifecycle ----------
    def start(self, **g_kwargs: Any) -> None:
        self.g = G(outfile=str(self.outfile), **g_kwargs)
        try:
            self._init_from_setup()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        if self.g is None:
            return
        try:
            self.g.teardown()
        finally:
            self.g = None # even if teardown fails

    # -------- context manager --------
    def __enter__(self) -> "PipetG":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
    
    # ---------- g-getter ----------
    def _get_g(self) -> G:
        self._get_ready()
        if self.g is None:
            raise RuntimeError("PipetG is not started. Call .start() or use `with PipetG(...) as g:`.")
        return self.g

    def _get_ready(self) -> None:
        if (
            self.max_volume_ul is None
            or self.waste_pos is None
            or self.solvent_positions is None
            or self.vial_positions is None
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
    def _get_syringe(self):
        s = next((x for x in self.setup.syringes if x.id == self.syringe_id), None)
        if s is None:
            raise ValueError(f"No syringe with id={self.syringe_id} in setup.")
        if s.id is None:
            raise ValueError("Selected syringe has id=None (not saved to DB?).")
        return s

    # ---------- init ----------
    def _init_from_setup(self) -> None:
        if len(self.setup.racks) == 0:
            raise ValueError("Racks are not set in setup.")

        syringe = self._get_syringe()
        racks = self.setup.racks
        machine = self.setup.machine
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
        self.waste_pos = (racks[0].waste_x, racks[0].waste_y) #TODO figure it out how to deal with multiple wastes

        # derived
        self.solvent_positions = self.setup.solvent_positions
        self.vial_positions = self.setup.vial_positions

        self._get_ready()

    # ---------- displacement ----------
    def displacement(self, volume_ul: PositiveFloat, solvent_id: PositiveInt) -> float:
        self._get_ready()

        v = volume_ul
        if v > self.max_volume_ul:  # type: ignore[arg-type]
            raise ValueError(f"Volume too large: {v} µL (max {self.max_volume_ul}).")

        link = self.setup.get_link(self.syringe_id, solvent_id)
        if link is None:
            raise ValueError(f"No SyringeSolventLink for syringe_id={self.syringe_id}, solvent_id={solvent_id}")
        factor = link.real_correlation_factor
        backlash = link.backlash_correction
        return v * factor + backlash

    # ---------- gcode blocks ----------

    def move_to(self, *, slow: bool=False, **attr) -> None:
        if "z" in attr or "A" in attr:
            raise ValueError("move_to() expects only XY/feed args, not z or A.")

        g = self._get_g()
        g.absolute()
        g.move(z=self.Z_max, F=self.Fz)
        g.move(**attr)
        if slow:
            g.move(z=self.Z_slow, F=self.Fz)
        else:
            g.move(z=self.Z_min, F=self.Fz)

    # ----------- main funcs -----------
    def home(self) -> None:
        g = self._get_g()
        g.write("G21")     # mm
        g.write("G28 Z")   # home Z
        g.write("G28 Y X A")

    def finish(self) -> None:
        g = self._get_g()

        self.move_to(x=self.Rest_x, y=self.Rest_y, F=self.Fxy)
        g.write("M84")

    def remove_from_vial(self, x: float, y: float, volume_ul: float, solvent_id: PositiveInt) -> None:
        g = self._get_g()

        g.write("remove_from_vial")

        disp = self.displacement(volume_ul, solvent_id)

        self.move_to(x=x, y=y, F=self.Fxy)

        g.relative()
        g.move(A=disp, F=self.Fa_pull)
        g.absolute()

        g.move(z=self.Z_max, F=self.Fz)

    def fill_vial(self, x: float, y: float, slow: bool = False) -> None:
        g = self._get_g()

        g.write("fill_vial")

        self.move_to(slow=slow, x=x, y=y, F=self.Fxy)
        if slow:
            g.move(A=0, F=self.Fa_push_slow)
        else:
            g.move(A=0, F=self.Fa_push)

        g.move(z=self.Z_max, F=self.Fz)

    def flush(self, volume_ul: float, *,
              repeats: PositiveInt = 1,
              solvent_idx: NonNegativeInt,
              solvent_id: PositiveInt) -> None:

        g = self._get_g()

        pos = self.solvent_positions  # type: ignore[assignment]
        if not (solvent_idx < len(pos)):
            raise IndexError(f"Solvent idx '{solvent_idx}' is out of bound {len(pos)-1}.")

        g.write("flush")
        sx, sy = pos[solvent_idx]

        for _ in range(int(repeats)):
            self.remove_from_vial(sx, sy, volume_ul, solvent_id)

            wx, wy = self.waste_pos  # type: ignore[misc]
            self.fill_vial(wx, wy)

    def process_vial(
        self,
        *,
        vial_idx: NonNegativeInt,
        solvent_idx: NonNegativeInt,
        solvent_id: PositiveInt,
        volume_ul: float,
        slow: bool = False,
        flush_repeats: NonNegativeInt = 0,
    ) -> None:
        if flush_repeats > 0:
            self.flush(volume_ul, repeats=flush_repeats, solvent_idx=solvent_idx, solvent_id=solvent_id)

        pos = self.solvent_positions  # type: ignore[assignment]
        sx, sy = pos[solvent_idx]
        self.remove_from_vial(sx, sy, volume_ul, solvent_id=solvent_id)

        vx, vy = self.vial_positions[vial_idx]
        self.fill_vial(vx, vy, slow=slow)
