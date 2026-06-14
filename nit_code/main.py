"""Einstiegspunkt für NIT_Code."""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from .main_window import MainWindow, build_global_style


def _find_logo() -> QIcon:
    """Sucht logo.png im Paket- oder Projektordner."""
    candidates = []
    if getattr(sys, 'frozen', False):
        # PyInstaller-Bundle: logo.png liegt neben der EXE in nit_code/
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "nit_code" / "logo.png")
        if hasattr(sys, '_MEIPASS'):
            candidates.append(Path(sys._MEIPASS) / "nit_code" / "logo.png")
    candidates += [
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
    app.setStyleSheet(build_global_style())

    logo = _find_logo()
    if not logo.isNull():
        app.setWindowIcon(logo)

    # Standard-Schrift (plattformspezifisch, um Font-Scan-Warnung zu vermeiden)
    import sys as _sys
    if _sys.platform == "darwin":
        _font_family = ".AppleSystemUIFont"
    elif _sys.platform == "win32":
        _font_family = "Segoe UI"
    else:
        _font_family = "Ubuntu"
    app.setFont(QFont(_font_family, 13))

    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
