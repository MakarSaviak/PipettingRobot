from pydantic import BaseModel, PositiveFloat, PositiveInt


class Rack(BaseModel):
    name: str
    vial1_x: PositiveFloat
    vial1_y: PositiveFloat
    solvent1_x: PositiveFloat
    solvent1_y: PositiveFloat
    waste_x: PositiveFloat
    waste_y: PositiveFloat
    dy_s: PositiveFloat
    dx_s: PositiveFloat
    number_of_solvents: PositiveInt
    increment_y: PositiveFloat
    vials_per_row: PositiveInt #I think they mean the number of rows
    columns: PositiveInt #The number of columns
