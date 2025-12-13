from .db import create_db_and_tables
from .Syringe import Syringe
from .config_io import save_model, load_model, delete_model
from .Rack import Rack
from .Machine import Machine


def main() -> None:
    machine_data = {
        "z_min_limit": 20,
        "z_max_limit": 80,
        "Z_min": 25,
        "Z_max": 75,
        "Z_slow": 35,
        "Fz": 2000,
        "Fxy": 7000,
        "Fa_push": 800,
        "Fa_push_slow": 240,
        "Fa_pull": 300,
        "Rest_x": 5,
        "Rest_y": 5,
    }
    machine = Machine.model_validate(machine_data)
    save_model(machine, "current")


if __name__ == "__main__":
    main()
