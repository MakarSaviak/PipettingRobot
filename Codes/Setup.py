from pydantic import BaseModel, Field, PositiveFloat, model_validator
from typing import Optional, Callable

#TODO create a class Integrated_Syringe to additionally account for the min_volume, syringe offset etc
class Setup(BaseModel):
    name: str
    pass
