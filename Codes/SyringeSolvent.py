from Syringe import Syringe
from Solvent import Solvent

from pydantic import BaseModel, Field, computed_field
from typing import List, Optional

class SyringeSolvent(BaseModel):
    syringe_type: Syringe
    solvent_type: Solvent
