from __future__ import annotations

from pydantic import BaseModel, Field
from .Syringe import Syringe


class IntegratedSyringe(BaseModel):
    syringe: Syringe           # the SQLModel instance
    min_volume: float
    offset: float = Field(default=0.0)

    # optional: convenience properties that forward to Syringe
    @property
    def nominal_volume_ul(self) -> float:
        return float(self.syringe.nominal_volume_ul)
