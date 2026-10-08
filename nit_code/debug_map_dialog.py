"""Hilfe → Debugging-Landkarte: zeigt die Poster für Klasse 8/9 und 10/KS."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QLabel, QScrollArea, QTabWidget, QVBoxLayout

from .config import asset_path
from .error_hints import LEVEL_KL10, LEVEL_KL89

_POSTER = {
    LEVEL_KL89: ("Klasse 8/9", "debug/landkarte_kl89.png"),
    LEVEL_KL10: ("Klasse 10/KS", "debug/landkarte_kl10.png"),
}


class _FitLabel(QLabel):
    """Bild, das sich an die Breite des Fensters anpasst."""

    def __init__(self, pixmap: QPixmap):
        super().__init__()
        self._pix = pixmap
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

    def fit(self, width: int):
        if self._pix.isNull():
            return
        w = max(300, min(width, self._pix.width()))
        self.setPixmap(self._pix.scaledToWidth(w, Qt.TransformationMode.SmoothTransformation))


class DebugMapDialog(QDialog):
    def __init__(self, parent=None, level: str = LEVEL_KL10):
        super().__init__(parent)
        self.setWindowTitle("🗺  Debugging-Landkarte")
        self.resize(980, 860)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self._tabs = QTabWidget()
        lay.addWidget(self._tabs)
        self._labels: list[tuple[QScrollArea, _FitLabel]] = []
        for key in (LEVEL_KL89, LEVEL_KL10):
            title, rel = _POSTER[key]
            p = asset_path(rel)
            pix = QPixmap(str(p)) if p else QPixmap()
            lbl = _FitLabel(pix)
            if pix.isNull():
                lbl.setText(f"Bild nicht gefunden: {rel}")
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setWidget(lbl)
            self._tabs.addTab(area, title)
            self._labels.append((area, lbl))
        self._tabs.setCurrentIndex(0 if level == LEVEL_KL89 else 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for area, lbl in self._labels:
            lbl.fit(area.viewport().width() - 4)

    def showEvent(self, event):
        super().showEvent(event)
        for area, lbl in self._labels:
            lbl.fit(area.viewport().width() - 4)
