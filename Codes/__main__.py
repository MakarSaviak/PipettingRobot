from pathlib import Path

from .db import create_db_and_tables
from .config_io import load_model
from .Syringe import Syringe
from .Solvent import Solvent
from .Setup import Setup
from .Rack import Rack
from .Machine import Machine
from .PipetG import PipetG  # wherever you put it
from .InputXlsx import InputXlsx


def creat_PipetG(out_name):
    create_db_and_tables()

    syringes = [Syringe.get_by_id(1)]
    solvents = Solvent.get_all()

    rack1 = load_model(Rack, "GC-10-3_3-1")
    rack2 = load_model(Rack, "counterion-96")
    racks = [rack1, rack2]

    machine = load_model(Machine, "current")

    setup_data = {
        "name": "Test",
        "syringes": syringes,
        "solvents": solvents,
        "racks": racks,
        "machine": machine
    }
    setup = Setup.model_validate(setup_data)

    syringe_id = 1

    out = Path(f"G-codes/{out_name}.gcode")
    pg = PipetG(outfile=out, setup=setup, syringe_id=syringe_id)
    pg.start()

    return pg


def get_empty_table(excel: InputXlsx, out_excel: Path):
    excel.create_empty_table(out_excel)

def gcode(excel, out_excel, pg):
    excel.load(out_excel)
    try:
        excel.generate_gcode()
    finally:
        pg.stop()


def main():
    out_name = "test_run"
    pg = creat_PipetG(out_name)

    out_excel = Path(f"csv/{out_name}.xlsx")
    excel = InputXlsx(pipet=pg)
    #gcode(excel, out_excel, pg)
    get_empty_table(excel, out_excel)


if __name__ == "__main__":
    main()