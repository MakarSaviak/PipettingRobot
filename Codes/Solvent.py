from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint
from pydantic import PositiveFloat


class Solvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    density_g_per_ml: PositiveFloat | None = Field(default=None)
    notes: str | None = Field(default=None)
    __table_args__ = (UniqueConstraint("name",
                                       "density_g_per_ml",
                                       "notes",
                                       name="uq_solvent_identity"),)

    # relationship to the link table
    syringe_links: list['SyringeSolventLink'] = Relationship(
        back_populates="solvent"
    )

    @classmethod
    def get_by_id(cls, solvent_id: int) -> "Solvent | None":
        # Local import avoids circular imports at module import time
        from .db import get_session

        with get_session() as session:
            return session.get(cls, solvent_id)
        