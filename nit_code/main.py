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


def _install_truststore():
    """Lässt Python (und damit ``requests``) den Zertifikatspeicher des
    Betriebssystems verwenden statt des mitgelieferten certifi-Bundles.

    Hintergrund: In Schul- und Firmennetzen wird HTTPS häufig über einen Proxy
    mit TLS-Inspektion geführt, der die Verbindung mit einem eigenen
    Root-Zertifikat neu signiert. Dieses Zertifikat ist auf den verwalteten
    Rechnern im Windows-Zertifikatspeicher hinterlegt – ``requests`` kennt es
    aber nicht und bricht den Download der NIT-Bibliotheken mit einem SSL-Fehler
    ab, obwohl der Browser dieselbe Adresse problemlos öffnet. ``truststore``
    verbindet Pythons ssl-Modul mit dem OS-Speicher und behebt genau das (der
    eingebettete AIS-Chat nutzt über QtWebEngine ohnehin schon den Windows-Store).

    Schlägt der Import fehl (z. B. truststore nicht installiert), läuft die App
    unverändert mit certifi weiter – der Aufruf darf den Start nie verhindern.
    """
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass


def _suppress_child_consoles():
    """Verhindert, dass unter Windows bei jedem Subprozess ein schwarzes
    Konsolenfenster aufpoppt.

    NIT_Code ist eine GUI-Anwendung (PyInstaller: console=False). Alle
    Hilfsprozesse (git, pip, mpremote, die Python-Shell …) sollen unsichtbar
    im Hintergrund laufen – ihre Ausgabe wird ohnehin in der GUI angezeigt.
    Ohne das Flag CREATE_NO_WINDOW oeffnet Windows fuer jeden dieser Aufrufe
    kurz ein eigenes Konsolenfenster.

    subprocess.run() nutzt intern Popen, daher genuegt es, Popen.__init__ an
    einer Stelle zu patchen – das deckt alle Aufrufstellen ab.
    """
    if sys.platform != "win32":
        return
    import subprocess
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    _orig_init = subprocess.Popen.__init__

    def _patched_init(self, *args, **kwargs):
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | create_no_window
        _orig_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _patched_init


def main():
    _install_truststore()
    _suppress_child_consoles()

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
