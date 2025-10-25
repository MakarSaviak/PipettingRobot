from pydantic import BaseModel, Field, PositiveFloat, model_validator, ConfigDict
from typing import Optional, Callable, List
from SyringeSolvent import SyringeSolvent

#TODO create a class Integrated_Syringe to additionally account for the min_volume, syringe offset etc
class Setup(BaseModel):
    name: str
    syringe_solvents: List[SyringeSolvent] = Field(default_factory=list)

    # Keep the model consistent even when attributes are modified later
    model_config = ConfigDict(validate_assignment=True)
