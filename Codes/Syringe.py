import numpy as np
from pydantic import BaseModel, computed_field, PositiveFloat, PositiveInt


class Syringe(BaseModel):
    nominal_volume: PositiveFloat
    name: str
    inner_diameter: PositiveFloat  # in [mm]
    id: PositiveInt

    # Make the theoretical correlation factor available on every instance.
    # Units: [mm/µL] = 1 / (π * (ID/2)^2)
    @computed_field
    @property
    def theoretical_correlation_factor(self) -> float:
        return 1 / (np.pi * (self.inner_diameter / 2) ** 2)


if __name__ == "__main__":
    syringe1000 = Syringe(
        nominal_volume=100,
        name = "Hamilton1001",
        inner_diameter=4.61
    )
    print(syringe1000.theoretical_correlation_factor)
