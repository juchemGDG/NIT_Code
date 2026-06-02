"""AIS-Chat-Panel – eingebettete Web-Ansicht von app.ais-chat.schule."""
try:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _WEBENGINE_AVAILABLE = True
except ImportError:
    _WEBENGINE_AVAILABLE = False

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .config import AIS_CHAT_URL, THEME


class AisChatPanel(QWidget):
    """Seitliches Panel mit eingebetteter AIS-Chat-Webseite."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self.setMinimumWidth(260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(
            f"background:{THEME['bg_panel']};"
            f"border-bottom:1px solid {THEME['border']};"
        )
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(10, 0, 10, 0)
        title_lbl = QLabel("🏫  AIS-Chat")
        title_lbl.setStyleSheet(
            f"color:{THEME['text']}; font-weight:bold; font-size:13px;"
        )
        hlay.addWidget(title_lbl)
        layout.addWidget(header)

        if _WEBENGINE_AVAILABLE:
            # Eingebettete Web-Ansicht
            self._view = QWebEngineView()
            self._view.setUrl(QUrl(AIS_CHAT_URL))
            layout.addWidget(self._view, stretch=1)
        else:
            # Hinweis wenn PyQt6-WebEngine nicht installiert ist
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
