from pydantic import BaseModel, PositiveFloat, PositiveInt, NonNegativeFloat


class Rack(BaseModel):
    name: str
    vial1_x: NonNegativeFloat
    vial1_y: NonNegativeFloat
    solvent1_x: NonNegativeFloat
    solvent1_y: NonNegativeFloat
    waste_x: NonNegativeFloat
    waste_y: NonNegativeFloat
    dy_s: NonNegativeFloat
    dx_s: NonNegativeFloat
    number_of_solvents: PositiveInt
    increment_y: PositiveFloat | None
    vials_per_row: PositiveInt #I think they mean the number of rows
    columns: PositiveInt #The number of columns

if __name__ == "__main__":
    # python -m Codes.Rack
    rack_data = {
        "name": "test",
        "vial1_x": 180,
        "vial1_y": 0,
        "solvent1_x": 235,
        "solvent1_y": 7.5,
        "waste_x": 235,
        "waste_y": 110,
        "dy_s": 15,
        "dx_s": 15,
        "number_of_solvents": 3,
        "increment_y": 35,
        "vials_per_row": 10,
        "columns": 3,
    }
    rack = Rack.model_validate(rack_data)

    print(rack)
