from pydantic import BaseModel, Field, PositiveFloat, model_validator, PositiveInt, ConfigDict
from typing import Optional, Callable

#TODO change all the god damn z_min and z_max to the proper values IN THE LIQUID HANDLING CODE
class Machine(BaseModel):
    # Per-instance hard limits
    z_min_limit: float = Field(..., description="Lowest allowed Z (mm) for this machine instance")
    z_max_limit: float = Field(..., description="Highest allowed Z (mm) for this machine instance")

    Z_min: float # 35
    Z_max: float # 75
    Z_slow: float # 45
    Fz: PositiveInt
    Fxy: PositiveInt
    Fa_push: PositiveInt
    Fa_push_slow: PositiveInt
    Fa_pull: PositiveInt
    Rest_x: PositiveFloat
    Rest_y: PositiveFloat

    # Re-validate on assignment so updates are also checked
    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _bounds_and_consistency_checks(self):
        if self.Z_min > self.Z_max:
            raise ValueError("Z_min must be < Z_max")
        if self.z_min_limit >= self.z_max_limit:
            raise ValueError("z_min_limit must be < z_max_limit")
        if not (self.z_min_limit <= self.Z_min <= self.Z_max <= self.z_max_limit):
            raise ValueError(
                f"Z bounds invalid: require {self.z_min_limit} <= Z_min <= Z_max <= {self.z_max_limit}"
            )
        if not (self.Z_min <= self.Z_slow <= self.Z_max):
            raise ValueError("Z_slow must be between Z_min and Z_max")
        return self
