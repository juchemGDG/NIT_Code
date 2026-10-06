"""Datenauswertung (CSV) – StatPlot eingebettet wie PAP-/IBD-Editor.

StatPlot (github.com/juchemGDG/StatPlot) ist die frühere Datenauswertung von
NIT_Code als Web-App: Diagramme, Kennwerte, Häufigkeiten, Statistik-Tests und
Python-Code-Export. Dieselbe Seite läuft auf statplot.mint-checker.de, als
Desktop-App und hier im iframe mit ``?embed=1``.

Anders als PAP/IBD kommt die Seite nicht aus dem Netz: Eine Kopie liegt in
``nit_code/assets/statplot`` (abgleichen mit release/scripts/sync_statplot.sh)
und wird über einen kleinen lokalen HTTP-Server auf 127.0.0.1 ausgeliefert.
So funktioniert die Datenauswertung wie bisher ohne Internet, und die Host-Seite
bekommt eine echte Origin für postMessage (siehe pap_editor.py).

Zusätzlich zum PAP-Protokoll (Schalter in ``_LOAD``):

* open:true      – „CSV öffnen“ meldet 'open'; wir zeigen den Dateidialog im
                   Sketchbook und schicken load + csv/name/path zurück.
* code:true      – „In neuen Editor-Tab“ meldet 'code' → ``set_code_sink``.
* clipboard:true – Kopieren läuft über Qt ('copy'), im iframe ist die
                   Zwischenablage sonst oft gesperrt.
* nit:true       – der Python-Code verweist auf NIT_Codes Paket-Menü.
"""
import functools
import http.server
import os
import socketserver
import threading
from pathlib import Path

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QFileDialog

from .config import asset_path
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
    _LOAD = {"downloads": True, "open": True, "code": True, "clipboard": True, "nit": True}
    _NO_CONNECTION = "bitte NIT_Code neu starten."
    _HINT = ("„In Projekt übernehmen“ legt das Diagramm als Bild in die Zwischenablage, "
             "„Als Python-Code“ öffnet das Programm in einem neuen Editor-Tab.")

    def __init__(self, parent=None, sketchbook_dir=None):
        origin = _local_origin()
        # Vor super().__init__: dort wird die Host-Seite schon geladen.
        self._ORIGIN = origin or "http://127.0.0.1"
        self._URL = self._ORIGIN + "/index.html?embed=1"
        self._code_sink = None
        self._last_load: dict | None = None      # nach „Neu laden“ erneut schicken
        self._csv_dir: str | None = None
        super().__init__(parent, sketchbook_dir=sketchbook_dir)
        self.resize(1240, 840)
        if origin is None:
            self._set_status("Die Datenauswertung fehlt in dieser Installation "
                             "(nit_code/assets/statplot).", kind="error")

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
