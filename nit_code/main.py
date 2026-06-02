"""Einstiegspunkt für NIT_Code."""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from .main_window import MainWindow, GLOBAL_STYLE


def _find_logo() -> QIcon:
    """Sucht logo.png im Paket- oder Projektordner."""
    candidates = [
        Path(__file__).resolve().parent / "logo.png",          # nit_code/logo.png
        Path(__file__).resolve().parent.parent / "logo.png",    # Projektordner/logo.png
    ]
    from PyQt6.QtGui import QPixmap
    for p in candidates:
        if p.exists():
            px = QPixmap(str(p))
            if not px.isNull():
                return QIcon(px)
    return QIcon()


def main():
    # High-DPI Unterstützung
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("NIT_Code")
    app.setOrganizationName("NIT")
    app.setStyleSheet(GLOBAL_STYLE)

    logo = _find_logo()
    if not logo.isNull():
        app.setWindowIcon(logo)

    # Standard-Schrift
    font = QFont("Segoe UI, Ubuntu, Helvetica Neue, sans-serif", 13)
    app.setFont(font)

    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
