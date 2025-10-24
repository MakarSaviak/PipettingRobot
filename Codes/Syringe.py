import numpy as np
from pydantic import BaseModel, Field, computed_field, PositiveFloat
from typing import List, Optional


class Syringe(BaseModel):
    nominal_volume: PositiveFloat
    name: str
    inner_diameter: PositiveFloat # in [mm]

    def theoretical_correlation_factor(self) -> float:
        return 1 / (np.pi * (self.inner_diameter / 2) ** 2)


if __name__ == "__main__":
    syringe_solvent = Syringe(
        nominal_volume=100,
        name = "Hamilton1001",
        inner_diameter=9.2
    )
