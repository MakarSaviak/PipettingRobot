from pydantic import BaseModel, Field, model_validator, ConfigDict
from sqlmodel import select
from typing import List

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
    machine: Machine | None = None

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


if __name__ == "__main__":
    create_db_and_tables()

    syringes = [Syringe.get_by_id(1)]

    solvents = Solvent.get_all()

    rack_data = {
        "name": "GC-10-by-3_Solvent-20ml-3-by-1",
        "vial1_x": 180,
        "vial1_y": 0,
        "solvent1_x": 235,
        "solvent1_y": 7.5,
        "waste_x": 235,
        "waste_y": 110,
        "vial_dy": 15,
        "vial_dx": 15,
        "vial_rows": 10,
        "vial_columns": 3,
        "solvent_rows": 3,
        "solvent_columns": 1,
        "solvent_dy": 35,
        "solvent_dx": None,
    }
    rack = Rack.model_validate(rack_data)

    machine_data = {
        "z_min_limit": 20,
        "z_max_limit": 80,
        "Z_min": 25,
        "Z_max": 75,
        "Z_slow": 35,
        "Fz": 2000,
        "Fxy": 7000,
        "Fa_push": 800,
        "Fa_push_slow": 240,
        "Fa_pull": 300,
        "Rest_x": 5,
        "Rest_y": 5,
    }
    machine = Machine.model_validate(machine_data)

    setup_data = {
        "name": "Test",
        "syringes": syringes,
        "solvents": solvents,
        "racks": [rack],
        "machine": machine
    }
    setup = Setup.model_validate(setup_data)

    print(setup)
