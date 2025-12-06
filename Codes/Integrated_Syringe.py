from __future__ import annotations

from pydantic import BaseModel, Field
from Syringe import Syringe


class IntegratedSyringe(BaseModel):
    syringe: Syringe           # the SQLModel instance
    min_volume: float
    offset: float = Field(default=0.0)

    # optional: convenience properties that forward to Syringe
    @property
    def nominal_volume_ul(self) -> float:
        return float(self.syringe.nominal_volume_ul)


if __name__ == "__main__":
    # Example: build a Syringe, then wrap it
    s = Syringe(
        nominal_volume_ul=1000,
        name="Hamilton 1 mL",
        inner_diameter_mm=4.61,
    )
    integrated = IntegratedSyringe(syringe=s, min_volume=0.0, offset=0.0)
    print(integrated)
    print("CF:", integrated.theoretical_correlation_factor)
