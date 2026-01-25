from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..config_io import load_model
from ..InputXlsx import InputXlsx
from ..Machine import Machine
from ..PipetG import PipetG
from ..Rack import Rack
from ..Setup import Setup
from ..Solvent import Solvent
from ..Syringe import Syringe


class GCodeTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._base_dir = Path(__file__).resolve().parent.parent
        self._config_dir = self._base_dir.parent / "config"
        self._racks_dir = self._config_dir / "racks"
        self._machines_dir = self._config_dir / "machines"
        self._setups_dir = self._config_dir / "setups_for_gui"

        self._rack_defs: dict[str, Rack] = {}
        self._machine_names: list[str] = []
        self._rack_actions: dict[str, QAction] = {}
        self._setup_defs: dict[str, dict] = {}

        self._build_ui()
        self._load_config_lists()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        # LEFT: setup
        left = QVBoxLayout()
        left.setSpacing(12)
        root.addLayout(left, 1)

        title = QLabel("Setup")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        left.addWidget(title)

        setup_card = self._card()
        left.addWidget(setup_card)

        form = QFormLayout(setup_card)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.cmb_setup = QComboBox()
        self.cmb_setup.currentIndexChanged.connect(self._on_setup_selected)
        form.addRow("Setup", self.cmb_setup)

        self.cmb_syringe = QComboBox()
        form.addRow("Syringe", self.cmb_syringe)

        self.cmb_machine = QComboBox()
        form.addRow("Machine", self.cmb_machine)

        racks_row = QWidget()
        racks_row_l = QVBoxLayout(racks_row)
        racks_row_l.setContentsMargins(0, 0, 0, 0)
        racks_row_l.setSpacing(6)

        top_rack_bar = QHBoxLayout()
        top_rack_bar.setContentsMargins(0, 0, 0, 0)
        top_rack_bar.setSpacing(8)

        self.btn_racks_menu = QToolButton()
        self.btn_racks_menu.setText("Select racks…")
        self.btn_racks_menu.setPopupMode(QToolButton.InstantPopup)
        self.racks_menu = QMenu(self)
        self.btn_racks_menu.setMenu(self.racks_menu)

        self.btn_racks_clear = QPushButton("Clear")
        self.btn_racks_clear.clicked.connect(self._clear_selected_racks)

        top_rack_bar.addWidget(self.btn_racks_menu, 1)
        top_rack_bar.addWidget(self.btn_racks_clear)
        racks_row_l.addLayout(top_rack_bar)

        self.lst_selected_racks = QListWidget()
        self.lst_selected_racks.setDragDropMode(QListWidget.InternalMove)
        self.lst_selected_racks.setDefaultDropAction(Qt.MoveAction)
        self.lst_selected_racks.setMinimumHeight(140)
        self.lst_selected_racks.model().rowsMoved.connect(lambda *_: self._update_setup_summary())
        racks_row_l.addWidget(self.lst_selected_racks)

        self.lbl_setup_summary = QLabel("No racks selected.")
        self.lbl_setup_summary.setWordWrap(True)
        racks_row_l.addWidget(self.lbl_setup_summary)

        form.addRow("Racks (order matters)", racks_row)

        # RIGHT: workflow
        right = QVBoxLayout()
        right.setSpacing(12)
        root.addLayout(right, 2)

        wtitle = QLabel("Workflow")
        wtitle.setFont(QFont("Segoe UI", 14, QFont.Bold))
        right.addWidget(wtitle)

        # Template card
        template_card = self._card()
        right.addWidget(template_card)

        tlay = QVBoxLayout(template_card)
        tlay.setContentsMargins(12, 12, 12, 12)
        tlay.setSpacing(10)

        t_head = QLabel("1) Create Excel template")
        t_head.setFont(QFont("Segoe UI", 11, QFont.Bold))
        tlay.addWidget(t_head)

        t_path_row = QHBoxLayout()
        self.edt_template_path = QLineEdit()
        self.edt_template_path.setPlaceholderText("Choose where to save the template .xlsx …")
        btn_browse_template = QPushButton("Save as…")
        btn_browse_template.clicked.connect(self._pick_template_path)
        t_path_row.addWidget(self.edt_template_path, 1)
        t_path_row.addWidget(btn_browse_template)
        tlay.addLayout(t_path_row)

        self.btn_create_template = QPushButton("Create template")
        self.btn_create_template.clicked.connect(self._on_create_template)
        tlay.addWidget(self.btn_create_template)

        # G-code card
        gcode_card = self._card()
        right.addWidget(gcode_card)

        glay = QVBoxLayout(gcode_card)
        glay.setContentsMargins(12, 12, 12, 12)
        glay.setSpacing(10)

        g_head = QLabel("2) Load Excel program → Generate G-code")
        g_head.setFont(QFont("Segoe UI", 11, QFont.Bold))
        glay.addWidget(g_head)

        prog_row = QHBoxLayout()
        self.edt_program_path = QLineEdit()
        self.edt_program_path.setPlaceholderText("Select an existing program .xlsx …")
        btn_open_prog = QPushButton("Open…")
        btn_open_prog.clicked.connect(self._pick_program_path)
        prog_row.addWidget(self.edt_program_path, 1)
        prog_row.addWidget(btn_open_prog)
        glay.addLayout(prog_row)

        out_row = QHBoxLayout()
        self.edt_gcode_path = QLineEdit()
        self.edt_gcode_path.setPlaceholderText("Select output .gcode path …")
        btn_save_gcode = QPushButton("Save as…")
        btn_save_gcode.clicked.connect(self._pick_gcode_path)
        out_row.addWidget(self.edt_gcode_path, 1)
        out_row.addWidget(btn_save_gcode)
        glay.addLayout(out_row)

        self.btn_generate_gcode = QPushButton("Generate G-code")
        self.btn_generate_gcode.clicked.connect(self._on_generate_gcode)
        glay.addWidget(self.btn_generate_gcode)

        # Log card
        log_card = self._card()
        right.addWidget(log_card, 1)

        llay = QVBoxLayout(log_card)
        llay.setContentsMargins(12, 12, 12, 12)
        llay.setSpacing(8)

        l_head = QLabel("Log")
        l_head.setFont(QFont("Segoe UI", 11, QFont.Bold))
        llay.addWidget(l_head)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        llay.addWidget(self.txt_log, 1)

    def _card(self) -> QFrame:
        """Returns a panel object called 'card' used for buttons and fields."""
        f = QFrame()
        f.setFrameShape(QFrame.StyledPanel)
        f.setObjectName("card")
        return f

    # ---------------- Config discovery ----------------

    def _load_config_lists(self) -> None:
        if not self._racks_dir.exists() or not self._machines_dir.exists():
            QMessageBox.critical(
                self,
                "Config folder missing",
                f"Expected config folders:\n\n{self._racks_dir}\n{self._machines_dir}\n\n"
                f"Make sure this GUI file is inside your Codes package next to 'config/'.",
            )
            return

        rack_names = sorted(p.stem for p in self._racks_dir.glob("*.json"))
        machine_names = sorted(p.stem for p in self._machines_dir.glob("*.json"))

        self._machine_names = machine_names
        self.cmb_machine.clear()
        self.cmb_machine.addItem("— select —")
        for m in machine_names:
            self.cmb_machine.addItem(m)

        self._rack_defs.clear()
        for name in rack_names:
            try:
                self._rack_defs[name] = load_model(Rack, name)
            except Exception as e:
                self._log(f"[WARN] Cannot load rack '{name}': {e!s}")

        self.racks_menu.clear()

        act_all = QAction("Select all", self)
        act_all.triggered.connect(lambda *_: self._set_all_racks_checked(True))
        self.racks_menu.addAction(act_all)

        act_none = QAction("Select none", self)
        act_none.triggered.connect(lambda *_: self._set_all_racks_checked(False))
        self.racks_menu.addAction(act_none)

        self.racks_menu.addSeparator()

        self._rack_actions.clear()
        for name in rack_names:
            act = QAction(name, self)
            act.setCheckable(True)
            act.toggled.connect(lambda checked, n=name: self._on_rack_toggled(n, checked))
            self.racks_menu.addAction(act)
            self._rack_actions[name] = act

        self._update_racks_button_text()
        self._load_syringe_list()
        self._load_setup_list()

    def _load_setup_list(self) -> None:
        self.cmb_setup.clear()
        self._setup_defs.clear()
        if not self._setups_dir.exists():
            self.cmb_setup.addItem("— no setups —", None)
            return

        setup_paths = sorted(self._setups_dir.glob("*.json"))
        if not setup_paths:
            self.cmb_setup.addItem("— no setups —", None)
            return

        self.cmb_setup.addItem("— select —", None)
        for path in setup_paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                self._log(f"[WARN] Cannot load setup '{path.name}': {e!s}")
                continue
            name = data.get("name", path.stem)
            self._setup_defs[name] = data
            self.cmb_setup.addItem(name, name)

    def _selected_setup(self) -> dict | None:
        key = self.cmb_setup.currentData()
        if key is None:
            return None
        return self._setup_defs.get(str(key))

    def _on_setup_selected(self, *_) -> None:
        data = self._selected_setup()
        if not data:
            return

        machine_name = data.get("machine")
        if machine_name:
            idx = self.cmb_machine.findText(machine_name)
            if idx >= 0:
                self.cmb_machine.setCurrentIndex(idx)

        s_id = data.get("syringe_id")
        if s_id is not None:
            idx = self.cmb_syringe.findData(int(s_id))
            if idx >= 0:
                self.cmb_syringe.setCurrentIndex(idx)

        rack_names = data.get("racks") or []
        self._set_selected_racks_in_order(rack_names)

    def _set_selected_racks_in_order(self, rack_names: list[str]) -> None:
        self.lst_selected_racks.clear()
        for act in self._rack_actions.values():
            act.blockSignals(True)
            act.setChecked(False)
            act.blockSignals(False)

        for name in rack_names:
            if name in self._rack_actions:
                self._rack_actions[name].blockSignals(True)
                self._rack_actions[name].setChecked(True)
                self._rack_actions[name].blockSignals(False)
                self._add_selected_rack(name)

        self._update_racks_button_text()
        self._update_setup_summary()

    def _load_syringe_list(self) -> None:
        self.cmb_syringe.clear()
        self.cmb_syringe.addItem("— select —", None)
        try:
            syringes = Syringe.get_all()
        except Exception as e:
            self._log(f"[WARN] Cannot load syringes from DB: {e!s}")
            return

        for s in syringes:
            if s.id is None:
                continue
            label = f"{s.id} - {s.name}"
            self.cmb_syringe.addItem(label, int(s.id))

    def refresh_syringe_list(self) -> None:
        self._load_syringe_list()

    def _selected_syringe_id(self) -> int:
        s_id = self.cmb_syringe.currentData()
        if s_id is None:
            raise ValueError("Please select a syringe.")
        return int(s_id)

    def _set_all_racks_checked(self, checked: bool) -> None:
        for act in self._rack_actions.values():
            act.blockSignals(True)
            act.setChecked(checked)
            act.blockSignals(False)

        self.lst_selected_racks.clear()
        if checked:
            for name in self._rack_actions.keys():
                self._add_selected_rack(name)

        self._update_racks_button_text()
        self._update_setup_summary()

    def _on_rack_toggled(self, rack_name: str, checked: bool) -> None:
        if checked:
            self._add_selected_rack(rack_name)
        else:
            self._remove_selected_rack(rack_name)
        self._update_racks_button_text()
        self._update_setup_summary()

    def _add_selected_rack(self, rack_name: str) -> None:
        for i in range(self.lst_selected_racks.count()):
            if self.lst_selected_racks.item(i).text() == rack_name:
                return
        self.lst_selected_racks.addItem(rack_name)

    def _remove_selected_rack(self, rack_name: str) -> None:
        for i in range(self.lst_selected_racks.count()):
            if self.lst_selected_racks.item(i).text() == rack_name:
                self.lst_selected_racks.takeItem(i)
                return

    def _clear_selected_racks(self, *_) -> None:
        self.lst_selected_racks.clear()
        for act in self._rack_actions.values():
            act.blockSignals(True)
            act.setChecked(False)
            act.blockSignals(False)
        self._update_racks_button_text()
        self._update_setup_summary()

    def _update_racks_button_text(self) -> None:
        n = self.lst_selected_racks.count()
        self.btn_racks_menu.setText(f"Select racks…  ({n} selected)")

    def _selected_rack_names_in_order(self) -> list[str]:
        return [self.lst_selected_racks.item(i).text() for i in range(self.lst_selected_racks.count())]

    def _update_setup_summary(self, *_) -> None:
        names = self._selected_rack_names_in_order()
        if not names:
            self.lbl_setup_summary.setText("No racks selected.")
            return

        total_vials = 0
        total_solvents = 0
        missing = []

        for n in names:
            r = self._rack_defs.get(n)
            if r is None:
                try:
                    r = load_model(Rack, n)
                    self._rack_defs[n] = r
                except Exception:
                    missing.append(n)
                    continue
            total_vials += int(r.vial_rows) * int(r.vial_columns)
            total_solvents += int(r.solvent_rows) * int(r.solvent_columns)

        msg = (
            f"Selected racks (in order): {', '.join(names)}\n"
            f"Total vial slots: {total_vials} | Total solvent slots: {total_solvents}"
        )
        if missing:
            msg += f"\nMissing/failed racks: {', '.join(missing)}"
        self.lbl_setup_summary.setText(msg)

    # ---------------- File pickers ----------------

    def _pick_template_path(self, *_) -> None:
        csv_dir = self._base_dir.parent / "csv"
        start_dir = str(csv_dir if csv_dir.is_dir() else self._base_dir)
        path, _ = QFileDialog.getSaveFileName(self, "Save Excel template", start_dir, "Excel files (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        self.edt_template_path.setText(str(Path(path)))

    def _pick_program_path(self, *_) -> None:
        csv_dir = self._base_dir.parent / "csv"
        start_dir = str(csv_dir if csv_dir.is_dir() else self._base_dir)
        path, _ = QFileDialog.getOpenFileName(self, "Open Excel program", start_dir, "Excel files (*.xlsx)")
        if not path:
            return
        self.edt_program_path.setText(str(Path(path)))
        suggested = str(Path(path).with_suffix(".gcode"))
        self.edt_gcode_path.setText(suggested)

    def _pick_gcode_path(self, *_) -> None:
        gcode_dir = self._base_dir.parent / "G-codes"
        start_dir = str(gcode_dir if gcode_dir.is_dir() else self._base_dir)
        path, _ = QFileDialog.getSaveFileName(self, "Save G-code", start_dir, "G-code files (*.gcode)")
        if not path:
            return
        if not path.lower().endswith(".gcode"):
            path += ".gcode"
        self.edt_gcode_path.setText(str(Path(path)))

    # ---------------- Core: build Setup/Pipet ----------------

    def _build_setup(self) -> Setup:
        machine_name = self.cmb_machine.currentText()
        if machine_name == "— select —":
            raise ValueError("Please select a machine.")

        rack_names = self._selected_rack_names_in_order()
        if not rack_names:
            raise ValueError("Please select at least one rack.")

        machine = load_model(Machine, machine_name)
        racks = [load_model(Rack, rn) for rn in rack_names]

        s_id = self._selected_syringe_id()
        syringe = Syringe.get_by_id(s_id)
        if syringe is None:
            raise ValueError(f"No syringe with id={s_id} found in DB.")

        solvents = Solvent.get_all()
        if not solvents:
            raise ValueError("No solvents found in DB. Populate your Solvent table first.")

        setup_name = "GUI"
        data = self._selected_setup()
        if data and data.get("name"):
            setup_name = str(data["name"])
        setup_data = {
            "name": setup_name,
            "syringes": [syringe],
            "solvents": solvents,
            "racks": racks,
            "machine": machine,
        }
        return Setup.model_validate(setup_data)

    def _build_pipet(self, outfile: Path) -> PipetG:
        setup = self._build_setup()
        s_id = self._selected_syringe_id()
        return PipetG(outfile=outfile, setup=setup, syringe_id=s_id)

    # ---------------- Actions ----------------

    def _on_create_template(self, *_) -> None:
        try:
            out = self.edt_template_path.text().strip()
            if not out:
                self._pick_template_path()
                out = self.edt_template_path.text().strip()
                if not out:
                    return

            out_path = Path(out)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            dummy_gcode = (out_path.parent / "_dummy.gcode").resolve()
            pg = self._build_pipet(dummy_gcode)

            ix = InputXlsx(pipet=pg)
            ix.create_empty_table(out_path)

            self.edt_program_path.setText(str(out_path))
            self.edt_gcode_path.setText(str(out_path.with_suffix(".gcode")))
            self._log(f"[OK] Template written: {out_path}")
            QMessageBox.information(self, "Done", f"Excel template saved:\n{out_path}")

        except Exception as e:
            self._log(f"[ERR] Template creation failed: {e!s}")
            QMessageBox.critical(self, "Error", str(e))

    def _on_generate_gcode(self, *_) -> None:
        try:
            xlsx = self.edt_program_path.text().strip()
            if not xlsx:
                self._pick_program_path()
                xlsx = self.edt_program_path.text().strip()
                if not xlsx:
                    return

            out = self.edt_gcode_path.text().strip()
            if not out:
                suggested = str(Path(xlsx).with_suffix(".gcode"))
                self.edt_gcode_path.setText(suggested)
                out = suggested

            xlsx_path = Path(xlsx)
            if not xlsx_path.exists():
                raise ValueError(f"Excel program not found:\n{xlsx_path}")

            out_path = Path(out)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            pg = self._build_pipet(out_path)
            ix = InputXlsx(pipet=pg).load(xlsx_path)

            ix.generate_gcode()

            self._log(f"[OK] G-code written: {out_path}")
            QMessageBox.information(self, "Done", f"G-code saved:\n{out_path}")

        except Exception as e:
            self._log(f"[ERR] G-code generation failed: {e!s}")
            QMessageBox.critical(self, "Error", str(e))

    # ---------------- Helpers ----------------

    def _log(self, msg: str) -> None:
        self.txt_log.append(msg)
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())
