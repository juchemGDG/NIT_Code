"""Kurzanleitung: zeigt die mitgelieferte Markdown-Anleitung und bietet sie zum Speichern an."""
import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QFileDialog, QMessageBox,
)

from .config import asset_path
from .worksheet_panel import WorksheetPanel

GUIDE_NAME = "Kurzanleitung.md"


def guide_path() -> Path | None:
    return asset_path(f"hilfe/{GUIDE_NAME}")


class HelpDialog(QDialog):
    """Nicht-modales Fenster mit der Kurzanleitung (Rendering wie Arbeitsblatt-Vorschau)."""

    def __init__(self, guide: Path, parent=None):
        super().__init__(parent)
        self._guide = guide
        self.setWindowTitle("Kurzanleitung")
        self.resize(900, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        self.panel = WorksheetPanel()
        self.panel.close_requested.connect(self.close)
        layout.addWidget(self.panel, stretch=1)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(10, 0, 10, 0)
        save_btn = QPushButton("Als Datei speichern …")
        save_btn.setToolTip("Markdown-Datei samt Bildern in einen Ordner kopieren")
        save_btn.clicked.connect(self._save_copy)
        buttons.addStretch(1)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

        self.panel.load_file(str(guide))

    def _save_copy(self):
        target = QFileDialog.getExistingDirectory(self, "Zielordner für die Kurzanleitung")
        if not target:
            return
        try:
            dest = Path(target)
            shutil.copy2(self._guide, dest / GUIDE_NAME)
            img = self._guide.parent / "img"
            if img.is_dir():
                shutil.copytree(img, dest / "img", dirs_exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, "Speichern fehlgeschlagen", str(e))
            return
        QMessageBox.information(
            self, "Gespeichert",
            f"{GUIDE_NAME} und der Ordner „img“ liegen jetzt in:\n{target}",
        )
