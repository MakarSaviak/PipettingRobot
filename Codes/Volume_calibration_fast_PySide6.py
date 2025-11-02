# Volume_calibration_fast_PySide6.py
from __future__ import annotations

import sys
import configparser
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QFileDialog, QMessageBox, QInputDialog
)

from mecode import G

# --- globals filled in main() to mimic original module-level variables ---
config: configparser.ConfigParser
available_syringes: list[str]
syringe_name: str
factor: float
backlash: float
syringe_vol: int

vial1_s: list[float]
dx_s: int
dy_s: int
solvent1_x: float
solvent1_y: float
vial_waste: list[float]
vials_per_row: int
columns: int

Z_slow: int
Z_max: int
Z_min: int
Fz: int
Fxy: int
Fa_push: int
Fa_push_slow: int
Fa_pull: int
Rest_x: int
Rest_y: int

g = G()  # will be replaced with G(outfile=...) when generating


# --- helpers & motions (same formulas/logic as your script) ---
def syringe(volume_uL: float) -> float:
    return (volume_uL * factor) + backlash


def vial_s(vial_index: int) -> tuple[float, float]:
    col = vial_index // vials_per_row
    row = vial_index % vials_per_row
    total_vials = vials_per_row * columns
    if vial_index >= total_vials:
        raise ValueError(f"Vial index out of bounds {total_vials}")
    x = vial1_s[0] + col * dx_s
    y = vial1_s[1] + row * dy_s
    return x, y


def flush(volume_uL: float, repeats: int = 1):
    for _ in range(repeats):
        remove_from_vial(solvent1_x, solvent1_y, volume_uL)
        g.absolute()
        g.move(z=Z_max, F=Fz)
        g.move(x=vial_waste[0], y=vial_waste[1], F=Fxy)
        g.move(z=Z_min, F=Fz)
        g.move(A=0, F=Fa_push)
        g.move(z=Z_max, F=Fz)


def fill_vial(x: float, y: float, non_contact: bool = False):
    g.write("fill_vial")
    g.absolute()
    g.move(z=Z_max, F=Fz)
    g.move(x=x, y=y, F=Fxy)
    if non_contact:
        g.move(z=Z_slow, F=Fz)
    else:
        g.move(z=Z_min, F=Fz)
    g.move(A=0, F=Fa_push)
    g.absolute()
    g.move(z=Z_max, F=Fz)


def remove_from_vial(x: float, y: float, volume_uL: float):
    g.write("remove_from_vial")
    g.absolute()
    g.move(z=Z_max, F=Fz)
    g.move(x=x, y=y, F=Fxy)
    g.move(z=Z_min, F=Fz)
    g.move(A=syringe(volume_uL), F=Fa_pull)
    g.move(z=Z_max, F=Fz)


def home():
    g.absolute()
    g.move(z=Z_max, F=Fz)
    g.move(x=Rest_x, y=Rest_y, F=Fxy)
    g.move(A=0, F=Fa_pull)
    g.move(z=Z_min, F=Fz)
    g.write("M84")


def generate_g_code_fast(
    syringe_vol: int,
    pause: int,
    x: float,
    y: float,
    n_vials_per_vol: int = 3,
    n_data_points: int = 10,
    initial_flush: bool = True,
):
    """
    Creates a G-code for calibration (same behavior as your Tk version).

    :param syringe_vol: Syringe size (µL)
    :param x: X coordinate of the scale vial
    :param y: Y coordinate of the scale vial
    :param n_vials_per_vol: vials per volume point
    :param n_data_points: number of volumes
    :param pause: wait time between dispenses [ms]
    :param initial_flush: whether to pre-flush
    """
    global g

    # Qt file save dialog
    filepath, _ = QFileDialog.getSaveFileName(
        None, "Save G-code", "calibration.gcode", "G-code (*.gcode)"
    )
    if not filepath:
        QMessageBox.warning(None, "File Not Saved",
                            "No file was selected. G-code generation was canceled.")
        return

    g = G(outfile=filepath)
    g.write("G21")  # mm
    g.write("G28")  # home

    if initial_flush:
        flush(500, repeats=3)  # same as original example

    start = 0.1 * syringe_vol
    stop = syringe_vol
    steps = n_data_points

    volumes = np.linspace(start=start, stop=stop, num=steps)
    vials_count = n_vials_per_vol * np.ones_like(volumes, dtype=int)
    current_vial = 0

    for vol_index, count in enumerate(vials_count):
        for i in range(count):
            volume = float(volumes[vol_index])
            g.dwell(pause)  # ms
            remove_from_vial(solvent1_x, solvent1_y, volume)
            fill_vial(x, y)  # non_contact=False default (same as original)
            current_vial += 1

    home()
    QMessageBox.information(None, "Success", "G-code generation complete!")


def main():
    app = QApplication(sys.argv)

    # --- load config.ini like original ---
    global config, available_syringes, syringe_name, factor, backlash, syringe_vol
    global vial1_s, dx_s, dy_s, solvent1_x, solvent1_y, vial_waste, vials_per_row, columns
    global Z_slow, Z_max, Z_min, Fz, Fxy, Fa_push, Fa_push_slow, Fa_pull, Rest_x, Rest_y

    config = configparser.ConfigParser()
    if not config.read("config.ini"):
        QMessageBox.critical(None, "Error", "No config.ini found in the working directory.")
        sys.exit(1)

    available_syringes = [s for s in config.sections() if "syringe" in s.lower()]
    if not available_syringes:
        QMessageBox.critical(None, "Error", "No sections containing 'syringe' found in config.ini.")
        sys.exit(1)

    # Show a Qt combo dialog instead of input()
    syringe_name, ok = QInputDialog.getItem(
        None,
        "Select Syringe",
        "Choose a syringe section from config.ini:",
        available_syringes,
        0,
        False,
    )
    if not ok:
        sys.exit(0)

    # Syringe params
    factor = config.getfloat(syringe_name, "theoretical_factor")
    backlash = config.getfloat(syringe_name, "backlash_correction")
    syringe_vol = config.getint(syringe_name, "max_volume")

    # Rack settings (keep same getint/getfloat pattern)
    vial1_s = [config.getfloat("Rack", "vial1_x"), config.getfloat("Rack", "vial1_y")]
    dx_s = config.getint("Rack", "dx_s")  # keep as int like original
    dy_s = config.getint("Rack", "dy_s")
    solvent1_x = config.getfloat("Rack", "solvent1_x")
    solvent1_y = config.getfloat("Rack", "solvent1_y")
    vial_waste = [config.getfloat("Rack", "waste_x"), config.getfloat("Rack", "waste_y")]
    vials_per_row = config.getint("Rack", "vials_per_row")
    columns = config.getint("Rack", "columns")

    # Machine settings (keep getint like original script)
    Z_slow = config.getint("Machine", "Z_slow")
    Z_max = config.getint("Machine", "Z_max")
    Z_min = config.getint("Machine", "Z_min")
    Fz = config.getint("Machine", "Fz")
    Fxy = config.getint("Machine", "Fxy")
    Fa_push = config.getint("Machine", "Fa_push")
    Fa_push_slow = config.getint("Machine", "Fa_push_slow")
    Fa_pull = config.getint("Machine", "Fa_pull")
    Rest_x = config.getint("Machine", "Rest_x")
    Rest_y = config.getint("Machine", "Rest_y")

    # --- defaults matching your __main__ ---
    x = 10
    y = 185
    pause = 10 * 1000  # seconds -> ms

    # Run once (dialogs are modal; no need to app.exec())
    generate_g_code_fast(syringe_vol=syringe_vol, pause=pause, x=x, y=y)
    sys.exit(0)


if __name__ == "__main__":
    main()
