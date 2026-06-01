"""Haupt-Fenster von NIT_Code."""
import os
import sys
import traceback
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QAction, QFont, QIcon, QKeySequence, QColor,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QLabel, QStatusBar, QToolBar, QToolButton,
    QComboBox, QFileDialog, QMessageBox, QInputDialog,
    QDialog, QPushButton,
)

from .config import APP_NAME, APP_VERSION, THEME, SUPPORTED_BOARDS
from .editor_widget import CodeEditor
from .file_panel import FilePanel, DeviceFilePanel
from .console_panel import ConsolePanel, ProcessRunner, MicroPythonRunner
from .settings_dialog import SettingsDialog
from .tutor_panel import TutorPanel


# ──────────────────────────────────────────────────────────────────────────────
# Globales Stylesheet
# ──────────────────────────────────────────────────────────────────────────────
GLOBAL_STYLE = f"""
QMainWindow, QWidget {{
    background: {THEME['bg_dark']};
    color: {THEME['text']};
    font-family: system-ui, -apple-system, 'Segoe UI', 'Ubuntu', 'Helvetica Neue', sans-serif;
    font-size: 13px;
}}
QMenuBar {{
    background: {THEME['bg_panel']};
    color: {THEME['text']};
    border-bottom: 1px solid {THEME['border']};
    padding: 2px 0;
}}
QMenuBar::item {{
    padding: 4px 12px;
    border-radius: 3px;
}}
QMenuBar::item:selected {{
    background: {THEME['accent']};
    color: white;
}}
QMenu {{
    background: {THEME['bg_panel']};
    color: {THEME['text']};
    border: 1px solid {THEME['border']};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 20px 5px 12px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background: {THEME['accent']};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {THEME['border']};
    margin: 3px 6px;
}}
QTabWidget::pane {{
    border: none;
    background: {THEME['bg_editor']};
}}
QTabBar::tab {{
    background: {THEME['bg_panel']};
    color: {THEME['text_dim']};
    padding: 6px 14px 6px 14px;
    border: none;
    border-right: 1px solid {THEME['border']};
    min-width: 80px;
}}
QTabBar::tab:selected {{
    background: {THEME['bg_editor']};
    color: {THEME['text']};
    border-top: 2px solid {THEME['accent']};
}}
QTabBar::tab:hover {{
    background: {THEME['selection']};
    color: {THEME['text']};
}}
QTabBar::close-button {{
    subcontrol-position: right;
    width: 14px;
    height: 14px;
    margin-left: 4px;
    border-radius: 3px;
}}
QTabBar::close-button:hover {{
    background: {THEME['accent']};
}}
QSplitter::handle {{
    background: {THEME['border']};
}}
QToolBar {{
    background: {THEME['bg_panel']};
    border: none;
    border-bottom: 1px solid {THEME['border']};
    spacing: 4px;
    padding: 2px 6px;
}}
QToolButton {{
    background: transparent;
    color: {THEME['text']};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}
QToolButton:hover {{
    background: {THEME['selection']};
    color: {THEME['accent']};
}}
QToolButton:pressed {{
    background: {THEME['accent']};
    color: white;
}}
QStatusBar {{
    background: {THEME['bg_panel']};
    color: {THEME['text_dim']};
    border-top: 1px solid {THEME['border']};
    font-size: 11px;
    padding: 0 8px;
}}
QScrollBar:vertical {{
    background: {THEME['bg_dark']};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {THEME['border']};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {THEME['accent']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {THEME['bg_dark']};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {THEME['border']};
    border-radius: 4px;
    min-width: 20px;
}}
"""


# ──────────────────────────────────────────────────────────────────────────────
# Tab-Daten
# ──────────────────────────────────────────────────────────────────────────────
class EditorTab:
    def __init__(self, filepath: str | None = None):
        self.filepath: str | None = filepath
        self.editor = CodeEditor()
        self.modified = False

    @property
    def display_name(self) -> str:
        if self.filepath:
            return os.path.basename(self.filepath)
        return "Unbenannt"


# ──────────────────────────────────────────────────────────────────────────────
# Haupt-Fenster
# ──────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._tabs: list[EditorTab] = []
        self._mode = "python"       # "python" | "micropython"
        self._board = "ESP32"
        self._process: ProcessRunner | None = None
        self._retired_threads: list = []   # hält QThread-Referenzen bis finished
        self._port_busy = False     # verhindert gleichzeitige mpremote-Prozesse
        self._settings_font_size: int = 14
        self._settings_line_numbers: bool = True
        self._settings_word_wrap: bool = False
        self._settings_highlight_line: bool = True
        self._settings_autosave_secs: int = 0
        self._settings_python_exec: str = ""
        self._settings_scrollback: int = 5000
        self._settings_tutor_enabled: bool = False
        self._settings_tutor_url: str = ""
        self._settings_tutor_model: str = ""
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave_all)
        self._setup_window()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()
        self._new_tab()             # Startdatei
        self._apply_settings()      # Standard-Einstellungen sofort anwenden
        # currentIndexChanged feuerte beim addItem noch nicht (Signal erst danach verbunden)
        # → Modus einmalig manuell initialisieren
        QTimer.singleShot(0, lambda: self._on_mode_changed(0))

    # ──────────────────────────────────────────────────────────────────────
    # Fenster
    # ──────────────────────────────────────────────────────────────────────
    def _setup_window(self):
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1280, 780)
        self.setStyleSheet(GLOBAL_STYLE)
        # Window-Icon (falls Logo noch nicht per app.setWindowIcon gesetzt)
        from pathlib import Path
        from PyQt6.QtGui import QIcon as _QIcon, QPixmap as _QPixmap
        for p in [
            Path(__file__).resolve().parent / "logo.png",
            Path(__file__).resolve().parent.parent / "logo.png",
        ]:
            if p.exists():
                px = _QPixmap(str(p))
                if not px.isNull():
                    self.setWindowIcon(_QIcon(px))
                    break

    # ──────────────────────────────────────────────────────────────────────
    # Menüleiste
    # ──────────────────────────────────────────────────────────────────────
    def _setup_menubar(self):
        mb = self.menuBar()

        # ── Datei ──
        m_file = mb.addMenu("Datei")
        self._add_action(m_file, "Neu",          self._new_tab,       "Ctrl+N")
        self._add_action(m_file, "Öffnen …",     self._open_file,     "Ctrl+O")
        self._add_action(m_file, "Speichern",    self._save_file,     "Ctrl+S")
        self._add_action(m_file, "Speichern als …", self._save_file_as, "Ctrl+Shift+S")
        m_file.addSeparator()
        self._add_action(m_file, "⚙  Einstellungen …", self._open_settings, "Ctrl+,")
        m_file.addSeparator()
        self._add_action(m_file, "Beenden",      self.close,          "Ctrl+Q")

        # ── Bearbeiten ──
        m_edit = mb.addMenu("Bearbeiten")
        self._add_action(m_edit, "Rückgängig",   self._undo,  "Ctrl+Z")
        self._add_action(m_edit, "Wiederholen",  self._redo,  "Ctrl+Y")
        m_edit.addSeparator()
        self._add_action(m_edit, "Ausschneiden", self._cut,   "Ctrl+X")
        self._add_action(m_edit, "Kopieren",     self._copy,  "Ctrl+C")
        self._add_action(m_edit, "Einfügen",     self._paste, "Ctrl+V")

        # ── Ausführen ──
        m_run = mb.addMenu("Ausführen")
        self._add_action(m_run, "Programm starten",  self._run_program, "F5")
        self._add_action(m_run, "Stoppen",           self._stop_program, "F6")
        m_run.addSeparator()
        self._act_upload = self._add_action(
            m_run, "Auf Controller hochladen", self._upload_to_device, "F7"
        )
        self._act_upload.setVisible(False)

        # ── Python ──
        self._m_python = mb.addMenu("Python")
        self._add_action(self._m_python, "📦  Pakete installieren (pip) …", self._open_pip_manager)
        self._m_upy = mb.addMenu("MicroPython")
        self._m_upy.setEnabled(False)

        self._act_flash = self._add_action(
            self._m_upy, "Firmware flashen …", self._flash_firmware
        )
        self._act_libs = self._add_action(
            self._m_upy, "Bibliotheken installieren …", self._open_library_manager
        )
        self._m_upy.addSeparator()
        self._add_action(
            self._m_upy, "ℹ️  Firmware-Version abfragen", self._query_firmware_version
        )
        self._add_action(
            self._m_upy, "🔄  Controller neu starten", self._reset_controller
        )
        self._m_upy.addSeparator()

        # ── Hilfe ──
        m_help = mb.addMenu("Hilfe")
        self._add_action(m_help, f"Über {APP_NAME}", self._show_about)

    def _add_action(self, menu, label: str, slot, shortcut: str | None = None):
        act = QAction(label, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    # ──────────────────────────────────────────────────────────────────────
    # Toolbar
    # ──────────────────────────────────────────────────────────────────────
    def _setup_toolbar(self):
        tb = self.addToolBar("Hauptleiste")
        tb.setMovable(False)

        def tbtn(label, slot, tooltip=""):
            act = QAction(label, self)
            act.setToolTip(tooltip)
            act.triggered.connect(slot)
            tb.addAction(act)
            return act

        tbtn("▶  Starten", self._run_program, "Programm ausführen (F5)")
        tbtn("■  Stoppen", self._stop_program, "Ausführung stoppen (F6)")
        tb.addSeparator()

        # Modus-Auswahl
        mode_lbl = QLabel("  Modus: ")
        mode_lbl.setStyleSheet(f"color:{THEME['text_dim']};")
        tb.addWidget(mode_lbl)

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("🐍  Python (lokal)", "python")
        self._mode_combo.addItem("⚡  MicroPython", "micropython")
        self._mode_combo.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f" border:1px solid {THEME['border']}; border-radius:4px;"
            f" padding:3px 6px; min-width:160px;"
        )
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        tb.addWidget(self._mode_combo)

        tb.addSeparator()

        # Geräte-Auswahl (nur im MicroPython-Modus sichtbar)
        self._port_lbl = QLabel("  Gerät: ")
        self._port_lbl.setStyleSheet(f"color:{THEME['text_dim']};")
        self._port_lbl_act = tb.addWidget(self._port_lbl)

        self._port_combo = QComboBox()
        self._port_combo.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f" border:1px solid {THEME['border']}; border-radius:4px;"
            f" padding:3px 6px; min-width:200px;"
        )
        self._port_combo.currentIndexChanged.connect(self._on_port_selected)
        self._port_combo_act = tb.addWidget(self._port_combo)

        self._port_refresh_act = tbtn("↻", self._refresh_ports, "Geräte aktualisieren")
        # Widget für den ↻-Button suchen und vergrößern
        for w in tb.findChildren(QToolButton):
            if w.text() == "↻":
                w.setStyleSheet(
                    f"QToolButton {{ font-size:18px; padding:2px 6px; "
                    f"background:transparent; color:{THEME['text']}; border:none; border-radius:4px; }}"
                    f"QToolButton:hover {{ background:{THEME['accent']}; color:#fff; }}"
                )
                break
        self._port_lbl_act.setVisible(False)
        self._port_combo_act.setVisible(False)
        self._port_refresh_act.setVisible(False)

        tb.addSeparator()
        self._upload_btn_act = tbtn("↑  Hochladen", self._upload_to_device,
                                     "Code auf Controller übertragen (F7)")
        self._reset_btn_act = tbtn("🔄  Neustart", self._reset_controller,
                                    "Controller neu starten")
        self._upload_btn_act.setVisible(False)
        self._reset_btn_act.setVisible(False)

        # Timer für automatisches Port-Scanning im MicroPython-Modus
        self._port_scan_timer = QTimer(self)
        self._port_scan_timer.setInterval(3000)
        self._port_scan_timer.timeout.connect(self._refresh_ports)

    # ──────────────────────────────────────────────────────────────────────
    # Zentralbereich
    # ──────────────────────────────────────────────────────────────────────
    def _setup_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Haupt-Splitter: Links (Dateien) | Rechts (Editor + Konsole)
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setHandleWidth(2)

        # Linker Bereich: vertikaler Splitter (lokale Dateien + Controller-Dateien)
        self._left_splitter = QSplitter(Qt.Orientation.Vertical)
        self._left_splitter.setHandleWidth(2)
        self._left_splitter.setMinimumWidth(180)
        self._left_splitter.setMaximumWidth(350)

        self._file_panel = FilePanel()
        self._file_panel.setMinimumWidth(0)
        self._file_panel.setMaximumWidth(10000)
        self._file_panel.file_open_requested.connect(self._open_file_path)
        self._left_splitter.addWidget(self._file_panel)

        self._device_panel = DeviceFilePanel()
        self._device_panel.file_open_requested.connect(self._open_file_path)
        self._device_panel.setVisible(False)
        self._left_splitter.addWidget(self._device_panel)
        # FilePanel wächst mit, DeviceFilePanel bleibt kompakt
        self._left_splitter.setStretchFactor(0, 1)
        self._left_splitter.setStretchFactor(1, 0)

        self._main_splitter.addWidget(self._left_splitter)

        # Rechter Bereich: vertikaler Splitter (Editor oben, Konsole unten)
        self._right_splitter = QSplitter(Qt.Orientation.Vertical)
        self._right_splitter.setHandleWidth(2)

        # Editor-Tabs
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.tabCloseRequested.connect(self._close_tab)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        self._right_splitter.addWidget(self._tab_widget)

        # Konsole
        self._console = ConsolePanel()
        self._console.error_link_clicked.connect(self._jump_to_error)
        self._device_panel.refresh_started.connect(self._on_device_refresh_start)
        self._device_panel.refresh_done.connect(self._on_device_refresh_done)
        self._device_panel.firmware_info.connect(
            lambda info: self._console.append_success(f"✓  MicroPython {info}\n")
        )
        self._right_splitter.addWidget(self._console)

        self._right_splitter.setSizes([520, 200])
        self._main_splitter.addWidget(self._right_splitter)

        # Tutor-Panel (standardmäßig ausgeblendet)
        self._tutor_panel = TutorPanel()
        self._tutor_panel.setVisible(False)
        self._main_splitter.addWidget(self._tutor_panel)

        self._main_splitter.setSizes([220, 1060, 0])

        root_layout.addWidget(self._main_splitter)

    # ──────────────────────────────────────────────────────────────────────
    # Statusleiste
    # ──────────────────────────────────────────────────────────────────────
    def _setup_statusbar(self):
        sb = self.statusBar()
        self._status_mode = QLabel("Python (lokal)")
        self._status_mode.setStyleSheet(
            f"color:{THEME['accent']}; font-weight:bold; padding:0 8px;"
        )
        sb.addPermanentWidget(self._status_mode)

        self._status_board = QLabel("")
        self._status_board.setStyleSheet(f"color:{THEME['text_dim']}; padding:0 8px;")
        sb.addPermanentWidget(self._status_board)

        self._status_file = QLabel("Bereit")
        sb.addWidget(self._status_file)

    # ──────────────────────────────────────────────────────────────────────
    # Port-Busy-Verwaltung (verhindert parallele mpremote-Prozesse)
    # ──────────────────────────────────────────────────────────────────────
    def _acquire_port(self) -> bool:
        """True wenn Port frei war und jetzt reserviert wird, sonst False."""
        if self._port_busy:
            self._console.append_error(
                "⚠  Port wird gerade verwendet. Bitte kurz warten.\n"
            )
            return False
        self._port_busy = True
        self._console.pause_shell()
        return True

    def _release_port(self):
        self._port_busy = False
        self._console.resume_shell()

    def _retire_process(self):
        """Alten self._process sicher aufbewahren bis QThread.finished feuert.
        Verhindert 'QThread destroyed while still running' → abort()."""
        old = self._process
        if old is None:
            return
        if old.isRunning():
            old.terminate_process()
            self._retired_threads.append(old)
            old.finished.connect(
                lambda t=old: self._retired_threads.remove(t)
                if t in self._retired_threads else None
            )

    def _on_device_refresh_start(self):
        self._port_busy = True
        self._console.pause_shell()

    def _on_device_refresh_done(self):
        self._port_busy = False
        self._console.resume_shell()
    def _new_tab(self, filepath: str | None = None):
        tab = EditorTab(filepath)
        if filepath and os.path.isfile(filepath):
            try:
                with open(filepath, encoding="utf-8") as f:
                    tab.editor.set_text(f.read())
            except Exception as e:
                self._console.append_error(f"Datei konnte nicht geladen werden: {e}\n")

        self._tabs.append(tab)
        idx = self._tab_widget.addTab(tab.editor, tab.display_name)
        self._tab_widget.setCurrentIndex(idx)
        return tab

    def _close_tab(self, index: int):
        tab = self._tabs[index]
        if tab.editor.is_modified():
            reply = QMessageBox.question(
                self, "Ungespeicherte Änderungen",
                f'"{tab.display_name}" hat ungespeicherte Änderungen.\nTrotzdem schließen?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._tabs.pop(index)
        self._tab_widget.removeTab(index)
        if not self._tabs:
            self._new_tab()

    def _current_tab(self) -> EditorTab | None:
        idx = self._tab_widget.currentIndex()
        if 0 <= idx < len(self._tabs):
            return self._tabs[idx]
        return None

    def _on_tab_changed(self, index: int):
        tab = self._tabs[index] if 0 <= index < len(self._tabs) else None
        if tab:
            name = tab.filepath or tab.display_name
            self._status_file.setText(name)

    def _update_tab_title(self, tab: EditorTab):
        idx = self._tabs.index(tab)
        title = ("● " if tab.editor.is_modified() else "") + tab.display_name
        self._tab_widget.setTabText(idx, title)

    # ──────────────────────────────────────────────────────────────────────
    # Dateioperationen
    # ──────────────────────────────────────────────────────────────────────
    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Datei öffnen", str(Path.home()),
            "Python-Dateien (*.py);;Alle Dateien (*)"
        )
        if path:
            self._open_file_path(path)

    def _open_file_path(self, path: str):
        # Prüfen ob bereits geöffnet
        for i, tab in enumerate(self._tabs):
            if tab.filepath == path:
                self._tab_widget.setCurrentIndex(i)
                return
        self._new_tab(path)
        # Dateibaum auf das Verzeichnis der geöffneten Datei setzen
        folder = os.path.dirname(os.path.abspath(path))
        if os.path.isdir(folder):
            self._file_panel.set_root(folder)

    def _save_file(self):
        tab = self._current_tab()
        if not tab:
            return
        if tab.filepath:
            self._do_save(tab, tab.filepath)
        else:
            self._save_file_as()

    def _save_file_as(self):
        tab = self._current_tab()
        if not tab:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Speichern als", str(Path.home()),
            "Python-Dateien (*.py);;Alle Dateien (*)"
        )
        if path:
            tab.filepath = path
            self._do_save(tab, path)
            self._update_tab_title(tab)

    def _do_save(self, tab: EditorTab, path: str, silent: bool = False):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(tab.editor.get_text())
            if hasattr(tab.editor, "sci"):
                tab.editor.sci.setModified(False)
            self._update_tab_title(tab)
            self._status_file.setText(f"💾  Gespeichert: {os.path.basename(path)}")
            # Statusmeldung nach 3 Sekunden zurücksetzen
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(3000, lambda: self._status_file.setText(path))
            if not silent:
                self._console.append_success(f"Gespeichert: {path}\n")
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Speichern", str(e))

    # ──────────────────────────────────────────────────────────────────────
    # Bearbeiten-Aktionen
    # ──────────────────────────────────────────────────────────────────────
    def _undo(self):
        tab = self._current_tab()
        if tab and hasattr(tab.editor, "sci"):
            tab.editor.sci.undo()

    def _redo(self):
        tab = self._current_tab()
        if tab and hasattr(tab.editor, "sci"):
            tab.editor.sci.redo()

    def _cut(self):
        tab = self._current_tab()
        if tab and hasattr(tab.editor, "sci"):
            tab.editor.sci.cut()

    def _copy(self):
        tab = self._current_tab()
        if tab and hasattr(tab.editor, "sci"):
            tab.editor.sci.copy()

    def _paste(self):
        tab = self._current_tab()
        if tab and hasattr(tab.editor, "sci"):
            tab.editor.sci.paste()

    # ────────────────────────────────────────────────────────────────────��─
    # Modus & Board
    # ──────────────────────────────────────────────────────────────────────
    def _on_mode_changed(self, index: int):
        self._mode = self._mode_combo.itemData(index)
        is_upy = self._mode == "micropython"
        self._m_upy.setEnabled(is_upy)
        self._m_python.setEnabled(not is_upy)
        self._port_lbl_act.setVisible(is_upy)
        self._port_combo_act.setVisible(is_upy)
        self._port_refresh_act.setVisible(is_upy)
        self._act_upload.setVisible(is_upy)
        self._upload_btn_act.setVisible(is_upy)
        self._reset_btn_act.setVisible(is_upy)
        self._device_panel.setVisible(is_upy)
        if is_upy:
            self._refresh_ports()
            self._port_scan_timer.start()
            self._status_mode.setText("MicroPython")
            self._left_splitter.setSizes([300, 250])
        else:
            self._port_scan_timer.stop()
            self._status_mode.setText("Python (lokal)")
            self._device_panel.refresh("")
            self._left_splitter.setSizes([600, 0])
            self._console.set_shell_mode("python",
                                         python_exec=self._get_python_executable())

    def _set_board(self, board_id: str):
        self._board = board_id

    # ──────────────────────────────────────────────────────────────────────
    # Programmausführung
    # ──────────────────────────────────────────────────────────────────────
    def _run_program(self):
        tab = self._current_tab()
        if not tab:
            return
        # Unbenannte Datei: einmal Speichern-Dialog zeigen
        if not tab.filepath:
            self._save_file_as()
            if not tab.filepath:
                return
        else:
            # Lautlos speichern – kein Popup, nur Statusleiste
            self._do_save(tab, tab.filepath, silent=True)

        tab.editor.clear_error_markers()
        self._console.clear_output()
        self._console.append_info(f"▶  Starte: {tab.filepath}\n")

        self._retire_process()
        if self._mode == "python":
            python = self._get_python_executable()
            cmd = [python, "-u", tab.filepath]
            self._process = ProcessRunner(cmd, cwd=os.path.dirname(tab.filepath))
        else:
            # MicroPython: Raw-REPL über pyserial (stdin-Forwarding)
            port = self._get_serial_port()
            if not port:
                return
            # mpremote-Shell pausieren damit Port frei ist
            self._console.pause_shell()
            self._process = MicroPythonRunner(port, tab.filepath)
        self._process.output.connect(self._on_process_output)
        self._process.finished_run.connect(self._on_process_done)
        self._process.start()
        self._console.set_active_runner(self._process)

    def _stop_program(self):
        if self._process and self._process.isRunning():
            self._process.terminate_process()
            self._console.append_info("\n■  Abgebrochen.\n")
        self._console.set_active_runner(None)
        if self._mode == "micropython":
            self._console.resume_shell()

    def _on_process_output(self, text: str, kind: str):
        if kind == "stderr":
            self._console.append_error(text)
            # Fehlerzeilen im Editor markieren
            import re
            for m in re.finditer(r'File "([^"]+)", line (\d+)', text):
                fp, ln = m.group(1), int(m.group(2))
                tab = self._current_tab()
                if tab and tab.filepath and os.path.abspath(fp) == os.path.abspath(tab.filepath):
                    tab.editor.mark_error_line(ln)
        else:
            self._console.append_output(text)

    def _on_process_done(self, code: int):
        self._console.set_active_runner(None)
        if self._mode == "micropython":
            self._console.resume_shell()
        if code == 0:
            self._console.append_success(f"\n✓  Programm beendet (Code {code})\n")
        else:
            self._console.append_error(f"\n✗  Programm beendet mit Code {code}\n")

    # ──────────────────────────────────────────────────────────────────────
    # MicroPython-Aktionen
    # ──────────────────────────────────────────────────────────────────────
    def _upload_to_device(self):
        tab = self._current_tab()
        if not tab or not tab.filepath:
            self._save_file_as()
            tab = self._current_tab()
            if not tab or not tab.filepath:
                return
        else:
            self._do_save(tab, tab.filepath, silent=True)

        port = self._get_serial_port()
        if not port:
            return

        remote_name = os.path.basename(tab.filepath)
        self._console.append_info(f"↑  Lade {remote_name} auf {port} hoch ...\n")
        cmd = [sys.executable, "-m", "mpremote", "connect", port,
               "cp", tab.filepath, f":{remote_name}"]
        self._retire_process()
        self._process = ProcessRunner(cmd)
        self._process.output.connect(self._on_process_output)
        self._process.finished_run.connect(
            lambda code: self._console.append_success("✓  Upload abgeschlossen.\n")
            if code == 0 else self._console.append_error("✗  Upload fehlgeschlagen.\n")
        )
        self._process.start()

    def _flash_firmware(self):
        from .micropython_dialogs import FlashDialog
        dlg = FlashDialog(self._board, self)
        dlg.exec()

    def _query_firmware_version(self):
        port = self._get_serial_port()
        if not port:
            return
        if not self._acquire_port():
            return
        self._console.append_info(f"ℹ️  Lese Firmware-Version von {port} ...\n")
        code = (
            "import sys; "
            "v = sys.implementation; "
            "print('MicroPython', sys.version, 'auf', sys.platform); "
            "print('Implementation:', v.name, v.version)"
        )
        cmd = [sys.executable, "-m", "mpremote", "connect", port, "exec", code]
        proc = ProcessRunner(cmd)
        proc.output.connect(
            lambda text, kind: (
                self._console.append_success(text)
                if kind == "stdout"
                else self._console.append_error(text)
            )
        )
        proc.finished_run.connect(
            lambda rc: self._console.append_error(
                "✗  Konnte keine Verbindung herstellen.\n"
                "Bitte Controller anschließen und erneut versuchen.\n"
            ) if rc != 0 else None
        )
        proc.finished_run.connect(lambda _rc: self._release_port())
        self._retire_process()
        proc.start()
        self._process = proc

    def _reset_controller(self):
        port = self._get_serial_port()
        if not port:
            return
        if not self._acquire_port():
            return
        self._console.append_info(f"🔄  Starte Controller auf {port} neu ...\n")
        cmd = [
            sys.executable, "-m", "mpremote",
            "connect", port, "reset",
        ]
        proc = ProcessRunner(cmd)
        proc.finished_run.connect(
            lambda rc: self._console.append_success("✓  Controller neu gestartet.\n")
        )
        proc.finished_run.connect(lambda _rc: self._release_port())
        self._retire_process()
        proc.start()
        self._process = proc

    def _open_library_manager(self):
        from .micropython_dialogs import LibraryManagerDialog
        port = self._get_serial_port(silent=True)
        dlg = LibraryManagerDialog(port or "", self)
        dlg.exec()

    def _open_pip_manager(self):
        from .micropython_dialogs import PipManagerDialog
        dlg = PipManagerDialog(self)
        dlg.exec()

    # ──────────────────────────────────────────────────────────────────────
    # Fehlernavigation
    # ──────────────────────────────────────────────────────────────────────
    def _jump_to_error(self, filepath: str, lineno: int):
        self._open_file_path(filepath)
        tab = self._current_tab()
        if tab:
            tab.editor.goto_line(lineno)
            tab.editor.mark_error_line(lineno)

    # ──────────────────────────────────────────────────────────────────────
    # Hilfsfunktionen
    # ──────────────────────────────────────────────────────────────────────
    def _get_python_executable(self) -> str:
        venv_py = Path(__file__).parents[1] / ".venv" / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
        if venv_py.exists():
            return str(venv_py)
        return sys.executable

    def _refresh_ports(self):
        """Scannt serielle Ports und aktualisiert die Combo-Box in der Toolbar."""
        try:
            import serial.tools.list_ports
            ports = [(p.device, p.description) for p in serial.tools.list_ports.comports()]
        except Exception:
            ports = []
        current = self._port_combo.currentData()
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        if not ports:
            self._port_combo.addItem("— Kein Gerät —", None)
        else:
            for device, desc in ports:
                label = f"{device}  ({desc})" if desc and desc != device else device
                self._port_combo.addItem(label, device)
        self._port_combo.blockSignals(False)

        if current:
            idx = self._port_combo.findData(current)
            if idx >= 0:
                self._port_combo.blockSignals(True)
                self._port_combo.setCurrentIndex(idx)
                self._port_combo.blockSignals(False)
            else:
                self._status_mode.setText("MicroPython  –  ⚠ Gerät getrennt")
        elif ports:
            # Erstmalige Befüllung: ersten Port auswählen und Firmware-Version lesen
            self._on_port_selected(0)

    def _on_port_selected(self, index: int):
        """Wird aufgerufen wenn der Nutzer ein Gerät auswählt – liest Firmware-Version."""
        port = self._port_combo.itemData(index)
        if not port:
            self._status_mode.setText("MicroPython")
            return
        self._status_mode.setText(f"MicroPython  –  {port}")
        self._device_panel.refresh(port)
        # mpremote REPL starten – der REPL-Banner zeigt Firmware-Version
        self._console.set_shell_mode("micropython", port=port)

    def _get_serial_port(self, silent: bool = False) -> str | None:
        """Gibt den aktuell in der Toolbar gewählten Port zurück."""
        port = self._port_combo.currentData() if hasattr(self, "_port_combo") else None
        if not port and not silent:
            QMessageBox.warning(
                self, "Kein Gerät",
                "Kein serielles Gerät ausgewählt.\n"
                "Bitte Controller anschließen und in der Toolbar auswählen."
            )
        return port

    def _show_about(self):
        QMessageBox.about(
            self, f"Über {APP_NAME}",
            f"<h2>{APP_NAME} {APP_VERSION}</h2>"
            f"<p>Ein Python- und MicroPython-Editor für den Schulunterricht.</p>"
            f"<p>Unterstützte Controller:<br>"
            + "<br>".join(b["label"] for b in SUPPORTED_BOARDS.values())
            + "</p>"
        )

    def _open_settings(self):
        dlg = SettingsDialog(
            self,
            font_size=self._settings_font_size,
            line_numbers=self._settings_line_numbers,
            word_wrap=self._settings_word_wrap,
            highlight_line=self._settings_highlight_line,
            autosave_secs=self._settings_autosave_secs,
            python_exec=self._settings_python_exec,
            scrollback=self._settings_scrollback,
            tutor_enabled=self._settings_tutor_enabled,
            tutor_url=self._settings_tutor_url,
            tutor_model=self._settings_tutor_model,
        )
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            self._settings_font_size = dlg.font_size
            self._settings_line_numbers = dlg.line_numbers
            self._settings_word_wrap = dlg.word_wrap
            self._settings_highlight_line = dlg.highlight_line
            self._settings_autosave_secs = dlg.autosave_secs
            self._settings_python_exec = dlg.python_exec
            self._settings_scrollback = dlg.scrollback_lines
            self._settings_tutor_enabled = dlg.tutor_enabled
            self._settings_tutor_url = dlg.tutor_url
            self._settings_tutor_model = dlg.tutor_model
            try:
                self._apply_settings()
            except Exception as exc:
                traceback.print_exc()
                QMessageBox.critical(
                    self,
                    "Einstellungen",
                    f"Einstellungen konnten nicht angewendet werden:\n{exc}",
                )

    def _apply_settings(self):
        """Einstellungen auf alle offenen Tabs + Konsole anwenden."""
        for tab in self._tabs:
            tab.editor.set_font_size(self._settings_font_size)
            tab.editor.set_line_numbers_visible(self._settings_line_numbers)
            tab.editor.set_word_wrap(self._settings_word_wrap)
            tab.editor.set_highlight_current_line(self._settings_highlight_line)
        self._console.set_font_size(self._settings_font_size)
        self._console.set_scrollback_limit(self._settings_scrollback)
        # Auto-Save-Timer
        self._autosave_timer.stop()
        if self._settings_autosave_secs > 0:
            self._autosave_timer.start(self._settings_autosave_secs * 1000)
        # KI-Tutor
        self._tutor_panel.setVisible(self._settings_tutor_enabled)
        if self._settings_tutor_enabled:
            self._tutor_panel.apply_settings(
                self._settings_tutor_url,
                self._settings_tutor_model,
            )
            sizes = self._main_splitter.sizes()
            if sizes[2] == 0:
                total = sum(sizes)
                self._main_splitter.setSizes([sizes[0], total - sizes[0] - 320, 320])
        else:
            sizes = self._main_splitter.sizes()
            self._main_splitter.setSizes([sizes[0], sizes[1] + sizes[2], 0])

    def _autosave_all(self):
        """Alle geänderten, bereits gespeicherten Tabs automatisch speichern."""
        for tab in self._tabs:
            if tab.filepath and tab.editor.is_modified():
                try:
                    self._do_save(tab, tab.filepath, silent=True)
                except Exception:
                    pass

    def closeEvent(self, event):
        for tab in self._tabs:
            if tab.editor.is_modified():
                reply = QMessageBox.question(
                    self, "Ungespeicherte Änderungen",
                    "Es gibt ungespeicherte Änderungen.\nTrotzdem beenden?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
                break
        # Laufende QThreads synchron beenden bevor Python-GC greift
        if self._process and self._process.isRunning():
            self._process.terminate_process()
            self._process.wait(2000)
        for t in list(self._retired_threads):
            if t.isRunning():
                t.wait(1000)
        event.accept()
