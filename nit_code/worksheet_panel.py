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

from .config import THEME
from .worksheet_renderer import HAS_MARKDOWN, pygments_css, render_worksheet

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{style}</style>
</head><body>
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

_BASE_CSS = """
body {{
  background: {bg_editor}; color: {text};
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 15px; line-height: 1.5; padding: 16px 24px; margin: 0;
}}
a {{ color: {accent}; }}
h1, h2, h3, h4 {{ color: {text}; border-bottom: 1px solid {border}; padding-bottom: 4px; }}
code {{ background: {bg_panel}; padding: 2px 5px; border-radius: 3px; font-family: monospace; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid {border}; padding: 4px 8px; }}

.admonition, details.admonition {{
  border-left: 4px solid {border};
  background: {bg_panel};
  border-radius: 6px;
  padding: 0.6em 1em;
  margin: 1em 0;
}}
.admonition-title, details.admonition > summary {{
  font-weight: 600; margin: 0 0 0.4em 0; cursor: default;
}}
details.admonition > summary {{ cursor: pointer; list-style: none; }}
details.admonition > summary::-webkit-details-marker {{ display: none; }}
.admonition.note, .admonition.info, .admonition.abstract {{ border-left-color: {info}; }}
.admonition.tip, .admonition.success {{ border-left-color: {success}; }}
.admonition.question, .admonition.todo {{ border-left-color: {accent}; }}
.admonition.warning {{ border-left-color: {warning}; }}
.admonition.danger, .admonition.failure, .admonition.bug {{ border-left-color: {error}; }}
.admonition.example, .admonition.quote {{ border-left-color: {text_dim}; }}

.nit-codeblock {{ margin: 1em 0; border: 1px solid {border}; border-radius: 6px; overflow: hidden; }}
.nit-code-toolbar {{
  display: flex; align-items: center; gap: 10px;
  background: {bg_mid}; padding: 4px 10px; font-size: 12px; color: {text_dim};
}}
.nit-code-lang {{ flex: 1; text-transform: uppercase; }}
.nit-btn {{ color: {accent}; text-decoration: none; cursor: pointer; }}
.nit-btn:hover {{ color: {accent_hover}; }}
.codehilite {{ margin: 0; padding: 10px; overflow-x: auto; }}
.codehilite pre {{ margin: 0; }}
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
        dark = self._is_dark()
        body, self._blocks = render_worksheet(text, dark)
        style = _BASE_CSS.format(**THEME) + pygments_css(dark)
        html_doc = _PAGE_TEMPLATE.format(style=style, body=body)
        base_dir = os.path.dirname(self._path) if self._path else "."
        base = QUrl.fromLocalFile(base_dir + os.sep)
        self._view.setHtml(html_doc, base)

    @staticmethod
    def _is_dark() -> bool:
        bg = THEME.get("bg_editor", "#ffffff").lstrip("#")
        try:
            r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
            return (r + g + b) / 3 < 128
        except Exception:
            return False

    def _on_page_insert_requested(self, block_id: str):
        code = self._blocks.get(block_id)
        if code is not None:
            self.insert_into_editor_requested.emit(code)

    def refresh_theme(self):
        """Wie MermaidPreview.apply_theme: bei offener Datei neu rendern."""
        if self._available and self._path:
            self._reload()
