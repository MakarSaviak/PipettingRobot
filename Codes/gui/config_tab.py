from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..config_io import delete_model, load_model, save_model
from ..Machine import Machine
from ..Rack import Rack
from ..Syringe import Syringe


class ConfigTab(QWidget):
    NEW_ITEM = "__new__"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._base_dir = Path(__file__).resolve().parent.parent
        self._config_dir = self._base_dir.parent / "config"
        self._setups_dir = self._config_dir / "setups_for_gui"
        self._machines_dir = self._config_dir / "machines"
        self._racks_dir = self._config_dir / "racks"

        self._setup_paths: dict[str, Path] = {}
        self._machine_paths: dict[str, Path] = {}
        self._rack_paths: dict[str, Path] = {}
        self._machine_names: list[str] = []
        self._rack_names: list[str] = []
        self._setup_rack_actions: dict[str, QAction] = {}
        self._setup_rack_defs: dict[str, Rack] = {}

        self._loading_setup = False
        self._loading_machine = False
        self._loading_rack = False

        self._build_ui()
        self._load_syringe_list()
        self._reload_all_lists()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Configuration")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        root.addWidget(title)

        self.subtabs = QTabWidget()
        root.addWidget(self.subtabs, 1)

        self._build_setup_tab()
        self._build_machine_tab()
        self._build_rack_tab()

    def _card(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.StyledPanel)
        f.setObjectName("card")
        return f

    def _row_fields(self, *pairs: tuple[str, QWidget]) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        for label, widget in pairs:
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)
        layout.addStretch(1)
        return row

    def _build_setup_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        select_row = QHBoxLayout()
        select_row.addWidget(QLabel("Setup"))
        self.cmb_setup_select = QComboBox()
        self.cmb_setup_select.currentIndexChanged.connect(self._on_setup_selected)
        select_row.addWidget(self.cmb_setup_select, 1)
        self.btn_setup_add = QPushButton("Add")
        self.btn_setup_add.clicked.connect(self._start_new_setup)
        select_row.addWidget(self.btn_setup_add)
        select_row.addStretch(1)
        layout.addLayout(select_row)

        card = self._card()
        form = QFormLayout(card)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.edt_setup_name = QLineEdit()
        form.addRow("Name", self.edt_setup_name)

        self.cmb_setup_syringe = QComboBox()
        form.addRow("Syringe", self.cmb_setup_syringe)

        self.cmb_setup_machine = QComboBox()
        form.addRow("Machine", self.cmb_setup_machine)

        racks_row = QWidget()
        racks_row_layout = QVBoxLayout(racks_row)
        racks_row_layout.setContentsMargins(0, 0, 0, 0)
        racks_row_layout.setSpacing(6)

        top_rack_bar = QHBoxLayout()
        top_rack_bar.setContentsMargins(0, 0, 0, 0)
        top_rack_bar.setSpacing(8)

        self.btn_setup_racks_menu = QToolButton()
        self.btn_setup_racks_menu.setText("Select racks…")
        self.btn_setup_racks_menu.setPopupMode(QToolButton.InstantPopup)
        self.setup_racks_menu = QMenu(self)
        self.btn_setup_racks_menu.setMenu(self.setup_racks_menu)

        self.btn_setup_racks_clear = QPushButton("Clear")
        self.btn_setup_racks_clear.clicked.connect(self._clear_setup_racks)

        top_rack_bar.addWidget(self.btn_setup_racks_menu, 1)
        top_rack_bar.addWidget(self.btn_setup_racks_clear)
        racks_row_layout.addLayout(top_rack_bar)

        self.lst_setup_racks = QListWidget()
        self.lst_setup_racks.setDragDropMode(QListWidget.InternalMove)
        self.lst_setup_racks.setDefaultDropAction(Qt.MoveAction)
        self.lst_setup_racks.setMinimumHeight(140)
        self.lst_setup_racks.model().rowsMoved.connect(lambda *_: self._update_setup_summary())
        racks_row_layout.addWidget(self.lst_setup_racks)

        self.lbl_setup_summary = QLabel("No racks selected.")
        self.lbl_setup_summary.setWordWrap(True)
        racks_row_layout.addWidget(self.lbl_setup_summary)

        form.addRow("Racks (order matters)", racks_row)

        layout.addWidget(card)

        buttons = QHBoxLayout()
        self.btn_setup_save = QPushButton("Save")
        self.btn_setup_save.clicked.connect(self._save_setup)
        self.btn_setup_rollback = QPushButton("Rollback")
        self.btn_setup_rollback.clicked.connect(self._rollback_setup)
        self.btn_setup_delete = QPushButton("Delete")
        self.btn_setup_delete.clicked.connect(self._delete_setup)
        buttons.addWidget(self.btn_setup_save)
        buttons.addWidget(self.btn_setup_rollback)
        buttons.addWidget(self.btn_setup_delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.subtabs.addTab(tab, "Setup")

    def _build_machine_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        select_row = QHBoxLayout()
        select_row.addWidget(QLabel("Machine"))
        self.cmb_machine_select = QComboBox()
        self.cmb_machine_select.currentIndexChanged.connect(self._on_machine_selected)
        select_row.addWidget(self.cmb_machine_select, 1)
        self.btn_machine_add = QPushButton("Add")
        self.btn_machine_add.clicked.connect(self._start_new_machine)
        select_row.addWidget(self.btn_machine_add)
        select_row.addStretch(1)
        layout.addLayout(select_row)

        card = self._card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        self.edt_machine_name = QLineEdit()

        self.spn_z_min_limit = self._float_box(minimum=-1e6, maximum=1e6)
        self.spn_z_max_limit = self._float_box(minimum=-1e6, maximum=1e6)
        self.spn_z_min = self._float_box(minimum=-1e6, maximum=1e6)
        self.spn_z_max = self._float_box(minimum=-1e6, maximum=1e6)
        self.spn_z_slow = self._float_box(minimum=-1e6, maximum=1e6)

        self.spn_fz = self._float_box(minimum=0.0, maximum=1e6, decimals=3)
        self.spn_fxy = self._float_box(minimum=0.0, maximum=1e6, decimals=3)
        self.spn_fa_push = self._float_box(minimum=0.0, maximum=1e6, decimals=3)
        self.spn_fa_push_slow = self._float_box(minimum=0.0, maximum=1e6, decimals=3)
        self.spn_fa_pull = self._float_box(minimum=0.0, maximum=1e6, decimals=3)
        self.spn_rest_x = self._float_box(minimum=0.0, maximum=1e6, decimals=3)
        self.spn_rest_y = self._float_box(minimum=0.0, maximum=1e6, decimals=3)

        card_layout.addWidget(self._row_fields(("Name", self.edt_machine_name)))
        card_layout.addWidget(
            self._row_fields(
                ("z_min_limit", self.spn_z_min_limit),
                ("z_min", self.spn_z_min),
                ("z_max", self.spn_z_max),
                ("z_max_limit", self.spn_z_max_limit),
            )
        )
        card_layout.addWidget(self._row_fields(("z_slow", self.spn_z_slow)))
        card_layout.addWidget(
            self._row_fields(
                ("Fz", self.spn_fz),
                ("Fxy", self.spn_fxy),
                ("Fa_push", self.spn_fa_push),
                ("Fa_push_slow", self.spn_fa_push_slow),
                ("Fa_pull", self.spn_fa_pull),
            )
        )
        card_layout.addWidget(self._row_fields(("rest_x", self.spn_rest_x), ("rest_y", self.spn_rest_y)))

        layout.addWidget(card)

        buttons = QHBoxLayout()
        self.btn_machine_save = QPushButton("Save")
        self.btn_machine_save.clicked.connect(self._save_machine)
        self.btn_machine_rollback = QPushButton("Rollback")
        self.btn_machine_rollback.clicked.connect(self._rollback_machine)
        self.btn_machine_delete = QPushButton("Delete")
        self.btn_machine_delete.clicked.connect(self._delete_machine)
        buttons.addWidget(self.btn_machine_save)
        buttons.addWidget(self.btn_machine_rollback)
        buttons.addWidget(self.btn_machine_delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.subtabs.addTab(tab, "Machine")

    def _build_rack_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        select_row = QHBoxLayout()
        select_row.addWidget(QLabel("Rack"))
        self.cmb_rack_select = QComboBox()
        self.cmb_rack_select.currentIndexChanged.connect(self._on_rack_selected)
        select_row.addWidget(self.cmb_rack_select, 1)
        self.btn_rack_add = QPushButton("Add")
        self.btn_rack_add.clicked.connect(self._start_new_rack)
        select_row.addWidget(self.btn_rack_add)
        select_row.addStretch(1)
        layout.addLayout(select_row)

        card = self._card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        self.edt_rack_name = QLineEdit()

        self.spn_vial1_x = self._float_box(minimum=0.0, maximum=1e6)
        self.spn_vial1_y = self._float_box(minimum=0.0, maximum=1e6)
        self.spn_vial_dy = self._float_box(minimum=0.0, maximum=1e6)
        self.spn_vial_dx = self._float_box(minimum=0.0, maximum=1e6)
        self.spn_vial_rows = self._int_box(minimum=0, maximum=1000)
        self.spn_vial_columns = self._int_box(minimum=0, maximum=1000)
        self.edt_z_min_vials = QLineEdit()
        self.edt_z_min_vials.setPlaceholderText("blank = use machine z_min")

        self.spn_solvent1_x = self._float_box(minimum=0.0, maximum=1e6)
        self.spn_solvent1_y = self._float_box(minimum=0.0, maximum=1e6)
        self.spn_solvent_rows = self._int_box(minimum=0, maximum=1000)
        self.spn_solvent_columns = self._int_box(minimum=0, maximum=1000)
        self.edt_solvent_dy = QLineEdit()
        self.edt_solvent_dy.setPlaceholderText("blank = 0")
        self.edt_solvent_dx = QLineEdit()
        self.edt_solvent_dx.setPlaceholderText("blank = 0")
        self.edt_z_min_solvents = QLineEdit()
        self.edt_z_min_solvents.setPlaceholderText("blank = use machine z_min")

        self.spn_waste_x = self._float_box(minimum=0.0, maximum=1e6)
        self.spn_waste_y = self._float_box(minimum=0.0, maximum=1e6)

        card_layout.addWidget(self._row_fields(("Name", self.edt_rack_name)))
        card_layout.addWidget(
            self._row_fields(
                ("vial1_x", self.spn_vial1_x),
                ("vial1_y", self.spn_vial1_y),
                ("vial_dy", self.spn_vial_dy),
                ("vial_dx", self.spn_vial_dx),
            )
        )
        card_layout.addWidget(
            self._row_fields(
                ("vial_rows", self.spn_vial_rows),
                ("vial_columns", self.spn_vial_columns),
                ("z_min_vials", self.edt_z_min_vials),
            )
        )
        card_layout.addWidget(
            self._row_fields(
                ("solvent1_x", self.spn_solvent1_x),
                ("solvent1_y", self.spn_solvent1_y),
                ("solvent_dy", self.edt_solvent_dy),
                ("solvent_dx", self.edt_solvent_dx),
            )
        )
        card_layout.addWidget(
            self._row_fields(
                ("solvent_rows", self.spn_solvent_rows),
                ("solvent_columns", self.spn_solvent_columns),
                ("z_min_solvents", self.edt_z_min_solvents),
            )
        )
        card_layout.addWidget(self._row_fields(("waste_x", self.spn_waste_x), ("waste_y", self.spn_waste_y)))

        layout.addWidget(card)

        buttons = QHBoxLayout()
        self.btn_rack_save = QPushButton("Save")
        self.btn_rack_save.clicked.connect(self._save_rack)
        self.btn_rack_rollback = QPushButton("Rollback")
        self.btn_rack_rollback.clicked.connect(self._rollback_rack)
        self.btn_rack_delete = QPushButton("Delete")
        self.btn_rack_delete.clicked.connect(self._delete_rack)
        buttons.addWidget(self.btn_rack_save)
        buttons.addWidget(self.btn_rack_rollback)
        buttons.addWidget(self.btn_rack_delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.subtabs.addTab(tab, "Rack")

    # ---------------- Widgets helpers ----------------

    def _float_box(
        self,
        *,
        minimum: float = 0.0,
        maximum: float = 1e6,
        decimals: int = 3,
        step: float = 0.1,
    ) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setRange(minimum, maximum)
        box.setSingleStep(step)
        box.setMinimumHeight(28)
        return box

    def _int_box(self, *, minimum: int = 0, maximum: int = 100000) -> QSpinBox:
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setMinimumHeight(28)
        return box

    def _populate_combo(
        self,
        combo: QComboBox,
        items: list[str],
        *,
        include_select: bool = True,
        include_new: bool = False,
        current_data: str | None = None,
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        if include_select:
            combo.addItem("— select —", None)
        for item in items:
            combo.addItem(item, item)
        if include_new:
            combo.addItem("new", self.NEW_ITEM)
        if current_data is not None:
            idx = combo.findData(current_data)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    # ---------------- Data loading ----------------

    def _load_syringe_list(self) -> None:
        self.cmb_setup_syringe.clear()
        self.cmb_setup_syringe.addItem("— select —", None)
        try:
            syringes = Syringe.get_all()
        except Exception as e:
            QMessageBox.warning(self, "DB error", f"Cannot load syringes: {e!s}")
            return

        for s in syringes:
            if s.id is None:
                continue
            label = f"{s.id} - {s.name}"
            self.cmb_setup_syringe.addItem(label, int(s.id))

    def _reload_all_lists(self) -> None:
        self._reload_machine_list()
        self._reload_rack_list()
        self._reload_setup_list()

    def _reload_setup_list(self) -> None:
        current = self.cmb_setup_select.currentData() if hasattr(self, "cmb_setup_select") else None
        self._setup_paths.clear()
        names: list[str] = []
        if self._setups_dir.exists():
            for path in sorted(self._setups_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    name = str(data.get("name") or path.stem)
                except Exception:
                    name = path.stem
                self._setup_paths[name] = path
                names.append(name)
        self._populate_combo(self.cmb_setup_select, names, include_new=True, current_data=current)
        if not names:
            self._start_new_setup()

    def _reload_machine_list(self) -> None:
        current = self.cmb_machine_select.currentData() if hasattr(self, "cmb_machine_select") else None
        self._machine_paths.clear()
        names: list[str] = []
        if self._machines_dir.exists():
            for path in sorted(self._machines_dir.glob("*.json")):
                name = path.stem
                self._machine_paths[name] = path
                names.append(name)
        self._machine_names = names
        self._populate_combo(self.cmb_machine_select, names, include_new=True, current_data=current)

        current_machine = self.cmb_setup_machine.currentData() if hasattr(self, "cmb_setup_machine") else None
        self._populate_combo(
            self.cmb_setup_machine, names, include_new=False, include_select=True, current_data=current_machine
        )

        if not names:
            self._start_new_machine()

    def _reload_rack_list(self) -> None:
        current = self.cmb_rack_select.currentData() if hasattr(self, "cmb_rack_select") else None
        self._rack_paths.clear()
        names: list[str] = []
        if self._racks_dir.exists():
            for path in sorted(self._racks_dir.glob("*.json")):
                name = path.stem
                self._rack_paths[name] = path
                names.append(name)
        self._rack_names = names
        self._populate_combo(self.cmb_rack_select, names, include_new=True, current_data=current)
        self._setup_rack_defs.clear()
        self._refresh_setup_rack_menu()
        if not names:
            self._start_new_rack()

    # ---------------- Setup tab ----------------

    def _on_setup_selected(self, *_: object) -> None:
        if self._loading_setup:
            return
        selected = self.cmb_setup_select.currentData()
        if selected == self.NEW_ITEM:
            self._apply_setup_data(None, new_mode=True)
            return
        if selected is None:
            self._apply_setup_data(None, new_mode=False)
            return

        name = str(selected)
        path = self._setup_paths.get(name)
        if path is None or not path.exists():
            QMessageBox.warning(self, "Load error", f"Setup config '{name}' not found.")
            self._apply_setup_data(None, new_mode=False)
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.warning(self, "Load error", f"Could not read setup '{name}': {e!s}")
            self._apply_setup_data(None, new_mode=False)
            return
        self._apply_setup_data(data, new_mode=False, selected_name=name)

    def _apply_setup_data(self, data: dict | None, *, new_mode: bool, selected_name: str | None = None) -> None:
        self._loading_setup = True
        self.edt_setup_name.setReadOnly(not new_mode)
        if data is None:
            self.edt_setup_name.setText("")
            self.cmb_setup_syringe.setCurrentIndex(0)
            self.cmb_setup_machine.setCurrentIndex(0)
            self._set_selected_racks_in_order([])
            self._loading_setup = False
            return

        name = selected_name or str(data.get("name") or "")
        self.edt_setup_name.setText(name)

        syringe_id = data.get("syringe_id")
        if syringe_id is not None:
            idx = self.cmb_setup_syringe.findData(int(syringe_id))
            if idx >= 0:
                self.cmb_setup_syringe.setCurrentIndex(idx)
            else:
                self.cmb_setup_syringe.setCurrentIndex(0)
        else:
            self.cmb_setup_syringe.setCurrentIndex(0)

        machine_name = data.get("machine")
        if machine_name is not None:
            idx = self.cmb_setup_machine.findData(str(machine_name))
            if idx >= 0:
                self.cmb_setup_machine.setCurrentIndex(idx)
            else:
                self.cmb_setup_machine.setCurrentIndex(0)
        else:
            self.cmb_setup_machine.setCurrentIndex(0)

        racks = data.get("racks") or []
        if isinstance(racks, list):
            self._set_selected_racks_in_order([str(r) for r in racks])
        else:
            self._set_selected_racks_in_order([])

        self._loading_setup = False

    def _start_new_setup(self) -> None:
        idx = self.cmb_setup_select.findData(self.NEW_ITEM)
        if idx >= 0:
            self.cmb_setup_select.setCurrentIndex(idx)
        else:
            self._apply_setup_data(None, new_mode=True)

    def _refresh_setup_rack_menu(self) -> None:
        if not hasattr(self, "setup_racks_menu"):
            return

        existing = self._selected_setup_rack_names_in_order()

        self.setup_racks_menu.clear()

        act_all = QAction("Select all", self)
        act_all.triggered.connect(lambda *_: self._set_all_setup_racks_checked(True))
        self.setup_racks_menu.addAction(act_all)

        act_none = QAction("Select none", self)
        act_none.triggered.connect(lambda *_: self._set_all_setup_racks_checked(False))
        self.setup_racks_menu.addAction(act_none)

        self.setup_racks_menu.addSeparator()

        self._setup_rack_actions.clear()
        for name in self._rack_names:
            act = QAction(name, self)
            act.setCheckable(True)
            act.toggled.connect(lambda checked, n=name: self._on_setup_rack_toggled(n, checked))
            self.setup_racks_menu.addAction(act)
            self._setup_rack_actions[name] = act

        filtered = [n for n in existing if n in self._setup_rack_actions]
        self._set_selected_racks_in_order(filtered)
        self._update_setup_racks_button_text()

    def _set_all_setup_racks_checked(self, checked: bool) -> None:
        for act in self._setup_rack_actions.values():
            act.blockSignals(True)
            act.setChecked(checked)
            act.blockSignals(False)

        self.lst_setup_racks.clear()
        if checked:
            for name in self._setup_rack_actions.keys():
                self._add_setup_selected_rack(name)

        self._update_setup_racks_button_text()
        self._update_setup_summary()

    def _on_setup_rack_toggled(self, rack_name: str, checked: bool) -> None:
        if checked:
            self._add_setup_selected_rack(rack_name)
        else:
            self._remove_setup_selected_rack(rack_name)
        self._update_setup_racks_button_text()
        self._update_setup_summary()

    def _add_setup_selected_rack(self, rack_name: str) -> None:
        for i in range(self.lst_setup_racks.count()):
            if self.lst_setup_racks.item(i).text() == rack_name:
                return
        self.lst_setup_racks.addItem(rack_name)

    def _remove_setup_selected_rack(self, rack_name: str) -> None:
        for i in range(self.lst_setup_racks.count()):
            if self.lst_setup_racks.item(i).text() == rack_name:
                self.lst_setup_racks.takeItem(i)
                return

    def _clear_setup_racks(self, *_) -> None:
        self.lst_setup_racks.clear()
        for act in self._setup_rack_actions.values():
            act.blockSignals(True)
            act.setChecked(False)
            act.blockSignals(False)
        self._update_setup_racks_button_text()
        self._update_setup_summary()

    def _update_setup_racks_button_text(self) -> None:
        n = self.lst_setup_racks.count()
        self.btn_setup_racks_menu.setText(f"Select racks…  ({n} selected)")

    def _selected_setup_rack_names_in_order(self) -> list[str]:
        return [self.lst_setup_racks.item(i).text() for i in range(self.lst_setup_racks.count())]

    def _set_selected_racks_in_order(self, rack_names: list[str]) -> None:
        if not hasattr(self, "lst_setup_racks"):
            return
        self.lst_setup_racks.clear()
        for act in self._setup_rack_actions.values():
            act.blockSignals(True)
            act.setChecked(False)
            act.blockSignals(False)

        for name in rack_names:
            act = self._setup_rack_actions.get(name)
            if act is None:
                continue
            act.blockSignals(True)
            act.setChecked(True)
            act.blockSignals(False)
            self._add_setup_selected_rack(name)

        self._update_setup_racks_button_text()
        self._update_setup_summary()

    def _update_setup_summary(self, *_) -> None:
        if not hasattr(self, "lbl_setup_summary"):
            return
        names = self._selected_setup_rack_names_in_order()
        if not names:
            self.lbl_setup_summary.setText("No racks selected.")
            return

        total_vials = 0
        total_solvents = 0
        missing: list[str] = []

        for name in names:
            rack = self._setup_rack_defs.get(name)
            if rack is None:
                try:
                    rack = load_model(Rack, name)
                    self._setup_rack_defs[name] = rack
                except Exception:
                    missing.append(name)
                    continue
            total_vials += int(rack.vial_rows) * int(rack.vial_columns)
            total_solvents += int(rack.solvent_rows) * int(rack.solvent_columns)

        msg = (
            f"Selected racks (in order): {', '.join(names)}\n"
            f"Total vial slots: {total_vials} | Total solvent slots: {total_solvents}"
        )
        if missing:
            msg += f"\nMissing/failed racks: {', '.join(missing)}"
        self.lbl_setup_summary.setText(msg)

    def _save_setup(self) -> None:
        selected = self.cmb_setup_select.currentData()
        is_new = selected == self.NEW_ITEM or selected is None

        name = self.edt_setup_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation error", "Setup name is required.")
            return
        if is_new and name in self._setup_paths:
            QMessageBox.warning(
                self,
                "Validation error",
                f"A setup named '{name}' already exists. Select it to edit or choose a new name.",
            )
            return
        if not is_new:
            name = str(selected)

        syringe_id = self.cmb_setup_syringe.currentData()
        if syringe_id is None:
            QMessageBox.warning(self, "Validation error", "Please select a syringe.")
            return

        machine_name = self.cmb_setup_machine.currentData()
        if machine_name is None:
            QMessageBox.warning(self, "Validation error", "Please select a machine.")
            return

        racks = self._selected_setup_rack_names_in_order()
        if not racks:
            QMessageBox.warning(self, "Validation error", "Please enter at least one rack.")
            return
        unknown = [r for r in racks if r not in self._rack_names]
        if unknown:
            QMessageBox.warning(
                self,
                "Validation error",
                f"Unknown rack(s): {', '.join(unknown)}",
            )
            return

        data = {
            "name": name,
            "syringe_id": int(syringe_id),
            "machine": str(machine_name),
            "racks": racks,
        }
        try:
            self._setups_dir.mkdir(parents=True, exist_ok=True)
            path = self._setups_dir / f"{name}.json"
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, "Save error", f"Could not save setup: {e!s}")
            return

        self._reload_setup_list()
        idx = self.cmb_setup_select.findData(name)
        if idx >= 0:
            self.cmb_setup_select.setCurrentIndex(idx)
        self._notify_config_changed()

    def _rollback_setup(self) -> None:
        selected = self.cmb_setup_select.currentData()
        if selected == self.NEW_ITEM:
            self._apply_setup_data(None, new_mode=True)
            return
        if selected is None:
            self._apply_setup_data(None, new_mode=False)
            return
        self._on_setup_selected()

    def _delete_setup(self) -> None:
        selected = self.cmb_setup_select.currentData()
        if selected is None or selected == self.NEW_ITEM:
            QMessageBox.warning(self, "Delete error", "Select a setup to delete.")
            return
        name = str(selected)
        path = self._setup_paths.get(name)
        if path is None or not path.exists():
            QMessageBox.warning(self, "Delete error", f"Setup '{name}' not found.")
            return
        confirm = QMessageBox.question(self, "Delete setup", f"Delete setup '{name}'?")
        if confirm != QMessageBox.Yes:
            return
        try:
            path.unlink()
        except Exception as e:
            QMessageBox.warning(self, "Delete error", f"Could not delete setup: {e!s}")
            return
        self._reload_setup_list()
        self._notify_config_changed()

    # ---------------- Machine tab ----------------

    def _on_machine_selected(self, *_: object) -> None:
        if self._loading_machine:
            return
        selected = self.cmb_machine_select.currentData()
        if selected == self.NEW_ITEM:
            self._apply_machine_data(None, new_mode=True)
            return
        if selected is None:
            self._apply_machine_data(None, new_mode=False)
            return

        name = str(selected)
        try:
            machine = load_model(Machine, name)
        except Exception as e:
            QMessageBox.warning(self, "Load error", f"Could not load machine '{name}': {e!s}")
            self._apply_machine_data(None, new_mode=False)
            return
        self._apply_machine_data(machine, new_mode=False, selected_name=name)

    def _apply_machine_data(self, machine: Machine | None, *, new_mode: bool, selected_name: str | None = None) -> None:
        self._loading_machine = True
        self.edt_machine_name.setReadOnly(not new_mode)
        if machine is None:
            self.edt_machine_name.setText("")
            for spin in (
                self.spn_z_min_limit,
                self.spn_z_max_limit,
                self.spn_z_min,
                self.spn_z_max,
                self.spn_z_slow,
                self.spn_fz,
                self.spn_fxy,
                self.spn_fa_push,
                self.spn_fa_push_slow,
                self.spn_fa_pull,
                self.spn_rest_x,
                self.spn_rest_y,
            ):
                spin.setValue(0.0)
            self._loading_machine = False
            return

        self.edt_machine_name.setText(selected_name or "")
        self.spn_z_min_limit.setValue(float(machine.z_min_limit))
        self.spn_z_max_limit.setValue(float(machine.z_max_limit))
        self.spn_z_min.setValue(float(machine.z_min))
        self.spn_z_max.setValue(float(machine.z_max))
        self.spn_z_slow.setValue(float(machine.z_slow))
        self.spn_fz.setValue(float(machine.Fz))
        self.spn_fxy.setValue(float(machine.Fxy))
        self.spn_fa_push.setValue(float(machine.Fa_push))
        self.spn_fa_push_slow.setValue(float(machine.Fa_push_slow))
        self.spn_fa_pull.setValue(float(machine.Fa_pull))
        self.spn_rest_x.setValue(float(machine.rest_x))
        self.spn_rest_y.setValue(float(machine.rest_y))
        self._loading_machine = False

    def _start_new_machine(self) -> None:
        idx = self.cmb_machine_select.findData(self.NEW_ITEM)
        if idx >= 0:
            self.cmb_machine_select.setCurrentIndex(idx)
        else:
            self._apply_machine_data(None, new_mode=True)

    def _save_machine(self) -> None:
        selected = self.cmb_machine_select.currentData()
        is_new = selected == self.NEW_ITEM or selected is None

        name = self.edt_machine_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation error", "Machine name is required.")
            return
        if is_new and name in self._machine_paths:
            QMessageBox.warning(
                self,
                "Validation error",
                f"A machine named '{name}' already exists. Select it to edit or choose a new name.",
            )
            return
        if not is_new:
            name = str(selected)

        data = {
            "z_min_limit": float(self.spn_z_min_limit.value()),
            "z_max_limit": float(self.spn_z_max_limit.value()),
            "z_min": float(self.spn_z_min.value()),
            "z_max": float(self.spn_z_max.value()),
            "z_slow": float(self.spn_z_slow.value()),
            "Fz": float(self.spn_fz.value()),
            "Fxy": float(self.spn_fxy.value()),
            "Fa_push": float(self.spn_fa_push.value()),
            "Fa_push_slow": float(self.spn_fa_push_slow.value()),
            "Fa_pull": float(self.spn_fa_pull.value()),
            "rest_x": float(self.spn_rest_x.value()),
            "rest_y": float(self.spn_rest_y.value()),
        }

        for key in ("Fz", "Fxy", "Fa_push", "Fa_push_slow", "Fa_pull", "rest_x", "rest_y"):
            if data[key] <= 0:
                QMessageBox.warning(self, "Validation error", f"{key} must be > 0.")
                return

        try:
            machine = Machine.model_validate(data)
            save_model(machine, name)
        except Exception as e:
            QMessageBox.warning(self, "Save error", f"Could not save machine: {e!s}")
            return

        self._reload_machine_list()
        idx = self.cmb_machine_select.findData(name)
        if idx >= 0:
            self.cmb_machine_select.setCurrentIndex(idx)
        self._notify_config_changed()

    def _rollback_machine(self) -> None:
        selected = self.cmb_machine_select.currentData()
        if selected == self.NEW_ITEM:
            self._apply_machine_data(None, new_mode=True)
            return
        if selected is None:
            self._apply_machine_data(None, new_mode=False)
            return
        self._on_machine_selected()

    def _delete_machine(self) -> None:
        selected = self.cmb_machine_select.currentData()
        if selected is None or selected == self.NEW_ITEM:
            QMessageBox.warning(self, "Delete error", "Select a machine to delete.")
            return
        name = str(selected)
        confirm = QMessageBox.question(self, "Delete machine", f"Delete machine '{name}'?")
        if confirm != QMessageBox.Yes:
            return
        try:
            delete_model(Machine, name)
        except Exception as e:
            QMessageBox.warning(self, "Delete error", f"Could not delete machine: {e!s}")
            return
        self._reload_machine_list()
        self._notify_config_changed()

    # ---------------- Rack tab ----------------

    def _on_rack_selected(self, *_: object) -> None:
        if self._loading_rack:
            return
        selected = self.cmb_rack_select.currentData()
        if selected == self.NEW_ITEM:
            self._apply_rack_data(None, new_mode=True)
            return
        if selected is None:
            self._apply_rack_data(None, new_mode=False)
            return

        name = str(selected)
        try:
            rack = load_model(Rack, name)
        except Exception as e:
            QMessageBox.warning(self, "Load error", f"Could not load rack '{name}': {e!s}")
            self._apply_rack_data(None, new_mode=False)
            return
        self._apply_rack_data(rack, new_mode=False, selected_name=name)

    def _apply_rack_data(self, rack: Rack | None, *, new_mode: bool, selected_name: str | None = None) -> None:
        self._loading_rack = True
        self.edt_rack_name.setReadOnly(not new_mode)
        if rack is None:
            self.edt_rack_name.setText("")
            for spin in (
                self.spn_vial1_x,
                self.spn_vial1_y,
                self.spn_vial_dy,
                self.spn_vial_dx,
                self.spn_vial_rows,
                self.spn_vial_columns,
                self.spn_solvent1_x,
                self.spn_solvent1_y,
                self.spn_solvent_rows,
                self.spn_solvent_columns,
                self.spn_waste_x,
                self.spn_waste_y,
            ):
                spin.setValue(0)
            self.edt_z_min_vials.setText("")
            self.edt_solvent_dy.setText("")
            self.edt_solvent_dx.setText("")
            self.edt_z_min_solvents.setText("")
            self._loading_rack = False
            return

        self.edt_rack_name.setText(selected_name or "")
        self.spn_vial1_x.setValue(float(rack.vial1_x))
        self.spn_vial1_y.setValue(float(rack.vial1_y))
        self.spn_vial_dy.setValue(float(rack.vial_dy))
        self.spn_vial_dx.setValue(float(rack.vial_dx))
        self.spn_vial_rows.setValue(int(rack.vial_rows))
        self.spn_vial_columns.setValue(int(rack.vial_columns))
        self.edt_z_min_vials.setText("" if rack.z_min_vials is None else str(rack.z_min_vials))

        self.spn_solvent1_x.setValue(float(rack.solvent1_x))
        self.spn_solvent1_y.setValue(float(rack.solvent1_y))
        self.spn_solvent_rows.setValue(int(rack.solvent_rows))
        self.spn_solvent_columns.setValue(int(rack.solvent_columns))
        self.edt_solvent_dy.setText("" if rack.solvent_dy is None else str(rack.solvent_dy))
        self.edt_solvent_dx.setText("" if rack.solvent_dx is None else str(rack.solvent_dx))
        self.edt_z_min_solvents.setText("" if rack.z_min_solvents is None else str(rack.z_min_solvents))

        self.spn_waste_x.setValue(float(rack.waste_x))
        self.spn_waste_y.setValue(float(rack.waste_y))
        self._loading_rack = False

    def _start_new_rack(self) -> None:
        idx = self.cmb_rack_select.findData(self.NEW_ITEM)
        if idx >= 0:
            self.cmb_rack_select.setCurrentIndex(idx)
        else:
            self._apply_rack_data(None, new_mode=True)

    def _parse_optional_float(self, field: QLineEdit, label: str, *, positive: bool = False) -> float | None:
        text = field.text().strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError as e:
            raise ValueError(f"{label} must be a valid number.") from e
        if positive and value <= 0:
            raise ValueError(f"{label} must be > 0.")
        return value

    def _save_rack(self) -> None:
        selected = self.cmb_rack_select.currentData()
        is_new = selected == self.NEW_ITEM or selected is None

        name = self.edt_rack_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation error", "Rack name is required.")
            return
        if is_new and name in self._rack_paths:
            QMessageBox.warning(
                self,
                "Validation error",
                f"A rack named '{name}' already exists. Select it to edit or choose a new name.",
            )
            return
        if not is_new:
            name = str(selected)

        if self.spn_vial_rows.value() <= 0 or self.spn_vial_columns.value() <= 0:
            QMessageBox.warning(self, "Validation error", "Vial rows/columns must be > 0.")
            return
        if self.spn_solvent_rows.value() <= 0 or self.spn_solvent_columns.value() <= 0:
            QMessageBox.warning(self, "Validation error", "Solvent rows/columns must be > 0.")
            return

        try:
            z_min_vials = self._parse_optional_float(self.edt_z_min_vials, "z_min_vials", positive=False)
            z_min_solvents = self._parse_optional_float(self.edt_z_min_solvents, "z_min_solvents", positive=False)
            solvent_dy = self._parse_optional_float(self.edt_solvent_dy, "solvent_dy", positive=True)
            solvent_dx = self._parse_optional_float(self.edt_solvent_dx, "solvent_dx", positive=True)
        except ValueError as e:
            QMessageBox.warning(self, "Validation error", str(e))
            return

        data = {
            "name": name,
            "vial1_x": float(self.spn_vial1_x.value()),
            "vial1_y": float(self.spn_vial1_y.value()),
            "vial_dy": float(self.spn_vial_dy.value()),
            "vial_dx": float(self.spn_vial_dx.value()),
            "vial_rows": int(self.spn_vial_rows.value()),
            "vial_columns": int(self.spn_vial_columns.value()),
            "z_min_vials": z_min_vials,
            "solvent1_x": float(self.spn_solvent1_x.value()),
            "solvent1_y": float(self.spn_solvent1_y.value()),
            "solvent_rows": int(self.spn_solvent_rows.value()),
            "solvent_columns": int(self.spn_solvent_columns.value()),
            "solvent_dy": solvent_dy,
            "solvent_dx": solvent_dx,
            "z_min_solvents": z_min_solvents,
            "waste_x": float(self.spn_waste_x.value()),
            "waste_y": float(self.spn_waste_y.value()),
        }

        try:
            rack = Rack.model_validate(data)
            save_model(rack, name)
        except Exception as e:
            QMessageBox.warning(self, "Save error", f"Could not save rack: {e!s}")
            return

        self._reload_rack_list()
        idx = self.cmb_rack_select.findData(name)
        if idx >= 0:
            self.cmb_rack_select.setCurrentIndex(idx)
        self._notify_config_changed()

    def _rollback_rack(self) -> None:
        selected = self.cmb_rack_select.currentData()
        if selected == self.NEW_ITEM:
            self._apply_rack_data(None, new_mode=True)
            return
        if selected is None:
            self._apply_rack_data(None, new_mode=False)
            return
        self._on_rack_selected()

    def _delete_rack(self) -> None:
        selected = self.cmb_rack_select.currentData()
        if selected is None or selected == self.NEW_ITEM:
            QMessageBox.warning(self, "Delete error", "Select a rack to delete.")
            return
        name = str(selected)
        confirm = QMessageBox.question(self, "Delete rack", f"Delete rack '{name}'?")
        if confirm != QMessageBox.Yes:
            return
        try:
            delete_model(Rack, name)
        except Exception as e:
            QMessageBox.warning(self, "Delete error", f"Could not delete rack: {e!s}")
            return
        self._reload_rack_list()
        self._notify_config_changed()

    # ---------------- Integration ----------------

    def _notify_config_changed(self) -> None:
        parent = self.parent()
        gcode_tab = getattr(parent, "gcode_tab", None)
        if gcode_tab is not None and hasattr(gcode_tab, "_load_config_lists"):
            try:
                gcode_tab._load_config_lists()
            except Exception:
                pass
        calibration_tab = getattr(parent, "calibration_tab", None)
        if calibration_tab is not None and hasattr(calibration_tab, "_load_config_lists"):
            try:
                calibration_tab._load_config_lists()
            except Exception:
                pass
