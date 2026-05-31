"""Dateibaum-Panel (linke Sidebar)."""
import os
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QDir
from PyQt6.QtGui import QFileSystemModel, QIcon, QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView,
    QPushButton, QLabel, QFileDialog, QMenu, QInputDialog,
    QMessageBox,
)

from .config import THEME


class FilePanel(QWidget):
    """Dateibaum-Sidebar mit Kontextmenü."""

    file_open_requested = pyqtSignal(str)   # Pfad zur Datei

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = str(Path.home())
        self._setup_ui()
        self.set_root(self._root)

    def _setup_ui(self):
        self.setMinimumWidth(180)
        self.setMaximumWidth(350)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(f"background:{THEME['bg_panel']};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 6, 4, 6)

        title = QLabel("DATEIEN")
        title.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:11px; font-weight:bold; letter-spacing:1px;"
        )
        h_layout.addWidget(title)
        h_layout.addStretch()

        btn_open = QPushButton("⊕")
        btn_open.setToolTip("Ordner öffnen")
        btn_open.setFixedSize(22, 22)
        btn_open.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{THEME['accent']};"
            f" border:none; font-size:16px; }}"
            f"QPushButton:hover {{ color:{THEME['accent_hover']}; }}"
        )
        btn_open.clicked.connect(self._open_folder)
        h_layout.addWidget(btn_open)
        layout.addWidget(header)

        # Aktueller Pfad
        self._path_label = QLabel()
        self._path_label.setStyleSheet(
            f"background:{THEME['bg_panel']}; color:{THEME['text_dim']};"
            f" font-size:10px; padding:2px 8px 4px 8px;"
        )
        self._path_label.setWordWrap(True)
        layout.addWidget(self._path_label)

        # Trennlinie
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{THEME['border']};")
        layout.addWidget(sep)

        # Dateimodell
        self._model = QFileSystemModel()
        self._model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)
        self._model.setNameFilters(["*.py", "*.txt", "*.json", "*.md", "*.csv",
                                    "*.html", "*.css", "*.js", "*.bin", "*.mpy"])
        self._model.setNameFilterDisables(False)

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setStyleSheet(
            f"""
            QTreeView {{
                background: {THEME['bg_dark']};
                color: {THEME['text']};
                border: none;
                outline: none;
                font-size: 12px;
            }}
            QTreeView::item:hover {{
                background: {THEME['selection']};
            }}
            QTreeView::item:selected {{
                background: {THEME['accent']};
                color: white;
            }}
            QTreeView::branch {{
                background: {THEME['bg_dark']};
            }}
            """
        )
        self._tree.setHeaderHidden(True)
        # Nur Name-Spalte anzeigen
        for col in range(1, 4):
            self._tree.hideColumn(col)
        self._tree.setAnimated(True)
        self._tree.setIndentation(16)
        self._tree.doubleClicked.connect(self._on_double_click)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._tree)

    def set_root(self, path: str):
        self._root = path
        self._model.setRootPath(path)
        self._tree.setRootIndex(self._model.index(path))
        short = path if len(path) < 30 else "…" + path[-27:]
        self._path_label.setText(short)

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Ordner öffnen", self._root)
        if folder:
            self.set_root(folder)

    def _on_double_click(self, index):
        path = self._model.filePath(index)
        if os.path.isfile(path):
            self.file_open_requested.emit(path)

    def _show_context_menu(self, pos):
        index = self._tree.indexAt(pos)
        path = self._model.filePath(index) if index.isValid() else self._root
        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu {{
                background: {THEME['bg_panel']};
                color: {THEME['text']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item:selected {{
                background: {THEME['accent']};
                color: white;
                border-radius: 3px;
            }}
            """
        )
        if os.path.isfile(path):
            menu.addAction("Öffnen", lambda: self.file_open_requested.emit(path))
            menu.addSeparator()
        menu.addAction("Neue Datei", lambda: self._new_file(
            os.path.dirname(path) if os.path.isfile(path) else path
        ))
        menu.addAction("Neuer Ordner", lambda: self._new_folder(
            os.path.dirname(path) if os.path.isfile(path) else path
        ))
        if os.path.exists(path) and path != self._root:
            menu.addSeparator()
            menu.addAction("Löschen", lambda: self._delete(path))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _new_file(self, folder: str):
        name, ok = QInputDialog.getText(self, "Neue Datei", "Dateiname:")
        if ok and name:
            fp = os.path.join(folder, name)
            try:
                open(fp, "a").close()
                self.file_open_requested.emit(fp)
            except Exception as e:
                QMessageBox.critical(self, "Fehler", str(e))

    def _new_folder(self, parent: str):
        name, ok = QInputDialog.getText(self, "Neuer Ordner", "Ordnername:")
        if ok and name:
            try:
                os.makedirs(os.path.join(parent, name), exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Fehler", str(e))

    def _delete(self, path: str):
        reply = QMessageBox.question(
            self, "Löschen?",
            f'"{os.path.basename(path)}" wirklich löschen?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    import shutil
                    shutil.rmtree(path)
            except Exception as e:
                QMessageBox.critical(self, "Fehler", str(e))
