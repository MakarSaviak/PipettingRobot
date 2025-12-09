from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from .Syringe import Syringe
from .db import create_db_and_tables


class IntegratedSyringe(BaseModel):
    syringe: Syringe           # the SQLModel instance
    min_volume: float | None = None
    offset: float = Field(default=0.0)

    # optional: convenience properties that forward to Syringe
    @property
    def nominal_volume_ul(self) -> float:
        return float(self.syringe.nominal_volume_ul)

    @model_validator(mode="after")
    def set_min_volume_default(self):
        if self.min_volume is None:
            self.min_volume = 0.1 * float(self.syringe.nominal_volume_ul)
        return self

if __name__ == "__main__":
    # python -m Codes.IntegratedSyringe
    create_db_and_tables()
    s = Syringe.get_by_id(1)
    if s:
        print(s.name, s.theoretical_correlation_factor)
    else:
        print("No syringe with id=1 in the database.")

    s_i = IntegratedSyringe(syringe=s)
    print(s_i)
