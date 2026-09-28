"""PAP-Editor (Programmablaufplan) als Extrafenster – Ergebnis als PNG in die Zwischenablage.

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

Das fertige PNG holt die Python-Seite per runJavaScript() ab (kurzes Polling,
solange das Fenster offen ist) und legt es in die Zwischenablage.
"""
import base64
import json

from PyQt6.QtCore import Qt, QByteArray, QMimeData, QTimer, QUrl
from PyQt6.QtGui import QAction, QGuiApplication, QImage
from PyQt6.QtWidgets import QLabel, QMainWindow, QMessageBox, QToolBar, QVBoxLayout, QWidget

try:
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except Exception:
    HAS_WEBENGINE = False

from .config import PAP_EDITOR_ORIGIN, PAP_EDITOR_URL, THEME

# Auflösung des erzeugten PNG (2× = scharf genug für Arbeitsblätter/Word)
_PNG_SCALE = 2

# Host-Seite mit dem eingebetteten Editor. Platzhalter werden per replace()
# ersetzt (kein format()/%, damit die vielen JS-Klammern nicht escaped werden
# müssen).
_HOST_HTML = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>PAP-Editor</title>
<style>
  html, body { margin: 0; padding: 0; height: 100%; background: #ffffff; }
  iframe { display: block; width: 100%; height: 100%; border: 0; }
</style>
</head>
<body>
<iframe id="pap" src="__PAP_URL__"></iframe>
<script>
(function () {
  var ORIGIN = '__PAP_ORIGIN__';
  var SCALE  = __PNG_SCALE__;
  var frame  = document.getElementById('pap');

  // Puffer für die Python-Seite; __nitPapTake() holt ihn ab und leert ihn.
  var out = null;
  function reset() { out = { ready: false, png: null, error: null, exit: false }; }
  reset();

  window.__nitPapTake = function () {
    var o = out;
    if (!o.ready && !o.png && !o.error && !o.exit) return null;
    reset();
    return JSON.stringify(o);
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
    if (!m || typeof m !== 'object' || m.source !== 'pap-editor') return;

    if (m.event === 'ready') {
      // Pflicht-Handshake: erst dadurch kennt der Editor unsere Origin und
      // kann das Diagramm später überhaupt zurückschicken.
      frame.contentWindow.postMessage(
        { target: 'pap-editor', action: 'load', diagram: null, title: 'NIT_Code' },
        ORIGIN
      );
      out.ready = true;
    } else if (m.event === 'save') {
      if (m.svg) svgToPng(m.svg);
      else out.error = 'Der Ablaufplan ist noch leer – bitte erst Bausteine einfügen.';
    } else if (m.event === 'exit') {
      out.exit = true;
    }
  });
})();
</script>
</body>
</html>
"""


def _host_html() -> str:
    return (_HOST_HTML
            .replace("__PAP_URL__", PAP_EDITOR_URL)
            .replace("__PAP_ORIGIN__", PAP_EDITOR_ORIGIN)
            .replace("__PNG_SCALE__", str(_PNG_SCALE)))


class PapEditorWindow(QMainWindow):
    """Eigenständiges Fenster: Programmablaufplan zeichnen, Ergebnis als PNG kopieren."""

    _HINT = ("Ablaufplan zeichnen und oben im Editor auf "
             "„In Projekt übernehmen“ klicken – das Diagramm landet dann als "
             "Bild in der Zwischenablage.")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NIT PAP-Editor")
        self.resize(1100, 760)
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
            "Der PAP-Editor ist nicht verfügbar.\n\n"
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
        self._view.setHtml(_host_html(), QUrl(PAP_EDITOR_ORIGIN + "/"))
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
            "Keine Verbindung zu pap.mint-checker.de – Internetverbindung/Proxy prüfen.",
            kind="error",
        )

    def _on_render_crashed(self, _status, _exit_code):
        """Chromium-Renderprozess abgestürzt (typisch: GPU-Problem auf Servern)."""
        if not self._render_retry_done:
            self._render_retry_done = True
            self._reload()
            return
        QMessageBox.warning(
            self, "PAP-Editor",
            "Die Anzeige des PAP-Editors ist abgestürzt (Grafik-Problem).\n\n"
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
        self._poll.stop()
        super().closeEvent(ev)

    def _poll_result(self):
        if self._view is None:
            return
        self._view.page().runJavaScript(
            "window.__nitPapTake ? window.__nitPapTake() : null", self._on_result
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
        if data.get("error"):
            self._set_status(str(data["error"]), kind="error")
        if data.get("png"):
            self._copy_png(str(data["png"]))
        if data.get("exit"):
            self.close()

    def _copy_png(self, data_url: str):
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
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            self._set_status("Auf die Zwischenablage konnte nicht zugegriffen werden.", kind="error")
            return
        clipboard.setMimeData(mime)
        self._set_status(
            f"✓ Als PNG in der Zwischenablage ({img.width()}×{img.height()} px) – "
            "mit Strg+V / Cmd+V einfügen.",
            kind="success",
        )

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
