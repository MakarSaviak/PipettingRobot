from pydantic import BaseModel, PositiveFloat, PositiveInt, NonNegativeFloat
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

    solvent1_x: NonNegativeFloat
    solvent1_y: NonNegativeFloat
    solvent_rows: PositiveInt
    solvent_columns: PositiveInt
    solvent_dy: PositiveFloat | None
    solvent_dx: PositiveFloat | None

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
        "name": "counterion-96_EDIT-THIS",
        "vial1_x": 0,
        "vial1_y": 0,
        "solvent1_x": 100,
        "solvent1_y": 7.5,
        "waste_x": 100,
        "waste_y": 110,
        "vial_dy": 10,
        "vial_dx": 10,
        "vial_rows": 6,
        "vial_columns": 16,
        "solvent_rows": 6,
        "solvent_columns": 16,
        "solvent_dy": 10,
        "solvent_dx": 10
    }
    rack2 = Rack.model_validate(rack_data2)

    save_model(rack2, "counterion-96_EDIT-THIS")
