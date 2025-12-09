from datetime import date
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship, Session, create_engine
from sqlalchemy import event
from pydantic import PositiveFloat

from .Syringe import Syringe
from .Solvent import Solvent
from .db import create_db_and_tables

class SyringeSolventLink(SQLModel, table=True):
    # composite PK prevents duplicate pairs (no second link for same person+tool)
    syringe_id: int = Field(foreign_key="syringe.id", primary_key=True)
    solvent_id: int = Field(foreign_key="solvent.id", primary_key=True)

    # optional metadata about the liquid handling
    calibrated: bool = False
    backlash_correction: PositiveFloat = Field(default=0.0)
    real_correlation_factor: Optional[float] = Field(default=None)
    since: Optional[date] = None

    syringe: Syringe = Relationship(back_populates="solvent_links")
    solvent: Solvent = Relationship(back_populates="syringe_links")

    @classmethod
    def __declare_last__(cls):
        @event.listens_for(cls, "before_insert")
        def _fill_factor_on_insert(_mapper, _connection, target: 'SyringeSolventLink'):
            if target.real_correlation_factor is None and getattr(target, "syringe", None) is not None:
                target.real_correlation_factor = target.syringe.theoretical_correlation_factor
