from Syringe import Syringe
from Solvent import Solvent

from pydantic import BaseModel, Field, computed_field, PositiveFloat, model_validator
from typing import List, Optional

class SyringeSolvent(BaseModel):
    syringe_type: Syringe
    solvent_type: Solvent
    # Calibration parameters (per syringe–solvent pairing)
    # Backlash compensation in mm.
    backlash_correction: PositiveFloat = Field(0.0,
        description="Backlash compensation (mm) accounts for the systematic error.")
    real_correlation_factor: Optional[PositiveFloat] = Field(
        default=None,
        description="Calibrated correlation factor (mm/µL) for this syringe–solvent pair."
    )

    @model_validator(mode="after")
    def _init_real_factor(self):
        if self.real_correlation_factor is None:
            # Use syringe-provided theoretical factor as a starting point
            self.real_correlation_factor = self.syringe_type.theoretical_correlation_factor()
        return self
