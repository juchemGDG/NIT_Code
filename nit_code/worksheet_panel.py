"""Arbeitsblatt-Vorschau: rendert Obsidian-Markdown (Callouts, Codeblöcke,
raw-HTML-Templates) als echte HTML/CSS-Ansicht (QWebEngineView)."""
import os
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, QUrlQuery, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

try:
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _WEBENGINE_AVAILABLE = True
except ImportError:
    _WEBENGINE_AVAILABLE = False

from .worksheet_renderer import HAS_MARKDOWN, pygments_css, render_worksheet

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{style}</style>
</head><body class="arbeitsblatt">
{body}
<script>
function nitCopyBlock(id, btn) {{
  var pre = document.querySelector('[data-id="' + id + '"] pre');
  if (!pre) return;
  navigator.clipboard.writeText(pre.innerText).then(function() {{
    var old = btn.textContent;
    btn.textContent = '✓ Kopiert';
    setTimeout(function() {{ btn.textContent = old; }}, 1200);
  }});
}}
</script>
</body></html>"""

# Bewusst theme-unabhängig: Arbeitsblätter sind auf Papier/Druck ausgelegt
# (feste helle Grautöne in arbeitsblatt-farben.css/arbeitsblatt.css) und
# sollen 1:1 wie in Obsidian aussehen – die Vorschau bleibt deshalb immer
# hell, auch wenn NIT_Code im Dunkelmodus läuft.
_BASE_CSS = """
:root {
  --ab-linie:   #999;
  --ab-grau:    #f5f5f5;
  --ab-rand:    #ddd;
  --ab-muted:   #777;
  --ab-akzent:  #00695c;
  --ab-loesung: #1565c0;
}
body {
  background: #ffffff; color: #1a1a1a;
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 15px; line-height: 1.5; padding: 16px 24px; margin: 0;
}
a { color: #3b6ea5; }
h1, h2, h3, h4 { color: #1a1a1a; border-bottom: 1px solid var(--ab-rand); padding-bottom: 4px; }
code { background: var(--ab-grau); padding: 2px 5px; border-radius: 3px; font-family: monospace; }
table { border-collapse: collapse; }
th, td { border: 1px solid var(--ab-rand); padding: 4px 8px; }

.admonition, details.admonition {
  border-left: 4px solid var(--ab-rand);
  background: var(--ab-grau);
  border-radius: 6px;
  padding: 0.6em 1em;
  margin: 1em 0;
}
.admonition-title, details.admonition > summary {
  font-weight: 600; margin: 0 0 0.4em 0; cursor: default;
}
details.admonition > summary { cursor: pointer; list-style: none; }
details.admonition > summary::-webkit-details-marker { display: none; }

.nit-codeblock { margin: 1em 0; border: 1px solid var(--ab-rand); border-radius: 6px; overflow: hidden; }
.nit-code-toolbar {
  display: flex; align-items: center; gap: 10px;
  background: var(--ab-grau); padding: 4px 10px; font-size: 12px; color: var(--ab-muted);
}
.nit-code-lang { flex: 1; text-transform: uppercase; }
.nit-btn { color: #3b6ea5; text-decoration: none; cursor: pointer; }
.nit-btn:hover { color: #7f0055; }
.codehilite { margin: 0; padding: 10px; overflow-x: auto; }
.codehilite pre { margin: 0; }
"""

# Palette aus dem Obsidian-Snippet arbeitsblatt-farben.css – gilt für
# Callouts (obsidian-callouts normalisiert Alias-Typen wie hint/important
# auf tip, caution/attention auf warning, error auf danger usw., siehe
# obsidian_callouts.extension.ObsidianCalloutProcessor.to_callout_type)
# UND für die gleichnamigen <div class="…">-Kästen aus den HTML-Vorlagen –
# beide teilen bei dir dieselbe Basis, siehe Kommentar in der CSS-Datei.
_ARBEITSBLATT_PALETTE_CSS = """
.admonition.hinweis, .admonition.note, .admonition.info,
.admonition.abstract, .admonition.quote,
.ab-hinweis, .hinweis { --nit-c: 33,150,243; }

.admonition.tipp, .admonition.tip,
.ab-tipp, .tipp { --nit-c: 255,152,0; }

.admonition.merke, .admonition.success, .admonition.example,
.ab-merksatz, .merksatz { --nit-c: 76,175,80; }

.admonition.sicherheit, .admonition.warning, .admonition.danger,
.admonition.failure, .admonition.bug,
.ab-sicherheit, .sicherheit { --nit-c: 244,67,54; }

.admonition.aufgabe, .admonition.question, .admonition.todo,
.ab-aufgabenbox, .aufgabe { --nit-c: 0,105,92; }

.admonition.material,
.ab-material, .material { --nit-c: 120,124,126; }

.admonition.loesung, .ab-loesung { --nit-c: 21,101,192; }

.admonition[class], .ab-merksatz, .merksatz, .ab-hinweis, .hinweis,
.ab-material, .material, .ab-sicherheit, .sicherheit,
.ab-tipp, .tipp, .ab-aufgabenbox, .aufgabe, .ab-loesung {
  background: rgba(var(--nit-c, 153,153,153), 0.10);
  border-left-color: rgb(var(--nit-c, 153,153,153));
}
.admonition-title, details.admonition > summary {
  color: rgb(var(--nit-c, 153,153,153));
}

/* Div-Kästen aus den HTML-Vorlagen (arbeitsblatt.css / unterricht-layout.css) */
.ab-merksatz, .merksatz, .ab-hinweis, .hinweis, .ab-material, .material,
.ab-sicherheit, .sicherheit, .ab-tipp, .tipp, .ab-aufgabenbox, .aufgabe,
.ab-loesung {
  padding: 10px 14px; margin: 14px 0; border-radius: 4px; border-left: 4px solid;
  font-size: 0.95em;
}
.ab-loesung::before {
  content: "Lösung"; display: block; font-size: 0.75em; font-weight: 600;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: rgb(var(--nit-c, 21,101,192)); margin-bottom: 3px;
}

/* [!tabelle]-Callout: unsichtbarer Rahmen, dient nur dazu, dass die
   Tabelle innerhalb des Callouts als Markdown geparst wird. */
.admonition.tabelle {
  background: none; border: none; padding: 0; margin: 14px 0;
}
.admonition.tabelle > .admonition-title { display: none; }
"""

# Struktur/Layout aus arbeitsblatt.css, arbeitsblatt-listen.css (nur die
# Bildschirm-Teile – @media print und CodeMirror-Editoransicht-Regeln bleiben
# außen vor, die betreffen nur Obsidian selbst) und unterricht-layout.css.
# <body> bekommt in _PAGE_TEMPLATE fest die Klasse "arbeitsblatt", da die
# Aufgabennummerierung/Zähler in den Originaldateien darüber aktiviert
# werden (normalerweise per cssclasses im Frontmatter, das diese Vorschau
# nicht einliest). Umschalt-Klassen wie ohne-loesung/mit-loesung,
# tabelle-mittig, mc-einfach, druck-* und Multiple-Choice-Checkboxen
# ([ ]/[x]) sind hier (noch) nicht umgesetzt.
_ARBEITSBLATT_STRUCTURE_CSS = """
/* --- Kopfzeile --- */
.ab-header {
  display: grid; grid-template-columns: auto 1fr auto; gap: 16px;
  align-items: center; padding-bottom: 10px; margin-bottom: 20px;
  border-bottom: 2.5px solid var(--ab-akzent);
}
.ab-logo { height: 52px; width: auto; display: block; }
.ab-titel h1 { margin: 0 0 2px 0; font-size: 1.5em; line-height: 1.2; border: none; padding: 0; }
.ab-fach { font-size: 0.85em; color: var(--ab-muted); letter-spacing: 0.02em; }
.ab-meta { font-size: 0.82em; line-height: 1.9; text-align: right; white-space: nowrap; }
.ab-feld {
  display: inline-block; border-bottom: 1px solid var(--ab-linie);
  min-width: 100px; height: 1.1em; vertical-align: bottom;
}
.ab-feld.kurz { min-width: 55px; }
.ab-feld.lang { min-width: 190px; }
.ab-footer {
  margin-top: 28px; padding-top: 8px; border-top: 1px solid var(--ab-rand);
  font-size: 0.75em; color: var(--ab-muted); display: flex; justify-content: space-between;
}

/* --- Bild + Text (Verhältnis 1:3) --- */
.ab-bild-links, .ab-bild-rechts { display: grid; gap: 16px; align-items: start; margin: 14px 0; }
.ab-bild-links { grid-template-columns: 1fr 3fr; }
.ab-bild-rechts { grid-template-columns: 3fr 1fr; }
.ab-bild-rechts img { order: 2; }
.ab-bild-links img, .ab-bild-rechts img { width: 100%; height: auto; display: block; border-radius: 3px; }
.ab-bild-links.v1-2 { grid-template-columns: 1fr 2fr; }
.ab-bild-links.v1-4 { grid-template-columns: 1fr 4fr; }
.ab-bild-links.v2-3 { grid-template-columns: 2fr 3fr; }
@media screen and (max-width: 650px) {
  .ab-bild-links, .ab-bild-rechts { grid-template-columns: 1fr; }
  .ab-bild-rechts img { order: 0; }
}

/* --- Aufgabenblock mit Kopfzeile + automatischer Nummer --- */
.ab-aufgabe { margin: 16px 0; padding-left: 12px; border-left: 3px solid var(--ab-akzent); }
.ab-aufgabe-kopf {
  font-weight: 600; color: var(--ab-akzent); margin-bottom: 5px;
  display: flex; justify-content: space-between; align-items: baseline;
}
.ab-punkte {
  font-weight: 400; font-size: 0.82em; color: var(--ab-muted);
  border: 1px solid var(--ab-rand); border-radius: 3px; padding: 1px 7px;
}
body.arbeitsblatt { counter-reset: ab-nr; }
.ab-aufgabe.auto { counter-increment: ab-nr; }
.ab-aufgabe.auto > .ab-aufgabe-kopf::before { content: "Aufgabe " counter(ab-nr); }

/* --- Wahr/Falsch-Tabelle --- */
.ab-wf { width: 100%; border-collapse: collapse; margin: 12px 0; }
.ab-wf th, .ab-wf td { border: 1px solid var(--ab-rand); padding: 6px 9px; vertical-align: top; }
.ab-wf th { background: var(--ab-grau); font-size: 0.85em; }
.ab-wf th:not(:first-child), .ab-wf td:not(:first-child) { width: 62px; text-align: center; }

/* --- Schreib- und Zeichenflächen --- */
.ab-feldbox { border: 1px solid var(--ab-linie); border-radius: 3px; min-height: 28mm; margin: 10px 0; }
.ab-feldbox.klein { min-height: 16mm; }
.ab-feldbox.gross { min-height: 55mm; }
.ab-linien {
  margin: 10px 0; min-height: 84px;
  background-image: repeating-linear-gradient(
    transparent, transparent 27px, var(--ab-linie) 27px, var(--ab-linie) 27.8px);
}
.ab-linien.z2 { min-height: 56px; }
.ab-linien.z5 { min-height: 140px; }
.ab-linien.z8 { min-height: 224px; }
.ab-kariert {
  border: 1px solid var(--ab-rand); min-height: 60mm; margin: 10px 0;
  background-image:
    repeating-linear-gradient(transparent, transparent 4.9mm, var(--ab-rand) 4.9mm, var(--ab-rand) 5mm),
    repeating-linear-gradient(90deg, transparent, transparent 4.9mm, var(--ab-rand) 4.9mm, var(--ab-rand) 5mm);
}
.ab-kariert.gross { min-height: 100mm; }

/* --- Lückentext, Wortspeicher, Marker, Zuordnung, Bewertung --- */
.ab-luecke {
  display: inline-block; border-bottom: 1px solid var(--ab-linie);
  min-width: 90px; height: 1.15em; vertical-align: bottom; margin: 0 3px;
}
.ab-luecke.kurz { min-width: 45px; }
.ab-luecke.lang { min-width: 170px; }
.ab-wortspeicher {
  border: 1px dashed var(--ab-linie); border-radius: 3px; padding: 8px 12px;
  margin: 12px 0; font-size: 0.92em; text-align: center; background: var(--ab-grau);
}
.ab-wortspeicher::before { content: "Wortspeicher: "; font-weight: 600; color: var(--ab-muted); }
.ab-marker {
  display: inline-block; font-size: 0.72em; padding: 1px 7px; border-radius: 9px;
  background: var(--ab-grau); border: 1px solid var(--ab-rand); color: var(--ab-muted);
  margin-right: 5px; vertical-align: middle;
}
.ab-zuordnung { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 60px; margin: 14px 0; }
.ab-zuordnung > div { border: 1px solid var(--ab-rand); border-radius: 3px; padding: 6px 10px; font-size: 0.92em; }
.ab-bewertung { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 0.85em; }
.ab-bewertung th, .ab-bewertung td { border: 1px solid var(--ab-linie); padding: 5px 8px; text-align: center; }
.ab-bewertung th { background: var(--ab-grau); }
.ab-bewertung td:first-child, .ab-bewertung th:first-child { text-align: left; }
.ab-loesung-inline { color: var(--ab-loesung); font-weight: 600; border-bottom: 1px dotted var(--ab-loesung); }

/* --- Aufgabennummerierung 1. -> a) -> i) --- */
body.arbeitsblatt ol, .ab-aufgaben ol { list-style: none; padding-left: 0; counter-reset: aufgabe; }
body.arbeitsblatt ol > li, .ab-aufgaben ol > li {
  position: relative; list-style: none; margin: 0.6em 0;
  counter-increment: aufgabe; padding-left: 2.2em;
}
body.arbeitsblatt ol > li::marker, .ab-aufgaben ol > li::marker { content: none; }
body.arbeitsblatt ol > li::before, .ab-aufgaben ol > li::before {
  content: counter(aufgabe) "."; position: absolute; left: 0; top: 0;
  font-weight: 600; color: var(--ab-akzent);
}
body.arbeitsblatt ol ol, .ab-aufgaben ol ol { counter-reset: teilaufgabe; margin-top: 0.35em; margin-bottom: 0.2em; }
body.arbeitsblatt ol ol > li, .ab-aufgaben ol ol > li { counter-increment: teilaufgabe; padding-left: 2em; margin: 0.3em 0; }
body.arbeitsblatt ol ol > li::before, .ab-aufgaben ol ol > li::before {
  content: counter(teilaufgabe, lower-alpha) ")"; font-weight: 600; color: var(--ab-akzent);
}
body.arbeitsblatt ol ol ol, .ab-aufgaben ol ol ol { counter-reset: unteraufgabe; }
body.arbeitsblatt ol ol ol > li, .ab-aufgaben ol ol ol > li { counter-increment: unteraufgabe; padding-left: 2.4em; }
body.arbeitsblatt ol ol ol > li::before, .ab-aufgaben ol ol ol > li::before {
  content: counter(unteraufgabe, lower-roman) ")"; color: var(--ab-muted); font-weight: 400;
}
.weiterzaehlen { counter-reset: aufgabe; }
.weiterzaehlen ol { counter-reset: none; }
.weiterzaehlen ol ol { counter-reset: teilaufgabe; }

/* --- Grid-Layouts (grid2/3/4) --- */
.grid2, .grid3, .grid4 { display: grid; gap: 16px; margin: 1.5em 0; align-items: start; }
.grid2 { grid-template-columns: repeat(2, 1fr); }
.grid3 { grid-template-columns: repeat(3, 1fr); }
.grid4 { grid-template-columns: repeat(4, 1fr); }
.grid2 img, .grid3 img, .grid4 img { width: 100%; height: auto; display: block; border-radius: 4px; }
.gleich-hoch img { height: 150px; object-fit: cover; }
.grid2 > div > p, .grid3 > div > p, .grid4 > div > p { margin-top: 0.4em; font-size: 0.9em; line-height: 1.4; }
@media screen and (max-width: 700px) {
  .grid3, .grid4 { grid-template-columns: repeat(2, 1fr); }
  .grid2 { grid-template-columns: 1fr; }
}

/* --- Bild über die volle Breite --- */
.bild, .bild img { width: 100%; height: auto; display: block; margin: 1.5em 0; border-radius: 4px; }
figure.bild { margin: 1.5em 0; }
figure.bild figcaption { font-size: 0.85em; font-style: italic; text-align: center; color: var(--ab-muted); margin-top: 0.5em; }
.bild-breit img { width: 110%; max-width: none; margin-left: -5%; height: auto; display: block; }

/* --- Bild neben Text --- */
.bild-text, .text-bild { display: grid; gap: 20px; align-items: center; margin: 1.5em 0; }
.bild-text { grid-template-columns: 1fr 2fr; }
.text-bild { grid-template-columns: 2fr 1fr; }
.bild-text img, .text-bild img { width: 100%; height: auto; border-radius: 4px; }
@media screen and (max-width: 700px) {
  .bild-text, .text-bild { grid-template-columns: 1fr; }
}

/* --- Kleinigkeiten --- */
.zentriert { text-align: center; }
.klein { font-size: 0.8em; color: var(--ab-muted); }
.spalten2 { column-count: 2; column-gap: 30px; margin: 1.5em 0; }
.trenner { border-top: 2px solid var(--ab-rand); margin: 2em 0; }
"""


class _WorksheetPage(QWebEnginePage if _WEBENGINE_AVAILABLE else object):
    """Fängt Klicks auf nitcode://insert?id=… ab, statt sie zu navigieren."""

    insert_requested = pyqtSignal(str)  # block_id

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() == "nitcode" and url.host() == "insert":
            block_id = QUrlQuery(url).queryItemValue("id")
            if block_id:
                self.insert_requested.emit(block_id)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class WorksheetPanel(QWidget):
    """Seitliches Panel: rendert eine .md-Datei als Arbeitsblatt-Vorschau."""

    insert_into_editor_requested = pyqtSignal(str)  # roher Code
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path = None
        self._blocks = {}
        self._available = _WEBENGINE_AVAILABLE and HAS_MARKDOWN
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QWidget()
        self._header.setFixedHeight(36)
        hlay = QHBoxLayout(self._header)
        hlay.setContentsMargins(10, 0, 4, 0)
        self._title_lbl = QLabel("📄  Arbeitsblatt-Vorschau")
        hlay.addWidget(self._title_lbl, stretch=1)
        self._reload_btn = QPushButton("↻")
        self._reload_btn.setToolTip("Neu laden")
        self._reload_btn.setFixedWidth(28)
        self._reload_btn.clicked.connect(self._reload)
        hlay.addWidget(self._reload_btn)
        self._close_btn = QPushButton("✕")
        self._close_btn.setToolTip("Schließen")
        self._close_btn.setFixedWidth(28)
        self._close_btn.clicked.connect(self.close_requested.emit)
        hlay.addWidget(self._close_btn)
        layout.addWidget(self._header)

        if self._available:
            # Reihenfolge wie bei AisChatPanel: Profile zuerst als Kind anlegen,
            # View danach – Qt räumt Kinder in umgekehrter Reihenfolge auf, so
            # wird die View (+ Page) vor dem Profile zerstört.
            self._profile = QWebEngineProfile(self)
            self._view = QWebEngineView(self)
            page = _WorksheetPage(self._profile, self._view)
            settings = page.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, True)
            page.insert_requested.connect(self._on_page_insert_requested)
            self._view.setPage(page)
            layout.addWidget(self._view, stretch=1)
        else:
            self._view = None
            missing = []
            if not _WEBENGINE_AVAILABLE:
                missing.append("PyQt6-WebEngine")
            if not HAS_MARKDOWN:
                missing.append("markdown / obsidian-callouts / Pygments")
            fallback = QLabel(
                "Arbeitsblatt-Vorschau nicht verfügbar.\n(Fehlt: " + ", ".join(missing) + ")"
            )
            fallback.setWordWrap(True)
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(fallback, stretch=1)
            self._reload_btn.setEnabled(False)

    def load_file(self, path: str):
        self._path = path
        self._title_lbl.setText(f"📄  {os.path.basename(path)}")
        self._reload()

    def _reload(self):
        if not self._available or not self._path:
            return
        try:
            text = Path(self._path).read_text(encoding="utf-8")
        except Exception as e:
            text = f"*(Datei konnte nicht geladen werden: {e})*"
        self._render(text)

    def _render(self, text: str):
        body, self._blocks = render_worksheet(text, dark=False)
        style = _BASE_CSS + _ARBEITSBLATT_PALETTE_CSS + _ARBEITSBLATT_STRUCTURE_CSS + pygments_css(dark=False)
        html_doc = _PAGE_TEMPLATE.format(style=style, body=body)
        base_dir = os.path.dirname(self._path) if self._path else "."
        base = QUrl.fromLocalFile(base_dir + os.sep)
        self._view.setHtml(html_doc, base)

    def _on_page_insert_requested(self, block_id: str):
        code = self._blocks.get(block_id)
        if code is not None:
            self.insert_into_editor_requested.emit(code)

    def refresh_theme(self):
        """Die Vorschau ist bewusst theme-unabhängig (Papier-Look) – kein
        Neu-Rendern nötig, nur Teil der main_window-Refresh-Kaskade."""
        pass
