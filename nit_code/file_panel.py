"""Dateibaum-Panel (linke Sidebar)."""
import os
import sys
import tempfile
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QDir, QThread, QSortFilterProxyModel, QModelIndex
from PyQt6.QtGui import QFileSystemModel, QIcon, QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView,
    QPushButton, QLabel, QFileDialog, QMenu, QInputDialog,
    QMessageBox, QListWidget, QListWidgetItem, QSplitter,
)

from .config import THEME


class _DirsFirstProxy(QSortFilterProxyModel):
    """Sortiert Verzeichnisse vor Dateien und danach alphabetisch."""

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return super().lessThan(left, right)

        left_is_dir = model.fileInfo(left).isDir()
        right_is_dir = model.fileInfo(right).isDir()
        if left_is_dir != right_is_dir:
            return left_is_dir and not right_is_dir

        left_name = str(model.data(left, Qt.ItemDataRole.DisplayRole) or "")
        right_name = str(model.data(right, Qt.ItemDataRole.DisplayRole) or "")
        return left_name.casefold() < right_name.casefold()


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
        self._model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot
        )
        self._model.setNameFilters(["*.py", "*.txt", "*.json", "*.md", "*.csv",
                                    "*.html", "*.css", "*.js", "*.bin", "*.mpy"])
        # Ordner immer sichtbar lassen; nur nicht passende Dateien ausgrauen.
        self._model.setNameFilterDisables(True)

        self._proxy = _DirsFirstProxy(self)
        self._proxy.setSourceModel(self._model)

        self._tree = QTreeView()
        self._tree.setModel(self._proxy)
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
        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._tree.doubleClicked.connect(self._on_double_click)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._tree)

    def set_root(self, path: str):
        self._root = path
        self._model.setRootPath(path)
        source_root = self._model.index(path)
        self._tree.setRootIndex(self._proxy.mapFromSource(source_root))
        short = path if len(path) < 30 else "…" + path[-27:]
        self._path_label.setText(short)

    def _index_to_path(self, index) -> str:
        if not index.isValid():
            return self._root
        source_index = self._proxy.mapToSource(index)
        return self._model.filePath(source_index)

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Ordner öffnen", self._root)
        if folder:
            self.set_root(folder)

    def _on_double_click(self, index):
        path = self._index_to_path(index)
        if os.path.isfile(path):
            self.file_open_requested.emit(path)

    def _show_context_menu(self, pos):
        index = self._tree.indexAt(pos)
        path = self._index_to_path(index)
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
            menu.addAction("Öffnen mit …", lambda: self._open_with(path))
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

    def _open_with(self, path: str):
        app, _ = QFileDialog.getOpenFileName(
            self,
            "Programm für 'Öffnen mit …' wählen",
            "/usr/bin",
            "Alle Dateien (*)",
        )
        if not app:
            return
        try:
            subprocess.Popen([app, path])
        except Exception as e:
            QMessageBox.critical(self, "Fehler", str(e))

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


# ──────────────────────────────────────────────────────────────────────────────
# Controller-Dateiliste
# ──────────────────────────────────────────────────────────────────────────────

class _DeviceListWorker(QThread):
    result       = pyqtSignal(list)   # [(name, size_str), ...]
    firmware_info = pyqtSignal(str)   # Firmware-Version-String
    error        = pyqtSignal(str)

    def __init__(self, port: str):
        super().__init__()
        self._port = port

    def run(self):
        code = (
            "import os, sys\n"
            "v = sys.implementation\n"
            "print('FIRMWARE:' + sys.version + ' auf ' + sys.platform)\n"
            "for f in sorted(os.listdir()):\n"
            "    try:\n"
            "        print(str(os.stat(f)[6]) + '|' + f)\n"
            "    except:\n"
            "        print('?|' + f)\n"
        )
        try:
            r = subprocess.run(
                [sys.executable, "-m", "mpremote", "connect", self._port, "exec", code],
                capture_output=True, text=True, timeout=12,
            )
        except Exception as e:
            self.error.emit(str(e))
            return
        if r.returncode != 0:
            self.error.emit(r.stderr.strip() or "Verbindung fehlgeschlagen")
            return
        files = []
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("FIRMWARE:"):
                self.firmware_info.emit(line[len("FIRMWARE:"):])
            elif "|" in line:
                size_str, name = line.split("|", 1)
                files.append((name.strip(), size_str.strip()))
        self.result.emit(files)


class DeviceFilePanel(QWidget):
    """Zeigt Dateien auf dem angeschlossenen MicroPython-Controller."""

    file_open_requested = pyqtSignal(str)
    refresh_started     = pyqtSignal()
    refresh_done        = pyqtSignal()
    firmware_info       = pyqtSignal(str)   # Firmware-Version an main_window weiterleiten

    def __init__(self, parent=None):
        super().__init__(parent)
        self._port = ""
        self._worker: _DeviceListWorker | None = None
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(f"background:{THEME['bg_panel']};")
        h = QHBoxLayout(header)
        h.setContentsMargins(8, 6, 4, 6)
        title = QLabel("CONTROLLER")
        title.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:11px; font-weight:bold; letter-spacing:1px;"
        )
        h.addWidget(title)
        h.addStretch()
        self._btn_refresh = QPushButton("↻")
        self._btn_refresh.setToolTip("Dateiliste aktualisieren")
        self._btn_refresh.setFixedSize(22, 22)
        self._btn_refresh.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{THEME['accent']};"
            f" border:none; font-size:14px; }}"
            f"QPushButton:hover {{ color:{THEME['accent_hover']}; }}"
        )
        self._btn_refresh.clicked.connect(lambda: self.refresh(self._port))
        h.addWidget(self._btn_refresh)
        layout.addWidget(header)

        # Trennlinie
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{THEME['border']};")
        layout.addWidget(sep)

        # Status
        self._status_lbl = QLabel("(kein Gerät verbunden)")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:11px; padding:6px;"
        )
        layout.addWidget(self._status_lbl)

        # Dateiliste
        self._list = QListWidget()
        self._list.setStyleSheet(
            f"""
            QListWidget {{
                background: {THEME['bg_dark']};
                color: {THEME['text']};
                border: none;
                outline: none;
                font-size: 12px;
            }}
            QListWidget::item:hover {{
                background: {THEME['selection']};
            }}
            QListWidget::item:selected {{
                background: {THEME['accent']};
                color: white;
            }}
            """
        )
        self._list.setVisible(False)
        self._list.doubleClicked.connect(self._on_double_click)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list)
        layout.addStretch()   # leerer Raum bleibt unten

    def refresh(self, port: str):
        self._port = port
        self._list.clear()
        self._list.setVisible(False)
        if not port:
            self._status_lbl.setText("(kein Gerät verbunden)")
            self._status_lbl.setVisible(True)
            return
        self._status_lbl.setText(f"⏳ Lade {port} …")
        self._status_lbl.setVisible(True)
        self._btn_refresh.setEnabled(False)

        worker = _DeviceListWorker(port)
        worker.result.connect(self._on_result)
        worker.firmware_info.connect(self.firmware_info)
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda: self._btn_refresh.setEnabled(True))
        worker.finished.connect(lambda: self.refresh_done.emit())
        worker.start()
        self._worker = worker
        self.refresh_started.emit()

    def _on_result(self, files: list):
        self._list.clear()
        if not files:
            self._status_lbl.setText("(keine Dateien auf Controller)")
            self._status_lbl.setVisible(True)
            self._list.setVisible(False)
            return
        for name, size in files:
            label = f"{name}  ({size} B)" if size != "?" else name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(item)
        self._status_lbl.setVisible(False)
        self._list.setVisible(True)

    def _on_error(self, msg: str):
        self._status_lbl.setText(f"⚠ {msg}")
        self._status_lbl.setVisible(True)
        self._list.setVisible(False)

    def _on_double_click(self, index):
        item = self._list.currentItem()
        if item:
            self._open_file(item.data(Qt.ItemDataRole.UserRole))

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
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
        if item:
            name = item.data(Qt.ItemDataRole.UserRole)
            menu.addAction("📂 Öffnen (herunterladen)", lambda: self._open_file(name))
            menu.addSeparator()
            menu.addAction("🗑 Vom Controller löschen", lambda: self._delete_file(name))
        menu.addSeparator()
        menu.addAction("↻ Aktualisieren", lambda: self.refresh(self._port))
        menu.exec(self._list.viewport().mapToGlobal(pos))

    def _open_file(self, name: str):
        if not self._port or not name:
            return
        tmp_path = os.path.join(tempfile.gettempdir(), name)
        try:
            r = subprocess.run(
                [sys.executable, "-m", "mpremote", "connect", self._port,
                 "cp", f":{name}", tmp_path],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                self.file_open_requested.emit(tmp_path)
            else:
                QMessageBox.critical(self, "Fehler", r.stderr.strip() or "Download fehlgeschlagen")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", str(e))

    def _delete_file(self, name: str):
        reply = QMessageBox.question(
            self, "Löschen?",
            f'"{name}" vom Controller löschen?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            r = subprocess.run(
                [sys.executable, "-m", "mpremote", "connect", self._port,
                 "rm", f":{name}"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                self.refresh(self._port)
            else:
                QMessageBox.critical(self, "Fehler", r.stderr.strip() or "Löschen fehlgeschlagen")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", str(e))

