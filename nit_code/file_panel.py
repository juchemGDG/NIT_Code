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

from .config import THEME, tool_command


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
        self._header = QWidget()
        h_layout = QHBoxLayout(self._header)
        h_layout.setContentsMargins(8, 6, 4, 6)

        self._title_lbl = QLabel("DATEIEN")
        h_layout.addWidget(self._title_lbl)
        h_layout.addStretch()

        self._btn_open = QPushButton("⊕")
        self._btn_open.setToolTip("Ordner öffnen")
        self._btn_open.setFixedSize(22, 22)
        self._btn_open.clicked.connect(self._open_folder)
        h_layout.addWidget(self._btn_open)
        layout.addWidget(self._header)

        # Aktueller Pfad
        self._path_label = QLabel()
        self._path_label.setWordWrap(True)
        layout.addWidget(self._path_label)

        # Trennlinie
        self._sep_widget = QWidget()
        self._sep_widget.setFixedHeight(1)
        layout.addWidget(self._sep_widget)

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
        self.refresh_theme()

    def refresh_theme(self):
        self._header.setStyleSheet(f"background:{THEME['bg_panel']};")
        self._title_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:11px; font-weight:bold; letter-spacing:1px;"
        )
        self._btn_open.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{THEME['accent']};"
            f" border:none; font-size:16px; }}"
            f"QPushButton:hover {{ color:{THEME['accent_hover']}; }}"
        )
        self._path_label.setStyleSheet(
            f"background:{THEME['bg_panel']}; color:{THEME['text_dim']};"
            f" font-size:10px; padding:2px 8px 4px 8px;"
        )
        self._sep_widget.setStyleSheet(f"background:{THEME['border']};")
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
    result       = pyqtSignal(list)   # [(name, size_str, is_dir), ...]
    firmware_info = pyqtSignal(str)   # Firmware-Version-String
    error        = pyqtSignal(str)

    def __init__(self, port: str, subdir: str = ""):
        super().__init__()
        self._port = port
        self._subdir = subdir   # "" = Wurzelverzeichnis, sonst z. B. "lib"

    @staticmethod
    def _friendly_error(raw: str) -> str:
        """Macht aus einem mpremote-Traceback eine kurze, verständliche Meldung."""
        low = raw.lower()
        if "could not enter raw repl" in low or "raw repl" in low:
            return ("Controller gerade beschäftigt – bitte ↻ erneut versuchen "
                    "(läuft noch ein Programm?).")
        if "no device" in low or "failed to access" in low or "could not open" in low:
            return "Kein Controller gefunden. Ist das Gerät angeschlossen?"
        # Nur die letzte, aussagekräftige Zeile zeigen statt des ganzen Tracebacks
        last = next((ln.strip() for ln in reversed(raw.splitlines()) if ln.strip()), raw)
        return last[:200]

    def run(self):
        # Verzeichnis, das gelistet werden soll (als Python-Literal eingebettet).
        code = (
            "import os, sys\n"
            "v = sys.implementation\n"
            "print('FIRMWARE:' + sys.version + ' auf ' + sys.platform)\n"
            f"p = {self._subdir!r}\n"
            "entries = os.listdir(p) if p else os.listdir()\n"
            "for f in sorted(entries):\n"
            "    full = (p + '/' + f) if p else f\n"
            "    try:\n"
            "        st = os.stat(full)\n"
            "        d = '1' if (st[0] & 0x4000) else '0'\n"
            "        print(d + '|' + str(st[6]) + '|' + f)\n"
            "    except:\n"
            "        print('0|?|' + f)\n"
        )
        # Der serielle Port kann kurzzeitig belegt sein (REPL-Shell, laufendes
        # Programm). Das äußert sich in "could not enter raw repl" – in dem Fall
        # ein paar Mal mit kurzer Pause erneut versuchen, statt sofort zu scheitern.
        import time
        r = None
        last_err = ""
        for attempt in range(3):
            try:
                r = subprocess.run(
                    [*tool_command("mpremote"), "connect", self._port, "exec", code],
                    capture_output=True, text=True, timeout=12,
                )
            except Exception as e:
                last_err = str(e)
                r = None
            else:
                if r.returncode == 0:
                    break
                last_err = r.stderr.strip() or "Verbindung fehlgeschlagen"
            if "raw repl" in last_err.lower() or "could not enter" in last_err.lower() \
                    or (r is None):
                time.sleep(0.4)
                continue
            break

        if r is None or r.returncode != 0:
            self.error.emit(self._friendly_error(last_err))
            return
        files = []
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("FIRMWARE:"):
                self.firmware_info.emit(line[len("FIRMWARE:"):])
            elif line.count("|") >= 2:
                dir_flag, size_str, name = line.split("|", 2)
                files.append((name.strip(), size_str.strip(), dir_flag.strip() == "1"))
        self.result.emit(files)


class DeviceFilePanel(QWidget):
    """Zeigt Dateien auf dem angeschlossenen MicroPython-Controller."""

    file_open_requested = pyqtSignal(str)
    refresh_started     = pyqtSignal()
    refresh_done        = pyqtSignal()
    firmware_info       = pyqtSignal(str)   # Firmware-Version an main_window weiterleiten

    # Zusätzliche Datenrollen für Listeneinträge
    _ROLE_NAME   = Qt.ItemDataRole.UserRole
    _ROLE_IS_DIR = Qt.ItemDataRole.UserRole + 1
    _ROLE_IS_UP  = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._port = ""
        self._cwd = ""   # aktuell angezeigtes Verzeichnis ("" = Wurzel)
        self._worker: _DeviceListWorker | None = None
        self._retired_workers: list = []
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._dev_header = QWidget()
        h = QHBoxLayout(self._dev_header)
        h.setContentsMargins(8, 6, 4, 6)
        self._dev_title_lbl = QLabel("CONTROLLER")
        h.addWidget(self._dev_title_lbl)
        h.addStretch()
        self._btn_refresh = QPushButton("↻")
        self._btn_refresh.setToolTip("Dateiliste aktualisieren")
        self._btn_refresh.setFixedSize(22, 22)
        self._btn_refresh.clicked.connect(lambda: self.refresh(self._port))
        h.addWidget(self._btn_refresh)
        layout.addWidget(self._dev_header)

        # Trennlinie
        self._dev_sep = QWidget()
        self._dev_sep.setFixedHeight(1)
        layout.addWidget(self._dev_sep)

        # Status
        self._status_lbl = QLabel("(kein Gerät verbunden)")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_lbl)

        # Dateiliste
        self._list = QListWidget()
        self._list.setVisible(False)
        self._list.doubleClicked.connect(self._on_double_click)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list)
        layout.addStretch()   # leerer Raum bleibt unten
        self.refresh_theme()

    def refresh_theme(self):
        self._dev_header.setStyleSheet(f"background:{THEME['bg_panel']};")
        self._dev_title_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:11px; font-weight:bold; letter-spacing:1px;"
        )
        self._btn_refresh.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{THEME['accent']};"
            f" border:none; font-size:14px; }}"
            f"QPushButton:hover {{ color:{THEME['accent_hover']}; }}"
        )
        self._dev_sep.setStyleSheet(f"background:{THEME['border']};")
        self._status_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:11px; padding:6px;"
        )
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

    def refresh(self, port: str):
        # Bei einem anderen/getrennten Gerät zurück in die Wurzel springen –
        # der Pfad eines vorigen Controllers ist sonst evtl. ungültig.
        if port != self._port:
            self._cwd = ""
        self._port = port
        if not port:
            self._cwd = ""
            self._list.clear()
            self._list.setVisible(False)
            self._status_lbl.setText("(kein Gerät verbunden)")
            self._status_lbl.setVisible(True)
            return
        # Bereits angezeigte Dateien NICHT sofort löschen – erst beim Ergebnis
        # ersetzen. So bleibt die Liste bei einer kurzen Störung erhalten.

        # Keep a reference to the old worker until its thread has stopped so
        # QThread::~QThread() is never called while the thread is still running.
        old = self._worker
        if old is not None and old.isRunning():
            # Ergebnis-/Fehler-Signale trennen, damit ein verspätetes Resultat
            # des alten Workers (z. B. beim Wechsel in einen Unterordner) die
            # neue Ansicht nicht überschreibt.
            try:
                old.result.disconnect(self._on_result)
                old.error.disconnect(self._on_error)
                old.firmware_info.disconnect(self.firmware_info)
            except TypeError:
                pass
            self._retired_workers.append(old)
            old.finished.connect(
                lambda t=old: self._retired_workers.remove(t)
                if t in self._retired_workers else None
            )

        # Ladehinweis nur zeigen, wenn noch keine Dateien sichtbar sind –
        # sonst bleibt die bestehende Liste ruhig stehen.
        if self._list.count() == 0:
            self._status_lbl.setText(f"⏳ Lade {port} …")
            self._status_lbl.setVisible(True)
        self._btn_refresh.setEnabled(False)

        worker = _DeviceListWorker(port, self._cwd)
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
        self._update_title()

        # Im Unterordner: Eintrag zum Zurückspringen anbieten.
        if self._cwd:
            up = QListWidgetItem("⬆  ..  (zurück)")
            up.setData(self._ROLE_IS_UP, True)
            self._list.addItem(up)

        # Ordner zuerst, dann Dateien – jeweils alphabetisch.
        def _key(entry):
            name, _size, is_dir = entry
            return (0 if is_dir else 1, name.lower())

        for name, size, is_dir in sorted(files, key=_key):
            if is_dir:
                label = f"📁  {name}"
            elif size != "?":
                label = f"📄  {name}  ({size} B)"
            else:
                label = f"📄  {name}"
            item = QListWidgetItem(label)
            item.setData(self._ROLE_NAME, name)
            item.setData(self._ROLE_IS_DIR, is_dir)
            self._list.addItem(item)

        if not files and not self._cwd:
            self._status_lbl.setText("(keine Dateien auf Controller)")
            self._status_lbl.setVisible(True)
            self._list.setVisible(False)
            return
        if not files:
            self._status_lbl.setText("(Ordner ist leer)")
            self._status_lbl.setVisible(True)
        else:
            self._status_lbl.setVisible(False)
        self._list.setVisible(True)

    def _update_title(self):
        """Zeigt im Kopf das aktuelle Verzeichnis an."""
        if self._cwd:
            self._dev_title_lbl.setText(f"CONTROLLER / {self._cwd}")
        else:
            self._dev_title_lbl.setText("CONTROLLER")

    def _navigate_into(self, name: str):
        self._cwd = f"{self._cwd}/{name}" if self._cwd else name
        self._list.clear()   # alte Einträge nicht stehen lassen während des Ladens
        self.refresh(self._port)

    def _navigate_up(self):
        if "/" in self._cwd:
            self._cwd = self._cwd.rsplit("/", 1)[0]
        else:
            self._cwd = ""
        self._list.clear()
        self.refresh(self._port)

    def _remote_path(self, name: str) -> str:
        """Vollständiger Pfad auf dem Controller für einen Eintrag."""
        return f"{self._cwd}/{name}" if self._cwd else name

    def _on_error(self, msg: str):
        # Sind bereits Dateien sichtbar, NICHT die Liste leeren – die Anzeige
        # bleibt erhalten, der Fehler war vermutlich nur vorübergehend.
        if self._list.count() > 0:
            self._status_lbl.setVisible(False)
            self._list.setVisible(True)
            return
        self._status_lbl.setText(f"⚠ {msg}")
        self._status_lbl.setVisible(True)
        self._list.setVisible(False)

    def _on_double_click(self, index):
        item = self._list.currentItem()
        if not item:
            return
        if item.data(self._ROLE_IS_UP):
            self._navigate_up()
        elif item.data(self._ROLE_IS_DIR):
            self._navigate_into(item.data(self._ROLE_NAME))
        else:
            self._open_file(item.data(self._ROLE_NAME))

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
        if item and item.data(self._ROLE_IS_UP):
            pass   # "zurück"-Eintrag: nur Aktualisieren anbieten
        elif item and item.data(self._ROLE_IS_DIR):
            name = item.data(self._ROLE_NAME)
            menu.addAction("📂 Ordner öffnen", lambda: self._navigate_into(name))
            menu.addSeparator()
        elif item:
            name = item.data(self._ROLE_NAME)
            menu.addAction("📂 Öffnen (herunterladen)", lambda: self._open_file(name))
            menu.addAction("📦 In Ordner verschieben …", lambda: self._move_file(name))
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
                [*tool_command("mpremote"), "connect", self._port,
                 "cp", f":{self._remote_path(name)}", tmp_path],
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
                [*tool_command("mpremote"), "connect", self._port,
                 "rm", f":{self._remote_path(name)}"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                self.refresh(self._port)
            else:
                QMessageBox.critical(self, "Fehler", r.stderr.strip() or "Löschen fehlgeschlagen")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", str(e))

    def _visible_subdirs(self) -> list[str]:
        """Ordner im aktuell angezeigten Verzeichnis (aus der Liste gelesen)."""
        dirs = []
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it.data(self._ROLE_IS_DIR):
                dirs.append(it.data(self._ROLE_NAME))
        return dirs

    def _move_file(self, name: str):
        """Verschiebt eine Datei in einen (auch neuen) Ordner – per os.rename."""
        if not self._port or not name:
            return
        ROOT = "⬆  Hauptebene (Wurzel)"
        NEW  = "➕  Neuer Ordner …"
        label_to_dir: dict[str, str] = {}
        options: list[str] = []
        if self._cwd:
            options.append(ROOT)
            label_to_dir[ROOT] = ""
        for d in self._visible_subdirs():
            lab = f"📁  {d}"
            options.append(lab)
            label_to_dir[lab] = self._remote_path(d)
        options.append(NEW)

        choice, ok = QInputDialog.getItem(
            self, "Verschieben", f'"{name}" verschieben nach:', options, 0, False
        )
        if not ok:
            return

        if choice == NEW:
            new, ok2 = QInputDialog.getText(self, "Neuer Ordner", "Name des Ordners:")
            new = new.strip().strip("/")
            if not ok2 or not new:
                return
            target_dir = f"{self._cwd}/{new}" if self._cwd else new
        else:
            target_dir = label_to_dir.get(choice, "")

        src = self._remote_path(name)
        dst = f"{target_dir}/{name}" if target_dir else name
        if src == dst:
            return

        # Zielordner ggf. anlegen, dann auf dem Controller umbenennen/verschieben.
        code = "import os\n"
        if target_dir:
            code += f"try:\n os.mkdir({target_dir!r})\nexcept OSError: pass\n"
        code += f"os.rename({src!r}, {dst!r})\n"
        try:
            r = subprocess.run(
                [*tool_command("mpremote"), "connect", self._port, "exec", code],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                self.refresh(self._port)
            else:
                QMessageBox.critical(
                    self, "Fehler", r.stderr.strip() or "Verschieben fehlgeschlagen"
                )
        except Exception as e:
            QMessageBox.critical(self, "Fehler", str(e))

    def show_folder(self, port: str, folder: str = ""):
        """Öffnet das Geräte-Panel direkt in einem bestimmten Ordner."""
        self._port = port
        self._cwd = folder or ""
        self.refresh(port)

