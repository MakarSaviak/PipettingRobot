from pydantic import BaseModel, Field, model_validator, ConfigDict, computed_field
from sqlmodel import select
from typing import List

from .Solvent import Solvent
from .Syringe import Syringe
from .SyringeSolventLink import SyringeSolventLink
from .Rack import Rack
from .Machine import Machine
from .IntegratedSyringe import IntegratedSyringe
from .db import create_db_and_tables, get_session

#TODO create a dir with dirs of each class where u store different class configurations in json format.
class Setup(BaseModel):
    name: str
    syringes: List[Syringe] = Field(default_factory=list)
    solvents: List[Solvent] = Field(default_factory=list)
    syringe_solvents: List[SyringeSolventLink] = Field(default_factory=list)
    racks: List[Rack] = Field(default_factory=list)
    machines: List[Machine] = Field(default_factory=list)

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

    @computed_field
    @property
    def integrated_syringes(self) -> List[IntegratedSyringe]:
        return [IntegratedSyringe(syringe=s) for s in self.syringes]

    # Convenience lookup by syringe/solvent name
    def get_syringe_solvent(
        self,
        syringe_name: str,
        solvent_name: str,
        ) -> SyringeSolventLink | None:
        syringe = next((s for s in self.syringes if s.name == syringe_name), None)
        solvent = next((s for s in self.solvents if s.name == solvent_name), None)
        if syringe is None or solvent is None:
            return None

        for link in self.syringe_solvents:
            if link.syringe_id == syringe.id and link.solvent_id == solvent.id:
                return link
        return None




if __name__ == "__main__":
    create_db_and_tables()

    syringes = [Syringe.get_by_id(1)]

    solvents = [Solvent.get_by_id(n) for n in range(1,5)] #from 1 to 4

    rack_data = {
        "name": "test",
        "vial1_x": 180,
        "vial1_y": 0,
        "solvent1_x": 235,
        "solvent1_y": 7.5,
        "waste_x": 235,
        "waste_y": 110,
        "dy_s": 15,
        "dx_s": 15,
        "number_of_solvents": 3,
        "increment_y": 35,
        "vials_per_row": 10,
        "columns": 3,
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
        "machines": [machine]
    }
    setup = Setup.model_validate(setup_data)

    print(setup.syringe_solvents)
