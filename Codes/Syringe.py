from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint, exc
from pydantic import PositiveFloat, computed_field, NonNegativeInt
import numpy as np

from .db import get_session


class Syringe(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
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

    @classmethod
    def get_by_id(cls, syringe_id: int) -> "Syringe | None":
        # Local import avoids circular imports at module import time

        with get_session() as session:
            return session.get(cls, syringe_id)

    @classmethod
    def create(cls, **data) -> "Syringe":
        """
        Add a syringe to the database.
        :param name: str.
        :param nominal_volume_uL: PositiveFloat.
        :param inner_diameter_mm: PositiveFloat.
        :return: a Syringe instance.
        """

        obj = cls(**data)

        with get_session() as session:
            try:
                session.add(obj); session.commit(); session.refresh(obj)
            except exc.IntegrityError as e:
                session.rollback()
                raise ValueError(
                    f"Syringe already exists or violates constraints: "
                    f"name='{obj.name}', nominal_volume_ul={obj.nominal_volume_ul}, "
                    f"inner_diameter_mm={obj.inner_diameter_mm}"
                ) from e
            except Exception as e:
                session.rollback()
                raise ValueError(f"Could not create syringe '{obj.name}'") from e

            return obj

    @classmethod
    def delete_by_id(cls, syringe_id: NonNegativeInt) -> bool:
        """
        Delete syringe with given id.
        Returns True if something was deleted, False if not found.
        """
        with get_session() as session:
            obj = session.get(cls, syringe_id)
            if obj is None:
                return False

            try:
                session.delete(obj); session.commit()
            except exc.IntegrityError as e:
                session.rollback()
                raise ValueError(
                    f"Could not delete syringe id={syringe_id} due to database constraints "
                    f"(it may still be referenced)."
                ) from e
            except Exception as e:
                session.rollback()
                raise ValueError(f"Could not delete syringe id={syringe_id}.") from e

        return True
