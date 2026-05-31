"""Einstiegspunkt für NIT PyEd."""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .main_window import MainWindow, GLOBAL_STYLE


def main():
    # High-DPI Unterstützung
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("NIT PyEd")
    app.setOrganizationName("NIT")
    app.setStyleSheet(GLOBAL_STYLE)

    # Standard-Schrift
    font = QFont("Segoe UI, Ubuntu, Helvetica Neue, sans-serif", 13)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
