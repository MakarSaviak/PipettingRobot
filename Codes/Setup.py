from pydantic import BaseModel, Field, model_validator, ConfigDict
from sqlmodel import select
from typing import List
from itertools import chain

from Codes.config_io import load_model
from .Solvent import Solvent
from .Syringe import Syringe
from .SyringeSolventLink import SyringeSolventLink
from .Rack import Rack
from .Machine import Machine
from .db import create_db_and_tables, get_session


class Setup(BaseModel):
    name: str
    syringes: List[Syringe] = Field(default_factory=list)
    solvents: List[Solvent] = Field(default_factory=list)
    syringe_solvents: List[SyringeSolventLink] = Field(default_factory=list)
    racks: List[Rack] = Field(default_factory=list)
    machine: Machine

    # Keep the model consistent even when attributes are modified later
    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _populate_links_and_validate(self) -> "Setup":
        # --- 1) Uniqueness of syringe/solvent names -------------------------
        syringe_names = [s.name for s in self.syringes]
        if len(syringe_names) != len(set(syringe_names)):
            raise ValueError("Duplicate syringe names in setup.")

        solvent_names = [s.name for s in self.solvents]
        if len(solvent_names) != len(set(solvent_names)):
            raise ValueError("Duplicate solvent names in setup.")

        # Pre-compute id sets (only for syringes/solvents that have an id)
        syringe_ids = {s.id for s in self.syringes if s.id is not None}
        solvent_ids = {s.id for s in self.solvents if s.id is not None}

        # --- 2) Auto-populate syringe_solvents from DB if empty -------------
        if (not self.syringe_solvents) and syringe_ids and solvent_ids:
            with get_session() as session:
                stmt = (
                    select(SyringeSolventLink)
                    .where(SyringeSolventLink.syringe_id.in_(syringe_ids))
                    .where(SyringeSolventLink.solvent_id.in_(solvent_ids))
                )
                links = session.exec(stmt).all()

            self.syringe_solvents = links

        # --- 3) Validate that all links refer to known syringes/solvents -----
        for link in self.syringe_solvents:
            if link.syringe_id not in syringe_ids:
                raise ValueError(
                    f"SyringeSolventLink references unknown syringe_id={link.syringe_id}"
                )
            if link.solvent_id not in solvent_ids:
                raise ValueError(
                    f"SyringeSolventLink references unknown solvent_id={link.solvent_id}"
                )

        # --- 4) No duplicate (syringe_id, solvent_id) combinations ----------
        keys = [(link.syringe_id, link.solvent_id) for link in self.syringe_solvents]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate syringe–solvent pairs in setup.")

        return self

    def get_rack(self, name: str) -> Rack | None:
        return next((r for r in self.racks if r.name == name), None)

    def get_link(self, syringe_id: int, solvent_id: int) -> "SyringeSolventLink | None":
        return next(
            (l for l in self.syringe_solvents if l.syringe_id == syringe_id and l.solvent_id == solvent_id), None)

    @property
    def vial_positions(self) -> list[tuple[float, float]]:
        # concatenates rack.positions_vial in self.racks order
        return list(chain.from_iterable(r.positions_vial for r in self.racks))

    @property
    def solvent_positions(self) -> list[tuple[float, float]]:
        # concatenates rack.positions_solvent in self.racks order
        return list(chain.from_iterable(r.positions_solvent for r in self.racks))


if __name__ == "__main__":
    create_db_and_tables()

    syringes = [Syringe.get_by_id(1)]
    solvents = Solvent.get_all()

    rack1 = load_model(Rack, "GC-10-by-3_Solvent-20ml-3-by-1")
    rack2 = load_model(Rack, "counterion-96_EDIT-THIS")
    racks = [rack1, rack2]

    machine = load_model(Machine, "current")

    setup_data = {
        "name": "Test",
        "syringes": syringes,
        "solvents": solvents,
        "racks": racks,
        "machine": machine
    }
    setup = Setup.model_validate(setup_data)
