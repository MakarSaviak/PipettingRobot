from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import event, exc
from pydantic import NonNegativeFloat, PositiveFloat
from datetime import datetime

from .Syringe import Syringe
from .Solvent import Solvent
from .db import get_session


class SyringeSolventLink(SQLModel, table=True):
    syringe_id: int = Field(foreign_key="syringe.id", primary_key=True)
    solvent_id: int = Field(foreign_key="solvent.id", primary_key=True)

    calibrated: bool = False
    backlash_correction: NonNegativeFloat = Field(default=0.0)
    real_correlation_factor: float | None = Field(default=None)
    since: datetime | None = None

    syringe: Syringe = Relationship(back_populates="solvent_links")
    solvent: Solvent = Relationship(back_populates="syringe_links")

    @classmethod    # to ensure that any way of creation will set the initial correlation factor to the theoretical one
    def __declare_last__(cls):
        @event.listens_for(cls, "before_insert")
        def _fill_factor_on_insert(_mapper, _connection, target: 'SyringeSolventLink'):
            if target.real_correlation_factor is None and getattr(target, "syringe", None) is not None:
                target.real_correlation_factor = target.syringe.theoretical_correlation_factor

    @classmethod
    def create(cls, **data) -> "SyringeSolventLink":
        syringe_id = data.get("syringe_id")
        solvent_id = data.get("solvent_id")
        if syringe_id is None or solvent_id is None:
            raise ValueError("create() needs syringe_id and solvent_id")

        with get_session() as session:
            if data.get("real_correlation_factor") is None:
                syr = session.get(Syringe, syringe_id)
                if syr is None:
                    raise ValueError(f"Unknown syringe_id={syringe_id}")
                data["real_correlation_factor"] = syr.theoretical_correlation_factor

            obj = cls.model_validate(data)

            try:
                session.add(obj)
                session.commit()
                session.refresh(obj)
            except exc.IntegrityError as e:
                session.rollback()
                raise ValueError(
                    f"Link already exists or violates constraints: "
                    f"(syringe_id={syringe_id}, solvent_id={solvent_id})"
                ) from e
            except Exception as e:
                session.rollback()
                raise ValueError(
                    f"Could not create link (syringe_id={syringe_id}, solvent_id={solvent_id})."
                ) from e

        return obj

    @classmethod
    def delete_by_ids(cls, syringe_id: int, solvent_id: int) -> bool:
        """
        Delete the link row identified by (syringe_id, solvent_id).
        Returns True if deleted, False if not found.
        """
        with get_session() as session:
            obj = session.get(cls, (syringe_id, solvent_id))
            if obj is None:
                return False

            try:
                session.delete(obj)
                session.commit()
            except exc.IntegrityError as e:
                session.rollback()
                raise ValueError(
                    f"Could not delete link (syringe_id={syringe_id}, solvent_id={solvent_id}) "
                    f"due to database constraints."
                ) from e
            except Exception as e:
                session.rollback()
                raise ValueError(
                    f"Could not delete link (syringe_id={syringe_id}, solvent_id={solvent_id})."
                ) from e

        return True

    @classmethod
    def set_calibration(
            cls,
            *,
            syringe_id: int,
            solvent_id: int,
            real_correlation_factor: PositiveFloat | None = None,
            backlash_correction: float | None = None,
            calibrated: bool | None = None,
            since: datetime | None = None,
    ) -> "SyringeSolventLink":

        # auto-defaults (as you requested)
        if calibrated is None:
            calibrated = True
        if since is None:
            since = datetime.now()

        with get_session() as session:
            link: SyringeSolventLink | None = session.get(cls, (syringe_id, solvent_id))
            if link is None:
                raise ValueError(f"No link found for (syringe_id={syringe_id}, solvent_id={solvent_id})")

            # update fields
            if real_correlation_factor is not None:
                link.real_correlation_factor = float(real_correlation_factor)
            if backlash_correction is not None:
                link.backlash_correction = float(backlash_correction)

            link.calibrated = bool(calibrated)
            link.since = since

            try:
                session.commit()
                session.refresh(link)
            except exc.IntegrityError as e:
                session.rollback()
                raise ValueError("Could not update link due to DB constraints.") from e
            except Exception as e:
                session.rollback()
                raise ValueError("Could not update link.") from e

        return link
