import numpy as np
from pydantic import BaseModel, Field, computed_field
from typing import List, Optional

class Syringe(BaseModel):
    nominal_volume: float
    name: str
    inner_diameter: float # in [mm]

    def theoretical_correlation_factor(self) -> float:
        return 1 / (np.pi * (self.inner_diameter / 2) ** 2)
