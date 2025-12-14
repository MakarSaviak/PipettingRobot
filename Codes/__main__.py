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

def main():
    # assume you already created `setup` (loaded from json/db/etc.)
    create_db_and_tables()

    syringes = [Syringe.get_by_id(1)]
    solvents = Solvent.get_all()

    rack1 = load_model(Rack, "GC-10-3_3-1")
    rack2 = load_model(Rack, "counterion-96_EDIT-THIS")
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

    # map solvent_idx -> solvent_id (DB id)
    # this assumes setup.solvents order matches your solvent grid order
    solvent_ids = [s.id for s in setup.solvents]
    if any(x is None for x in solvent_ids):
        raise ValueError("Some solvents in setup have id=None; cannot use solvent_id.")
    solvent_ids = [int(x) for x in solvent_ids]

    out = Path("G-codes/test_run.gcode")
    out_excel = Path("csv/test_run.xlsx")
    pg = PipetG(outfile=out, setup=setup, syringe_id=syringe_id)
    excel = InputXlsx(pipet=pg)
    excel.create_empty_table(out_excel)

        # pg.home()
        #
        # # ---- prime/flush with solvent #0 into waste ----
        # pg.flush(
        #     volume_ul=200.0,
        #     repeats=2,
        #     solvent_idx=0,
        #     solvent_id=solvent_ids[0],
        # )
        #
        # # ---- fill first 5 vials with solvent #0 ----
        # for vial_idx in range(0, 5):
        #     pg.process_vial(
        #         vial_idx=vial_idx,
        #         solvent_idx=0,
        #         solvent_id=solvent_ids[0],
        #         volume_ul=100,
        #         slow=False,
        #         flush_repeats=0,
        #     )
        # vial_idx=5
        # pg.process_vial(
        #     vial_idx=vial_idx,
        #     solvent_idx=1,
        #     solvent_id=solvent_ids[1],
        #     volume_ul=250,
        #     slow=True,  # demo: slow dispense
        #     flush_repeats=1,  # demo: flush once before dispensing
        # )
        # # ---- fill next 4 vials with solvent #2 ----
        # pg.flush(
        #     volume_ul=500.0,
        #     repeats=2,
        #     solvent_idx=2,
        #     solvent_id=solvent_ids[2],
        # )
        # for vial_idx in range(6, 10):
        #     pg.process_vial(
        #         vial_idx=vial_idx,
        #         solvent_idx=2,
        #         solvent_id=solvent_ids[2],
        #         volume_ul=500.0,
        #         slow=True,
        #         flush_repeats=0,
        #     )
        #
        # pg.finish()

if __name__ == "__main__":
    main()