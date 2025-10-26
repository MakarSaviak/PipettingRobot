from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint
from pydantic import PositiveFloat, computed_field
import numpy as np


class Syringe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nominal_volume_ul: PositiveFloat
    name: str = Field(index=True)
    inner_diameter_mm: PositiveFloat
    __table_args__ = (UniqueConstraint("nominal_volume_ul",
                                       "name",
                                       "inner_diameter_mm",
                                       name="uq_syringe_identity"),)

    # relationship to the link table
    solvent_links: list['SyringeSolventLink'] = Relationship(
        back_populates="syringe",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    @computed_field(return_type=float)
    @property
    def theoretical_correlation_factor(self) -> float:
        """Calculate correlation factor on demand [mm/µL]."""
        r = float(self.inner_diameter_mm) / 2.0
        return 1.0 / (np.pi * r ** 2)


if __name__ == "__main__":
    pass