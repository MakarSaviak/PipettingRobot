from pydantic import BaseModel, PositiveFloat, PositiveInt, NonNegativeFloat
import numpy as np

from .config_io import load_model


class Rack(BaseModel):
    name: str
    vial1_x: NonNegativeFloat
    vial1_y: NonNegativeFloat
    solvent1_x: NonNegativeFloat
    solvent1_y: NonNegativeFloat
    waste_x: NonNegativeFloat
    waste_y: NonNegativeFloat
    dy_s: NonNegativeFloat
    dx_s: NonNegativeFloat
    number_of_solvents: PositiveInt
    increment_y: PositiveFloat | None
    vials_per_row: PositiveInt #I think they mean the number of rows
    columns: PositiveInt #The number of columns

    @property
    def vial_positions(self) -> list[tuple[float, float]]:
        n_rows = self.vials_per_row
        n_cols = self.columns
        n = n_rows * n_cols

        idx = np.arange(n, dtype=int)
        col = idx // n_rows  # 0,0,...0, 1,1,...1, 2,2,...2
        row = idx % n_rows  # 0..n_rows-1 repeating

        x = self.vial1_x + col * self.dx_s
        y = self.vial1_y + row * self.dy_s

        # Nx2 array -> list[(x,y), ...]
        return list(map(tuple, np.column_stack((x, y))))


if __name__ == "__main__":
    # python -m Codes.Rack
    rack = load_model(Rack, "GC-10-by-3_Solvent-20ml-3-by-1")
    positions = rack.vial_positions
    for pos in positions:
        print(pos)
    print(len(positions))
