"""Datenauswertung (CSV) – StatPlot eingebettet wie PAP-/IBD-Editor.

StatPlot (github.com/juchemGDG/StatPlot) ist die frühere Datenauswertung von
NIT_Code als Web-App: Diagramme, Kennwerte, Häufigkeiten, Statistik-Tests und
Python-Code-Export. Dieselbe Seite läuft auf statplot.mint-checker.de, als
Desktop-App und hier im iframe mit ``?embed=1``.

Wie PAP/IBD wird zuerst die Online-Version geladen – Änderungen an
statplot.mint-checker.de sind damit sofort in NIT_Code zu sehen. Meldet sich die
Seite nicht innerhalb von ``_ONLINE_TIMEOUT_MS`` (kein Netz, Proxy), schalten wir
auf die mitgelieferte Kopie in ``nit_code/assets/statplot`` um. Sie wird über
einen kleinen lokalen HTTP-Server auf 127.0.0.1 ausgeliefert, damit die
Host-Seite eine echte Origin für postMessage hat (siehe pap_editor.py). Die
Kopie aktualisiert der Release-Build automatisch (sync_statplot.sh), von Hand
geht es mit ``bash release/scripts/sync_statplot.sh <StatPlot-Pfad>``.

Zusätzlich zum PAP-Protokoll (Schalter in ``_LOAD``):

* open:true      – „CSV öffnen“ meldet 'open'; wir zeigen den Dateidialog im
                   Sketchbook und schicken load + csv/name/path zurück.
* code:true      – „In neuen Editor-Tab“ meldet 'code' → ``set_code_sink``.
* clipboard:true – Kopieren läuft über Qt ('copy'), im iframe ist die
                   Zwischenablage sonst oft gesperrt.
* nit:true       – der Python-Code verweist auf NIT_Codes Paket-Menü.
* save:false     – kein „In Projekt übernehmen“: NIT_Code übernimmt kein
                   Diagramm, der Code-Export ist der Weg ins Projekt.
"""
import functools
import http.server
import os
import socketserver
import threading
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QFileDialog

from .config import STATPLOT_ORIGIN, STATPLOT_URL, asset_path
from .pap_editor import PapEditorWindow

_server_lock = threading.Lock()
_server_origin: str | None = None


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def statplot_dir() -> Path | None:
    """Ordner mit der mitgelieferten StatPlot-Seite (index.html)."""
    folder = asset_path("statplot")
    return folder if folder and (folder / "index.html").is_file() else None


def _local_origin() -> str | None:
    """Startet einmalig den lokalen Server (nur 127.0.0.1, freier Port)."""
    global _server_origin
    with _server_lock:
        if _server_origin is None:
            folder = statplot_dir()
            if folder is None:
                return None
            handler = functools.partial(_QuietHandler, directory=str(folder))
            httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
            httpd.daemon_threads = True
            threading.Thread(target=httpd.serve_forever, daemon=True,
                             name="statplot-server").start()
            _server_origin = f"http://127.0.0.1:{httpd.server_address[1]}"
        return _server_origin


def read_csv_text(path: str) -> str:
    """CSV-Datei als Text – UTF-8, sonst Windows-1252 (Excel speichert CSV oft so)."""
    raw = Path(path).read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


class StatPlotWindow(PapEditorWindow):
    """Datenauswertung: StatPlot im Extrafenster, Code-Export in einen Editor-Tab."""

    _SOURCE = "statplot"
    _NAME = "Datenauswertung"
    _WINDOW_TITLE = "NIT Datenauswertung"
    _HOST = "der Datenauswertung"
    _PNG_NAME = "diagramm.png"
    _SAVE_TITLE = "Datenauswertung speichern"
    _MIME = None
    _LOAD = {"downloads": True, "open": True, "code": True, "clipboard": True, "nit": True,
             "save": False}
    _NO_CONNECTION = "bitte NIT_Code neu starten."
    _HINT = "„Als Python-Code“ öffnet das Programm in einem neuen Editor-Tab."
    _OFFLINE_HINT = "Offline-Version der Datenauswertung (keine Verbindung zu statplot.mint-checker.de)."
    _ONLINE_TIMEOUT_MS = 8000

    def __init__(self, parent=None, sketchbook_dir=None):
        # Vor super().__init__: dort wird die Host-Seite schon geladen.
        self._ORIGIN = STATPLOT_ORIGIN
        self._URL = STATPLOT_URL
        self._offline = False
        self._code_sink = None
        self._last_load: dict | None = None      # nach „Neu laden“ erneut schicken
        self._csv_dir: str | None = None
        super().__init__(parent, sketchbook_dir=sketchbook_dir)
        self.resize(1240, 840)
        # Gibt es hier nie (save:false) – nur Platz in der Werkzeugleiste.
        self._act_save_png.setVisible(False)

    def _load_host_page(self):
        super()._load_host_page()
        if not self._offline:
            QTimer.singleShot(self._ONLINE_TIMEOUT_MS, self._fall_back_offline)

    def _fall_back_offline(self):
        """Online-Version meldet sich nicht → mitgelieferte Kopie laden."""
        if self._connected or self._offline or self._view is None:
            return
        origin = _local_origin()
        if origin is None:
            self._set_status("Keine Verbindung zu statplot.mint-checker.de, und die "
                             "Offline-Version fehlt in dieser Installation "
                             "(nit_code/assets/statplot).", kind="error")
            return
        self._offline = True
        self._ORIGIN = origin
        self._URL = origin + "/index.html?embed=1"
        self._load_host_page()

    def set_code_sink(self, sink):
        """Callback, der erzeugten Python-Code in einen neuen Editor-Tab übernimmt."""
        self._code_sink = sink

    def load_csv(self, path: str):
        """CSV-Datei laden – auch bevor die Seite fertig geladen ist."""
        try:
            text = read_csv_text(path)
        except OSError as e:
            self._set_status(f"Datei konnte nicht gelesen werden: {e}", kind="error")
            return
        self._csv_dir = os.path.dirname(path)
        self._last_load = {"action": "load", "csv": text,
                           "name": os.path.basename(path), "path": path}
        if self._connected:
            self._send(self._last_load)

    # ── Ereignisse der Seite ─────────────────────────────────────────────
    def _on_ready(self):
        if self._offline:
            self._set_status(self._OFFLINE_HINT)
        if self._last_load:
            self._send(self._last_load)

    def _on_embed_event(self, event: dict):
        kind = event.get("event")
        if kind == "open":
            self._choose_csv()
        elif kind == "code":
            code = str(event.get("code") or "")
            if code and self._code_sink is not None:
                self._code_sink(code)
                self._set_status("✓ Python-Code in einem neuen Editor-Tab geöffnet.", kind="success")
        elif kind == "copy":
            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(str(event.get("text") or ""))

    def _choose_csv(self):
        start = self._csv_dir if self._csv_dir and os.path.isdir(self._csv_dir) else self._start_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, "CSV-Datei öffnen", start,
            "CSV-Dateien (*.csv *.tsv *.txt);;Alle Dateien (*)",
        )
        if path:
            self.load_csv(path)
