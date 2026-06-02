"""Haupt-Fenster von NIT_Code."""
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import (
    QAction, QFont, QIcon, QKeySequence, QColor, QPalette,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStackedWidget, QTabWidget, QLabel, QStatusBar, QToolBar, QToolButton,
    QComboBox, QFileDialog, QMessageBox, QInputDialog, QMenu,
    QDialog, QPushButton, QTextEdit,
)

from .config import APP_NAME, APP_VERSION, THEME, SUPPORTED_BOARDS
from .editor_widget import CodeEditor
from .file_panel import FilePanel, DeviceFilePanel
from .console_panel import ConsolePanel, ProcessRunner, MicroPythonRunner
from .ais_chat_panel import AisChatPanel
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
        self._settings_tutor_mode: str = "none"
        self._settings_tutor_url: str = ""
        self._settings_tutor_model: str = ""
        self._settings_sketchbook: str = str(Path.home())
        self._settings_git_repo: str = ""
        self._settings_store = QSettings()
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave_all)
        self._load_persistent_settings()
        self._setup_window()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()
        self._update_git_status_label()
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
        self._m_file = m_file
        self._add_action(m_file, "Neu",          self._new_tab,       "Ctrl+N")
        self._add_action(m_file, "Öffnen …",     self._open_file,     "Ctrl+O")
        self._add_action(m_file, "Speichern",    self._save_file,     "Ctrl+S")
        self._add_action(m_file, "Speichern als …", self._save_file_as, "Ctrl+Shift+S")
        self._m_sketchbook = m_file.addMenu("Sketchbook")
        self._m_sketchbook.aboutToShow.connect(self._rebuild_sketchbook_menu)
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

        # ── Git ──
        m_git = mb.addMenu("Git")
        self._add_action(m_git, "Repository klonen …", self._git_clone)
        self._add_action(m_git, "Repository auswählen …", self._git_select_repo)
        m_git.addSeparator()
        self._add_action(m_git, "Status", self._git_status)
        self._add_action(m_git, "Fetch", self._git_fetch)
        self._add_action(m_git, "Pull", self._git_pull)
        self._add_action(m_git, "Push", self._git_push)
        m_git.addSeparator()
        self._add_action(m_git, "Aktuellen Branch anzeigen", self._git_show_branch)
        self._add_action(m_git, "Branch wechseln …", self._git_switch_branch)
        self._add_action(m_git, "Historie anzeigen …", self._git_show_history)
        m_git.addSeparator()
        self._add_action(m_git, "Commit …", self._git_commit)

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
        self._left_splitter.setMinimumWidth(150)
        self._left_splitter.setMaximumWidth(300)

        self._file_panel = FilePanel()
        self._file_panel.setMinimumWidth(0)
        self._file_panel.setMaximumWidth(10000)
        self._file_panel.file_open_requested.connect(self._open_file_path)
        self._file_panel.set_root(self._settings_sketchbook)
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

        # KI-Panel: TutorPanel (Ollama) und AisChatPanel im Stack
        self._ai_stack = QStackedWidget()
        self._tutor_panel = TutorPanel()
        self._aischat_panel = AisChatPanel()
        self._ai_stack.addWidget(self._tutor_panel)    # Index 0 → Ollama
        self._ai_stack.addWidget(self._aischat_panel)  # Index 1 → AIS-Chat
        self._ai_stack.setVisible(False)
        self._main_splitter.addWidget(self._ai_stack)

        self._main_splitter.setSizes([150, 1060, 0])
        # Nur der Editor-Bereich wächst beim Vergrößern des Fensters
        self._main_splitter.setStretchFactor(0, 0)  # Datei-Panel: feste Breite
        self._main_splitter.setStretchFactor(1, 1)  # Editor: nimmt Extra-Platz
        self._main_splitter.setStretchFactor(2, 0)  # KI-Panel: feste Breite

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

        self._status_git = QLabel("Git: —")
        self._status_git.setStyleSheet(f"color:{THEME['text_dim']}; padding:0 8px;")
        sb.addPermanentWidget(self._status_git)

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
        start_dir = self._settings_sketchbook if os.path.isdir(self._settings_sketchbook) else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Datei öffnen", start_dir,
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
        start_dir = self._settings_sketchbook if os.path.isdir(self._settings_sketchbook) else str(Path.home())
        dlg = QFileDialog(
            self,
            "Speichern als",
            start_dir,
            "Python-Dateien (*.py);;Alle Dateien (*)",
        )
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dlg.setFileMode(QFileDialog.FileMode.AnyFile)
        # Nicht-nativer Dialog verhindert Fullscreen-Verhalten auf manchen Linux-Setups.
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.resize(900, 620)
        dlg.setWindowState(dlg.windowState() & ~Qt.WindowState.WindowFullScreen)

        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selectedFiles():
            path = dlg.selectedFiles()[0]
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
            # Nach Lauf/Stop im MicroPython-Modus Dateiliste automatisch aktualisieren.
            QTimer.singleShot(250, self._refresh_device_files_after_run)
        if code == 0:
            self._console.append_success(f"\n✓  Programm beendet (Code {code})\n")
        else:
            self._console.append_error(f"\n✗  Programm beendet mit Code {code}\n")

    def _refresh_device_files_after_run(self):
        port = self._get_serial_port(silent=True)
        if port and hasattr(self, "_device_panel") and self._mode == "micropython":
            self._device_panel.refresh(port)

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
    # Git-Aktionen
    # ──────────────────────────────────────────────────────────────────────
    def _get_git_base_dir(self) -> str:
        candidate = self._settings_sketchbook
        if candidate and os.path.isdir(candidate):
            return candidate
        return str(Path.home())

    def _detect_git_repo_root(self, start_dir: str) -> str | None:
        try:
            res = subprocess.run(
                ["git", "-C", start_dir, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            return None
        return None

    def _list_git_repos_in_sketchbook(self) -> list[str]:
        base = self._get_git_base_dir()
        repos: list[str] = []
        seen: set[str] = set()

        base_repo = self._detect_git_repo_root(base)
        if base_repo:
            normalized = str(Path(base_repo).resolve())
            repos.append(normalized)
            seen.add(normalized)

        for root, dirs, _files in os.walk(base):
            if ".git" in dirs:
                repo_root = str(Path(root).resolve())
                if repo_root not in seen:
                    repos.append(repo_root)
                    seen.add(repo_root)
                dirs[:] = [d for d in dirs if d != ".git"]

        repos.sort(key=lambda p: p.casefold())
        return repos

    def _select_git_repo_from_list(self, repos: list[str], title: str) -> str | None:
        if not repos:
            return None

        base = Path(self._get_git_base_dir())
        labels = []
        mapping: dict[str, str] = {}
        for repo in repos:
            repo_path = Path(repo)
            try:
                label = str(repo_path.relative_to(base))
                if not label:
                    label = "."
            except ValueError:
                label = repo
            if label in mapping:
                label = repo
            labels.append(label)
            mapping[label] = repo

        labels.sort(key=lambda s: s.casefold())
        default_idx = 0
        if self._settings_git_repo and self._settings_git_repo in repos:
            for i, lbl in enumerate(labels):
                if mapping[lbl] == self._settings_git_repo:
                    default_idx = i
                    break

        selected, ok = self._ask_item_input(
            title,
            "Repository:",
            labels,
            default_idx,
            False,
        )
        if not ok or not selected:
            return None
        return mapping[selected]

    def _resolve_git_repo(self, interactive: bool = True) -> str | None:
        if self._settings_git_repo and os.path.isdir(self._settings_git_repo):
            repo = self._detect_git_repo_root(self._settings_git_repo)
            if repo:
                normalized = str(Path(repo).resolve())
                if normalized == str(Path(self._settings_git_repo).resolve()):
                    self._settings_git_repo = normalized
                    return normalized

        repos = self._list_git_repos_in_sketchbook()
        if not repos:
            return None
        if len(repos) == 1:
            self._settings_git_repo = repos[0]
            self._update_git_status_label()
            return repos[0]
        if not interactive:
            return None

        selected_repo = self._select_git_repo_from_list(repos, "Git: Repository auswählen")
        if not selected_repo:
            return None
        self._settings_git_repo = selected_repo
        self._save_persistent_settings()
        self._update_git_status_label()
        return selected_repo

    def _require_git_repo(self) -> str | None:
        repo = self._resolve_git_repo(interactive=True)
        if repo:
            return repo
        QMessageBox.warning(
            self,
            "Git",
            "Im Sketchbook-Ordner wurde kein Git-Repository gefunden.\n"
            "Bitte zuerst ein Repository klonen oder initialisieren.",
        )
        return None

    def _git_select_repo(self):
        repos = self._list_git_repos_in_sketchbook()
        if not repos:
            QMessageBox.warning(
                self,
                "Git",
                "Im Sketchbook-Ordner wurden keine Repositories gefunden.",
            )
            return
        selected_repo = self._select_git_repo_from_list(repos, "Git: Repository auswählen")
        if not selected_repo:
            return
        self._settings_git_repo = selected_repo
        self._save_persistent_settings()
        self._update_git_status_label()
        self._console.append_info(f"[Git] Aktives Repository: {selected_repo}\n")

    def _run_git_process(self, cmd: list[str], cwd: str, label: str, on_success=None):
        if shutil.which("git") is None:
            QMessageBox.critical(self, "Git", "Git wurde auf diesem System nicht gefunden.")
            return

        self._console.append_info(f"\n[Git] {label}\n")
        self._console.append_info(f"[Git] Arbeitsordner: {cwd}\n")
        self._console.append_info(f"[Git] Befehl: {' '.join(cmd)}\n")

        proc = ProcessRunner(cmd, cwd=cwd)
        proc.output.connect(
            lambda text, kind: self._console.append_output(text)
            if kind == "stdout"
            else self._console.append_error(text)
        )
        proc.finished_run.connect(
            lambda code: self._console.append_success(f"[Git] Fertig (Code {code})\n")
            if code == 0
            else self._console.append_error(f"[Git] Fehler (Code {code})\n")
        )
        if on_success is not None:
            proc.finished_run.connect(lambda code: on_success() if code == 0 else None)
        self._retire_process()
        self._process = proc
        proc.start()

    def _is_light_system_palette(self) -> bool:
        palette = QApplication.instance().palette() if QApplication.instance() else self.palette()
        return palette.color(QPalette.ColorRole.Window).lightness() >= 128

    def _style_input_dialog_for_light_mode(self, dlg: QInputDialog):
        if not self._is_light_system_palette():
            return
        dlg.setStyleSheet(
            """
            QInputDialog QLabel {
                color: #111827;
            }
            QInputDialog QLineEdit,
            QInputDialog QComboBox,
            QInputDialog QListView {
                background: #ffffff;
                color: #111827;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 6px;
            }
            QInputDialog QLineEdit::placeholder {
                color: #6b7280;
            }
            QInputDialog QPushButton {
                background: #e2e8f0;
                color: #111827;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QInputDialog QPushButton:hover {
                background: #cbd5e1;
            }
            """
        )

    def _ask_text_input(self, title: str, label: str, default_text: str = "") -> tuple[str, bool]:
        dlg = QInputDialog(self)
        dlg.setInputMode(QInputDialog.InputMode.TextInput)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setTextValue(default_text)
        self._style_input_dialog_for_light_mode(dlg)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return dlg.textValue(), ok

    def _ask_item_input(
        self,
        title: str,
        label: str,
        items: list[str],
        current_index: int = 0,
        editable: bool = False,
    ) -> tuple[str, bool]:
        if not items:
            return "", False
        dlg = QInputDialog(self)
        dlg.setInputMode(QInputDialog.InputMode.TextInput)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setComboBoxItems(items)
        dlg.setComboBoxEditable(editable)
        if 0 <= current_index < len(items):
            dlg.setTextValue(items[current_index])
        self._style_input_dialog_for_light_mode(dlg)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return dlg.textValue(), ok

    def _git_clone(self):
        url, ok = self._ask_text_input(
            "Git: Repository klonen",
            "Repository-URL (HTTPS/SSH):",
        )
        if not ok or not url.strip():
            return
        url = url.strip()

        default_target = os.path.basename(url.rstrip("/")).removesuffix(".git") or "projekt"
        target_name, ok = self._ask_text_input(
            "Git: Zielordner",
            "Ordnername im Sketchbook:",
            default_target,
        )
        if not ok or not target_name.strip():
            return

        base = self._get_git_base_dir()
        target = os.path.join(base, target_name.strip())
        if os.path.exists(target):
            QMessageBox.warning(self, "Git", f"Zielordner existiert bereits:\n{target}")
            return
        self._run_git_process(
            ["git", "clone", url, target],
            cwd=base,
            label="Repository klonen",
            on_success=lambda: self._set_active_repo_after_clone(target),
        )

    def _set_active_repo_after_clone(self, repo_path: str):
        normalized = str(Path(repo_path).resolve())
        self._settings_git_repo = normalized
        self._save_persistent_settings()
        self._update_git_status_label()
        self._console.append_success(f"[Git] Aktives Repository gesetzt: {normalized}\n")

    def _git_show_branch(self):
        repo = self._require_git_repo()
        if not repo:
            return
        branch = self._get_current_branch(repo)
        if not branch:
            QMessageBox.warning(self, "Git", "Aktueller Branch konnte nicht ermittelt werden.")
            return
        self._console.append_info(f"[Git] Aktueller Branch: {branch}\n")
        QMessageBox.information(self, "Git", f"Aktueller Branch:\n{branch}")

    def _get_current_branch(self, repo: str) -> str | None:
        res = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return None
        branch = res.stdout.strip()
        return branch or None

    def _git_switch_branch(self):
        repo = self._require_git_repo()
        if not repo:
            return

        res = subprocess.run(
            ["git", "-C", repo, "branch", "--format", "%(refname:short)"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            self._console.append_error(res.stderr or "[Git] Branches konnten nicht gelesen werden.\n")
            return

        branches = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        if not branches:
            QMessageBox.warning(self, "Git", "Keine lokalen Branches gefunden.")
            return

        current = self._get_current_branch(repo) or ""
        try:
            default_idx = branches.index(current)
        except ValueError:
            default_idx = 0

        target, ok = self._ask_item_input(
            "Git: Branch wechseln",
            "Branch:",
            branches,
            default_idx,
            True,
        )
        if not ok or not target.strip():
            return
        target = target.strip()
        if target == current:
            self._console.append_info(f"[Git] Bereits auf Branch '{target}'.\n")
            return

        self._run_git_process(["git", "switch", target], cwd=repo, label=f"Branch wechseln zu {target}")

    def _git_show_history(self):
        repo = self._require_git_repo()
        if not repo:
            return

        res = subprocess.run(
            ["git", "-C", repo, "--no-pager", "log", "--oneline", "--decorate", "-n", "50"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            self._console.append_error(res.stderr or "[Git] Historie konnte nicht gelesen werden.\n")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Git: Historie")
        dialog.resize(760, 520)

        layout = QVBoxLayout(dialog)
        history_view = QTextEdit(dialog)
        history_view.setReadOnly(True)
        history_view.setFont(QFont("JetBrains Mono, Fira Code, Consolas, monospace", 10))
        history_view.setPlainText(res.stdout.strip() or "(Keine Commits gefunden)")
        layout.addWidget(history_view)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    def _git_status(self):
        repo = self._require_git_repo()
        if not repo:
            return
        self._run_git_process(["git", "status", "--short", "--branch"], cwd=repo, label="Status")

    def _git_fetch(self):
        repo = self._require_git_repo()
        if not repo:
            return
        self._run_git_process(["git", "fetch", "--all", "--prune"], cwd=repo, label="Fetch")

    def _git_pull(self):
        repo = self._require_git_repo()
        if not repo:
            return
        if self._ensure_pull_upstream(repo):
            self._run_git_process(["git", "pull"], cwd=repo, label="Pull")

    def _ensure_pull_upstream(self, repo: str) -> bool:
        subprocess.run(
            ["git", "-C", repo, "fetch", "--all", "--prune"],
            capture_output=True,
            text=True,
            check=False,
        )

        current = self._get_current_branch(repo)
        if not current or current == "HEAD":
            return True

        upstream = self._get_upstream_branch(repo)
        remote_branches = self._get_remote_origin_branches(repo)
        if not remote_branches:
            return True

        if upstream and upstream in remote_branches:
            return True

        if upstream and upstream.startswith("origin/"):
            missing = upstream
        elif upstream:
            missing = upstream
        else:
            missing = "(kein Upstream gesetzt)"

        msg = (
            f"Für den lokalen Branch '{current}' ist der Upstream '{missing}' nicht verfügbar.\n\n"
            "Bitte wähle einen Remote-Branch, der als neuer Upstream gesetzt werden soll."
        )
        selected, ok = self._ask_item_input(
            "Git: Upstream reparieren",
            msg,
            remote_branches,
            0,
            False,
        )
        if not ok or not selected:
            return False

        self._run_git_process(
            ["git", "branch", "--set-upstream-to", selected, current],
            cwd=repo,
            label=f"Upstream setzen ({current} -> {selected})",
            on_success=lambda: self._run_git_process(["git", "pull"], cwd=repo, label="Pull"),
        )
        return False

    def _get_upstream_branch(self, repo: str) -> str | None:
        res = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return None
        value = res.stdout.strip()
        return value or None

    def _get_remote_origin_branches(self, repo: str) -> list[str]:
        res = subprocess.run(
            ["git", "-C", repo, "for-each-ref", "--format", "%(refname:short)", "refs/remotes/origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return []
        branches = []
        for line in res.stdout.splitlines():
            branch = line.strip()
            if not branch or branch == "origin/HEAD":
                continue
            branches.append(branch)
        branches.sort(key=lambda b: b.casefold())
        return branches

    def _git_push(self):
        repo = self._require_git_repo()
        if not repo:
            return
        self._run_git_process(["git", "push"], cwd=repo, label="Push")

    def _git_commit(self):
        repo = self._require_git_repo()
        if not repo:
            return
        msg, ok = self._ask_text_input(
            "Git: Commit",
            "Commit-Nachricht:",
        )
        if not ok or not msg.strip():
            return
        self._run_git_process(
            ["git", "add", "-A"],
            cwd=repo,
            label="Änderungen stagen",
            on_success=lambda: self._run_git_process(
                ["git", "commit", "-m", msg.strip()],
                cwd=repo,
                label="Commit erstellen",
            ),
        )

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
            tutor_mode=self._settings_tutor_mode,
            tutor_url=self._settings_tutor_url,
            tutor_model=self._settings_tutor_model,
            sketchbook_dir=self._settings_sketchbook,
        )
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            self._settings_font_size = dlg.font_size
            self._settings_line_numbers = dlg.line_numbers
            self._settings_word_wrap = dlg.word_wrap
            self._settings_highlight_line = dlg.highlight_line
            self._settings_autosave_secs = dlg.autosave_secs
            self._settings_python_exec = dlg.python_exec
            self._settings_scrollback = dlg.scrollback_lines
            self._settings_tutor_mode = dlg.tutor_mode
            self._settings_tutor_url = dlg.tutor_url
            self._settings_tutor_model = dlg.tutor_model
            self._settings_sketchbook = self._normalize_sketchbook_dir(dlg.sketchbook_dir)
            try:
                self._apply_settings()
                self._apply_sketchbook_root()
                self._save_persistent_settings()
            except Exception as exc:
                traceback.print_exc()
                QMessageBox.critical(
                    self,
                    "Einstellungen",
                    f"Einstellungen konnten nicht angewendet werden:\n{exc}",
                )

    def _settings_bool(self, key: str, default: bool) -> bool:
        raw = self._settings_store.value(key, default)
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def _settings_int(self, key: str, default: int) -> int:
        raw = self._settings_store.value(key, default)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def _normalize_sketchbook_dir(self, path: str) -> str:
        candidate = Path(path).expanduser() if path else Path.home()
        if not candidate.exists() or not candidate.is_dir():
            return str(Path.home())
        return str(candidate.resolve())

    def _load_persistent_settings(self):
        self._settings_font_size = self._settings_int("editor/font_size", self._settings_font_size)
        self._settings_line_numbers = self._settings_bool("editor/line_numbers", self._settings_line_numbers)
        self._settings_word_wrap = self._settings_bool("editor/word_wrap", self._settings_word_wrap)
        self._settings_highlight_line = self._settings_bool("editor/highlight_line", self._settings_highlight_line)
        self._settings_autosave_secs = self._settings_int("editor/autosave_secs", self._settings_autosave_secs)
        self._settings_python_exec = str(self._settings_store.value("python/executable", self._settings_python_exec) or "")
        self._settings_scrollback = self._settings_int("console/scrollback", self._settings_scrollback)
        self._settings_tutor_mode = str(self._settings_store.value("tutor/mode", self._settings_tutor_mode) or "none")
        self._settings_tutor_url = str(self._settings_store.value("tutor/url", self._settings_tutor_url) or "")
        self._settings_tutor_model = str(self._settings_store.value("tutor/model", self._settings_tutor_model) or "")
        self._settings_sketchbook = self._normalize_sketchbook_dir(
            str(self._settings_store.value("files/sketchbook_dir", self._settings_sketchbook) or "")
        )
        self._settings_git_repo = str(self._settings_store.value("git/repo_dir", self._settings_git_repo) or "")

    def _save_persistent_settings(self):
        self._settings_store.setValue("editor/font_size", self._settings_font_size)
        self._settings_store.setValue("editor/line_numbers", self._settings_line_numbers)
        self._settings_store.setValue("editor/word_wrap", self._settings_word_wrap)
        self._settings_store.setValue("editor/highlight_line", self._settings_highlight_line)
        self._settings_store.setValue("editor/autosave_secs", self._settings_autosave_secs)
        self._settings_store.setValue("python/executable", self._settings_python_exec)
        self._settings_store.setValue("console/scrollback", self._settings_scrollback)
        self._settings_store.setValue("tutor/mode", self._settings_tutor_mode)
        self._settings_store.setValue("tutor/url", self._settings_tutor_url)
        self._settings_store.setValue("tutor/model", self._settings_tutor_model)
        self._settings_store.setValue("files/sketchbook_dir", self._settings_sketchbook)
        self._settings_store.setValue("git/repo_dir", self._settings_git_repo)
        self._settings_store.sync()

    def _choose_sketchbook_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Sketchbook-Ordner wählen",
            self._settings_sketchbook,
        )
        if folder:
            self._settings_sketchbook = self._normalize_sketchbook_dir(folder)
            self._settings_git_repo = ""
            self._apply_sketchbook_root()
            self._save_persistent_settings()
            self._update_git_status_label()

    def _update_git_status_label(self):
        if not hasattr(self, "_status_git"):
            return
        repo = self._settings_git_repo
        if not repo or not os.path.isdir(repo):
            self._status_git.setText("Git: —")
            return

        try:
            rel = Path(repo).resolve().relative_to(Path(self._settings_sketchbook).resolve())
            label = "." if str(rel) == "." else str(rel)
        except Exception:
            label = Path(repo).name or repo

        self._status_git.setText(f"Git: {label}")

    def _apply_sketchbook_root(self):
        if hasattr(self, "_file_panel"):
            self._file_panel.set_root(self._settings_sketchbook)

    def _rebuild_sketchbook_menu(self):
        self._m_sketchbook.clear()
        self._add_action(self._m_sketchbook, "Sketchbook-Ordner wählen …", self._choose_sketchbook_dir)
        self._m_sketchbook.addSeparator()

        root = Path(self._settings_sketchbook)
        if not root.exists() or not root.is_dir():
            info = self._m_sketchbook.addAction("(Sketchbook-Ordner nicht gefunden)")
            info.setEnabled(False)
            return

        has_entries = self._populate_sketchbook_menu(self._m_sketchbook, root)
        if not has_entries:
            info = self._m_sketchbook.addAction("(Keine .py-Dateien gefunden)")
            info.setEnabled(False)

    def _populate_sketchbook_menu(self, menu: QMenu, directory: Path) -> bool:
        has_entries = False
        try:
            children = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return False

        for child in children:
            if child.is_dir():
                sub_menu = menu.addMenu(child.name)
                if not self._populate_sketchbook_menu(sub_menu, child):
                    sub_menu.setEnabled(False)
                else:
                    has_entries = True
            elif child.is_file() and child.suffix.lower() == ".py":
                action = menu.addAction(child.name)
                action.triggered.connect(lambda _checked=False, p=str(child): self._open_file_path(p))
                has_entries = True

        return has_entries

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
        # KI-Tutor (3 Modi: none / ollama / aischat)
        from .ais_chat_panel import PANEL_WIDTH
        mode = self._settings_tutor_mode
        if mode == "none":
            self._ai_stack.setMinimumWidth(0)
            self._ai_stack.setMaximumWidth(16777215)
            self._ai_stack.setVisible(False)
            sizes = self._main_splitter.sizes()
            self._main_splitter.setSizes([sizes[0], sizes[1] + sizes[2], 0])
        elif mode == "ollama":
            self._ai_stack.setMinimumWidth(0)
            self._ai_stack.setMaximumWidth(16777215)
            self._ai_stack.setCurrentIndex(0)
            self._ai_stack.setVisible(True)
            self._tutor_panel.apply_settings(
                self._settings_tutor_url,
                self._settings_tutor_model,
            )
            sizes = self._main_splitter.sizes()
            if sizes[2] == 0:
                total = sum(sizes)
                self._main_splitter.setSizes([sizes[0], total - sizes[0] - 320, 320])
        elif mode == "aischat":
            self._ai_stack.setFixedWidth(PANEL_WIDTH)
            self._ai_stack.setCurrentIndex(1)
            self._ai_stack.setVisible(True)
            sizes = self._main_splitter.sizes()
            if sizes[2] == 0:
                total = sum(sizes)
                self._main_splitter.setSizes([sizes[0], total - sizes[0] - PANEL_WIDTH, PANEL_WIDTH])

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
        self._save_persistent_settings()
        event.accept()
