"""Einstiegspunkt für NIT_Code."""
import os
import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont

from .main_window import MainWindow, build_global_style
from .qt_utils import find_logo


class _ExceptionBridge(QObject):
    """Leitet Fehlermeldungen aus beliebigen Threads in den GUI-Thread.

    Qt-Widgets (QMessageBox) dürfen ausschließlich im GUI-Thread erzeugt
    werden. Ausnahmen aus Worker-Threads werden daher über dieses Signal
    gemeldet – die Queued-Connection stellt sicher, dass der Slot (und damit
    die Dialog-Anzeige) im GUI-Thread läuft.
    """
    occurred = pyqtSignal(str)


_exception_bridge: _ExceptionBridge | None = None


def _show_exception_box(msg: str):
    """Zeigt den Fehlerdialog – läuft immer im GUI-Thread (Signal-Slot)."""
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


def _install_exception_hook():
    """Fängt unbehandelte Ausnahmen ab, statt die App stillschweigend zu beenden.

    Hintergrund: In PyQt6 beendet eine nicht abgefangene Python-Ausnahme in
    einem Slot (Signal-Handler, Timer-Callback ...) standardmäßig den gesamten
    Prozess sofort – in der gebauten .exe ohne sichtbare Fehlermeldung. Das war
    die Ursache für die sporadischen Abstürze z. B. beim Wechsel in den
    MicroPython-Modus (Port-Scan/Geräteerkennung). Mit diesem Hook wird der
    Fehler stattdessen angezeigt und das Programm läuft weiter.

    Muss NACH dem Erzeugen der QApplication aufgerufen werden (GUI-Thread).
    """
    global _exception_bridge
    _exception_bridge = _ExceptionBridge()
    _exception_bridge.occurred.connect(_show_exception_box)

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
        # Für den Nutzer sichtbar machen, ohne die App zu beenden. Das Signal
        # sorgt dafür, dass der Dialog auch bei Ausnahmen in Worker-Threads
        # sicher im GUI-Thread erscheint.
        try:
            _exception_bridge.occurred.emit(msg)
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


def _is_windows_remote_session() -> bool:
    """True in einer RDP-/Terminalserver-Sitzung unter Windows."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        SM_REMOTESESSION = 0x1000
        return bool(ctypes.windll.user32.GetSystemMetrics(SM_REMOTESESSION))
    except Exception:
        return os.environ.get("SESSIONNAME", "").upper().startswith("RDP-")


def _configure_webengine():
    """Härtet QtWebEngine (Block-Editor, AIS-Chat, Mermaid) gegen GPU-Abstürze.

    Auf älteren Windows-Rechnern sowie in Terminalserver-/RDP-Sitzungen steht
    oft keine stabile GPU-Beschleunigung für QtWebEngine zur Verfügung.
    Chromiums GPU-Prozess kann dort beim Start einer WebEngine-Ansicht
    abstürzen und die App mitreißen (Symptom: „Block-Editor öffnen → NIT_Code
    beendet sich“).

    Daher nutzen wir unter Windows standardmäßig Software-Rendering. Das
    verhindert, dass Nutzer:innen (z. B. auf Schulservern) manuell
    Umgebungsvariablen setzen müssen.

    Steuerung per Umgebungsvariable:
    - NIT_SOFTWARE_RENDER=1: Software-Rendering erzwingen
    - NIT_SOFTWARE_RENDER=0: GPU-Beschleunigung erlauben (Opt-out)

    Muss VOR dem Erzeugen der QApplication laufen, da Chromium die Flags nur
    beim Start liest.
    """
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")

    def add(flag: str):
        nonlocal flags
        if flag not in flags:
            flags = f"{flags} {flag}".strip()

    force_render = os.environ.get("NIT_SOFTWARE_RENDER")
    use_software_render = (
        force_render == "1"
        or (force_render != "0" and (sys.platform == "win32" or _is_windows_remote_session()))
    )

    if use_software_render:
        # Chromium-GPU abschalten (QtWebEngine-Renderer).
        add("--disable-gpu")
        add("--disable-gpu-compositing")
        # Auf einigen alten/virtuellen Windows-GPUs reicht das nicht, weil Qt
        # weiterhin versucht, Hardware-OpenGL zu initialisieren.
        os.environ.setdefault("QT_OPENGL", "software")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        if sys.platform == "win32":
            # Manche stark eingeschränkte Schulserver-Profile blockieren die
            # Chromium-Sandbox und beenden den Renderer hart beim Start.
            os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    if flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = flags

    # Von QtWebEngine vorausgesetzt, wenn Ansichten in mehreren Fenstern
    # (Hauptfenster-Panels + Block-Editor-Extrafenster) erzeugt werden.
    QApplication.setAttribute(
        Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True
    )
    if use_software_render:
        try:
            QApplication.setAttribute(
                Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True
            )
        except Exception:
            pass


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
    _configure_webengine()

    # High-DPI Unterstützung
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    _install_exception_hook()
    app.setApplicationName("NIT_Code")
    app.setOrganizationName("NIT")
    app.setStyleSheet(build_global_style())

    logo = find_logo()
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
