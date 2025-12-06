# LiquidHandling_PySide6.py
from __future__ import annotations

import sys
import configparser
import pandas as pd
import Solvent
import Syringe
import SyringeSolventLink
import Rack
import Machine
import Setup

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QScrollArea, QFrame, QLineEdit,
    QFileDialog, QMessageBox
)

from mecode import G


class LiquidHandlingWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Liquid Handling System (PySide6)")
        self.resize(800, 600)

        # ---- Load config.ini ----
        self.config = configparser.ConfigParser()
        if not self.config.read("config.ini"):
            self._fatal("No config.ini found in the working directory.")

        # Syringe 1 settings
        try:
            self.factor_1 = self.config.getfloat("Syringe_1", "theoretical_factor")
            self.backlash_1 = self.config.getfloat("Syringe_1", "backlash_correction")
            self.max_vol_1 = self.config.getint("Syringe_1", "max_volume")
            self.min_vol_1 = self.config.getint("Syringe_1", "min_volume")
        except Exception as e:
            self._fatal(f"Syringe_1 settings missing/invalid:\n{e!s}")

        # Syringe 2 settings
        try:
            self.factor_2 = self.config.getfloat("Syringe_2", "theoretical_factor")
            self.backlash_2 = self.config.getfloat("Syringe_2", "backlash_correction")
            self.max_vol_2 = self.config.getint("Syringe_2", "max_volume")
            self.min_vol_2 = self.config.getint("Syringe_2", "min_volume")
            self.syringe2_offset_x = self.config.getfloat("Syringe_2", "syringe2_offset_x")
            self.syringe2_offset_y = self.config.getfloat("Syringe_2", "syringe2_offset_y")
        except Exception as e:
            self._fatal(f"Syringe_2 settings missing/invalid:\n{e!s}")

        # Rack settings
        try:
            self.vial1_s = [self.config.getfloat("Rack", "vial1_x"),
                            self.config.getfloat("Rack", "vial1_y")]
            self.dx_s = self.config.getfloat("Rack", "dx_s")
            self.dy_s = self.config.getfloat("Rack", "dy_s")
            self.solvent1_x = self.config.getfloat("Rack", "solvent1_x")
            self.solvent1_y = self.config.getfloat("Rack", "solvent1_y")
            self.solvent_y_increment = self.config.getint("Rack", "increment_y")
            self.vial_waste = [self.config.getfloat("Rack", "waste_x"),
                               self.config.getfloat("Rack", "waste_y")]
            self.vials_per_row = self.config.getint("Rack", "vials_per_row")
            self.columns = self.config.getint("Rack", "columns")
            self.solvent_number = self.config.getint("Rack", "number_of_solvents")
        except Exception as e:
            self._fatal(f"Rack settings missing/invalid:\n{e!s}")

        # Machine settings
        try:
            self.Z_slow = self.config.getint("Machine", "Z_slow")
            self.Z_max = self.config.getint("Machine", "Z_max")
            self.Z_min = self.config.getint("Machine", "Z_min")
            self.Fz = self.config.getint("Machine", "Fz")
            self.Fxy = self.config.getint("Machine", "Fxy")
            self.Fa_push = self.config.getint("Machine", "Fa_push")
            self.Fa_push_slow = self.config.getint("Machine", "Fa_push_slow")
            self.Fa_pull = self.config.getint("Machine", "Fa_pull")
            self.Rest_x = self.config.getint("Machine", "Rest_x")
            self.Rest_y = self.config.getint("Machine", "Rest_y")
        except Exception as e:
            self._fatal(f"Machine settings missing/invalid:\n{e!s}")

        # Derived positions
        self.solvent_positions = {
            f"Solvent_{i}": [
                self.solvent1_x,
                self.solvent1_y + ((i - 1) * self.solvent_y_increment),
            ]
            for i in range(1, self.solvent_number + 1)
        }

        # State
        self.solvents: list[str] = [f"Solvent_{i+1}" for i in range(self.solvent_number)]
        self.solvent_slow_push_vars: dict[str, QCheckBox] = {}
        self.vial_entries: list[list] = []  # [frame, (QLineEdit, QCheckBox Flush), ...]

        self.chk_mode_vial: QCheckBox | None = None
        self.chk_mode_solvent: QCheckBox | None = None
        self.lbl_vials_count: QLabel | None = None
        self.headers_layout: QHBoxLayout | None = None
        self.inputs_layout: QVBoxLayout | None = None

        self.g: G | None = None

        # --- UI ---
        self._build_ui()

    # --------- helpers ----------
    def _fatal(self, msg: str):
        QMessageBox.critical(self, "Configuration error", msg)
        sys.exit(1)

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # Top bar: save / load
        top = QHBoxLayout()
        root.addLayout(top)

        btn_export = QPushButton("Export Excel")
        btn_export.clicked.connect(self.on_save_method)
        top.addWidget(btn_export)

        btn_import = QPushButton("Import Excel/CSV")
        btn_import.clicked.connect(self.on_load_method)
        top.addWidget(btn_import)

        top.addStretch(1)

        # Mode / vial buttons
        mode = QHBoxLayout()
        root.addLayout(mode)

        btn_add_vial = QPushButton("Add Vial")
        btn_add_vial.clicked.connect(self.add_vial)
        mode.addWidget(btn_add_vial)

        btn_remove_vial = QPushButton("Remove Vial")
        btn_remove_vial.clicked.connect(self.remove_vial)
        mode.addWidget(btn_remove_vial)

        self.chk_mode_vial = QCheckBox("Vial after Vial")
        self.chk_mode_solvent = QCheckBox("Solvent after Solvent")
        self.chk_mode_vial.setChecked(True)
        self.chk_mode_solvent.setChecked(False)

        self.chk_mode_vial.stateChanged.connect(
            lambda _: self.on_mode_checkbox_changed(self.chk_mode_vial)
        )
        self.chk_mode_solvent.stateChanged.connect(
            lambda _: self.on_mode_checkbox_changed(self.chk_mode_solvent)
        )

        mode.addWidget(self.chk_mode_vial)
        mode.addWidget(self.chk_mode_solvent)

        self.lbl_vials_count = QLabel("Vials: 0")
        mode.addWidget(self.lbl_vials_count)

        mode.addStretch(1)

        btn_generate = QPushButton("Generate G-Code")
        btn_generate.clicked.connect(self.on_generate_gcode)
        mode.addWidget(btn_generate)

        # Headers
        headers_widget = QWidget()
        self.headers_layout = QHBoxLayout(headers_widget)
        self.headers_layout.setContentsMargins(5, 5, 5, 5)
        root.addWidget(headers_widget)

        # Scrollable vial list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.inputs_layout = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        # Build headers and initial vials
        self.setup_solvent_headers()
        for _ in range(10):
            self.add_vial()

    def update_vials_count_label(self):
        if self.lbl_vials_count is not None:
            self.lbl_vials_count.setText(f"Vials: {len(self.vial_entries)}")

    # --------- syringe / moves ----------
    def syringe(self, volume: float) -> tuple[float, int]:
        if self.min_vol_1 <= volume <= self.max_vol_1:
            syringe_type = 1
            return (volume * self.factor_1) + self.backlash_1, syringe_type
        elif self.min_vol_2 <= volume < self.max_vol_2:
            syringe_type = 2
            return (volume * self.factor_2) + self.backlash_2, syringe_type
        else:
            QMessageBox.critical(
                self,
                "Volume error",
                f"Volume out of range; please enter a volume between "
                f"{self.min_vol_1} and {self.max_vol_2} µL."
            )
            raise ValueError("Volume out of range")

    def vial_position(self, vial_index: int) -> tuple[float, float] | None:
        row = vial_index // self.vials_per_row
        col = vial_index % self.vials_per_row
        total_vials = self.vials_per_row * self.columns
        if vial_index >= total_vials:
            QMessageBox.warning(
                self,
                "Vial index error",
                f"Vial index out of bounds. Rack only has {total_vials} vials."
            )
            return None
        x = self.vial1_s[0] + row * self.dx_s
        y = self.vial1_s[1] + col * self.dy_s
        return x, y

    def flush(self, volume: float, repeats: int = 1, solvent_name: str = "Solvent_1"):
        if self.g is None:
            return
        self.g.write("flush")
        solvent_pos = self.solvent_positions[solvent_name]
        for _ in range(repeats):
            displacement, syringe_type = self.syringe(volume)
            self.remove_from_vial(solvent_pos[0], solvent_pos[1], volume)
            self.g.write("fill_vial")
            self.g.absolute()
            if syringe_type == 2:
                adjusted_waste = (
                    self.vial_waste[0] + self.syringe2_offset_x,
                    self.vial_waste[1] + self.syringe2_offset_y,
                )
                self.g.move(B=self.Z_max, F=self.Fz)
                self.g.move(adjusted_waste[0], adjusted_waste[1], F=self.Fxy)
                self.g.move(B=self.Z_min, F=self.Fz)
                self.g.move(C=0, F=self.Fa_push)
                self.g.move(B=self.Z_max, F=self.Fz)
            else:
                self.g.move(z=self.Z_max, F=self.Fz)
                self.g.move(self.vial_waste[0], self.vial_waste[1], F=self.Fxy)
                self.g.move(z=self.Z_min, F=self.Fz)
                self.g.move(A=0, F=self.Fa_push)
                self.g.move(z=self.Z_max, F=self.Fz)

    def fill_vial(self, x: float, y: float, volume: float, solvent_name: str):
        if self.g is None:
            return
        slow_push = False
        cb = self.solvent_slow_push_vars.get(solvent_name)
        if cb is not None and cb.isChecked():
            slow_push = True

        self.g.write("fill_vial")
        self.g.absolute()
        displacement, syringe_type = self.syringe(volume)
        adjusted_x, adjusted_y = x, y

        if syringe_type == 2:
            adjusted_x += self.syringe2_offset_x
            adjusted_y += self.syringe2_offset_y
            self.g.move(B=self.Z_max, F=self.Fz)
            self.g.move(adjusted_x, adjusted_y, F=self.Fxy)
            if slow_push:
                self.g.move(B=self.Z_slow, F=self.Fz)
                self.g.move(C=0, F=self.Fa_push_slow)
                print("slow push")
            else:
                self.g.move(B=self.Z_min, F=self.Fz)
                self.g.move(C=0, F=self.Fa_push)
            self.g.move(B=self.Z_max, F=self.Fz)
        else:
            self.g.move(z=self.Z_max, F=self.Fz)
            self.g.move(adjusted_x, adjusted_y, F=self.Fxy)
            if slow_push:
                self.g.move(z=self.Z_slow, F=self.Fz)
                self.g.move(A=0, F=self.Fa_push_slow)
                print("slow push")
            else:
                self.g.move(z=self.Z_min, F=self.Fz)
                self.g.move(A=0, F=self.Fa_push)
            self.g.move(z=self.Z_max, F=self.Fz)

    def remove_from_vial(self, x: float, y: float, volume: float):
        if self.g is None:
            return
        self.g.write("remove_from_vial")
        self.g.absolute()
        displacement, syringe_type = self.syringe(volume)
        adjusted_x, adjusted_y = x, y
        if syringe_type == 2:
            adjusted_x += self.syringe2_offset_x
            adjusted_y += self.syringe2_offset_y
            self.g.move(B=self.Z_max, F=self.Fz)
            self.g.move(adjusted_x, adjusted_y, F=self.Fxy)
            self.g.move(B=self.Z_min, F=self.Fz)
            self.g.relative()
            self.g.move(C=displacement, F=self.Fa_pull)
            self.g.absolute()
            self.g.move(B=self.Z_max, F=self.Fz)
        else:
            self.g.move(z=self.Z_max, F=self.Fz)
            self.g.move(adjusted_x, adjusted_y, F=self.Fxy)
            self.g.move(z=self.Z_min, F=self.Fz)
            self.g.relative()
            self.g.move(A=displacement, F=self.Fa_pull)
            self.g.absolute()
            self.g.move(z=self.Z_max, F=self.Fz)

    def home(self):
        if self.g is None:
            return
        self.g.absolute()
        self.g.move(z=self.Z_max, B=self.Z_max, F=self.Fz)
        self.g.move(self.Rest_x, self.Rest_y, F=self.Fxy)
        self.g.move(z=self.Z_min, B=self.Z_min, F=self.Fz)
        self.g.write("M84")

    def process_vial(self, volume: float, flush_required: bool,
                     solvent_name: str, vial_index: int):
        if self.g is None:
            return
        if flush_required:
            self.flush(volume, solvent_name=solvent_name)
        print(f"Picking up {volume} µL of {solvent_name}")
        solvent_pos = self.solvent_positions[solvent_name]
        self.remove_from_vial(solvent_pos[0], solvent_pos[1], volume)
        pos = self.vial_position(vial_index - 1)
        if pos is None:
            return
        x, y = pos
        self.fill_vial(x, y, volume, solvent_name)

    # --------- GUI building: headers / vials ----------
    def setup_solvent_headers(self):
        if self.headers_layout is None:
            return

        # Clear existing widgets
        while self.headers_layout.count():
            item = self.headers_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self.solvent_slow_push_vars.clear()

        lbl_pos = QLabel("Position")
        lbl_pos.setMinimumWidth(80)
        self.headers_layout.addWidget(lbl_pos)

        for solvent in self.solvents:
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(5, 0, 5, 0)

            lbl = QLabel(solvent)
            slow_cb = QCheckBox("Slow")

            hl.addWidget(lbl)
            hl.addWidget(slow_cb)

            self.headers_layout.addWidget(w)
            self.solvent_slow_push_vars[solvent] = slow_cb

        self.headers_layout.addStretch(1)

    def add_vial(self):
        if self.inputs_layout is None:
            return

        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        h = QHBoxLayout(frame)
        h.setContentsMargins(5, 5, 5, 5)

        vial_number = len(self.vial_entries) + 1
        lbl = QLabel(f"Vial {str(vial_number).zfill(2)}:")
        lbl.setMinimumWidth(80)
        h.addWidget(lbl)

        vial_entry_group = [frame]

        for solvent in self.solvents:
            container = QWidget()
            ch = QHBoxLayout(container)
            ch.setContentsMargins(0, 0, 0, 0)

            entry = QLineEdit()
            entry.setFixedWidth(70)
            flush_cb = QCheckBox("Flush")

            ch.addWidget(entry)
            ch.addWidget(flush_cb)
            h.addWidget(container)

            vial_entry_group.append((entry, flush_cb))

        self.vial_entries.append(vial_entry_group)
        self.inputs_layout.addWidget(frame)
        self.update_vials_count_label()

    def remove_vial(self):
        if not self.vial_entries:
            return
        frame = self.vial_entries.pop()[0]
        frame.setParent(None)
        frame.deleteLater()
        self.update_vials_count_label()

    def on_mode_checkbox_changed(self, changed: QCheckBox):
        if changed is self.chk_mode_vial:
            if self.chk_mode_vial.isChecked():
                self.chk_mode_solvent.setChecked(False)
            elif not self.chk_mode_solvent.isChecked():
                self.chk_mode_solvent.setChecked(True)
        elif changed is self.chk_mode_solvent:
            if self.chk_mode_solvent.isChecked():
                self.chk_mode_vial.setChecked(False)
            elif not self.chk_mode_vial.isChecked():
                self.chk_mode_vial.setChecked(True)

    # --------- Save / load methods ----------
    def on_save_method(self):
        if not self.vial_entries:
            QMessageBox.warning(self, "No data", "There are no vials to save.")
            return

        reply = QMessageBox.question(
            self,
            "Export Options",
            "Do you want to export flush information as well?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        include_flush = reply == QMessageBox.Yes

        data = {"Vial": []}
        for solvent in self.solvents:
            data[solvent] = []
            if include_flush:
                data[f"{solvent}_Flush"] = []

        for vial_index, vial_group in enumerate(self.vial_entries, start=1):
            data["Vial"].append(vial_index)
            for i, solvent in enumerate(self.solvents):
                entry, flush_cb = vial_group[1:][i]
                volume_value = entry.text().strip()
                if volume_value:
                    data[solvent].append(volume_value)
                    if include_flush:
                        data[f"{solvent}_Flush"].append(flush_cb.isChecked())
                else:
                    data[solvent].append("")
                    if include_flush:
                        data[f"{solvent}_Flush"].append(False)

        df = pd.DataFrame(data)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save method",
            "",
            "Excel files (*.xlsx);;CSV files (*.csv)",
        )
        if not path:
            return

        if path.lower().endswith(".csv"):
            df.to_csv(path, index=False)
        else:
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            df.to_excel(path, index=False)

        QMessageBox.information(self, "Save Successful", f"Method saved to:\n{path}")

    def on_load_method(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open method",
            "",
            "Excel/CSV files (*.xlsx *.csv)",
        )
        if not path:
            return

        if path.lower().endswith(".csv"):
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)

        reply = QMessageBox.question(
            self,
            "Import Options",
            "Do you want to import flush information if available?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        include_flush = reply == QMessageBox.Yes

        solvent_names: list[str] = []
        for col in df.columns:
            if col.startswith("Solvent_") and not col.endswith("_Flush"):
                solvent_names.append(col)

        if not solvent_names:
            QMessageBox.critical(
                self,
                "Error",
                "No solvent columns found (expected columns like 'Solvent_1').",
            )
            return

        # update solvents + headers
        self.solvents = solvent_names
        self.setup_solvent_headers()

        # clear existing vials
        for group in self.vial_entries:
            frame = group[0]
            frame.setParent(None)
            frame.deleteLater()
        self.vial_entries.clear()

        # populate from df
        for _, row in df.iterrows():
            frame = QFrame()
            frame.setFrameShape(QFrame.StyledPanel)
            h = QHBoxLayout(frame)
            h.setContentsMargins(5, 5, 5, 5)

            vial_number = len(self.vial_entries) + 1
            lbl = QLabel(f"Vial {str(vial_number).zfill(2)}:")
            lbl.setMinimumWidth(80)
            h.addWidget(lbl)

            vial_entry_group = [frame]

            for solvent in self.solvents:
                container = QWidget()
                ch = QHBoxLayout(container)
                ch.setContentsMargins(0, 0, 0, 0)

                entry = QLineEdit()
                entry_value = row.get(solvent, "")
                if pd.notna(entry_value):
                    entry.setText(str(entry_value))

                flush_flag = False
                if include_flush and f"{solvent}_Flush" in df.columns:
                    raw = row.get(f"{solvent}_Flush", False)
                    if pd.notna(raw):
                        flush_flag = bool(raw)

                flush_cb = QCheckBox("Flush")
                flush_cb.setChecked(flush_flag)

                ch.addWidget(entry)
                ch.addWidget(flush_cb)
                h.addWidget(container)

                vial_entry_group.append((entry, flush_cb))

            self.vial_entries.append(vial_entry_group)
            if self.inputs_layout is not None:
                self.inputs_layout.addWidget(frame)

        self.update_vials_count_label()
        QMessageBox.information(
            self,
            "Import Successful",
            f"Loaded method with {len(self.solvents)} solvent(s) from:\n{path}",
        )

    # --------- G-code generation ----------
    def on_generate_gcode(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save G-code",
            "",
            "G-code files (*.gcode)",
        )
        if not path:
            QMessageBox.warning(
                self, "File Not Saved",
                "No file selected. G-code generation canceled."
            )
            return

        if not path.lower().endswith(".gcode"):
            path += ".gcode"

        try:
            self.g = G(outfile=path)
            self.g.write("G21")
            self.g.write("G28 Z B")
            self.g.write("G28 Y X A C")

            if self.chk_mode_vial.isChecked():
                # vial after vial
                for vial_index, entries in enumerate(self.vial_entries, start=1):
                    for solvent_index, (entry, flush_cb) in enumerate(entries[1:]):
                        text = entry.text().strip()
                        if not text:
                            continue
                        try:
                            vol = float(text)
                        except ValueError:
                            QMessageBox.warning(
                                self,
                                "Invalid volume",
                                f"Invalid volume '{text}' in Vial {vial_index}, "
                                f"{self.solvents[solvent_index]}. Skipping.",
                            )
                            continue
                        flush_required = flush_cb.isChecked()
                        solvent_name = self.solvents[solvent_index]
                        self.process_vial(vol, flush_required, solvent_name, vial_index)

            elif self.chk_mode_solvent.isChecked():
                # solvent after solvent
                for solvent_index, solvent_name in enumerate(self.solvents):
                    for vial_index, entries in enumerate(self.vial_entries, start=1):
                        entry, flush_cb = entries[1:][solvent_index]
                        text = entry.text().strip()
                        if not text:
                            continue
                        try:
                            vol = float(text)
                        except ValueError:
                            QMessageBox.warning(
                                self,
                                "Invalid volume",
                                f"Invalid volume '{text}' in Vial {vial_index}, "
                                f"{solvent_name}. Skipping.",
                            )
                            continue
                        flush_required = flush_cb.isChecked()
                        self.process_vial(vol, flush_required, solvent_name, vial_index)

            self.home()
            self.g = None

            QMessageBox.information(
                self,
                "G-Code Generation Complete",
                "The G-code generation process has finished.\n"
                "Please restart the program for the next file generation.",
            )
            self.close()

        except Exception as e:
            QMessageBox.critical(self, "G-code Error", str(e))
            self.g = None


def main():
    app = QApplication(sys.argv)
    w = LiquidHandlingWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
