from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config_io import load_model
from ..db import get_session
from ..Machine import Machine
from ..PipetG import PipetG
from ..Rack import Rack
from ..Setup import Setup
from ..Solvent import Solvent
from ..Syringe import Syringe
from ..SyringeSolventLink import SyringeSolventLink


@dataclass
class _EvaluationWidgets:
    context: str
    table: QTableWidget
    lbl_cf_new: QLabel
    lbl_bc_new: QLabel
    lbl_error: QLabel


class _MassPlaceholderDelegate(QStyledItemDelegate):
    def __init__(self, owner: "CalibrationTab", parent: QWidget | None = None):
        super().__init__(parent)
        self._owner = owner

    def paint(self, painter, option, index):  # type: ignore[override]
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        super().paint(painter, opt, index)

        value = index.data(Qt.DisplayRole)
        if value is not None and str(value).strip() != "":
            return

        placeholder = self._owner._placeholder_mass_text(index.row())
        if not placeholder:
            return

        painter.save()
        font = opt.font
        font.setItalic(True)
        painter.setFont(font)
        painter.setPen(QColor(140, 150, 165))
        rect = option.rect.adjusted(4, 0, -4, 0)
        painter.drawText(rect, Qt.AlignCenter, placeholder)
        painter.restore()


class CalibrationTab(QWidget):
    _MASS_SUB_RE = re.compile(
        r"^\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*-\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*$"
    )

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._base_dir = Path(__file__).resolve().parent.parent
        self._config_dir = self._base_dir.parent / "config"
        self._racks_dir = self._config_dir / "racks"
        self._machines_dir = self._config_dir / "machines"

        self._rack_names: list[str] = []
        self._machine_names: list[str] = []
        self._eval_sections: list[_EvaluationWidgets] = []
        self._current_cf: float | None = None
        self._current_bc: float | None = None
        self._current_density: float | None = None
        self._eval_volumes: list[float] = []

        self._build_ui()
        self._load_config_lists()
        self._load_syringe_list()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        title = QLabel("Calibration")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        root.addWidget(title)
        root.addSpacing(10)

        syringe_row = QHBoxLayout()
        syringe_row.addWidget(QLabel("Syringe"))
        self.cmb_syringe = QComboBox()
        self.cmb_syringe.currentIndexChanged.connect(self._update_generate_enabled)
        self.cmb_syringe.currentIndexChanged.connect(self._update_calibration_factors)
        syringe_row.addWidget(self.cmb_syringe)
        syringe_row.addSpacing(12)
        syringe_row.addWidget(QLabel("Solvent id"))
        self.spn_solvent_id = QSpinBox()
        self.spn_solvent_id.setRange(0, 1_000_000)
        self.spn_solvent_id.setSpecialValueText("—")
        self.spn_solvent_id.setValue(0)
        self.spn_solvent_id.valueChanged.connect(self._update_generate_enabled)
        self.spn_solvent_id.valueChanged.connect(self._update_calibration_factors)
        syringe_row.addWidget(self.spn_solvent_id)
        syringe_row.addSpacing(12)
        self.lbl_cf_current = QLabel()
        self.lbl_cf_current.setTextFormat(Qt.RichText)
        syringe_row.addWidget(self.lbl_cf_current)
        syringe_row.addSpacing(12)
        self.lbl_bc_current = QLabel()
        self.lbl_bc_current.setTextFormat(Qt.RichText)
        syringe_row.addWidget(self.lbl_bc_current)
        syringe_row.addStretch(1)
        root.addLayout(syringe_row)
        root.addSpacing(10)

        rack_row = QHBoxLayout()
        rack_row.addWidget(QLabel("Rack"))
        self.cmb_rack = QComboBox()
        rack_row.addWidget(self.cmb_rack)
        rack_row.addSpacing(24)
        rack_row.addWidget(QLabel("Machine"))
        self.cmb_machine = QComboBox()
        rack_row.addWidget(self.cmb_machine)
        rack_row.addStretch(1)
        root.addLayout(rack_row)
        root.addSpacing(10)

        self.spn_fast_datapoints = QDoubleSpinBox()
        self.spn_fast_datapoints.setRange(1, 1000000)
        self.spn_fast_datapoints.setDecimals(0)
        self.spn_fast_datapoints.setSingleStep(1.0)
        self.spn_fast_datapoints.setValue(5)

        self.spn_fast_repeats = QDoubleSpinBox()
        self.spn_fast_repeats.setRange(1, 1000000)
        self.spn_fast_repeats.setDecimals(0)
        self.spn_fast_repeats.setSingleStep(1.0)
        self.spn_fast_repeats.setValue(3)

        self.spn_fast_start = QDoubleSpinBox()
        self.spn_fast_start.setRange(0.0, 1e6)
        self.spn_fast_start.setDecimals(3)
        self.spn_fast_start.setValue(0.0)

        self.spn_fast_end = QDoubleSpinBox()
        self.spn_fast_end.setRange(0.0, 1e6)
        self.spn_fast_end.setDecimals(3)
        self.spn_fast_end.setValue(0.0)
        self.spn_fast_datapoints.valueChanged.connect(self._refresh_eval_tables)
        self.spn_fast_repeats.valueChanged.connect(self._refresh_eval_tables)
        self.spn_fast_start.valueChanged.connect(self._refresh_eval_tables)
        self.spn_fast_end.valueChanged.connect(self._refresh_eval_tables)

        params_row = QHBoxLayout()
        params_row.addWidget(QLabel("Datapoints"))
        params_row.addWidget(self.spn_fast_datapoints)
        params_row.addSpacing(12)
        params_row.addWidget(QLabel("Repeats"))
        params_row.addWidget(self.spn_fast_repeats)
        params_row.addSpacing(12)
        params_row.addWidget(QLabel("Start"))
        params_row.addWidget(self.spn_fast_start)
        params_row.addSpacing(12)
        params_row.addWidget(QLabel("End"))
        params_row.addWidget(self.spn_fast_end)
        params_row.addStretch(1)
        root.addLayout(params_row)
        root.addSpacing(10)

        self.subtabs = QTabWidget()
        self.subtabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        root.addWidget(self.subtabs)

        self._build_fast_tab()
        self._build_vials_tab()
        self.subtabs.setMinimumHeight(self.subtabs.sizeHint().height())
        self._eval_sections.append(
            self._build_evaluation_section(root, context="Calibration", stretch=1)
        )
        self._refresh_eval_tables()

    def _card(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.StyledPanel)
        f.setObjectName("card")
        return f

    def _build_fast_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 2, 12, 12)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)
        layout.addSpacing(10)

        self.spn_fast_x = QDoubleSpinBox()
        self.spn_fast_x.setRange(-1e6, 1e6)
        self.spn_fast_x.setDecimals(3)
        self.spn_fast_x.setValue(10.0)
        self.spn_fast_x.setMinimumHeight(32)

        self.spn_fast_y = QDoubleSpinBox()
        self.spn_fast_y.setRange(-1e6, 1e6)
        self.spn_fast_y.setDecimals(3)
        self.spn_fast_y.setValue(185.0)
        self.spn_fast_y.setMinimumHeight(32)

        self.spn_fast_pause = QDoubleSpinBox()
        self.spn_fast_pause.setRange(0.0, 1e6)
        self.spn_fast_pause.setDecimals(3)
        self.spn_fast_pause.setValue(10.0)
        self.spn_fast_pause.setMinimumHeight(32)

        coord_row = QHBoxLayout()
        self.chk_fast_flush = QCheckBox("Initial flush (3×)")
        self.chk_fast_flush.setChecked(True)
        coord_row.addWidget(self.chk_fast_flush)
        coord_row.addSpacing(12)
        coord_row.addWidget(QLabel("X, mm"))
        coord_row.addWidget(self.spn_fast_x)
        coord_row.addSpacing(12)
        coord_row.addWidget(QLabel("Y, mm"))
        coord_row.addWidget(self.spn_fast_y)
        coord_row.addSpacing(12)
        coord_row.addWidget(QLabel("Pause, s"))
        coord_row.addWidget(self.spn_fast_pause)
        coord_row.addStretch(1)
        self.btn_fast_generate = QPushButton("Generate calibration G-code")
        self.btn_fast_generate.clicked.connect(self._on_generate_fast)
        coord_row.addWidget(self.btn_fast_generate)
        layout.addLayout(coord_row)

        self.subtabs.addTab(tab, "Same vial")

    def _build_vials_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 2, 12, 12)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)
        layout.addSpacing(10)

        self.chk_vials_flush = QCheckBox("Initial flush (3×)")
        self.chk_vials_flush.setChecked(True)
        self.chk_vials_non_contact = QCheckBox()
        self.chk_vials_non_contact.setChecked(True)
        lbl_non_contact = QLabel("Non-contact dispense (use Z<sub>slow</sub>)")
        lbl_non_contact.setTextFormat(Qt.RichText)

        opts = QHBoxLayout()
        opts.addWidget(self.chk_vials_flush)
        opts.addSpacing(24)
        opts.addWidget(self.chk_vials_non_contact)
        opts.addWidget(lbl_non_contact)
        opts.addStretch(1)
        self.btn_vials_generate = QPushButton("Generate calibration G-code")
        self.btn_vials_generate.clicked.connect(self._on_generate_vials)
        opts.addWidget(self.btn_vials_generate)
        layout.addLayout(opts)

        self.subtabs.addTab(tab, "Different vials")

    def _build_evaluation_section(
        self,
        layout: QVBoxLayout,
        *,
        context: str,
        stretch: int = 0,
    ) -> _EvaluationWidgets:
        card = self._card()
        layout.addWidget(card, stretch)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        head = QLabel("Calibration evaluation")
        head.setFont(QFont("Segoe UI", 11, QFont.Bold))
        card_layout.addWidget(head)

        note = QLabel("Enter measured mass per dispense in g. You can use subtraction like 0.3480-0.2070.")
        note.setWordWrap(True)
        card_layout.addWidget(note)

        table = QTableWidget()
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.verticalHeader().setDefaultSectionSize(28)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table.setItemDelegate(_MassPlaceholderDelegate(self, table))
        card_layout.addWidget(table, 1)

        outputs = QHBoxLayout()
        lbl_cf_new = QLabel("CF<sub>new</sub> (mm/uL) = —")
        lbl_bc_new = QLabel("BC<sub>new</sub> (mm) = —")
        lbl_cf_new.setTextFormat(Qt.RichText)
        lbl_bc_new.setTextFormat(Qt.RichText)
        lbl_error = QLabel("Error (mean abs %) = —")
        outputs.addWidget(lbl_cf_new)
        outputs.addSpacing(12)
        outputs.addWidget(lbl_bc_new)
        outputs.addSpacing(12)
        outputs.addWidget(lbl_error)
        outputs.addStretch(1)

        btn_apply = QPushButton("Apply calibration")
        btn_apply.clicked.connect(
            lambda: self._apply_calibration_to_link(context, lbl_cf_new, lbl_bc_new)
        )
        outputs.addWidget(btn_apply)

        btn_clear = QPushButton("Clear table")
        btn_clear.clicked.connect(lambda: self._clear_eval_table(table))
        outputs.addWidget(btn_clear)

        btn_calc = QPushButton("Evaluate calibration")
        btn_calc.clicked.connect(
            lambda: self._evaluate_calibration(table, context, lbl_cf_new, lbl_bc_new, lbl_error)
        )
        outputs.addWidget(btn_calc)

        card_layout.addLayout(outputs)

        return _EvaluationWidgets(context=context, table=table, lbl_cf_new=lbl_cf_new, lbl_bc_new=lbl_bc_new, lbl_error=lbl_error)

    # ---------------- Calibration evaluation ----------------

    def _refresh_eval_tables(self, *_: object) -> None:
        if not self._eval_sections:
            return

        datapoints = int(self.spn_fast_datapoints.value())
        repeats = int(self.spn_fast_repeats.value())
        if datapoints < 1 or repeats < 1:
            return

        start_ul = float(self.spn_fast_start.value())
        end_ul = float(self.spn_fast_end.value())
        if datapoints == 1:
            volumes = np.array([start_ul], dtype=float)
        else:
            volumes = np.linspace(start_ul, end_ul, num=datapoints)
        self._eval_volumes = [float(v) for v in volumes]

        row_labels = [f"{v:.2f} uL" for v in volumes]
        col_labels = [f"Rep {i + 1}" for i in range(repeats)]

        for section in self._eval_sections:
            table = section.table
            table.blockSignals(True)
            table.setUpdatesEnabled(False)
            table.setRowCount(datapoints)
            table.setColumnCount(repeats)
            table.setHorizontalHeaderLabels(col_labels)
            table.setVerticalHeaderLabels(row_labels)
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)
            header.setStretchLastSection(True)
            for row in range(datapoints):
                for col in range(repeats):
                    item = table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem("")
                        item.setTextAlignment(Qt.AlignCenter)
                        table.setItem(row, col, item)
            header.resizeSections(QHeaderView.Stretch)
            table.setUpdatesEnabled(True)
            table.blockSignals(False)
            table.viewport().update()

    def _clear_eval_table(self, table: QTableWidget) -> None:
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row, col, item)
                else:
                    item.setText("")
        table.viewport().update()

    def _refresh_eval_placeholders(self) -> None:
        for section in self._eval_sections:
            section.table.viewport().update()

    def _placeholder_mass_text(self, row: int) -> str:
        if row < 0 or row >= len(self._eval_volumes):
            return ""
        if self._current_density is None:
            return ""
        rho = self._current_density
        if rho <= 0:
            return ""
        mass_g = (self._eval_volumes[row] * rho) / 1000.0
        return f"{mass_g:.4f}"

    def _parse_mass_value(self, text: str) -> float:
        value = text.strip().replace("−", "-")
        if not value:
            raise ValueError("Mass value is empty.")
        try:
            return float(value)
        except ValueError:
            match = self._MASS_SUB_RE.match(value)
            if not match:
                raise ValueError(f"Invalid mass value '{text}'. Use a number or 'A-B'.")
            return float(match.group(1)) - float(match.group(2))

    def _read_mass_table(self, table: QTableWidget, datapoints: int, repeats: int) -> np.ndarray:
        masses = np.zeros((datapoints, repeats), dtype=float)
        for row in range(datapoints):
            for col in range(repeats):
                item = table.item(row, col)
                text = "" if item is None else item.text()
                if not text.strip():
                    raise ValueError(f"Missing mass value at row {row + 1}, column {col + 1}.")
                value = self._parse_mass_value(text)
                if value <= 0:
                    raise ValueError(f"Mass must be > 0 at row {row + 1}, column {col + 1}.")
                masses[row, col] = value
        return masses

    def _se_floor_ul(
        self,
        *,
        delta_m_g: float,
        rho_g_per_ml: float,
        n_reps: int,
        sigma_rep_g: float | None = None,
        use_quant_sd: bool = True,
    ) -> float:
        sigma_q = (delta_m_g / np.sqrt(12.0)) if use_quant_sd else delta_m_g
        if sigma_rep_g is not None:
            sigma_m = np.sqrt(sigma_rep_g ** 2 + sigma_q ** 2)
        else:
            sigma_m = sigma_q
        sigma_dm = np.sqrt(2.0) * sigma_m
        sigma_v_ul = (sigma_dm / rho_g_per_ml) * 1000.0
        return sigma_v_ul / np.sqrt(n_reps)

    def _evaluate_calibration(
        self,
        table: QTableWidget,
        context: str,
        lbl_cf_new: QLabel,
        lbl_bc_new: QLabel,
        lbl_error: QLabel,
    ) -> None:
        try:
            self._selected_syringe_id()
            solvent_id = self._selected_solvent_id()

            cf_current = self._current_cf
            bc_current = self._current_bc
            if cf_current is None:
                raise ValueError("CF_current is not available. Select a syringe and solvent.")
            if bc_current is None:
                raise ValueError(
                    "BC_current is not available for this syringe/solvent. Create a link in the DB tab."
                )

            solvent = Solvent.get_by_id(solvent_id)
            if solvent is None:
                raise ValueError(f"No solvent with id={solvent_id} found in DB.")
            if solvent.density_g_per_ml is None:
                raise ValueError("Selected solvent has no density (g/ml) set in the DB.")
            rho = float(solvent.density_g_per_ml)
            if rho <= 0:
                raise ValueError("Solvent density must be > 0.")

            datapoints = int(self.spn_fast_datapoints.value())
            repeats = int(self.spn_fast_repeats.value())
            if datapoints < 2:
                raise ValueError("Calibration evaluation needs at least 2 datapoints.")
            if repeats < 1:
                raise ValueError("Repeats must be >= 1.")

            start_ul = float(self.spn_fast_start.value())
            end_ul = float(self.spn_fast_end.value())
            if start_ul <= 0 or end_ul <= 0:
                raise ValueError("Start and end volumes must be > 0 for evaluation.")
            volumes = np.linspace(start_ul, end_ul, num=datapoints)
            if np.any(volumes <= 0):
                raise ValueError("All set volumes must be > 0.")

            masses_g = self._read_mass_table(table, datapoints, repeats)
            v_rep_ul = (masses_g / rho) * 1000.0
            mean_ul = v_rep_ul.mean(axis=1)
            if repeats > 1:
                sd_ul = v_rep_ul.std(axis=1, ddof=1)
            else:
                sd_ul = np.zeros(datapoints, dtype=float)
            se_ul = sd_ul / np.sqrt(repeats)

            eps_ul = self._se_floor_ul(delta_m_g=1e-4, rho_g_per_ml=rho, n_reps=repeats)
            weights = 1.0 / np.clip(se_ul, eps_ul, None)

            a2, b2 = np.polyfit(volumes, mean_ul, deg=1, w=weights)
            if a2 == 0:
                raise ValueError("Calibration fit failed (slope is zero). Check the input masses.")

            cf_new = cf_current / a2
            bc_new = bc_current - b2 * cf_new

            error_pct = np.abs(mean_ul - volumes) / volumes * 100.0
            mean_error = float(np.mean(error_pct))

            lbl_cf_new.setText(f"CF<sub>new</sub> (mm/uL) = {cf_new:.6f}")
            lbl_bc_new.setText(f"BC<sub>new</sub> (mm) = {bc_new:.6f}")
            lbl_error.setText(f"Error (mean abs %) = {mean_error:.2f}")

            self._log_eval_errors(context, volumes, mean_ul, error_pct)

        except Exception as e:
            QMessageBox.critical(self, "Calibration evaluation error", str(e))

    def _log_eval_errors(self, context: str, volumes: np.ndarray, mean_ul: np.ndarray, error_pct: np.ndarray) -> None:
        self._log_to_gcode(f"[CAL] {context}: per-volume errors (%)")
        for v_set, mean_val, err in zip(volumes, mean_ul, error_pct):
            self._log_to_gcode(
                f"[CAL] {context}: V_set={v_set:.2f} uL, mean={mean_val:.2f} uL, error={err:.2f}%"
            )

    def _apply_calibration_to_link(self, context: str, lbl_cf_new: QLabel, lbl_bc_new: QLabel) -> None:
        try:
            s_id = self._selected_syringe_id()
            solvent_id = self._selected_solvent_id()

            cf_text = lbl_cf_new.text().split("=", 1)[-1].strip()
            bc_text = lbl_bc_new.text().split("=", 1)[-1].strip()
            if cf_text == "—" or bc_text == "—":
                raise ValueError("Run evaluation first to compute CF_new and BC_new.")

            try:
                cf_new = float(cf_text)
                bc_new = float(bc_text)
            except ValueError as e:
                raise ValueError("CF_new/BC_new are not numeric. Re-run evaluation.") from e

            SyringeSolventLink.set_calibration(
                syringe_id=int(s_id),
                solvent_id=int(solvent_id),
                real_correlation_factor=cf_new,
                backlash_correction=bc_new,
            )

            self._log_to_gcode(
                f"[CAL] {context}: applied CF_new={cf_new:.6f} mm/uL, BC_new={bc_new:.6f} mm to link"
            )
            self._update_calibration_factors()
            QMessageBox.information(self, "Calibration applied", "Syringe-solvent link updated.")
        except Exception as e:
            QMessageBox.critical(self, "Apply calibration error", str(e))

    def _log_to_gcode(self, msg: str) -> None:
        parent = self.parent()
        gcode_tab = getattr(parent, "gcode_tab", None)
        if gcode_tab is not None and hasattr(gcode_tab, "_log"):
            try:
                gcode_tab._log(msg)
            except Exception:
                pass

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

        self.cmb_rack.clear()
        self.cmb_machine.clear()
        self.cmb_rack.addItem("— select —", None)
        self.cmb_machine.addItem("— select —", None)
        for name in self._rack_names:
            self.cmb_rack.addItem(name, name)
        for name in self._machine_names:
            self.cmb_machine.addItem(name, name)

        if self._rack_names:
            self.cmb_rack.setCurrentIndex(1)
        if self._machine_names:
            default_machine = "current" if "current" in self._machine_names else self._machine_names[0]
            idx = self.cmb_machine.findData(default_machine)
            if idx >= 0:
                self.cmb_machine.setCurrentIndex(idx)

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
        self._update_calibration_factors()

    def refresh_syringe_list(self) -> None:
        self._load_syringe_list()

    def set_selected_syringe_id(self, syringe_id: int | None) -> None:
        if syringe_id is None:
            return
        idx = self.cmb_syringe.findData(int(syringe_id))
        if idx >= 0:
            self.cmb_syringe.setCurrentIndex(idx)

    # ---------------- Helpers ----------------

    def _selected_syringe_id(self) -> int:
        s_id = self.cmb_syringe.currentData()
        if s_id is None:
            raise ValueError("Please select a syringe.")
        return int(s_id)

    def _selected_solvent_id(self) -> int:
        solvent_id = int(self.spn_solvent_id.value())
        if solvent_id <= 0:
            raise ValueError("Please enter a solvent id.")
        solvent = Solvent.get_by_id(solvent_id)
        if solvent is None:
            raise ValueError(f"No solvent with id={solvent_id} found in DB.")
        return solvent_id

    def _current_solvent_id(self) -> int | None:
        solvent_id = int(self.spn_solvent_id.value())
        if solvent_id <= 0:
            return None
        return solvent_id

    def _default_machine_name(self) -> str:
        if not self._machine_names:
            raise ValueError("No machine configs found under config/machines.")
        selected = self.cmb_machine.currentData() if hasattr(self, "cmb_machine") else None
        if selected is not None:
            return str(selected)
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
        has_solvent = self._current_solvent_id() is not None
        enabled = has_syringe and has_solvent
        self.btn_fast_generate.setEnabled(enabled)
        self.btn_vials_generate.setEnabled(enabled)

    def _format_value(self, value: float | None, decimals: int = 3) -> str:
        if value is None:
            return "—"
        return f"{value:.{decimals}f}"

    def _set_cf_bc_labels(self, cf_value: float | None, bc_value: float | None) -> None:
        cf_text = self._format_value(cf_value)
        bc_text = self._format_value(bc_value)
        self.lbl_cf_current.setText(f"CF<sub>current</sub> = {cf_text}")
        self.lbl_bc_current.setText(f"BC<sub>current</sub> = {bc_text}")

    def _update_calibration_factors(self) -> None:
        s_id = self.cmb_syringe.currentData()
        if s_id is None:
            self._current_cf = None
            self._current_bc = None
            self._current_density = None
            self._set_cf_bc_labels(None, None)
            self._refresh_eval_placeholders()
            return

        try:
            syringe = Syringe.get_by_id(int(s_id))
        except Exception:
            syringe = None

        solvent_id = self._current_solvent_id()
        self._current_density = None
        if solvent_id is not None:
            try:
                solvent = Solvent.get_by_id(int(solvent_id))
                if solvent is not None and solvent.density_g_per_ml is not None:
                    self._current_density = float(solvent.density_g_per_ml)
            except Exception:
                self._current_density = None

        link = None
        if solvent_id is not None:
            try:
                with get_session() as session:
                    link = session.get(SyringeSolventLink, (int(s_id), int(solvent_id)))
            except Exception:
                link = None

        cf_value = None
        bc_value = None
        if syringe is not None:
            if link is not None:
                if link.real_correlation_factor is not None:
                    cf_value = float(link.real_correlation_factor)
                else:
                    try:
                        cf_value = float(syringe.theoretical_correlation_factor)
                    except Exception:
                        cf_value = None

            if link is not None:
                try:
                    bc_value = float(link.backlash_correction)
                except Exception:
                    bc_value = None

            try:
                nominal = float(syringe.nominal_volume_ul)
            except Exception:
                nominal = None
            if nominal is not None:
                self.spn_fast_start.setValue(0.1 * nominal)
                self.spn_fast_end.setValue(nominal)

        self._current_cf = cf_value
        self._current_bc = bc_value
        self._set_cf_bc_labels(cf_value, bc_value)
        self._refresh_eval_tables()
        self._refresh_eval_placeholders()

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
            rack_name = self._selected_rack_name(self.cmb_rack)
            x = float(self.spn_fast_x.value())
            y = float(self.spn_fast_y.value())
            pause_ms = int(round(float(self.spn_fast_pause.value()) * 1000.0))
            initial_flush = self.chk_fast_flush.isChecked()
            datapoints = int(self.spn_fast_datapoints.value())
            repeats = int(self.spn_fast_repeats.value())
            start_ul = float(self.spn_fast_start.value())
            end_ul = float(self.spn_fast_end.value())

            out_path = self._pick_gcode_path("calibration_fast.gcode")
            if out_path is None:
                return
            out_path.parent.mkdir(parents=True, exist_ok=True)

            solvent_id = self._selected_solvent_id()

            with self._build_pipet(out_path, rack_name) as pg:
                pg.home()

                if initial_flush:
                    flush_vol = pg.max_volume_ul
                    pg.flush(flush_vol, repeats=3, solvent_idx=0, solvent_id=solvent_id)

                max_ul = float(pg.max_volume_ul)
                if start_ul < 0 or end_ul < 0:
                    raise ValueError("Start and end volumes must be >= 0.")
                if start_ul > max_ul or end_ul > max_ul:
                    raise ValueError("Start/end volumes exceed syringe max volume.")
                if datapoints < 1:
                    raise ValueError("Datapoints must be >= 1.")
                if repeats < 1:
                    raise ValueError("Repeats must be >= 1.")
                volumes = [float(v) for v in np.linspace(start_ul, end_ul, num=datapoints)]

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
            rack_name = self._selected_rack_name(self.cmb_rack, require=True)
            initial_flush = self.chk_vials_flush.isChecked()
            non_contact = self.chk_vials_non_contact.isChecked()
            datapoints = int(self.spn_fast_datapoints.value())
            repeats = int(self.spn_fast_repeats.value())
            start_ul = float(self.spn_fast_start.value())
            end_ul = float(self.spn_fast_end.value())

            out_path = self._pick_gcode_path("calibration_vials.gcode")
            if out_path is None:
                return
            out_path.parent.mkdir(parents=True, exist_ok=True)

            solvent_id = self._selected_solvent_id()

            with self._build_pipet(out_path, rack_name) as pg:
                pg.home()

                if initial_flush:
                    flush_vol = pg.max_volume_ul
                    pg.flush(flush_vol, repeats=3, solvent_idx=0, solvent_id=solvent_id)

                max_ul = float(pg.max_volume_ul)
                if start_ul < 0 or end_ul < 0:
                    raise ValueError("Start and end volumes must be >= 0.")
                if start_ul > max_ul or end_ul > max_ul:
                    raise ValueError("Start/end volumes exceed syringe max volume.")
                if datapoints < 1:
                    raise ValueError("Datapoints must be >= 1.")
                if repeats < 1:
                    raise ValueError("Repeats must be >= 1.")
                volumes = [float(v) for v in np.linspace(start_ul, end_ul, num=datapoints)]
                vial_positions = pg.vial_positions
                z_min_vials = pg.z_min_vials

                total_needed = len(volumes) * repeats
                if total_needed > len(vial_positions):
                    raise ValueError(
                        f"Not enough vial slots: need {total_needed}, "
                        f"rack provides {len(vial_positions)}."
                    )

                sx, sy = pg.solvent_positions[0]
                z_min_solvent = pg.z_min_solvents[0]
                current_vial = 0
                for volume in volumes:
                    for _ in range(repeats):
                        pg.remove_from_vial(sx, sy, volume, solvent_id, z_min=z_min_solvent)

                        x, y = vial_positions[current_vial]
                        z_min = z_min_vials[current_vial]
                        pg.fill_vial(x, y, slow=non_contact, z_min=z_min)
                        current_vial += 1

                pg.finish()

            QMessageBox.information(self, "Success", f"G-code written to:\n{out_path}")

        except Exception as e:
            QMessageBox.critical(self, "Calibration error", str(e))
