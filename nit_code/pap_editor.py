"""PAP-Editor (Programmablaufplan) und IBD-Editor (Informationsfluss) als Extrafenster – Ergebnis als PNG in die Zwischenablage.

Gezeichnet wird auf pap.mint-checker.de. Die Seite kennt einen Embed-Modus
(`?embed=1`), der sich aber nur einschaltet, wenn sie in einem iframe steckt
(`window.parent !== window`). Deshalb wird hier nicht die Seite selbst geladen,
sondern eine winzige lokale Host-Seite, die den Editor in einem iframe einbettet.

Protokoll des Editors (window.postMessage, Nachrichten sind Objekte):

    Editor → Host:  {source:'pap-editor', event:'ready'}
    Host → Editor:  {target:'pap-editor', action:'load', diagram:<JSON|null>, title?}
    Editor → Host:  {source:'pap-editor', event:'save', diagram:<JSON>, svg:<SVG-Text>}
    Editor → Host:  {source:'pap-editor', event:'exit'}

Zwei Dinge sind dabei wichtig:

* Der Editor antwortet ausschließlich an die Origin, die er aus der
  `load`-Nachricht gelernt hat. Ohne diesen Handshake meldet sein Button nur
  "Keine Verbindung zur einbettenden Seite". Eine `file://`- oder
  `about:blank`-Seite hätte die Origin "null" – kein gültiges targetOrigin für
  postMessage. Die Host-Seite wird deshalb per setHtml() mit der Editor-Origin
  als Base-URL geladen und ist damit same-origin zum iframe.
* Zurück kommt SVG, kein PNG. Gerastert wird im Browser (SVG → <img> → Canvas →
  PNG), nicht mit QtSvg: dessen SVG-Tiny-Renderer kennt `<marker>` nicht und
  würde alle Pfeilspitzen des Ablaufplans verschlucken.

Der IBD-Editor spricht dasselbe Protokoll mit source/target 'ibd-editor'
(Unterklasse IbdEditorWindow). Die Datenauswertung (StatPlot, siehe
statplot_window.py) nutzt dieselbe Host-Seite mit zusätzlichen Nachrichten:
Die Schalter der ersten load-Nachricht kommen aus ``_LOAD``, weitere
Nachrichten an die Seite schickt ``_send()``, und Ereignisse wie 'open',
'code' oder 'copy' landen in ``_on_embed_event()``.

Das fertige PNG holt die Python-Seite per runJavaScript() ab (kurzes Polling,
solange das Fenster offen ist) und legt es in die Zwischenablage.
"""
import base64
import json
import os
from pathlib import Path

from PyQt6.QtCore import Qt, QByteArray, QMimeData, QTimer, QUrl
from PyQt6.QtGui import QAction, QGuiApplication, QImage
from PyQt6.QtWidgets import (
    QFileDialog, QLabel, QMainWindow, QMessageBox, QToolBar, QVBoxLayout, QWidget,
)

try:
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except Exception:
    HAS_WEBENGINE = False

from .config import (
    IBD_EDITOR_ORIGIN, IBD_EDITOR_URL, PAP_EDITOR_ORIGIN, PAP_EDITOR_URL, THEME,
)
from .pap_import import PAP_MIME

# Auflösung des erzeugten PNG (2× = scharf genug für Arbeitsblätter/Word)
_PNG_SCALE = 2

# Host-Seite mit dem eingebetteten Editor. Platzhalter werden per replace()
# ersetzt (kein format()/%, damit die vielen JS-Klammern nicht escaped werden
# müssen).
_HOST_HTML = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  html, body { margin: 0; padding: 0; height: 100%; background: #ffffff; }
  iframe { display: block; width: 100%; height: 100%; border: 0; }
</style>
</head>
<body>
<iframe id="editor" src="__PAP_URL__"></iframe>
<script>
(function () {
  var ORIGIN = '__PAP_ORIGIN__';
  var SCALE  = __PNG_SCALE__;
  var frame  = document.getElementById('editor');
  var pendingDiagram = null;   // Diagrammdaten des letzten „save“, wandern zusammen mit dem PNG zurück

  // Puffer für die Python-Seite; __nitPapTake() holt ihn ab und leert ihn.
  var out = null;
  function reset() { out = { ready: false, png: null, diagram: null, download: null, error: null, exit: false, events: [] }; }
  reset();

  window.__nitEmbedTake = function () {
    var o = out;
    if (!o.ready && !o.png && !o.download && !o.error && !o.exit && !o.events.length) return null;
    reset();
    return JSON.stringify(o);
  };

  // Weitere Nachrichten der Python-Seite an die eingebettete Seite
  window.__nitEmbedSend = function (msg) {
    var m = { target: '__SOURCE__' };
    for (var k in msg) m[k] = msg[k];
    frame.contentWindow.postMessage(m, ORIGIN);
  };

  function svgToPng(svg) {
    var img = new Image();
    img.onload = function () {
      try {
        var w = Math.max(1, Math.round((img.naturalWidth  || 800) * SCALE));
        var h = Math.max(1, Math.round((img.naturalHeight || 600) * SCALE));
        var canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        var ctx = canvas.getContext('2d');
        // Weißer Grund: sonst wird der transparente Bereich beim Einfügen in
        // Word/LibreOffice je nach Ziel schwarz.
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        out.png = canvas.toDataURL('image/png');
        out.diagram = pendingDiagram;
      } catch (e) {
        out.error = 'Das Diagramm konnte nicht in ein PNG umgewandelt werden (' + e.message + ').';
      }
    };
    img.onerror = function () {
      out.error = 'Das Diagramm konnte nicht gelesen werden.';
    };
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }

  window.addEventListener('message', function (e) {
    // Nur Nachrichten aus unserem iframe annehmen (strenger als ein
    // Origin-Vergleich und unabhängig davon, wie Qt die Origin serialisiert).
    if (!frame || e.source !== frame.contentWindow) return;
    var m = e.data;
    if (!m || typeof m !== 'object' || m.source !== '__SOURCE__') return;

    if (m.event === 'ready') {
      // Pflicht-Handshake: erst dadurch kennt der Editor unsere Origin und
      // kann das Diagramm später überhaupt zurückschicken.
      var load = __LOAD__;
      load.target = '__SOURCE__';
      load.action = 'load';
      frame.contentWindow.postMessage(load, ORIGIN);
      out.ready = true;
    } else if (m.event === 'save') {
      pendingDiagram = (m.diagram === undefined) ? null : m.diagram;
      if (m.svg) svgToPng(m.svg);
      else out.error = 'Der Ablaufplan ist noch leer – bitte erst Bausteine einfügen.';
    } else if (m.event === 'download') {
      // "Speichern" und die Exporte (PNG/JPG/SVG) laufen im iframe nicht als
      // Browser-Download; die Seite reicht die fertige Datei stattdessen an
      // uns durch (wir haben das per downloads:true angefordert).
      if (!m.blob) { out.error = 'Es kamen keine Daten zum Speichern an.'; return; }
      (function (name, mime) {
        var reader = new FileReader();
        reader.onload = function () {
          var s = String(reader.result), i = s.indexOf(',');
          out.download = { name: name, mime: mime, b64: i >= 0 ? s.slice(i + 1) : '' };
        };
        reader.onerror = function () { out.error = 'Die Datei konnte nicht gelesen werden.'; };
        reader.readAsDataURL(m.blob);
      })(m.name || 'diagramm', m.mime || '');
    } else if (m.event === 'exit') {
      out.exit = true;
    } else if (m.event === 'open' || m.event === 'code' || m.event === 'copy') {
      // Nur Text-Felder weiterreichen (JSON-tauglich)
      out.events.push({ event: m.event, code: String(m.code || ''), title: String(m.title || ''),
                        text: String(m.text || '') });
    }
  });
})();
</script>
</body>
</html>
"""


def _host_html(url: str = PAP_EDITOR_URL, origin: str = PAP_EDITOR_ORIGIN,
               source: str = "pap-editor", title: str = "PAP-Editor",
               load: dict | None = None) -> str:
    if load is None:
        load = {"diagram": None, "title": "NIT_Code", "downloads": True}
    return (_HOST_HTML
            .replace("__PAP_URL__", url)
            .replace("__PAP_ORIGIN__", origin)
            .replace("__SOURCE__", source)
            .replace("__TITLE__", title)
            .replace("__LOAD__", json.dumps(load))
            .replace("__PNG_SCALE__", str(_PNG_SCALE)))


class PapEditorWindow(QMainWindow):
    """Eigenständiges Fenster: Programmablaufplan zeichnen, Ergebnis als PNG kopieren."""

    # Pro Editor überschreibbar (siehe IbdEditorWindow)
    _URL = PAP_EDITOR_URL
    _ORIGIN = PAP_EDITOR_ORIGIN
    _SOURCE = "pap-editor"            # source/target-Name im postMessage-Protokoll
    _NAME = "PAP-Editor"
    _WINDOW_TITLE = "NIT PAP-Editor"
    _HOST = "pap.mint-checker.de"
    _PNG_NAME = "diagramm.png"
    _SAVE_TITLE = "Ablaufplan speichern"
    _MIME = PAP_MIME                  # None = keine Diagrammdaten in die Zwischenablage
    # Inhalt der ersten load-Nachricht (Fähigkeiten des Hosts)
    _LOAD = {"diagram": None, "title": "NIT_Code", "downloads": True}
    _NO_CONNECTION = "Internetverbindung/Proxy prüfen."

    _HINT = ("„In Projekt übernehmen“ legt den Plan in die Zwischenablage – "
             "für Seiten, die kein Einfügen erlauben (z. B. AIS-Chat), danach "
             "„Bild speichern“ benutzen.")

    def __init__(self, parent=None, sketchbook_dir=None):
        super().__init__(parent)
        self.setWindowTitle(self._WINDOW_TITLE)
        self.resize(1100, 760)
        # Callable, damit ein spaeter in den Einstellungen geaenderter
        # Sketchbook-Ordner automatisch mitgenommen wird.
        self._sketchbook_dir = sketchbook_dir
        # Zuletzt übernommenes PNG: AIS-Chat & Co. nehmen kein Bild aus der
        # Zwischenablage an, deshalb muss es auch als Datei sicherbar sein.
        self._last_png: bytes | None = None
        self._last_png_saved = False
        self._connected = False
        self._render_retry_done = False
        self._build_ui()

        # Der Klick passiert in einer fremden Seite; abgeholt wird das Ergebnis
        # deshalb per kurzem Polling, solange das Fenster offen ist.
        self._poll = QTimer(self)
        self._poll.setInterval(400)
        self._poll.timeout.connect(self._poll_result)

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        tb = QToolBar("Aktionen")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._act_reload = QAction("↻  Neu laden", self)
        self._act_reload.setToolTip("Editor-Seite neu laden (verwirft den Ablaufplan)")
        self._act_reload.triggered.connect(self._reload)
        tb.addAction(self._act_reload)

        self._act_save_png = QAction("💾  Bild speichern …", self)
        self._act_save_png.setToolTip(
            "Das übernommene Diagramm als PNG-Datei speichern "
            "(für Seiten, die kein Einfügen aus der Zwischenablage erlauben)"
        )
        self._act_save_png.setEnabled(False)
        self._act_save_png.triggered.connect(self._save_last_png)
        tb.addAction(self._act_save_png)
        tb.addSeparator()

        self._status = QLabel("Editor wird geladen …")
        self._status.setWordWrap(False)
        tb.addWidget(self._status)

        self._view = None
        if HAS_WEBENGINE:
            # Wie im Block-Editor bewusst in try/except: auf stark
            # eingeschränkten Schulrechnern schlägt die WebEngine-Init
            # gelegentlich fehl – dann Hinweis statt Absturz.
            try:
                # Off-the-record-Profil (kein Name → keine Profildaten auf der
                # Platte). Profil als erstes Kind, View danach: Qt löscht
                # Kinder rückwärts, also View (+ Page) vor dem Profil.
                self._profile = QWebEngineProfile(self)
                self._view = QWebEngineView(self)
                page = QWebEnginePage(self._profile, self._view)
                self._view.setPage(page)
                page.renderProcessTerminated.connect(self._on_render_crashed)
                self.setCentralWidget(self._view)
                self._load_host_page()
            except Exception:
                self._view = None
        if self._view is None:
            self.setCentralWidget(self._fallback_widget())
            self._act_reload.setEnabled(False)
        self.apply_theme()

    def _fallback_widget(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel(
            f"Der {self._NAME} ist nicht verfügbar.\n\n"
            "Er benötigt PyQt6-WebEngine:\n\n"
            "    pip install PyQt6-WebEngine"
        )
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color:{THEME['text']}; font-size:13px; padding:24px;")
        lay.addWidget(lbl)
        return w

    def _load_host_page(self):
        """Host-Seite laden – Base-URL = Editor-Origin, siehe Modul-Docstring."""
        self._connected = False
        self._view.setHtml(
            _host_html(self._URL, self._ORIGIN, self._SOURCE, self._NAME, self._LOAD),
            QUrl(self._ORIGIN + "/"))
        self._set_status("Editor wird geladen …")
        # Kommt nach dieser Zeit kein 'ready', steckt meist Netz/Proxy dahinter.
        QTimer.singleShot(20000, self._check_connected)

    def _reload(self):
        if self._view is not None:
            self._load_host_page()

    def _check_connected(self):
        if self._connected or self._view is None or not self.isVisible():
            return
        self._set_status(
            f"Keine Verbindung zu {self._HOST} – {self._NO_CONNECTION}",
            kind="error",
        )

    def _on_render_crashed(self, _status, _exit_code):
        """Chromium-Renderprozess abgestürzt (typisch: GPU-Problem auf Servern)."""
        if not self._render_retry_done:
            self._render_retry_done = True
            self._reload()
            return
        QMessageBox.warning(
            self, self._NAME,
            f"Die Anzeige des {self._NAME} ist abgestürzt (Grafik-Problem).\n\n"
            "Unter Windows ist Software-Rendering bereits automatisch aktiv.\n"
            "Falls der Fehler weiter auftritt, NIT_Code neu starten.\n\n"
            "Optionaler Override:\n"
            "    NIT_SOFTWARE_RENDER=1\n"
            "(erzwingt Software-Rendering vor dem Start).",
        )

    # ── Ergebnis abholen ─────────────────────────────────────────────────────
    def showEvent(self, ev):
        super().showEvent(ev)
        if self._view is not None:
            self._poll.start()

    def hideEvent(self, ev):
        self._poll.stop()
        super().hideEvent(ev)

    def closeEvent(self, ev):
        # Ein übernommenes Bild liegt nur in der Zwischenablage – die überlebt
        # zwar das Schließen, geht aber beim nächsten Kopieren verloren.
        if self._last_png and not self._last_png_saved:
            antwort = QMessageBox.question(
                self, self._NAME,
                "Das übernommene Diagramm liegt bisher nur in der Zwischenablage.\n\n"
                "Soll es zusätzlich als PNG-Datei gespeichert werden?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if antwort == QMessageBox.StandardButton.Cancel:
                ev.ignore()
                return
            if antwort == QMessageBox.StandardButton.Save and not self._save_last_png():
                # Speichern abgebrochen → Fenster offen lassen, nichts verlieren.
                ev.ignore()
                return
        self._poll.stop()
        super().closeEvent(ev)

    def _poll_result(self):
        if self._view is None:
            return
        self._view.page().runJavaScript(
            "window.__nitEmbedTake ? window.__nitEmbedTake() : null", self._on_result
        )

    def _on_result(self, payload):
        if not payload:
            return
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            return
        if data.get("ready"):
            self._connected = True
            self._set_status(self._HINT)
            self._on_ready()
        for event in data.get("events") or []:
            if isinstance(event, dict):
                self._on_embed_event(event)
        if data.get("error"):
            self._set_status(str(data["error"]), kind="error")
        if data.get("png"):
            self._copy_png(str(data["png"]), data.get("diagram"))
        if data.get("download"):
            self._save_download(data["download"])
        if data.get("exit"):
            self.close()

    def _on_ready(self):
        """Die eingebettete Seite ist verbunden (Unterklassen: Daten nachschieben)."""

    def _on_embed_event(self, event: dict):
        """Weitere Ereignisse der Seite ('open', 'code', 'copy') – siehe Unterklassen."""

    def _send(self, msg: dict):
        """Nachricht an die eingebettete Seite (target wird ergänzt)."""
        if self._view is not None:
            self._view.page().runJavaScript(
                f"window.__nitEmbedSend && window.__nitEmbedSend({json.dumps(msg)})")

    def _copy_png(self, data_url: str, diagram=None):
        prefix = "data:image/png;base64,"
        if not data_url.startswith(prefix):
            self._set_status("Unerwartetes Bildformat vom Editor erhalten.", kind="error")
            return
        try:
            raw = base64.b64decode(data_url[len(prefix):], validate=True)
        except Exception:
            self._set_status("Das Bild konnte nicht dekodiert werden.", kind="error")
            return
        img = QImage()
        if not img.loadFromData(raw, "PNG") or img.isNull():
            self._set_status("Das Bild konnte nicht gelesen werden.", kind="error")
            return
        # Bild UND rohe PNG-Bytes anbieten: manche Ziele (Browser, GIMP) fragen
        # gezielt nach image/png, Office-Programme nehmen das Bildformat.
        mime = QMimeData()
        mime.setImageData(img)
        mime.setData("image/png", QByteArray(raw))
        # Diagrammdaten mitgeben: Der Code-Generator liest daraus den Ablauf
        # verlustfrei, ohne das Bild erkennen zu müssen.
        if diagram and self._MIME:
            payload = diagram if isinstance(diagram, str) else json.dumps(diagram, ensure_ascii=False)
            mime.setData(self._MIME, QByteArray(payload.encode("utf-8")))
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            self._set_status("Auf die Zwischenablage konnte nicht zugegriffen werden.", kind="error")
            return
        clipboard.setMimeData(mime)
        self._last_png = raw
        self._last_png_saved = False
        self._act_save_png.setEnabled(True)
        self._set_status(
            f"✓ Als PNG in der Zwischenablage ({img.width()}×{img.height()} px) – "
            "mit Strg+V / Cmd+V einfügen oder „Bild speichern“."
            + (" Der Code-Generator kann den Ablauf direkt daraus importieren."
               if self._MIME else ""),
            kind="success",
        )

    def _start_dir(self) -> str:
        """Startordner des Speichern-Dialogs: der Sketchbook-Ordner."""
        try:
            folder = self._sketchbook_dir() if callable(self._sketchbook_dir) else None
        except Exception:
            folder = None
        if folder and os.path.isdir(folder):
            return folder
        return str(Path.home())

    def _save_download(self, item: dict):
        """Speichert eine Datei, die der Editor an uns durchgereicht hat.

        Im iframe scheitern Browser-Downloads; die Seite schickt "Speichern"
        und die Exporte deshalb als download-Event an uns (angefordert per
        downloads:true in der load-Nachricht).
        """
        name = str(item.get("name") or "diagramm")
        try:
            raw = base64.b64decode(str(item.get("b64") or ""), validate=True)
        except Exception:
            self._set_status("Die Datei konnte nicht dekodiert werden.", kind="error")
            return
        if not raw:
            self._set_status("Es kamen keine Daten zum Speichern an.", kind="error")
            return

        self._write_file(name, raw)

    def _save_last_png(self) -> bool:
        """Speichert das zuletzt übernommene Diagramm als PNG-Datei.

        Nötig, weil manche Ziele (z. B. der AIS-Chat) kein Bild aus der
        Zwischenablage annehmen und eine Datei zum Hochladen brauchen.
        """
        if not self._last_png:
            self._set_status("Es wurde noch kein Diagramm übernommen.", kind="error")
            return False
        if self._write_file(self._PNG_NAME, self._last_png):
            self._last_png_saved = True
            return True
        return False

    def _write_file(self, name: str, raw: bytes) -> bool:
        """Speichern-Dialog (vorbelegt im Sketchbook-Ordner) und Datei schreiben."""
        suffix = Path(name).suffix.lower()
        beschreibung = {
            ".json": "PAP-Diagramm",
            ".png": "PNG-Bild",
            ".jpg": "JPEG-Bild",
            ".jpeg": "JPEG-Bild",
            ".svg": "SVG-Grafik",
            ".py": "Python-Programm",
        }.get(suffix, "Datei")
        pattern = f"{beschreibung} (*{suffix});;Alle Dateien (*)" if suffix else "Alle Dateien (*)"

        path, _ = QFileDialog.getSaveFileName(
            self, self._SAVE_TITLE, os.path.join(self._start_dir(), name), pattern
        )
        if not path:
            self._set_status("Speichern abgebrochen.")
            return False
        if suffix and not path.lower().endswith(suffix):
            path += suffix
        try:
            Path(path).write_bytes(raw)
        except OSError as e:
            self._set_status(f"Speichern fehlgeschlagen: {e}", kind="error")
            return False
        self._set_status(f"✓ Gespeichert: {path}", kind="success")
        return True

    # ── Darstellung ──────────────────────────────────────────────────────────
    def _set_status(self, text: str, kind: str = "info"):
        self._status_kind = kind
        self._status.setText(text)
        self._style_status()

    def _style_status(self):
        color = {
            "error": THEME["error"],
            "success": THEME["success"],
        }.get(getattr(self, "_status_kind", "info"), THEME["text_dim"])
        self._status.setStyleSheet(f"color:{color}; padding:0 8px;")

    def apply_theme(self):
        """Theme-Wechsel aus den Einstellungen (die Editor-Seite selbst ist hell)."""
        self._style_status()


class IbdEditorWindow(PapEditorWindow):
    """Informations-Blockdiagramm (ibd.mint-checker.de) – gleiches Protokoll wie der PAP-Editor."""

    _URL = IBD_EDITOR_URL
    _ORIGIN = IBD_EDITOR_ORIGIN
    _SOURCE = "ibd-editor"
    _NAME = "IBD-Editor"
    _WINDOW_TITLE = "NIT IBD-Editor"
    _HOST = "ibd.mint-checker.de"
    _PNG_NAME = "informationsfluss.png"
    _SAVE_TITLE = "Informationsfluss speichern"
    _MIME = None
    _HINT = ("„In Projekt übernehmen“ legt das Diagramm in die Zwischenablage – "
             "für Seiten, die kein Einfügen erlauben (z. B. AIS-Chat), danach "
             "„Bild speichern“ benutzen.")
