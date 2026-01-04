from pydantic import BaseModel, PositiveFloat, PositiveInt, NonNegativeFloat, Field
import numpy as np
from typing import Literal

from .config_io import save_model


class Rack(BaseModel):
    name: str
    vial1_x: NonNegativeFloat
    vial1_y: NonNegativeFloat
    vial_dy: NonNegativeFloat
    vial_dx: NonNegativeFloat
    vial_rows: PositiveInt  # I think they mean the number of rows
    vial_columns: PositiveInt  # The number of vial_columns
    z_min_vials: float | None = Field(default=None)

    solvent1_x: NonNegativeFloat
    solvent1_y: NonNegativeFloat
    solvent_rows: PositiveInt
    solvent_columns: PositiveInt
    solvent_dy: PositiveFloat | None
    solvent_dx: PositiveFloat | None
    z_min_solvents: float | None = Field(default=None)

    waste_x: NonNegativeFloat
    waste_y: NonNegativeFloat

    @property
    def positions_vial(self) -> list[tuple[float, float]]:
        return self.__positions("vial")

    @property
    def positions_solvent(self) -> list[tuple[float, float]]:
        return self.__positions("solvent")

    def __positions(self, kind: Literal["vial", "solvent"] = "vial") -> list[tuple[float, float]]:
        if kind == "vial":
            x0, y0 = self.vial1_x, self.vial1_y
            dx, dy = self.vial_dx, self.vial_dy
            n_rows, n_cols = self.vial_rows, self.vial_columns
        else:  # kind == "solvent"
            x0, y0 = self.solvent1_x, self.solvent1_y
            dx = 0.0 if self.solvent_dx is None else self.solvent_dx
            dy = 0.0 if self.solvent_dy is None else self.solvent_dy
            n_rows, n_cols = self.solvent_rows, self.solvent_columns

        n = int(n_rows) * int(n_cols)
        idx = np.arange(n, dtype=int)

        # column-by-column fill
        col = idx // int(n_rows)
        row = idx % int(n_rows)

        x = x0 + col * dx
        y = y0 + row * dy

        return list(map(tuple, np.column_stack((x, y))))


if __name__ == "__main__":
    # python -m Codes.Rack
    rack_data2 = {
        "name": "GC-10-3_3-1",
        "vial1_x": 180.0,
        "vial1_y": 0.0,
        "vial_dy": 15.0,
        "vial_dx": 15.0,
        "vial_rows": 10,
        "vial_columns": 3,
        "solvent1_x": 235.0,
        "solvent1_y": 7.5,
        "solvent_rows": 3,
        "solvent_columns": 1,
        "solvent_dy": 35.0,
        "solvent_dx": None,
        "waste_x": 235.0,
        "waste_y": 110.0
    }
    rack2 = Rack.model_validate(rack_data2)

    # print(rack2.z_min_vials)
    print(rack2.positions_vial)
    # save_model(rack2, "GC-10-3_3-1")
