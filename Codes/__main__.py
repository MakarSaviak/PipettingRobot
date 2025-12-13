from .db import create_db_and_tables
from .Syringe import Syringe
from .Solvent import Solvent
from .SyringeSolventLink import SyringeSolventLink


def main() -> None:
    create_db_and_tables()

    syringe1 = Syringe.create(
        name="Hamilton1001_1000uL",
        nominal_volume_ul=1000,
        inner_diameter_mm=4.61,
    )
    syringe_id = syringe1.id
    print(f"Created syringe: id={syringe_id} | name={syringe1.name}")

    solvent_list = [
        {"name": "H2O", "density_g_per_ml": 0.998, "notes": "distilled"},
        {"name": "Acetone", "density_g_per_ml": 0.785, "notes": "distilled"},
        {"name": "Et2O", "density_g_per_ml": 0.71, "notes": "SPS"},
        {"name": "ACN", "density_g_per_ml": 0.78, "notes": "SPS"},
        {"name": "Hexane", "density_g_per_ml": 0.66, "notes": "SPS"},
        {"name": "DCM", "density_g_per_ml": 1.326, "notes": "SPS"},
    ]

    for sd in solvent_list:
        sol = Solvent.create(**sd)
        print(f"Created solvent: id={sol.id} | name={sol.name}")

        link = SyringeSolventLink.create(
            syringe_id=syringe_id,
            solvent_id=sol.id,
            calibrated=False,
        )
        print(f"  Linked: ({link.syringe_id}, {link.solvent_id}) factor={link.real_correlation_factor}")


if __name__ == "__main__":
    main()
