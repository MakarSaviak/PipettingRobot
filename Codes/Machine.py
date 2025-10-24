from pydantic import BaseModel, Field, PositiveFloat, model_validator, PositiveInt
from typing import Optional, Callable


class Machine(BaseModel):
    Z_min: float
    Z_max: float
    Z_slow: float
    Fz: PositiveInt
    Fxy: PositiveInt
    Fa_push: PositiveInt
    Fa_push_slow: PositiveInt
    Fa_pull: PositiveInt
    Rest_x: PositiveFloat
    Rest_y: PositiveFloat
