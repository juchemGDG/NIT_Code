"""AIS-Chat-Panel – eingebettete Web-Ansicht von app.ais-chat.schule."""
try:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineCore import (
        QWebEnginePage,
        QWebEngineProfile,
        QWebEngineSettings,
    )
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _WEBENGINE_AVAILABLE = True
except ImportError:
    _WEBENGINE_AVAILABLE = False

_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .config import AIS_CHAT_URL, THEME

# Feste Breite des Panels und Zoom-Faktor für das mobile Layout
PANEL_WIDTH = 400
_VIEWPORT_WIDTH = 390   # Smartphone-Breite, auf die der Inhalt rendert
PANEL_ZOOM = 0.9


class AisChatPanel(QWidget):
    """Seitliches Panel mit eingebetteter AIS-Chat-Webseite (feste Breite)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = None
        self._build_ui()

    def _build_ui(self):
        # Breite wird vom _ai_stack in main_window gesteuert – hier nur Minimum
        self.setMinimumWidth(100)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QWidget()
        self._header.setFixedHeight(36)
        hlay = QHBoxLayout(self._header)
        hlay.setContentsMargins(10, 0, 10, 0)
        self._title_lbl = QLabel("🏫  AIS-Chat")
        hlay.addWidget(self._title_lbl)
        layout.addWidget(self._header)

        if _WEBENGINE_AVAILABLE:
            # Off-the-record Profil: kein Name → kein Persistenzordner auf Disk
            # Reihenfolge: Profile als erstes Kind, View als zweites Kind des Panels.
            # Qt löscht Kinder in umgekehrter Reihenfolge → View (+ Page) vor Profile → korrekte Cleanup-Reihenfolge.
            self._profile = QWebEngineProfile(self)
            self._profile.setHttpUserAgent(_MOBILE_UA)

            self._view = QWebEngineView(self)
            page = QWebEnginePage(self._profile, self._view)
            # Zwischenablage für JavaScript freigeben, damit die Copy-Buttons
            # der Webseite (navigator.clipboard / execCommand('copy')) funktionieren.
            settings = page.settings()
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True
            )
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.JavascriptCanPaste, True
            )
            self._view.setPage(page)
            self._view.loadFinished.connect(self._inject_viewport)
            self._view.setUrl(QUrl(AIS_CHAT_URL))
            layout.addWidget(self._view, stretch=1)
        else:
            info = QLabel(
                "PyQt6-WebEngine ist nicht installiert.\n\n"
                "Bitte im Terminal ausführen:\n\n"
                "pip install PyQt6-WebEngine"
            )
            info.setStyleSheet(
                f"color:{THEME['text_dim']}; font-size:12px; padding:20px;"
            )
            info.setWordWrap(True)
            layout.addWidget(info)
            layout.addStretch()
        self.refresh_theme()

    def refresh_theme(self):
        self._header.setStyleSheet(
            f"background:{THEME['bg_panel']};"
            f"border-bottom:1px solid {THEME['border']};"
        )
        self._title_lbl.setStyleSheet(
            f"color:{THEME['text']}; font-weight:bold; font-size:13px;"
        )

    def _inject_viewport(self, *_):
        if self._view is None:
            return
        self._view.setZoomFactor(PANEL_ZOOM)
        self._view.page().runJavaScript(f"""
            (function() {{
                var meta = document.querySelector('meta[name="viewport"]');
                if (!meta) {{
                    meta = document.createElement('meta');
                    meta.name = 'viewport';
                    document.head.appendChild(meta);
                }}
                meta.content = 'width={_VIEWPORT_WIDTH}, initial-scale=1.0';

                // Querscrollen der GESAMTEN Seite verhindern. Ursache in Chat-SPAs:
                // Flex-/Grid-Kinder haben standardmäßig min-width:auto und weigern
                // sich, schmaler als ihr Inhalt zu werden – ein breiter Code-Block
                // bläht so ALLE Eltern-Container auf. 'min-width:0' erlaubt ihnen
                // zu schrumpfen; der Code-Block scrollt dann nur in sich selbst.
                var STYLE_ID = 'nit-code-overflow-fix';
                var CSS = [
                    'html, body {{ max-width: 100% !important; overflow-x: hidden !important; }}',
                    '* {{ min-width: 0 !important; }}',
                    'pre {{ max-width: 100% !important; overflow-x: auto !important; box-sizing: border-box; white-space: pre-wrap !important; overflow-wrap: anywhere !important; word-break: break-word !important; }}',
                    'pre code {{ white-space: inherit !important; overflow-wrap: inherit !important; word-break: break-word !important; }}',
                    'code {{ overflow-wrap: anywhere !important; word-break: break-word !important; }}',
                    // Bilder/Medien skalieren auf die Panelbreite herunter, statt in
                    // ihrer Originalbreite zu rendern und so die Seite zu verbreitern.
                    'img, svg, video, canvas {{ max-width: 100% !important; height: auto !important; }}'
                ].join('\\n');

                function applyStyle() {{
                    if (!document.head) return;
                    var style = document.getElementById(STYLE_ID);
                    if (!style) {{
                        style = document.createElement('style');
                        style.id = STYLE_ID;
                        document.head.appendChild(style);
                    }}
                    if (style.textContent !== CSS) style.textContent = CSS;
                }}

                applyStyle();

                // Die Seite ist eine SPA: Inhalte (und ggf. der <head>) werden nach
                // dem Laden per JavaScript erneuert. Ein MutationObserver sorgt dafür,
                // dass unser Style erhalten bleibt bzw. wieder eingefügt wird.
                if (!window.__nitOverflowObserver) {{
                    window.__nitOverflowObserver = new MutationObserver(applyStyle);
                    window.__nitOverflowObserver.observe(
                        document.documentElement, {{ childList: true, subtree: true }}
                    );
                }}
            }})();
        """)
