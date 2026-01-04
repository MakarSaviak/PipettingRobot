from __future__ import annotations

# ---- Qt DLL bootstrap for this conda env ----
import os
from pathlib import Path

prefix = os.environ.get("CONDA_PREFIX")
if not prefix:
    raise RuntimeError("CONDA_PREFIX is not set. Activate your conda env before running.")

conda_bin = Path(prefix) / "Library" / "bin"
os.add_dll_directory(str(conda_bin))  # point Windows at the Qt6 DLLs

# (optional but helpful) let Qt find its plugins (platforms, styles, etc.)
plugins = Path(prefix) / "Library" / "plugins"
os.environ.setdefault("QT_PLUGIN_PATH", str(plugins))
# --------------------------------------------

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QSpinBox, QCheckBox, QPushButton, QFileDialog, QMessageBox, QComboBox
)

import configparser
import sys
from mecode import G


class VolumeCalibrationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Syringe Volume Calibration (PySide6)")
        self.resize(520, 360)

        # --- Load config.ini ---
        self.config = configparser.ConfigParser()
        if not self.config.read("config.ini"):
            self._fatal("No config.ini found in the working directory.")

        # Syringes
        self.available_syringes = [s for s in self.config.sections() if "syringe" in s.lower()]
        if not self.available_syringes:
            self._fatal("No sections containing 'syringe' found in config.ini.")

        # Rack settings
        try:
            self.vial1_s = [
                self.config.getfloat("Rack", "vial1_x"),
                self.config.getfloat("Rack", "vial1_y"),
            ]
            # use float here (original had ints; float works for sub-mm spacing too)
            self.dx_s = self.config.getfloat("Rack", "dx_s")
            self.dy_s = self.config.getfloat("Rack", "dy_s")

            self.solvent1_x = self.config.getfloat("Rack", "solvent1_x")
            self.solvent1_y = self.config.getfloat("Rack", "solvent1_y")

            self.vial_waste = [
                self.config.getfloat("Rack", "waste_x"),
                self.config.getfloat("Rack", "waste_y"),
            ]
            self.vials_per_row = self.config.getint("Rack", "vials_per_row")
            self.columns = self.config.getint("Rack", "columns")
        except Exception as e:
            self._fatal(f"Rack settings missing/invalid:\n{e!s}")

        # Machine settings
        try:
            self.Z_slow = self.config.getfloat("Machine", "Z_slow")
            self.Z_min = self.config.getfloat("Machine", "Z_min")
            self.Z_max = self.config.getfloat("Machine", "Z_max")
            self.Fz = self.config.getfloat("Machine", "Fz")
            self.Fxy = self.config.getfloat("Machine", "Fxy")
            self.Fa_push = self.config.getfloat("Machine", "Fa_push")
            self.Fa_push_slow = self.config.getfloat("Machine", "Fa_push_slow")
            self.Fa_pull = self.config.getfloat("Machine", "Fa_pull")
            self.Rest_x = self.config.getfloat("Machine", "Rest_x")
            self.Rest_y = self.config.getfloat("Machine", "Rest_y")
        except Exception as e:
            self._fatal(f"Machine settings missing/invalid:\n{e!s}")

        # Active syringe parameters (filled by _update_syringe)
        self.syringe_name = None
        self.factor = None
        self.backlash = None
        self.max_volume_uL = None

        # --- UI ---
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # Row: syringe selection
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Syringe:"))
        self.cmb_syringe = QComboBox()
        self.cmb_syringe.addItems(self.available_syringes)
        self.cmb_syringe.currentIndexChanged.connect(self._update_syringe)
        row1.addWidget(self.cmb_syringe, 1)
        root.addLayout(row1)

        # Info labels for syringe settings
        self.lbl_backlash = QLabel("Backlash correction: — mm")
        self.lbl_size = QLabel("Syringe size: — µL")
        info_row = QHBoxLayout()
        info_row.addWidget(self.lbl_backlash)
        info_row.addStretch(1)
        info_row.addWidget(self.lbl_size)
        root.addLayout(info_row)

        # Form with vial counts
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.spn_10 = QSpinBox()
        self.spn_10.setRange(0, self.vials_per_row * self.columns)
        self.spn_10.setValue(0)

        self.spn_50 = QSpinBox()
        self.spn_50.setRange(0, self.vials_per_row * self.columns)
        self.spn_50.setValue(0)

        self.spn_100 = QSpinBox()
        self.spn_100.setRange(0, self.vials_per_row * self.columns)
        self.spn_100.setValue(0)

        form.addRow("Vials @ 10% volume:", self.spn_10)
        form.addRow("Vials @ 50% volume:", self.spn_50)
        form.addRow("Vials @ 100% volume:", self.spn_100)
        root.addLayout(form)

        # Options
        self.chk_initial_flush = QCheckBox("Initial Flush")
        self.chk_leading_air = QCheckBox("Leading Air Gap")
        self.chk_non_contact = QCheckBox("Non-Contact dispense (use Z_slow)")

        opts = QHBoxLayout()
        opts.addWidget(self.chk_initial_flush)
        opts.addWidget(self.chk_leading_air)
        opts.addWidget(self.chk_non_contact)
        opts.addStretch(1)
        root.addLayout(opts)

        # Generate button
        self.btn_gen = QPushButton("Generate G-code")
        self.btn_gen.clicked.connect(self._on_generate)
        root.addWidget(self.btn_gen, alignment=Qt.AlignRight)

        # initialize syringe panel
        self._update_syringe()

        # gcode generator handler
        self.g = None  # type: G | None

    # ---------- helpers ----------
    def _fatal(self, msg: str):
        QMessageBox.critical(self, "Configuration error", msg)
        sys.exit(1)

    def _update_syringe(self):
        self.syringe_name = self.cmb_syringe.currentText()
        try:
            self.factor = self.config.getfloat(self.syringe_name, "theoretical_factor")
            self.backlash = self.config.getfloat(self.syringe_name, "backlash_correction")
            self.max_volume_uL = self.config.getint(self.syringe_name, "max_volume")
        except Exception as e:
            self._fatal(f"Syringe '{self.syringe_name}' missing keys:\n{e!s}")

        self.lbl_backlash.setText(f"Backlash correction: {self.backlash} mm")
        self.lbl_size.setText(f"Syringe size: {self.max_volume_uL} µL")

    def syringe_steps_for(self, volume_uL: float) -> float:
        """Map desired volume to A-axis movement including backlash."""
        return (volume_uL * self.factor) + self.backlash

    # ---------- kinematics / positions ----------
    def vial_s(self, vial_index: int) -> tuple[float, float]:
        col = vial_index // self.vials_per_row
        row = vial_index % self.vials_per_row
        total = self.vials_per_row * self.columns
        if vial_index >= total:
            raise ValueError(f"Vial index out of bounds (max {total-1}).")
        x = self.vial1_s[0] + col * self.dx_s
        y = self.vial1_s[1] + row * self.dy_s
        return x, y

    # ---------- motion macros (mecode) ----------
    def flush(self, volume_uL: float, repeats: int = 1):
        for _ in range(repeats):
            self.remove_from_vial(self.solvent1_x, self.solvent1_y, volume_uL)
            self.g.absolute()
            self.g.move(z=self.Z_min, F=self.Fz)
            self.g.move(x=self.vial_waste[0], y=self.vial_waste[1], F=self.Fxy)
            self.g.move(z=self.Z_max, F=self.Fz)
            self.g.move(A=0, F=self.Fa_push)
            self.g.move(z=self.Z_min, F=self.Fz)

    def fill_vial(self, x: float, y: float, non_contact: bool):
        self.g.write("fill_vial")
        self.g.absolute()
        self.g.move(z=self.Z_min, F=self.Fz)
        self.g.move(x=x, y=y, F=self.Fxy)
        if non_contact:
            self.g.move(z=self.Z_slow, F=self.Fz)
        else:
            self.g.move(z=self.Z_max, F=self.Fz)
        self.g.move(A=0, F=self.Fa_push)
        self.g.absolute()
        self.g.move(z=self.Z_min, F=self.Fz)

    def remove_from_vial(self, x: float, y: float, volume_uL: float):
        self.g.write("remove_from_vial")
        self.g.absolute()
        self.g.move(z=self.Z_min, F=self.Fz)
        self.g.move(x=x, y=y, F=self.Fxy)
        self.g.move(z=self.Z_max, F=self.Fz)
        self.g.move(A=self.syringe_steps_for(volume_uL), F=self.Fa_pull)
        self.g.move(z=self.Z_min, F=self.Fz)

    def home(self):
        self.g.absolute()
        self.g.move(z=self.Z_min, F=self.Fz)
        self.g.move(x=self.Rest_x, y=self.Rest_y, F=self.Fxy)
        self.g.move(A=0, F=self.Fa_pull)
        self.g.move(z=self.Z_max, F=self.Fz)
        self.g.write("M84")

    # ---------- main action ----------
    def _on_generate(self):
        try:
            n10 = int(self.spn_10.value())
            n50 = int(self.spn_50.value())
            n100 = int(self.spn_100.value())
            initial_flush = self.chk_initial_flush.isChecked()
            leading_air_gap = self.chk_leading_air.isChecked()
            non_contact = self.chk_non_contact.isChecked()
        except Exception as e:
            QMessageBox.critical(self, "Input Error", str(e))
            return

        # Save-as dialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save G-code", "run.gcode", "G-code (*.gcode)"
        )
        if not path:
            QMessageBox.warning(self, "Canceled", "No file selected. G-code generation canceled.")
            return

        try:
            self.g = G(outfile=path)
            self.g.write("G21")  # mm
            self.g.write("G28")  # home

            if initial_flush:
                self.flush(500, repeats=3)

            volumes = [0.1, 0.5, 1.0]  # fraction of syringe size
            counts = [n10, n50, n100]
            current_vial = 0

            for vi, count in enumerate(counts):
                frac = volumes[vi]
                for _ in range(count):
                    volume_uL = frac * float(self.max_volume_uL)

                    # Aspirate solvent
                    self.remove_from_vial(self.solvent1_x, self.solvent1_y, volume_uL)

                    # Optional leading air gap (relative A move)
                    if leading_air_gap:
                        air_gap = 0.1 * volume_uL
                        self.g.relative()
                        self.g.move(A=self.syringe_steps_for(air_gap), F=self.Fa_pull)
                        self.g.absolute()

                    # Dispense into next vial
                    x, y = self.vial_s(current_vial)
                    self.fill_vial(x, y, non_contact=non_contact)
                    current_vial += 1

            self.home()
            self.g = None

            QMessageBox.information(self, "Success", f"G-code written to:\n{path}")
            # close window like original did:
            self.close()

        except Exception as e:
            QMessageBox.critical(self, "G-code Error", str(e))


def main():
    app = QApplication(sys.argv)
    w = VolumeCalibrationWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
