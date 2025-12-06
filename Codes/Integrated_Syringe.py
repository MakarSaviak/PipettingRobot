from pydantic import BaseModel, Field, PositiveFloat, model_validator, ConfigDict
from Syringe import Syringe


class Integrated_Syringe(Syringe):
    min_vol: float
    offset: float = Field(default=0.0)
