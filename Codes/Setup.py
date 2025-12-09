from pydantic import BaseModel, Field, PositiveFloat, model_validator, ConfigDict, computed_field
from sqlmodel import SQLModel, create_engine
from typing import Optional, Callable, List

from .Solvent import Solvent
from .Syringe import Syringe
from .SyringeSolventLink import SyringeSolventLink
from .Rack import Rack
from .Machine import Machine
from .IntegratedSyringe import IntegratedSyringe
from .db import create_db_and_tables


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
    def _validate_members_and_uniqueness(self):
        # Uniqueness for names (acts as identifiers)
        syringe_names = [s.name for s in self.syringes]
        if len(syringe_names) != len(set(syringe_names)):
            raise ValueError("Duplicate syringe names in setup.")

        solvent_names = [s.name for s in self.solvents]
        if len(solvent_names) != len(set(solvent_names)):
            raise ValueError("Duplicate solvent names in setup.")

        # All syringe–solvent pairs must reference syringes/solvents present in this setup
        syringe_set = set(syringe_names)
        solvent_set = set(solvent_names)
        for p in self.syringe_solvents:
            if p.syringe_type.name not in syringe_set:
                raise ValueError(f"Syringe–solvent pair references unknown syringe: {p.syringe_type.name}")
            if p.solvent_type.name not in solvent_set:
                raise ValueError(f"Syringe–solvent pair references unknown solvent: {p.solvent_type.name}")

        # No duplicate (syringe, solvent) combinations
        keys = [(p.syringe_type.name, p.solvent_type.name) for p in self.syringe_solvents]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate syringe–solvent pairs in setup.")
        return self

    @computed_field
    @property
    def integrated_syringes(self) -> List[IntegratedSyringe]:
        return [IntegratedSyringe(syringe=s) for s in self.syringes]

    # Convenience lookup
    def get_syringe_solvent(self, syringe_name: str, solvent_name: str) -> Optional[SyringeSolventLink]:
        for p in self.syringe_solvents:
            if p.syringe_type.name == syringe_name and p.solvent_type.name == solvent_name:
                return p
        return None

if __name__ == "__main__":
    create_db_and_tables()

    syringe1 = Syringe.get_by_id(1)
    syringes = [syringe1]

    solvents = [Solvent.get_by_id(n) for n in range(1,5)] #from 1 to 4

    rack = Rack(name="test",
                vial1_x=180,
                vial1_y=0,
                solvent1_x=235,
                solvent1_y=7.5,
                waste_x=235,
                waste_y=110,
                dy_s=15,
                dx_s=15,
                number_of_solvents=3,
                increment_y=35,
                vials_per_row=10,
                columns=3)

    machine = Machine(
        z_min_limit=20,
        z_max_limit=80,
        Z_min=25,
        Z_max=75,
        Z_slow=35,
        Fz=2000,
        Fxy=7000,
        Fa_push=800,
        Fa_push_slow=240,
        Fa_pull=300,
        Rest_x=5,
        Rest_y=5
    )

    setup = Setup(name="Test",
                  syringes=syringes,
                   solvents=solvents,
                   racks=[rack],
                   machines=[machine])
    print(setup.syringe_solvents)
