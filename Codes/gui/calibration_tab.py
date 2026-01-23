from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config_io import load_model
from ..Machine import Machine
from ..PipetG import PipetG
from ..Rack import Rack
from ..Setup import Setup
from ..Solvent import Solvent
from ..Syringe import Syringe


class CalibrationTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._base_dir = Path(__file__).resolve().parent.parent
        self._config_dir = self._base_dir.parent / "config"
        self._racks_dir = self._config_dir / "racks"
        self._machines_dir = self._config_dir / "machines"

        self._rack_names: list[str] = []
        self._machine_names: list[str] = []

        self._build_ui()
        self._load_config_lists()
        self._load_syringe_list()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Calibration")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        root.addWidget(title)

        syringe_row = QHBoxLayout()
        syringe_row.addWidget(QLabel("Syringe"))
        self.cmb_syringe = QComboBox()
        self.cmb_syringe.currentIndexChanged.connect(self._update_generate_enabled)
        syringe_row.addWidget(self.cmb_syringe, 1)
        root.addLayout(syringe_row)

        self.subtabs = QTabWidget()
        root.addWidget(self.subtabs, 1)

        self._build_fast_tab()
        self._build_vials_tab()

    def _build_fast_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QLabel("Same vial (fast)")
        header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(header)

        rack_row = QHBoxLayout()
        rack_row.addWidget(QLabel("Rack"))
        self.cmb_fast_rack = QComboBox()
        rack_row.addWidget(self.cmb_fast_rack, 1)
        layout.addLayout(rack_row)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.spn_fast_x = QDoubleSpinBox()
        self.spn_fast_x.setRange(-1e6, 1e6)
        self.spn_fast_x.setDecimals(3)
        self.spn_fast_x.setValue(10.0)

        self.spn_fast_y = QDoubleSpinBox()
        self.spn_fast_y.setRange(-1e6, 1e6)
        self.spn_fast_y.setDecimals(3)
        self.spn_fast_y.setValue(185.0)

        self.spn_fast_pause = QDoubleSpinBox()
        self.spn_fast_pause.setRange(0.0, 1e6)
        self.spn_fast_pause.setDecimals(3)
        self.spn_fast_pause.setValue(10.0)

        form.addRow("X [mm]:", self.spn_fast_x)
        form.addRow("Y [mm]:", self.spn_fast_y)
        form.addRow("Pause [s]:", self.spn_fast_pause)
        layout.addLayout(form)

        self.chk_fast_flush = QCheckBox("Initial flush (3×)")
        self.chk_fast_flush.setChecked(True)
        layout.addWidget(self.chk_fast_flush)

        self.btn_fast_generate = QPushButton("Generate calibration G-code")
        self.btn_fast_generate.clicked.connect(self._on_generate_fast)
        layout.addWidget(self.btn_fast_generate, alignment=Qt.AlignRight)

        self.subtabs.addTab(tab, "Same vial")

    def _build_vials_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QLabel("Different vials")
        header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(header)

        rack_row = QHBoxLayout()
        rack_row.addWidget(QLabel("Rack"))
        self.cmb_vials_rack = QComboBox()
        rack_row.addWidget(self.cmb_vials_rack, 1)
        layout.addLayout(rack_row)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.spn_10 = QSpinBox()
        self.spn_10.setRange(0, 1000000)
        self.spn_10.setValue(0)

        self.spn_50 = QSpinBox()
        self.spn_50.setRange(0, 1000000)
        self.spn_50.setValue(0)

        self.spn_100 = QSpinBox()
        self.spn_100.setRange(0, 1000000)
        self.spn_100.setValue(0)

        form.addRow("Vials @ 10% volume:", self.spn_10)
        form.addRow("Vials @ 50% volume:", self.spn_50)
        form.addRow("Vials @ 100% volume:", self.spn_100)
        layout.addLayout(form)

        self.chk_vials_flush = QCheckBox("Initial flush")
        self.chk_vials_leading_air = QCheckBox("Leading air gap")
        self.chk_vials_non_contact = QCheckBox("Non-contact dispense (use Z_slow)")

        opts = QHBoxLayout()
        opts.addWidget(self.chk_vials_flush)
        opts.addWidget(self.chk_vials_leading_air)
        opts.addWidget(self.chk_vials_non_contact)
        opts.addStretch(1)
        layout.addLayout(opts)

        self.btn_vials_generate = QPushButton("Generate calibration G-code")
        self.btn_vials_generate.clicked.connect(self._on_generate_vials)
        layout.addWidget(self.btn_vials_generate, alignment=Qt.AlignRight)

        self.subtabs.addTab(tab, "Different vials")

    # ---------------- Data loading ----------------

    def _load_config_lists(self) -> None:
        if self._racks_dir.exists():
            self._rack_names = sorted(p.stem for p in self._racks_dir.glob("*.json"))
        else:
            self._rack_names = []

        if self._machines_dir.exists():
            self._machine_names = sorted(p.stem for p in self._machines_dir.glob("*.json"))
        else:
            self._machine_names = []

        self.cmb_fast_rack.clear()
        self.cmb_vials_rack.clear()

        self.cmb_fast_rack.addItem("— select —", None)
        self.cmb_vials_rack.addItem("— select —", None)
        for name in self._rack_names:
            self.cmb_fast_rack.addItem(name, name)
            self.cmb_vials_rack.addItem(name, name)

        if self._rack_names:
            self.cmb_fast_rack.setCurrentIndex(1)

    def _load_syringe_list(self) -> None:
        self.cmb_syringe.clear()
        self.cmb_syringe.addItem("— select —", None)
        try:
            syringes = Syringe.get_all()
        except Exception:
            return

        for s in syringes:
            if s.id is None:
                continue
            label = f"{s.id} - {s.name}"
            self.cmb_syringe.addItem(label, int(s.id))
        self._update_generate_enabled()

    def refresh_syringe_list(self) -> None:
        self._load_syringe_list()

    # ---------------- Helpers ----------------

    def _selected_syringe_id(self) -> int:
        s_id = self.cmb_syringe.currentData()
        if s_id is None:
            raise ValueError("Please select a syringe.")
        return int(s_id)

    def _default_machine_name(self) -> str:
        if not self._machine_names:
            raise ValueError("No machine configs found under config/machines.")
        if "current" in self._machine_names:
            return "current"
        return self._machine_names[0]

    def _selected_rack_name(self, combo: QComboBox, *, require: bool = False) -> str:
        rack = combo.currentData()
        if rack is None:
            if require:
                raise ValueError("Please select a rack for calibration.")
            if self._rack_names:
                return self._rack_names[0]
            raise ValueError("No rack configs found under config/racks.")
        return str(rack)

    def _default_solvent_id(self) -> int:
        solvents = Solvent.get_all()
        if not solvents:
            raise ValueError("No solvents found in DB. Populate your Solvent table first.")
        solvents = [s for s in solvents if s.id is not None]
        if not solvents:
            raise ValueError("No solvent ids found in DB.")
        solvents.sort(key=lambda s: int(s.id))
        return int(solvents[0].id)

    def _build_setup(self, rack_name: str) -> Setup:
        machine = load_model(Machine, self._default_machine_name())
        rack = load_model(Rack, rack_name)

        s_id = self._selected_syringe_id()
        syringe = Syringe.get_by_id(s_id)
        if syringe is None:
            raise ValueError(f"No syringe with id={s_id} found in DB.")

        solvents = Solvent.get_all()
        if not solvents:
            raise ValueError("No solvents found in DB. Populate your Solvent table first.")

        setup_data = {
            "name": "Calibration",
            "syringes": [syringe],
            "solvents": solvents,
            "racks": [rack],
            "machine": machine,
        }
        return Setup.model_validate(setup_data)

    def _build_pipet(self, outfile: Path, rack_name: str) -> PipetG:
        setup = self._build_setup(rack_name)
        s_id = self._selected_syringe_id()
        return PipetG(outfile=outfile, setup=setup, syringe_id=s_id)

    def _update_generate_enabled(self) -> None:
        has_syringe = self.cmb_syringe.currentData() is not None
        self.btn_fast_generate.setEnabled(has_syringe)
        self.btn_vials_generate.setEnabled(has_syringe)

    def _pick_gcode_path(self, default_name: str) -> Path | None:
        gcode_dir = self._base_dir.parent / "G-codes"
        start_dir = str(gcode_dir if gcode_dir.is_dir() else self._base_dir)
        path, _ = QFileDialog.getSaveFileName(self, "Save G-code", start_dir, "G-code files (*.gcode)")
        if not path:
            return None
        if not path.lower().endswith(".gcode"):
            path += ".gcode"
        return Path(path)

    # ---------------- Actions ----------------

    def _on_generate_fast(self) -> None:
        try:
            rack_name = self._selected_rack_name(self.cmb_fast_rack)
            x = float(self.spn_fast_x.value())
            y = float(self.spn_fast_y.value())
            pause_ms = int(round(float(self.spn_fast_pause.value()) * 1000.0))
            initial_flush = self.chk_fast_flush.isChecked()

            out_path = self._pick_gcode_path("calibration_fast.gcode")
            if out_path is None:
                return
            out_path.parent.mkdir(parents=True, exist_ok=True)

            solvent_id = self._default_solvent_id()

            with self._build_pipet(out_path, rack_name) as pg:
                pg.home()

                if initial_flush:
                    flush_vol = min(0.5 * float(pg.max_volume_ul), float(pg.max_volume_ul))
                    pg.flush(flush_vol, repeats=3, solvent_idx=0, solvent_id=solvent_id)

                start = 0.1 * float(pg.max_volume_ul)
                stop = float(pg.max_volume_ul)
                steps = 5
                repeats = 3
                if steps <= 1:
                    volumes = [stop]
                else:
                    step = (stop - start) / float(steps - 1)
                    volumes = [start + i * step for i in range(steps)]

                sx, sy = pg.solvent_positions[0]
                z_min_solvent = pg.z_min_solvents[0]
                for volume in volumes:
                    for _ in range(repeats):
                        if pause_ms > 0:
                            pg.dwell(pause_ms)
                        pg.remove_from_vial(sx, sy, volume, solvent_id, z_min=z_min_solvent)
                        pg.fill_vial(x, y, z_min=pg.z_min)

                pg.finish()

            QMessageBox.information(self, "Success", f"G-code written to:\n{out_path}")

        except Exception as e:
            QMessageBox.critical(self, "Calibration error", str(e))

    def _on_generate_vials(self) -> None:
        try:
            rack_name = self._selected_rack_name(self.cmb_vials_rack, require=True)
            n10 = int(self.spn_10.value())
            n50 = int(self.spn_50.value())
            n100 = int(self.spn_100.value())
            initial_flush = self.chk_vials_flush.isChecked()
            leading_air = self.chk_vials_leading_air.isChecked()
            non_contact = self.chk_vials_non_contact.isChecked()

            out_path = self._pick_gcode_path("calibration_vials.gcode")
            if out_path is None:
                return
            out_path.parent.mkdir(parents=True, exist_ok=True)

            solvent_id = self._default_solvent_id()

            with self._build_pipet(out_path, rack_name) as pg:
                pg.home()

                if initial_flush:
                    flush_vol = min(500.0, float(pg.max_volume_ul))
                    pg.flush(flush_vol, repeats=3, solvent_idx=0, solvent_id=solvent_id)

                volumes = [0.1, 0.5, 1.0]
                counts = [n10, n50, n100]
                vial_positions = pg.vial_positions
                z_min_vials = pg.z_min_vials

                total_needed = sum(counts)
                if total_needed > len(vial_positions):
                    raise ValueError(
                        f"Not enough vial slots: need {total_needed}, "
                        f"rack provides {len(vial_positions)}."
                    )

                sx, sy = pg.solvent_positions[0]
                z_min_solvent = pg.z_min_solvents[0]
                current_vial = 0
                for frac, count in zip(volumes, counts, strict=True):
                    for _ in range(count):
                        volume = frac * float(pg.max_volume_ul)
                        pg.remove_from_vial(sx, sy, volume, solvent_id, z_min=z_min_solvent)

                        if leading_air:
                            air_gap = 0.1 * volume
                            disp = pg.displacement(air_gap, solvent_id)
                            pg.g.relative()
                            pg.g.move(A=disp, F=pg.Fa_pull)
                            pg.g.absolute()

                        x, y = vial_positions[current_vial]
                        z_min = z_min_vials[current_vial]
                        pg.fill_vial(x, y, slow=non_contact, z_min=z_min)
                        current_vial += 1

                pg.finish()

            QMessageBox.information(self, "Success", f"G-code written to:\n{out_path}")

        except Exception as e:
            QMessageBox.critical(self, "Calibration error", str(e))
