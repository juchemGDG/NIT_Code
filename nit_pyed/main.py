"""Einstiegspunkt für NIT PyEd."""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from .main_window import MainWindow, GLOBAL_STYLE


def _find_logo() -> QIcon:
    """Sucht logo.png im Paket- oder Projektordner."""
    candidates = [
        Path(__file__).parent / "logo.png",          # nit_pyed/logo.png
        Path(__file__).parent.parent / "logo.png",    # Projektordner/logo.png
    ]
    for p in candidates:
        if p.exists():
            return QIcon(str(p))
    return QIcon()


def main():
    # High-DPI Unterstützung
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("NIT PyEd")
    app.setOrganizationName("NIT")
    app.setStyleSheet(GLOBAL_STYLE)

    logo = _find_logo()
    if not logo.isNull():
        app.setWindowIcon(logo)

    # Standard-Schrift
    font = QFont("Segoe UI, Ubuntu, Helvetica Neue, sans-serif", 13)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
