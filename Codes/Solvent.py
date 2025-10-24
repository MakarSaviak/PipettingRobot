from pydantic import BaseModel, Field, computed_field
from typing import List, Optional

class Solvent(BaseModel):
    name: str
