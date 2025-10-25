from pydantic import BaseModel, PositiveInt

class Solvent(BaseModel):
    name: str
    id: PositiveInt
