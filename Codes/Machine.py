from pydantic import BaseModel, Field, PositiveFloat, model_validator, ConfigDict

class Machine(BaseModel):
    # Per-instance hard limits
    z_min_limit: float = Field(..., description="Lowest allowed Z (mm) for this machine instance")
    z_max_limit: float = Field(..., description="Highest allowed Z (mm) for this machine instance")

    Z_min: float # 25
    Z_max: float # 75
    Z_slow: float # 35
    Fz: PositiveFloat
    Fxy: PositiveFloat
    Fa_push: PositiveFloat
    Fa_push_slow: PositiveFloat
    Fa_pull: PositiveFloat
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


if __name__ == "__main__":
    # python -m Codes.Machine
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

    print(machine)