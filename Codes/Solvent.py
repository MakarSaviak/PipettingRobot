from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint
from pydantic import PositiveFloat


class Solvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    density_g_per_ml: Optional[PositiveFloat] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    __table_args__ = (UniqueConstraint("name",
                                       "density_g_per_ml",
                                       "notes",
                                       name="uq_solvent_identity"),)

    # relationship to the link table
    syringe_links: list['SyringeSolventLink'] = Relationship(
        back_populates="solvent"
    )
