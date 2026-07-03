"""Block-Editor (Blockly) als Extrafenster – erzeugt Python/MicroPython-Code.

Blockbasiertes Programmieren (wie Snap!/Scratch) für Einsteiger:innen. Die
Blöcke werden über einen eingebetteten Blockly-Editor (offline, im WebEngine)
zusammengesteckt und per Knopfdruck in lesbaren Python-Code umgewandelt, der in
einem neuen Editor-Tab landet und ganz normal ausgeführt werden kann.
"""
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QToolBar, QFileDialog, QMessageBox,
)
from PyQt6.QtGui import QAction

try:
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except Exception:
    HAS_WEBENGINE = False

from .config import THEME, asset_path as _asset_path


class BlockEditorWindow(QMainWindow):
    """Eigenständiges Fenster mit Blockly-Editor und 'In Python umwandeln'-Aktion."""

    # Vom Nutzer ausgelöste Code-Erzeugung → Hauptfenster legt neuen Tab an
    code_generated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NIT Block-Editor")
        self.resize(1000, 680)
        self._editor_html = _asset_path("blockly/editor.html")
        self._page_ready = False
        self._pending_state = None   # State, der vor dem Laden der Seite kam
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        tb = QToolBar("Aktionen")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._act_to_python = QAction("▶  In Python umwandeln", self)
        self._act_to_python.setToolTip("Erzeugt Python-Code aus den Blöcken (neuer Tab)")
        self._act_to_python.triggered.connect(self._emit_python)
        tb.addAction(self._act_to_python)
        tb.addSeparator()

        self._act_save = QAction("💾  Blöcke speichern", self)
        self._act_save.triggered.connect(self._save_blocks)
        tb.addAction(self._act_save)

        self._act_load = QAction("📂  Blöcke laden", self)
        self._act_load.triggered.connect(self._load_blocks)
        tb.addAction(self._act_load)
        tb.addSeparator()

        self._act_clear = QAction("🗑  Leeren", self)
        self._act_clear.triggered.connect(self._clear_blocks)
        tb.addAction(self._act_clear)

        self._view = None
        if HAS_WEBENGINE and self._editor_html:
            # Absichtlich in try/except: Auf manchen Schulrechnern (Terminal-
            # server, stark eingeschränkte Profile) schlägt die WebEngine-
            # Initialisierung fehl – dann Fallback-Hinweis statt Absturz.
            try:
                # Off-the-record-Profil (kein Name → keine Cache-/Profildaten
                # auf der Platte). Der Editor braucht keine Persistenz
                # (Speichern läuft über .nitblocks-Dateien) – und auf Servern
                # mit gesperrtem/umgeleitetem %LOCALAPPDATA% verhindert das
                # Schreibfehler beim Anlegen des Chromium-Profils.
                # Reihenfolge: Profil als erstes Kind, View danach – Qt löscht
                # Kinder rückwärts, also View (+ Page) vor dem Profil.
                self._profile = QWebEngineProfile(self)
                self._view = QWebEngineView(self)
                page = QWebEnginePage(self._profile, self._view)
                self._view.setPage(page)
                # Stürzt der Chromium-Renderprozess ab (GPU-/Treiberprobleme),
                # die Seite einmal neu laden statt ein schwarzes Fenster zu zeigen.
                self._render_retry_done = False
                page.renderProcessTerminated.connect(self._on_render_crashed)
                self._view.loadFinished.connect(self._on_page_loaded)
                self._view.setUrl(QUrl.fromLocalFile(str(self._editor_html)))
                self.setCentralWidget(self._view)
            except Exception:
                self._view = None
        if self._view is None:
            self.setCentralWidget(self._fallback_widget())
            for act in (self._act_to_python, self._act_save, self._act_load, self._act_clear):
                act.setEnabled(False)

    def _fallback_widget(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        msg = ("Der Block-Editor ist nicht verfügbar.\n\n"
               "Benötigt PyQt6-WebEngine und die Blockly-Dateien im Ordner "
               "nit_code/assets/blockly/.")
        if not HAS_WEBENGINE:
            msg += "\n\n→ PyQt6-WebEngine fehlt."
        if not self._editor_html:
            msg += "\n\n→ blockly/editor.html wurde nicht gefunden."
        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color:{THEME['text']}; font-size:13px; padding:24px;")
        lay.addWidget(lbl)
        return w

    def _on_render_crashed(self, _status, _exit_code):
        """Chromium-Renderprozess abgestürzt (z. B. GPU-Problem auf Servern).

        Einmal automatisch neu laden – beim zweiten Absturz einen Hinweis mit
        dem Software-Rendering-Workaround zeigen, statt still zu scheitern.
        """
        if not self._render_retry_done:
            self._render_retry_done = True
            if self._view is not None:
                self._view.reload()
            return
        QMessageBox.warning(
            self, "Block-Editor",
            "Die Anzeige des Block-Editors ist abgestürzt (Grafik-Problem).\n\n"
            "Unter Windows ist Software-Rendering bereits automatisch aktiv.\n"
            "Falls der Fehler weiter auftritt, NIT_Code neu starten.\n\n"
            "Optionaler Override:\n"
            "    NIT_SOFTWARE_RENDER=1\n"
            "(erzwingt Software-Rendering vor dem Start).",
        )

    # ── Laden eines Block-States (z. B. aus "Coder → Blockly") ────────────────
    def _on_page_loaded(self, ok: bool):
        self._page_ready = bool(ok)
        if self._page_ready and self._pending_state is not None:
            state, self._pending_state = self._pending_state, None
            self._apply_state(state)

    def load_block_state(self, state: dict):
        """Lädt einen Blockly-Serialisierungs-State in den Workspace.

        Funktioniert auch, wenn die Seite noch lädt (wird dann nachgeholt).
        """
        if not self._view:
            return
        if self._page_ready:
            self._apply_state(state)
        else:
            self._pending_state = state

    def _apply_state(self, state: dict):
        import json
        self._view.page().runJavaScript("loadJson(%s);" % json.dumps(json.dumps(state)))

    # ── Aktionen ──────────────────────────────────────────────────────────────
    def _emit_python(self):
        if not self._view:
            return
        def _done(code: str):
            code = (code or "").strip()
            if not code:
                QMessageBox.information(
                    self, "Keine Blöcke",
                    "Es sind noch keine Blöcke vorhanden, aus denen Code "
                    "erzeugt werden könnte.\n\nZieh links Blöcke in die Fläche.")
                return
            self.code_generated.emit(code)
        self._view.page().runJavaScript("getPython();", _done)

    def _save_blocks(self):
        if not self._view:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Block-Programm speichern", "programm.nitblocks",
            "NIT-Blöcke (*.nitblocks);; Alle Dateien (*)")
        if not path:
            return
        def _done(xml: str):
            try:
                Path(path).write_text(xml or "", encoding="utf-8")
            except OSError as exc:
                QMessageBox.warning(self, "Fehler",
                                    f"Konnte nicht gespeichert werden:\n{exc}")
        self._view.page().runJavaScript("getXml();", _done)

    def _load_blocks(self):
        if not self._view:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Block-Programm laden", "",
            "NIT-Blöcke (*.nitblocks);; Alle Dateien (*)")
        if not path:
            return
        try:
            xml = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Fehler", f"Konnte nicht geladen werden:\n{exc}")
            return
        import json
        self._view.page().runJavaScript(f"loadXml({json.dumps(xml)});")

    def _clear_blocks(self):
        if not self._view:
            return
        if QMessageBox.question(
            self, "Leeren", "Alle Blöcke entfernen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._view.page().runJavaScript("clearWorkspace();")
