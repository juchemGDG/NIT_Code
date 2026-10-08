"""Hilfe → „Fehler finden: Schritt für Schritt“: das Cheatsheet (ohne Beispiel) für
Klasse 8/9 und 10/KS. Der Text kommt aus :mod:`debug_guide` – derselbe wie in Konsole
und Fehlerprotokoll."""
from PyQt6.QtWidgets import QDialog, QTabWidget, QTextBrowser, QVBoxLayout

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _WEBENGINE = True
except ImportError:      # ohne WebEngine: einfache Qt-Ansicht
    _WEBENGINE = False

from .debug_guide import LEVEL_KL10, LEVEL_KL89, LEVEL_LABEL, cheat_sheet_html


class DebugMapDialog(QDialog):
    def __init__(self, parent=None, level: str = LEVEL_KL10):
        super().__init__(parent)
        self.setWindowTitle("🗺  Fehler finden: Schritt für Schritt")
        self.resize(900, 860)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self._tabs = QTabWidget()
        lay.addWidget(self._tabs)
        self._views: list = []
        for key in (LEVEL_KL89, LEVEL_KL10):
            page = cheat_sheet_html(key)
            if _WEBENGINE:
                view = QWebEngineView(self)
                view.setHtml(page)
            else:
                view = QTextBrowser(self)
                view.setHtml(page)
            self._views.append(view)
            self._tabs.addTab(view, LEVEL_LABEL[key])
        self._tabs.setCurrentIndex(0 if level == LEVEL_KL89 else 1)

    def set_level(self, level: str):
        self._tabs.setCurrentIndex(0 if level == LEVEL_KL89 else 1)
