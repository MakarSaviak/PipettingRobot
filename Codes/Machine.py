from pydantic import BaseModel, Field, PositiveFloat, model_validator, ConfigDict

class Machine(BaseModel):
    # Per-instance hard limits
    z_min_limit: float = Field(..., description="Lowest allowed Z (mm) for this machine instance")
    z_max_limit: float = Field(..., description="Highest allowed Z (mm) for this machine instance")

    z_min: float # 25
    z_max: float # 75
    Fz: PositiveFloat
    Fxy: PositiveFloat
    Fa_push: PositiveFloat
    Fa_push_slow: PositiveFloat
    Fa_pull: PositiveFloat
    rest_x: PositiveFloat
    rest_y: PositiveFloat

    # Re-validate on assignment so updates are also checked
    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _bounds_and_consistency_checks(self):
        if self.z_min > self.z_max:
            raise ValueError("Z_min must be < Z_max")
        if self.z_min_limit >= self.z_max_limit:
            raise ValueError("z_min_limit must be < z_max_limit")
        if not (self.z_min_limit <= self.z_min <= self.z_max <= self.z_max_limit):
            raise ValueError(
                f"Z bounds invalid: require {self.z_min_limit} <= Z_min <= Z_max <= {self.z_max_limit}"
            )
        return self
