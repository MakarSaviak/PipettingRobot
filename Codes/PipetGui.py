from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QTabWidget

from .db import create_db_and_tables
from .gui.calibration_tab import CalibrationTab
from .gui.db_tab import DbTab
from .gui.gcode_tab import GCodeTab


class PipetGuiWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Setup • Excel → G-code")
        self.resize(1080, 680)

        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        try:
            create_db_and_tables()
        except Exception as e:
            QMessageBox.warning(
                self,
                "DB init warning",
                f"create_db_and_tables() raised an exception.\n\n{e!s}\n\n"
                f"If your DB is already initialized, you can ignore this.",
            )

        self.gcode_tab = GCodeTab(self)
        self.calibration_tab = CalibrationTab(self)
        self.db_tab = DbTab(
            self,
            on_syringe_changed=lambda: (
                self.gcode_tab.refresh_syringe_list(),
                self.calibration_tab.refresh_syringe_list(),
            ),
        )

        self.tabs.addTab(self.gcode_tab, "G-code")
        self.tabs.addTab(self.calibration_tab, "Calibration")
        self.tabs.addTab(self.db_tab, "Syringes and Solvents")

        self._apply_style()

    def _apply_style(self) -> None:
        base_style = """
            QMainWindow { background: #0f1115; }
            QLabel { color: #e9ecf1; }
            QCheckBox { color: #e9ecf1; }
            QLineEdit, QComboBox, QSpinBox, QListWidget, QTextEdit, QTableWidget {
                background: #151a22;
                color: #e9ecf1;
                border: 1px solid #263042;
                border-radius: 10px;
                padding: 8px;
                selection-background-color: #2b3b55;
            }
            QTableWidget::item:selected { background: #2b3b55; }
            QComboBox::drop-down { border: 0px; width: 24px; }
            QToolButton {
                background: #151a22;
                color: #e9ecf1;
                border: 1px solid #263042;
                border-radius: 10px;
                padding: 8px 10px;
            }
            QPushButton {
                background: #2a6df4;
                color: white;
                border: 0px;
                border-radius: 12px;
                padding: 10px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #3778ff; }
            QPushButton:pressed { background: #1f57c5; }
            QPushButton:disabled { background: #3a4a64; color: #9aa4b2; }
            QFrame#card {
                background: #0f141d;
                border: 1px solid #263042;
                border-radius: 16px;
            }
            QMenu {
                background: #151a22;
                color: #e9ecf1;
                border: 1px solid #263042;
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item { padding: 8px 10px; border-radius: 8px; }
            QMenu::item:selected { background: #2b3b55; }
            QTabWidget::pane { border: 0; }
            QTabBar::tab {
                background: #0f141d;
                color: #9aa4b2;
                padding: 8px 14px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
            }
            QTabBar::tab:selected { background: #151a22; color: #e9ecf1; }
            QHeaderView::section {
                background: #0f141d;
                color: #e9ecf1;
                border: 1px solid #263042;
                padding: 6px;
            }
            """
        linux_popup = ""
        if sys.platform.startswith("linux"):
            linux_popup = """
            QComboBox QAbstractItemView {
                background: #151a22;
                color: #e9ecf1;
                border: 1px solid #263042;
                padding: 4px;
                selection-background-color: #2b3b55;
            }
            QComboBox QAbstractItemView::viewport {
                background: #151a22;
            }
            QComboBox QAbstractItemView QScrollBar:vertical {
                background: #0f141d;
            }
            QComboBox QAbstractItemView::item {
                background: #151a22;
                color: #e9ecf1;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #2b3b55;
                color: #e9ecf1;
            }
            """
        self.setStyleSheet(base_style + linux_popup)


def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    w = PipetGuiWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
