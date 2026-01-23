from __future__ import annotations

from typing import Callable
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)
from sqlalchemy import exc
from sqlmodel import select

from ..db import get_session
from ..Solvent import Solvent
from ..Syringe import Syringe
from ..SyringeSolventLink import SyringeSolventLink


class DbTab(QWidget):
    def __init__(self, parent: QWidget | None = None, *, on_syringe_changed: Callable[[], None] | None = None):
        super().__init__(parent)

        self._on_syringe_changed = on_syringe_changed
        self._loading_syringes = False
        self._loading_solvents = False
        self._loading_links = False
        self._syringe_dirty = False
        self._solvent_dirty = False
        self._link_dirty = False

        self._build_ui()
        self._load_syringes()
        self._load_solvents()
        self._load_links()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        tables_row = QHBoxLayout()
        tables_row.setSpacing(14)
        root.addLayout(tables_row, 1)

        # LEFT: syringes
        syr_col = QVBoxLayout()
        syr_col.setSpacing(10)
        tables_row.addLayout(syr_col, 1)

        syr_head = QHBoxLayout()
        lbl_syr = QLabel("Syringes")
        lbl_syr.setFont(QFont("Segoe UI", 14, QFont.Bold))
        syr_head.addWidget(lbl_syr)
        syr_head.addStretch(1)

        self.btn_add_syringe = QToolButton()
        self.btn_add_syringe.setText("+")
        self.btn_add_syringe.setToolTip("Add a new syringe row")
        self.btn_add_syringe.clicked.connect(self._add_syringe_row)
        syr_head.addWidget(self.btn_add_syringe)
        syr_col.addLayout(syr_head)

        self.tbl_syringes = QTableWidget()
        self.tbl_syringes.setColumnCount(4)
        self.tbl_syringes.setHorizontalHeaderLabels(
            ["id", "nominal volume, μl", "name", "inner diameter, mm"]
        )
        self.tbl_syringes.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_syringes.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tbl_syringes.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_syringes.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_syringes.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_syringes.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tbl_syringes.verticalHeader().setVisible(False)
        self.tbl_syringes.itemChanged.connect(self._on_syringe_table_changed)
        self.tbl_syringes.selectionModel().selectionChanged.connect(self._update_delete_button)
        syr_col.addWidget(self.tbl_syringes, 1)

        # RIGHT: solvents
        solv_col = QVBoxLayout()
        solv_col.setSpacing(10)
        tables_row.addLayout(solv_col, 1)

        solv_head = QHBoxLayout()
        lbl_solv = QLabel("Solvents")
        lbl_solv.setFont(QFont("Segoe UI", 14, QFont.Bold))
        solv_head.addWidget(lbl_solv)
        solv_head.addStretch(1)

        self.btn_add_solvent = QToolButton()
        self.btn_add_solvent.setText("+")
        self.btn_add_solvent.setToolTip("Add a new solvent row")
        self.btn_add_solvent.clicked.connect(self._add_solvent_row)
        solv_head.addWidget(self.btn_add_solvent)
        solv_col.addLayout(solv_head)

        self.tbl_solvents = QTableWidget()
        self.tbl_solvents.setColumnCount(4)
        self.tbl_solvents.setHorizontalHeaderLabels(
            ["id", "name", "density, g/ml", "notes"]
        )
        self.tbl_solvents.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_solvents.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tbl_solvents.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_solvents.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_solvents.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl_solvents.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tbl_solvents.verticalHeader().setVisible(False)
        self.tbl_solvents.itemChanged.connect(self._on_solvent_table_changed)
        self.tbl_solvents.selectionModel().selectionChanged.connect(self._update_delete_button)
        solv_col.addWidget(self.tbl_solvents, 1)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 6, 0, 0)
        self.btn_save = QPushButton("Save changes")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_all)
        self.btn_rollback = QPushButton("Rollback")
        self.btn_rollback.clicked.connect(self._rollback_all)
        self.btn_delete = QPushButton("Delete selected")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_selected)
        for btn in (self.btn_save, self.btn_rollback, self.btn_delete):
            btn.setStyleSheet("QPushButton { padding: 6px 10px; }")
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls.addWidget(self.btn_save)
        controls.addWidget(self.btn_rollback)
        controls.addWidget(self.btn_delete)
        controls.addStretch(1)
        root.addLayout(controls)

        link_head = QHBoxLayout()
        lbl_link = QLabel("Syringe Solvent Link (calibration)")
        lbl_link.setFont(QFont("Segoe UI", 13, QFont.Bold))
        link_head.addWidget(lbl_link)
        link_head.addStretch(1)

        self.btn_add_link = QToolButton()
        self.btn_add_link.setText("+")
        self.btn_add_link.setToolTip("Add a new link row")
        self.btn_add_link.clicked.connect(self._add_link_row)
        link_head.addWidget(self.btn_add_link)
        root.addLayout(link_head)

        self.tbl_links = QTableWidget()
        self.tbl_links.setColumnCount(6)
        self.tbl_links.setHorizontalHeaderLabels(
            ["syringe_id", "solvent_id", "calibrated", "backlash_correction", "real_correlation_factor", "since"]
        )
        self.tbl_links.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_links.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tbl_links.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_links.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_links.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_links.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tbl_links.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tbl_links.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.tbl_links.verticalHeader().setVisible(False)
        self.tbl_links.verticalHeader().setDefaultSectionSize(32)
        # Use native checkbox rendering for the calibrated column to match other tabs.
        self.tbl_links.itemChanged.connect(self._on_link_table_changed)
        self.tbl_links.selectionModel().selectionChanged.connect(self._update_delete_button)
        self.tbl_links.setItemDelegateForColumn(5, _SincePlaceholderDelegate(self.tbl_links))
        root.addWidget(self.tbl_links, 1)

    def _set_readonly_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _set_editable_item(self, text: str) -> QTableWidgetItem:
        return QTableWidgetItem(text)

    def _set_syringe_dirty(self, dirty: bool) -> None:
        self._syringe_dirty = dirty
        self._update_save_button()

    def _set_solvent_dirty(self, dirty: bool) -> None:
        self._solvent_dirty = dirty
        self._update_save_button()

    def _set_link_dirty(self, dirty: bool) -> None:
        self._link_dirty = dirty
        self._update_save_button()

    def _update_save_button(self) -> None:
        self.btn_save.setEnabled(self._syringe_dirty or self._solvent_dirty or self._link_dirty)

    def _update_delete_button(self, *_):
        has_selection = bool(self.tbl_syringes.selectionModel().selectedRows()) or bool(
            self.tbl_solvents.selectionModel().selectedRows()
        ) or bool(self.tbl_links.selectionModel().selectedRows())
        self.btn_delete.setEnabled(has_selection)

    def _load_syringes(self) -> None:
        self._loading_syringes = True
        self.tbl_syringes.setRowCount(0)
        try:
            syringes = Syringe.get_all()
        except Exception as e:
            QMessageBox.warning(self, "DB error", f"Cannot load syringes: {e!s}")
            self._loading_syringes = False
            return

        for s in syringes:
            row = self.tbl_syringes.rowCount()
            self.tbl_syringes.insertRow(row)
            self.tbl_syringes.setItem(row, 0, self._set_readonly_item(str(s.id or "")))
            self.tbl_syringes.setItem(row, 1, self._set_editable_item(str(s.nominal_volume_ul)))
            self.tbl_syringes.setItem(row, 2, self._set_editable_item(str(s.name)))
            self.tbl_syringes.setItem(row, 3, self._set_editable_item(str(s.inner_diameter_mm)))

        self._loading_syringes = False
        self._set_syringe_dirty(False)

    def _load_solvents(self) -> None:
        self._loading_solvents = True
        self.tbl_solvents.setRowCount(0)
        try:
            solvents = Solvent.get_all()
        except Exception as e:
            QMessageBox.warning(self, "DB error", f"Cannot load solvents: {e!s}")
            self._loading_solvents = False
            return

        for s in solvents:
            row = self.tbl_solvents.rowCount()
            self.tbl_solvents.insertRow(row)
            self.tbl_solvents.setItem(row, 0, self._set_readonly_item(str(s.id or "")))
            self.tbl_solvents.setItem(row, 1, self._set_editable_item(str(s.name)))
            density = "" if s.density_g_per_ml is None else str(s.density_g_per_ml)
            notes = "" if s.notes is None else str(s.notes)
            self.tbl_solvents.setItem(row, 2, self._set_editable_item(density))
            self.tbl_solvents.setItem(row, 3, self._set_editable_item(notes))

        self._loading_solvents = False
        self._set_solvent_dirty(False)

    def _load_links(self) -> None:
        self._loading_links = True
        self.tbl_links.setRowCount(0)
        try:
            links = SyringeSolventLink.get_all()
        except Exception as e:
            QMessageBox.warning(self, "DB error", f"Cannot load links: {e!s}")
            self._loading_links = False
            return

        for link in links:
            row = self.tbl_links.rowCount()
            self.tbl_links.insertRow(row)
            self.tbl_links.setItem(row, 0, self._set_editable_item(str(link.syringe_id)))
            self.tbl_links.setItem(row, 1, self._set_editable_item(str(link.solvent_id)))
            calibrated_item = QTableWidgetItem()
            calibrated_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            calibrated_item.setCheckState(Qt.Checked if link.calibrated else Qt.Unchecked)
            self.tbl_links.setItem(row, 2, calibrated_item)
            self.tbl_links.setItem(row, 3, self._set_editable_item(str(link.backlash_correction)))
            real_cf = "" if link.real_correlation_factor is None else str(link.real_correlation_factor)
            self.tbl_links.setItem(row, 4, self._set_editable_item(real_cf))
            since = "" if link.since is None else link.since.isoformat(sep=" ")
            self.tbl_links.setItem(row, 5, self._set_editable_item(since))

        self._loading_links = False
        self._set_link_dirty(False)

    def _add_syringe_row(self) -> None:
        self._loading_syringes = True
        row = self.tbl_syringes.rowCount()
        self.tbl_syringes.insertRow(row)
        self.tbl_syringes.setItem(row, 0, self._set_readonly_item(""))
        self.tbl_syringes.setItem(row, 1, self._set_editable_item(""))
        self.tbl_syringes.setItem(row, 2, self._set_editable_item(""))
        self.tbl_syringes.setItem(row, 3, self._set_editable_item(""))
        self._loading_syringes = False
        self.tbl_syringes.setCurrentCell(row, 1)
        self.tbl_syringes.scrollToItem(self.tbl_syringes.item(row, 1))
        self._set_syringe_dirty(True)

    def _add_solvent_row(self) -> None:
        self._loading_solvents = True
        row = self.tbl_solvents.rowCount()
        self.tbl_solvents.insertRow(row)
        self.tbl_solvents.setItem(row, 0, self._set_readonly_item(""))
        self.tbl_solvents.setItem(row, 1, self._set_editable_item(""))
        self.tbl_solvents.setItem(row, 2, self._set_editable_item(""))
        self.tbl_solvents.setItem(row, 3, self._set_editable_item(""))
        self._loading_solvents = False
        self.tbl_solvents.setCurrentCell(row, 1)
        self.tbl_solvents.scrollToItem(self.tbl_solvents.item(row, 1))
        self._set_solvent_dirty(True)

    def _add_link_row(self) -> None:
        self._loading_links = True
        row = self.tbl_links.rowCount()
        self.tbl_links.insertRow(row)
        self.tbl_links.setItem(row, 0, self._set_editable_item(""))
        self.tbl_links.setItem(row, 1, self._set_editable_item(""))
        calibrated_item = QTableWidgetItem()
        calibrated_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        calibrated_item.setCheckState(Qt.Unchecked)
        self.tbl_links.setItem(row, 2, calibrated_item)
        self.tbl_links.setItem(row, 3, self._set_editable_item("0.0"))
        self.tbl_links.setItem(row, 4, self._set_editable_item(""))
        self.tbl_links.setItem(row, 5, self._set_editable_item(""))
        self._loading_links = False
        self.tbl_links.setCurrentCell(row, 0)
        self.tbl_links.scrollToItem(self.tbl_links.item(row, 0))
        self._set_link_dirty(True)

    def _delete_selected(self) -> None:
        syringe_rows = sorted({idx.row() for idx in self.tbl_syringes.selectionModel().selectedRows()}, reverse=True)
        solvent_rows = sorted({idx.row() for idx in self.tbl_solvents.selectionModel().selectedRows()}, reverse=True)
        link_rows = sorted({idx.row() for idx in self.tbl_links.selectionModel().selectedRows()}, reverse=True)
        for row in syringe_rows:
            self.tbl_syringes.removeRow(row)
        for row in solvent_rows:
            self.tbl_solvents.removeRow(row)
        for row in link_rows:
            self.tbl_links.removeRow(row)
        if syringe_rows:
            self._set_syringe_dirty(True)
        if solvent_rows:
            self._set_solvent_dirty(True)
        if link_rows:
            self._set_link_dirty(True)
        self._update_delete_button()

    def _on_syringe_table_changed(self, *_):
        if self._loading_syringes:
            return
        self._set_syringe_dirty(True)

    def _on_solvent_table_changed(self, *_):
        if self._loading_solvents:
            return
        self._set_solvent_dirty(True)

    def _on_link_table_changed(self, *_):
        if self._loading_links:
            return
        self._set_link_dirty(True)

    def _rollback_all(self) -> None:
        self._load_syringes()
        self._load_solvents()
        self._load_links()
        self._update_delete_button()

    def _cell_text(self, table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        return "" if item is None else item.text().strip()

    def _cell_checked(self, table: QTableWidget, row: int, col: int) -> bool:
        item = table.item(row, col)
        if item is None:
            return False
        return item.checkState() == Qt.Checked

    def _collect_syringe_rows(self) -> list[dict] | None:
        rows: list[dict] = []
        for row in range(self.tbl_syringes.rowCount()):
            id_text = self._cell_text(self.tbl_syringes, row, 0)
            nominal_text = self._cell_text(self.tbl_syringes, row, 1)
            name_text = self._cell_text(self.tbl_syringes, row, 2)
            inner_text = self._cell_text(self.tbl_syringes, row, 3)

            if not name_text:
                QMessageBox.warning(self, "Validation error", "Syringe name is required.")
                return None
            if not nominal_text:
                QMessageBox.warning(self, "Validation error", "Syringe nominal volume is required.")
                return None
            if not inner_text:
                QMessageBox.warning(self, "Validation error", "Syringe inner diameter is required.")
                return None

            try:
                nominal = float(nominal_text)
                inner = float(inner_text)
            except ValueError:
                QMessageBox.warning(self, "Validation error", "Syringe numeric fields must be valid numbers.")
                return None

            if nominal <= 0 or inner <= 0:
                QMessageBox.warning(self, "Validation error", "Syringe numeric fields must be > 0.")
                return None

            row_data = {
                "id": int(id_text) if id_text else None,
                "nominal_volume_ul": nominal,
                "name": name_text,
                "inner_diameter_mm": inner,
            }
            rows.append(row_data)

        return rows

    def _collect_solvent_rows(self) -> list[dict] | None:
        rows: list[dict] = []
        for row in range(self.tbl_solvents.rowCount()):
            id_text = self._cell_text(self.tbl_solvents, row, 0)
            name_text = self._cell_text(self.tbl_solvents, row, 1)
            density_text = self._cell_text(self.tbl_solvents, row, 2)
            notes_text = self._cell_text(self.tbl_solvents, row, 3)

            if not name_text:
                QMessageBox.warning(self, "Validation error", "Solvent rows require a name.")
                return None

            density = None
            if density_text:
                try:
                    density = float(density_text)
                except ValueError:
                    QMessageBox.warning(self, "Validation error", "Density must be a valid number.")
                    return None
                if density <= 0:
                    QMessageBox.warning(self, "Validation error", "Density must be > 0.")
                    return None

            row_data = {
                "id": int(id_text) if id_text else None,
                "name": name_text,
                "density_g_per_ml": density,
                "notes": notes_text or None,
            }
            rows.append(row_data)

        return rows

    def _collect_link_rows(self) -> list[dict] | None:
        rows: list[dict] = []
        for row in range(self.tbl_links.rowCount()):
            syringe_text = self._cell_text(self.tbl_links, row, 0)
            solvent_text = self._cell_text(self.tbl_links, row, 1)
            if not syringe_text or not solvent_text:
                QMessageBox.warning(
                    self,
                    "Validation error",
                    "Link rows require syringe_id and solvent_id.",
                )
                return None

            try:
                syringe_id = int(syringe_text)
                solvent_id = int(solvent_text)
            except ValueError:
                QMessageBox.warning(self, "Validation error", "Link ids must be integers.")
                return None

            backlash_text = self._cell_text(self.tbl_links, row, 3)
            try:
                backlash = float(backlash_text) if backlash_text else 0.0
            except ValueError:
                QMessageBox.warning(self, "Validation error", "Backlash correction must be a number.")
                return None
            if backlash < 0:
                QMessageBox.warning(self, "Validation error", "Backlash correction must be >= 0.")
                return None

            real_cf_text = self._cell_text(self.tbl_links, row, 4)
            real_cf = None
            if real_cf_text:
                try:
                    real_cf = float(real_cf_text)
                except ValueError:
                    QMessageBox.warning(self, "Validation error", "Real correlation factor must be a number.")
                    return None
                if real_cf <= 0:
                    QMessageBox.warning(self, "Validation error", "Real correlation factor must be > 0.")
                    return None

            since_text = self._cell_text(self.tbl_links, row, 5)
            since = None
            if since_text:
                try:
                    since = datetime.fromisoformat(since_text)
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Validation error",
                        "Since must be an ISO datetime (e.g. 2024-01-31 12:34:56).",
                    )
                    return None

            rows.append(
                {
                    "syringe_id": syringe_id,
                    "solvent_id": solvent_id,
                    "calibrated": self._cell_checked(self.tbl_links, row, 2),
                    "backlash_correction": backlash,
                    "real_correlation_factor": real_cf,
                    "since": since,
                }
            )

        return rows

    def _save_syringe_table(self) -> bool:
        rows = self._collect_syringe_rows()
        if rows is None:
            return False

        with get_session() as session:
            existing = {s.id: s for s in session.exec(select(Syringe)).all() if s.id is not None}
            desired_ids: set[int] = set()

            for row in rows:
                if row["id"] is None:
                    obj = Syringe(
                        nominal_volume_ul=row["nominal_volume_ul"],
                        name=row["name"],
                        inner_diameter_mm=row["inner_diameter_mm"],
                    )
                    session.add(obj)
                else:
                    s_id = row["id"]
                    desired_ids.add(s_id)
                    obj = existing.get(s_id)
                    if obj is None:
                        QMessageBox.warning(self, "Save error", f"Unknown syringe id={s_id}.")
                        session.rollback()
                        return False
                    obj.nominal_volume_ul = row["nominal_volume_ul"]
                    obj.name = row["name"]
                    obj.inner_diameter_mm = row["inner_diameter_mm"]

            for s_id, obj in existing.items():
                if s_id not in desired_ids:
                    session.delete(obj)

            try:
                session.commit()
            except exc.IntegrityError as e:
                session.rollback()
                QMessageBox.warning(self, "Save error", f"Could not save syringes: {e!s}")
                return False
            except Exception as e:
                session.rollback()
                QMessageBox.warning(self, "Save error", f"Could not save syringes: {e!s}")
                return False

        self._load_syringes()
        if self._on_syringe_changed is not None:
            self._on_syringe_changed()
        return True

    def _save_solvent_table(self) -> bool:
        rows = self._collect_solvent_rows()
        if rows is None:
            return False

        with get_session() as session:
            existing = {s.id: s for s in session.exec(select(Solvent)).all() if s.id is not None}
            desired_ids: set[int] = set()

            for row in rows:
                if row["id"] is None:
                    obj = Solvent(
                        name=row["name"],
                        density_g_per_ml=row["density_g_per_ml"],
                        notes=row["notes"],
                    )
                    session.add(obj)
                else:
                    s_id = row["id"]
                    desired_ids.add(s_id)
                    obj = existing.get(s_id)
                    if obj is None:
                        QMessageBox.warning(self, "Save error", f"Unknown solvent id={s_id}.")
                        session.rollback()
                        return False
                    obj.name = row["name"]
                    obj.density_g_per_ml = row["density_g_per_ml"]
                    obj.notes = row["notes"]

            for s_id, obj in existing.items():
                if s_id not in desired_ids:
                    session.delete(obj)

            try:
                session.commit()
            except exc.IntegrityError as e:
                session.rollback()
                QMessageBox.warning(self, "Save error", f"Could not save solvents: {e!s}")
                return False
            except Exception as e:
                session.rollback()
                QMessageBox.warning(self, "Save error", f"Could not save solvents: {e!s}")
                return False

        self._load_solvents()
        return True

    def _save_link_table(self) -> bool:
        rows = self._collect_link_rows()
        if rows is None:
            return False

        with get_session() as session:
            existing = {
                (s.syringe_id, s.solvent_id): s for s in session.exec(select(SyringeSolventLink)).all()
            }
            desired_keys: set[tuple[int, int]] = set()

            for row in rows:
                key = (row["syringe_id"], row["solvent_id"])
                desired_keys.add(key)
                obj = existing.get(key)
                if obj is None:
                    try:
                        obj = SyringeSolventLink(
                            syringe_id=row["syringe_id"],
                            solvent_id=row["solvent_id"],
                        )
                    except ValueError as e:
                        session.rollback()
                        QMessageBox.warning(self, "Save error", str(e))
                        return False
                    session.add(obj)
                if row["real_correlation_factor"] is None:
                    syringe = session.get(Syringe, row["syringe_id"])
                    if syringe is None:
                        session.rollback()
                        QMessageBox.warning(
                            self,
                            "Save error",
                            f"Unknown syringe id={row['syringe_id']} for link.",
                        )
                        return False
                    obj.real_correlation_factor = syringe.theoretical_correlation_factor
                else:
                    obj.real_correlation_factor = row["real_correlation_factor"]
                obj.calibrated = row["calibrated"]
                obj.backlash_correction = row["backlash_correction"]
                obj.since = row["since"]

            for key, obj in existing.items():
                if key not in desired_keys:
                    session.delete(obj)

            try:
                session.commit()
            except exc.IntegrityError as e:
                session.rollback()
                QMessageBox.warning(self, "Save error", f"Could not save links: {e!s}")
                return False
            except Exception as e:
                session.rollback()
                QMessageBox.warning(self, "Save error", f"Could not save links: {e!s}")
                return False

        self._load_links()
        return True

    def _save_all(self) -> None:
        ok_syr = True
        ok_sol = True
        ok_link = True
        if self._syringe_dirty:
            ok_syr = self._save_syringe_table()
        if self._solvent_dirty:
            ok_sol = self._save_solvent_table()
        if self._link_dirty:
            ok_link = self._save_link_table()
        if ok_syr and ok_sol and ok_link:
            self._update_save_button()


class _SincePlaceholderDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setPlaceholderText("yyyy-mm-dd")
        font = editor.font()
        font.setPointSize(max(8, font.pointSize() - 1))
        editor.setFont(font)
        return editor
