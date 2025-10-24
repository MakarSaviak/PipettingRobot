from pydantic import BaseModel, Field, computed_field
from typing import List, Optional

class Syringe(BaseModel):
    nominal_volume: float
    name: str
