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

    def mm_for_volume(self, volume_uL: float) -> float:
        """Convert a requested volume (µL) to plunger travel (mm)."""
        return volume_uL * float(self.real_correlation_factor) + self.backlash_correction

    def steps_for_volume(self, volume_uL: float, steps_per_mm: float, include_backlash: bool = True) -> int:
        """Convert a requested volume (µL) to stepper steps given steps/mm for the plunger axis."""
        mm = self.mm_for_volume(volume_uL, include_backlash=include_backlash)
        return int(round(mm * steps_per_mm))
