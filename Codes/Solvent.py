from sqlmodel import SQLModel, Field, Relationship
from pydantic import PositiveFloat, NonNegativeInt
from sqlalchemy import UniqueConstraint, exc
from sqlmodel import select
from typing import cast

from .db import get_session


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
        back_populates="solvent",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    @classmethod
    def get_by_id(cls, solvent_id: int) -> "Solvent | None":
        # Local import avoids circular imports at module import time
        from .db import get_session

        with get_session() as session:
            return session.get(cls, solvent_id)

    @classmethod
    def create(cls, **data) -> "Solvent":
        """
        Add a solvent to the database.
        :param name: str.
        :param density_g_per_ml: PositiveFloat.
        :param notes: str.
        :return: a solvent instance.
        """

        obj = cls(**data)

        with get_session() as session:
            try:
                session.add(obj); session.commit(); session.refresh(obj)
            except exc.IntegrityError as e:
                session.rollback()
                raise ValueError(
                    f"solvent already exists or violates constraints: "
                    f"name='{obj.name}', nominal_volume_ul={obj.nominal_volume_ul}, "
                    f"inner_diameter_mm={obj.inner_diameter_mm}"
                ) from e
            except Exception as e:
                session.rollback()
                raise ValueError(f"Could not create solvent '{obj.name}'") from e

            return obj

    @classmethod
    def delete_by_id(cls, solvent_id: NonNegativeInt) -> bool:
        """
        Delete solvent with given id.
        Returns True if something was deleted, False if not found.
        """
        with get_session() as session:
            obj = session.get(cls, solvent_id)
            if obj is None:
                return False

            try:
                session.delete(obj); session.commit()
            except exc.IntegrityError as e:
                session.rollback()
                raise ValueError(
                    f"Could not delete solvent id={solvent_id} due to database constraints "
                    f"(it may still be referenced)."
                ) from e
            except Exception as e:
                session.rollback()
                raise ValueError(f"Could not delete solvent id={solvent_id}.") from e

        return True

    @classmethod
    def get_all(cls) -> list["Solvent"]:
        with get_session() as session:
            rows = session.exec(select(cls)).all()
            return cast(list["Solvent"], rows)
