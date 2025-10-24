from Syringe import Syringe
from Solvent import Solvent

from pydantic import BaseModel, Field, PositiveFloat, model_validator
from typing import Optional, Callable


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
            self.real_correlation_factor = self.syringe_type.theoretical_correlation_factor
        return self

    def linear_mm_to_volume(self, plunger_shift_mm) -> float:
        """Apply a linear function `fn` to convert plunger shift [mm] to displaced volume [µL]."""
        effective_mm = max(0.0, plunger_shift_mm - self.backlash_correction)
        return effective_mm / self.real_correlation_factor

    def general_mm_to_volume(self, plunger_shift_mm: float, fn: Callable[[float], float]) -> float:
        """Apply a custom function `fn` to convert plunger shift [mm] to displaced volume [µL]."""
        effective_mm = max(0.0, plunger_shift_mm - self.backlash_correction)
        return fn(effective_mm)
