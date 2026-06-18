"""Einstiegspunkt für NIT_Code."""
import os
import sys
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from .main_window import MainWindow, build_global_style


def _install_exception_hook():
    """Fängt unbehandelte Ausnahmen ab, statt die App stillschweigend zu beenden.

    Hintergrund: In PyQt6 beendet eine nicht abgefangene Python-Ausnahme in
    einem Slot (Signal-Handler, Timer-Callback ...) standardmäßig den gesamten
    Prozess sofort – in der gebauten .exe ohne sichtbare Fehlermeldung. Das war
    die Ursache für die sporadischen Abstürze z. B. beim Wechsel in den
    MicroPython-Modus (Port-Scan/Geräteerkennung). Mit diesem Hook wird der
    Fehler stattdessen angezeigt und das Programm läuft weiter.
    """
    def _handle(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        # In die Konsole/Log schreiben (für Entwickler), wenn vorhanden.
        try:
            sys.stderr.write(msg)
        except Exception:
            pass
        # Für den Nutzer sichtbar machen, ohne die App zu beenden.
        try:
            box = QMessageBox()
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Unerwarteter Fehler")
            box.setText(
                "In NIT_Code ist ein unerwarteter Fehler aufgetreten.\n"
                "Das Programm versucht weiterzulaufen."
            )
            box.setDetailedText(msg)
            box.exec()
        except Exception:
            pass

    sys.excepthook = _handle

    # Ausnahmen in Worker-Threads (QThread/threading) ebenfalls abfangen,
    # damit auch dort nichts unbemerkt den Prozess gefährdet.
    import threading
    def _thread_handle(args):
        _handle(args.exc_type, args.exc_value, args.exc_traceback)
    try:
        threading.excepthook = _thread_handle
    except Exception:
        pass

    # Echte C-Level-Abstürze (Segfaults) zumindest auf stderr protokollieren.
    try:
        import faulthandler
        faulthandler.enable()
    except Exception:
        pass


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
    _install_exception_hook()
    app.setApplicationName("NIT_Code")
    app.setOrganizationName("NIT")
    app.setStyleSheet(build_global_style())

    logo = _find_logo()
    if not logo.isNull():
        app.setWindowIcon(logo)

    # Beim Start übergebener Dateipfad (z. B. Doppelklick auf .py über die
    # Windows-Dateizuordnung oder "NIT_Code datei.py" auf der Kommandozeile).
    initial_file = None
    for _arg in sys.argv[1:]:
        if not _arg.startswith("-") and os.path.isfile(_arg):
            initial_file = os.path.abspath(_arg)
            break

    # Standard-Schrift (plattformspezifisch, um Font-Scan-Warnung zu vermeiden)
    import sys as _sys
    if _sys.platform == "darwin":
        _font_family = ".AppleSystemUIFont"
    elif _sys.platform == "win32":
        _font_family = "Segoe UI"
    else:
        _font_family = "Ubuntu"
    app.setFont(QFont(_font_family, 13))

    window = MainWindow(initial_file=initial_file)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
