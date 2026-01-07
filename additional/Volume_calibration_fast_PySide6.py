# Volume_calibration_fast_PySide6.py
from __future__ import annotations

import sys
import configparser
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QComboBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QFileDialog, QMessageBox
)

from mecode import G


class FastCalibrationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fast Syringe Calibration (PySide6)")
        self.resize(560, 360)

        # ---- Load config.ini ----
        self.config = configparser.ConfigParser()
        if not self.config.read("config.ini"):
            self._fatal("No config.ini found in the working directory.")

        self.available_syringes = [s for s in self.config.sections() if "syringe" in s.lower()]
        if not self.available_syringes:
            self._fatal("No sections containing 'syringe' found in config.ini.")

        # Rack settings (use same types as the original fast script)
        try:
            self.vial1_s = [self.config.getfloat("Rack", "vial1_x"),
                            self.config.getfloat("Rack", "vial1_y")]
            self.dx_s = self.config.getint("Rack", "dx_s")
            self.dy_s = self.config.getint("Rack", "dy_s")
            self.solvent1_x = self.config.getfloat("Rack", "solvent1_x")
            self.solvent1_y = self.config.getfloat("Rack", "solvent1_y")
            self.vial_waste = [self.config.getfloat("Rack", "waste_x"),
                               self.config.getfloat("Rack", "waste_y")]
            self.vials_per_row = self.config.getint("Rack", "vials_per_row")
            self.columns = self.config.getint("Rack", "columns")
        except Exception as e:
            self._fatal(f"Rack settings missing/invalid:\n{e!s}")

        # Machine settings
        try:
            self.Z_slow = self.config.getint("Machine", "Z_slow")
            self.Z_max  = self.config.getint("Machine", "Z_max")
            self.Z_min  = self.config.getint("Machine", "Z_min")
            self.Fz     = self.config.getint("Machine", "Fz")
            self.Fxy    = self.config.getint("Machine", "Fxy")
            self.Fa_push = self.config.getint("Machine", "Fa_push")
            self.Fa_push_slow = self.config.getint("Machine", "Fa_push_slow")
            self.Fa_pull = self.config.getint("Machine", "Fa_pull")
            self.Rest_x  = self.config.getint("Machine", "Rest_x")
            self.Rest_y  = self.config.getint("Machine", "Rest_y")
        except Exception as e:
            self._fatal(f"Machine settings missing/invalid:\n{e!s}")

        # Active syringe (filled in _update_syringe)
        self.syringe_name = ""
        self.factor = 0.0
        self.backlash = 0.0
        self.syringe_vol = 0

        # --- UI ---
        central = QWidget(self); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(16,16,16,16); root.setSpacing(12)

        # Syringe row
        row = QHBoxLayout()
        row.addWidget(QLabel("Syringe:"))
        self.cmb_syringe = QComboBox()
        self.cmb_syringe.addItems(self.available_syringes)
        self.cmb_syringe.currentIndexChanged.connect(self._update_syringe)
        row.addWidget(self.cmb_syringe, 1)
        root.addLayout(row)

        # Syringe info
        info = QHBoxLayout()
        self.lbl_backlash = QLabel("Backlash: — mm")
        self.lbl_size = QLabel("Size: — µL")
        info.addWidget(self.lbl_backlash); info.addStretch(1); info.addWidget(self.lbl_size)
        root.addLayout(info)

        # Inputs: X, Y, Pause (s)
        form = QFormLayout(); form.setLabelAlignment(Qt.AlignRight)

        self.spn_x = QDoubleSpinBox(); self.spn_x.setRange(-1e6,1e6); self.spn_x.setDecimals(3); self.spn_x.setValue(10.0)
        self.spn_y = QDoubleSpinBox(); self.spn_y.setRange(-1e6,1e6); self.spn_y.setDecimals(3); self.spn_y.setValue(185.0)

        self.spn_pause_s = QDoubleSpinBox()
        self.spn_pause_s.setRange(0.0, 1e6)
        self.spn_pause_s.setDecimals(3)
        self.spn_pause_s.setValue(10.0)

        form.addRow("X [mm]:", self.spn_x)
        form.addRow("Y [mm]:", self.spn_y)
        form.addRow("Pause [s]:", self.spn_pause_s)
        root.addLayout(form)

        self.chk_initial_flush = QCheckBox("Initial Flush (3×500 µL)")
        self.chk_initial_flush.setChecked(True)
        root.addWidget(self.chk_initial_flush)

        btn = QPushButton("Generate G-code")
        btn.clicked.connect(self._on_generate)
        root.addWidget(btn, alignment=Qt.AlignRight)

        self._update_syringe()   # initialize
        self.g: G | None = None  # mecode handle

    # --------- helpers ----------
    def _fatal(self, msg: str):
        QMessageBox.critical(self, "Configuration error", msg)
        sys.exit(1)

    def _update_syringe(self):
        self.syringe_name = self.cmb_syringe.currentText()
        try:
            self.factor = self.config.getfloat(self.syringe_name, "theoretical_factor")
            self.backlash = self.config.getfloat(self.syringe_name, "backlash_correction")
            self.syringe_vol = self.config.getint(self.syringe_name, "max_volume")
        except Exception as e:
            self._fatal(f"Syringe '{self.syringe_name}' missing keys:\n{e!s}")
        self.lbl_backlash.setText(f"Backlash: {self.backlash} mm")
        self.lbl_size.setText(f"Size: {self.syringe_vol} µL")

    # --------- kinematics / moves ----------
    def syringe_steps_for(self, volume_uL: float) -> float:
        return (volume_uL * self.factor) + self.backlash

    def flush(self, volume_uL: float, repeats: int = 1):
        for _ in range(repeats):
            self.remove_from_vial(self.solvent1_x, self.solvent1_y, volume_uL)
            self.g.absolute()
            self.g.move(z=self.Z_max, F=self.Fz)
            self.g.move(x=self.vial_waste[0], y=self.vial_waste[1], F=self.Fxy)
            self.g.move(z=self.Z_min, F=self.Fz)
            self.g.move(A=0, F=self.Fa_push)
            self.g.move(z=self.Z_max, F=self.Fz)

    def fill_vial(self, x: float, y: float, non_contact: bool = False):
        self.g.write("fill_vial")
        self.g.absolute()
        self.g.move(z=self.Z_max, F=self.Fz)
        self.g.move(x=x, y=y, F=self.Fxy)
        self.g.move(z=(self.Z_slow if non_contact else self.Z_min), F=self.Fz)
        self.g.move(A=0, F=self.Fa_push)
        self.g.absolute()
        self.g.move(z=self.Z_max, F=self.Fz)

    def remove_from_vial(self, x: float, y: float, volume_uL: float):
        self.g.write("remove_from_vial")
        self.g.absolute()
        self.g.move(z=self.Z_max, F=self.Fz)
        self.g.move(x=x, y=y, F=self.Fxy)
        self.g.move(z=self.Z_min, F=self.Fz)
        self.g.move(A=self.syringe_steps_for(volume_uL), F=self.Fa_pull)
        self.g.move(z=self.Z_max, F=self.Fz)

    def home(self):
        self.g.absolute()
        self.g.move(z=self.Z_max, F=self.Fz)
        self.g.move(x=self.Rest_x, y=self.Rest_y, F=self.Fxy)
        self.g.move(A=0, F=self.Fa_pull)
        self.g.move(z=self.Z_min, F=self.Fz)
        self.g.write("M84")

    # --------- main action ----------
    def _on_generate(self):
        x = float(self.spn_x.value())
        y = float(self.spn_y.value())
        pause_ms = int(round(float(self.spn_pause_s.value()) * 1000.0))
        initial_flush = self.chk_initial_flush.isChecked()

        path, _ = QFileDialog.getSaveFileName(
            self, "Save G-code", "calibration.gcode", "G-code (*.gcode)"
        )
        if not path:
            QMessageBox.warning(self, "Canceled", "No file selected. G-code generation canceled.")
            return

        try:
            self.g = G(outfile=path)
            self.g.write("G21")  # mm
            self.g.write("G28")  # home

            if initial_flush:
                self.flush(self.syringe_vol/2, repeats=3)

            # Same “fast” pattern: 10 points from 10%→100%, 3 vials each
            start = 0.1 * self.syringe_vol
            stop  = self.syringe_vol
            steps = 5
            n_vials_per_vol = 3

            volumes = np.linspace(start=start, stop=stop, num=steps)
            vials_count = n_vials_per_vol * np.ones_like(volumes, dtype=int)

            current_vial = 0
            for vol_index, count in enumerate(vials_count):
                for _ in range(count):
                    volume = float(volumes[vol_index])
                    self.g.dwell(pause_ms)
                    self.remove_from_vial(self.solvent1_x, self.solvent1_y, volume)
                    self.fill_vial(x, y)
                    current_vial += 1

            self.home()
            self.g = None
            QMessageBox.information(self, "Success", f"G-code written to:\n{path}")

        except Exception as e:
            QMessageBox.critical(self, "G-code Error", str(e))


def main():
    app = QApplication(sys.argv)
    w = FastCalibrationWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
