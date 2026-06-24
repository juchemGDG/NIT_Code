"""Haupt-Fenster von NIT_Code."""
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from urllib.parse import urlparse, urlunparse, quote as urlquote

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import (
    QAction, QFont, QIcon, QKeySequence, QColor, QPalette,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStackedWidget, QTabWidget, QLabel, QStatusBar, QToolBar, QToolButton,
    QComboBox, QFileDialog, QMessageBox, QInputDialog, QMenu,
    QDialog, QPushButton, QTextEdit, QLineEdit, QFormLayout, QGroupBox,
    QListWidget, QListWidgetItem,
)

from .config import APP_NAME, APP_VERSION, THEME, THEMES, SUPPORTED_BOARDS, python_executable, tool_command, set_theme
from .editor_widget import CodeEditor
from .file_panel import FilePanel, DeviceFilePanel
from .console_panel import ConsolePanel, ProcessRunner, MicroPythonRunner
from .block_panel import BlockEditorWindow
from .ais_chat_panel import AisChatPanel
from .coder_panel import CoderPanel
from .settings_dialog import SettingsDialog
from .tutor_panel import TutorPanel


# ──────────────────────────────────────────────────────────────────────────────
# Globales Stylesheet (als Funktion, damit Theme-Wechsel möglich ist)
# ──────────────────────────────────────────────────────────────────────────────
def build_global_style() -> str:
    t = THEME
    return f"""
QMainWindow, QWidget {{
    background: {t['bg_dark']};
    color: {t['text']};
    font-family: system-ui, -apple-system, 'Segoe UI', 'Ubuntu', 'Helvetica Neue', sans-serif;
    font-size: 13px;
}}
QMenuBar {{
    background: {t['bg_panel']};
    color: {t['text']};
    border-bottom: 1px solid {t['border']};
    padding: 2px 0;
}}
QMenuBar::item {{
    padding: 4px 12px;
    border-radius: 3px;
}}
QMenuBar::item:selected {{
    background: {t['accent']};
    color: white;
}}
QMenu {{
    background: {t['bg_panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 20px 5px 12px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background: {t['accent']};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {t['border']};
    margin: 3px 6px;
}}
QTabWidget::pane {{
    border: none;
    background: {t['bg_editor']};
}}
QTabBar::tab {{
    background: {t['bg_panel']};
    color: {t['text_dim']};
    padding: 6px 14px 6px 14px;
    border: none;
    border-right: 1px solid {t['border']};
    min-width: 80px;
}}
QTabBar::tab:selected {{
    background: {t['bg_editor']};
    color: {t['text']};
    border-top: 2px solid {t['accent']};
}}
QTabBar::tab:hover {{
    background: {t['selection']};
    color: {t['text']};
}}
QTabBar::close-button {{
    subcontrol-position: right;
    width: 14px;
    height: 14px;
    margin-left: 4px;
    border-radius: 3px;
}}
QTabBar::close-button:hover {{
    background: {t['accent']};
}}
QSplitter::handle {{
    background: {t['border']};
}}
QToolBar {{
    background: {t['bg_panel']};
    border: none;
    border-bottom: 1px solid {t['border']};
    spacing: 4px;
    padding: 2px 6px;
}}
QToolButton {{
    background: transparent;
    color: {t['text']};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}
QToolButton:hover {{
    background: {t['selection']};
    color: {t['accent']};
}}
QToolButton:pressed {{
    background: {t['accent']};
    color: white;
}}
QStatusBar {{
    background: {t['bg_panel']};
    color: {t['text_dim']};
    border-top: 1px solid {t['border']};
    font-size: 11px;
    padding: 0 8px;
}}
QScrollBar:vertical {{
    background: {t['bg_dark']};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {t['border']};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t['accent']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {t['bg_dark']};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {t['border']};
    border-radius: 4px;
    min-width: 20px;
}}
"""


# ──────────────────────────────────────────────────────────────────────────────
# Git-Clone-Dialog
# ──────────────────────────────────────────────────────────────────────────────
class GitCloneDialog(QDialog):
    """Dialog zum Klonen eines Git-Repositories mit optionaler Credential-Eingabe."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Git: Repository klonen")
        self.setMinimumWidth(520)
        self._target_manually_edited = False
        self._build_ui()
        self._apply_light_style_if_needed()
        self._update_auth_section("")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(8)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://github.com/… oder git@github.com:…")
        self._url_edit.textChanged.connect(self._on_url_changed)
        form.addRow("Repository-URL:", self._url_edit)

        self._target_edit = QLineEdit()
        self._target_edit.setPlaceholderText("Ordnername im Sketchbook")
        self._target_edit.textEdited.connect(self._on_target_edited)
        form.addRow("Zielordner:", self._target_edit)

        layout.addLayout(form)

        # Anmeldedaten-Gruppe (nur bei HTTPS sichtbar)
        self._auth_group = QGroupBox("Anmeldedaten (für private Repositories)")
        auth_outer = QVBoxLayout(self._auth_group)
        auth_outer.setSpacing(8)
        auth_outer.setContentsMargins(8, 8, 8, 8)

        auth_form = QFormLayout()
        auth_form.setSpacing(8)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("Benutzername")
        auth_form.addRow("Benutzername:", self._username_edit)

        pw_widget = QWidget()
        pw_layout = QHBoxLayout(pw_widget)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        pw_layout.setSpacing(4)
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Passwort oder Access Token")
        self._pw_toggle = QPushButton("👁")
        self._pw_toggle.setCheckable(True)
        self._pw_toggle.setFixedSize(32, 28)
        self._pw_toggle.setToolTip("Passwort anzeigen / verbergen")
        self._pw_toggle.toggled.connect(
            lambda checked: self._password_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        pw_layout.addWidget(self._password_edit)
        pw_layout.addWidget(self._pw_toggle)
        auth_form.addRow("Passwort / Token:", pw_widget)

        auth_outer.addLayout(auth_form)

        # Hinweis unterhalb der Felder, volle Breite
        self._auth_hint = QLabel("")
        self._auth_hint.setWordWrap(True)
        self._auth_hint.setObjectName("hintLabel")
        auth_outer.addWidget(self._auth_hint)

        layout.addWidget(self._auth_group)

        # SSH-Hinweis (nur bei SSH-URLs sichtbar)
        self._ssh_hint = QLabel(
            "SSH-Authentifizierung: SSH-Schlüssel müssen im System eingerichtet sein "
            "(~/.ssh/id_rsa oder id_ed25519). Bei GitHub können Schlüssel unter "
            "Einstellungen → SSH and GPG keys hinzugefügt werden."
        )
        self._ssh_hint.setWordWrap(True)
        self._ssh_hint.setObjectName("hintLabel")
        self._ssh_hint.setVisible(False)
        layout.addWidget(self._ssh_hint)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        clone_btn = QPushButton("Klonen")
        clone_btn.setDefault(True)
        clone_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(clone_btn)
        layout.addLayout(btn_layout)

    def _apply_light_style_if_needed(self):
        app = QApplication.instance()
        if app is None:
            return
        if app.palette().color(QPalette.ColorRole.Window).lightness() < 128:
            return
        self.setStyleSheet("""
            QDialog, QWidget { background: #f8fafc; color: #111827; }
            QGroupBox {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding-top: 8px;
                margin-top: 8px;
                font-weight: 600;
                color: #374151;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
            }
            QLabel { color: #374151; }
            QLabel#hintLabel { color: #6b7280; font-size: 11px; }
            QLineEdit {
                background: #ffffff;
                color: #111827;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 8px;
            }
            QPushButton {
                background: #e2e8f0;
                color: #111827;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover { background: #cbd5e1; }
            QPushButton:default {
                background: #3b82f6;
                color: white;
                border-color: #2563eb;
            }
            QPushButton:default:hover { background: #2563eb; }
        """)

    @staticmethod
    def _clean_url(text: str) -> str:
        """Bereinigt versehentlich eingefügte 'git clone <url>'-Befehle zur reinen URL."""
        text = text.strip()
        # Nutzer kopieren oft den kompletten Befehl von GitHub/Doku
        import re
        text = re.sub(r"^git\s+clone\s+", "", text, flags=re.IGNORECASE).strip()
        return text

    def _on_url_changed(self, text: str):
        url = self._clean_url(text)
        if not self._target_manually_edited:
            name = os.path.basename(url.rstrip("/")).removesuffix(".git")
            if name:
                self._target_edit.setText(name)
        self._update_auth_section(url)

    def _on_target_edited(self):
        self._target_manually_edited = True

    # Bekannte Hosts, bei denen ein Token statt Passwort erforderlich ist
    _TOKEN_REQUIRED_HOSTS = {"github.com", "gitlab.com"}
    # Bekannte Hosts, bei denen normales Passwort funktioniert
    _PASSWORD_OK_HOSTS = {"codeberg.org"}

    def _update_auth_section(self, url: str):
        is_https = url.startswith(("https://", "http://"))
        is_ssh = url.startswith("git@") or url.startswith("ssh://")
        self._auth_group.setVisible(is_https)
        self._ssh_hint.setVisible(is_ssh)

        if is_https:
            try:
                host = urlparse(url).hostname or ""
            except Exception:
                host = ""

            if host in self._TOKEN_REQUIRED_HOSTS:
                self._auth_hint.setText(
                    f"Tipp ({host}): Passwörter werden nicht mehr akzeptiert. "
                    "Bitte einen Personal Access Token verwenden: "
                    "Einstellungen → Developer settings → Personal access tokens (Scope: repo)."
                )
            elif host in self._PASSWORD_OK_HOSTS:
                self._auth_hint.setText(
                    f"Tipp ({host}): Normaler Benutzername und Passwort funktionieren hier direkt."
                )
            elif host:
                self._auth_hint.setText(
                    f"Tipp: Je nach Anbieter ({host}) funktioniert entweder das normale "
                    "Passwort oder ein Access Token."
                )
            else:
                self._auth_hint.setText("")

        self.adjustSize()

    def url(self) -> str:
        return self._clean_url(self._url_edit.text())

    def target_name(self) -> str:
        return self._target_edit.text().strip()

    def username(self) -> str:
        return self._username_edit.text().strip()

    def password(self) -> str:
        return self._password_edit.text()


# ──────────────────────────────────────────────────────────────────────────────
# Git-Konflikt-Dialog
# ──────────────────────────────────────────────────────────────────────────────
class GitConflictDialog(QDialog):
    """Löst Merge-Konflikte ohne Terminal: pro Datei eine Version wählen,
    im Editor von Hand lösen, den Merge abschließen oder abbrechen."""

    def __init__(self, main_window, repo: str):
        super().__init__(main_window)
        self._main = main_window
        self._repo = repo

        self.setWindowTitle("Git: Merge-Konflikte lösen")
        self.resize(640, 460)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Bei diesen Dateien wurde an beiden Stellen unterschiedlich geändert.\n"
            "Wähle pro Datei eine Lösung – oder öffne sie zum Bearbeiten im Editor.",
            self,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._list = QListWidget(self)
        self._list.currentItemChanged.connect(lambda *_: self._update_buttons())
        layout.addWidget(self._list, 1)

        # Aktionen pro Datei
        file_row = QHBoxLayout()
        self._btn_ours = QPushButton("Meine Version behalten", self)
        self._btn_theirs = QPushButton("Andere Version übernehmen", self)
        self._btn_open = QPushButton("Im Editor öffnen", self)
        self._btn_mark = QPushButton("Als gelöst markieren", self)
        self._btn_ours.clicked.connect(lambda: self._resolve_with_side("ours"))
        self._btn_theirs.clicked.connect(lambda: self._resolve_with_side("theirs"))
        self._btn_open.clicked.connect(self._open_in_editor)
        self._btn_mark.clicked.connect(self._mark_resolved)
        for b in (self._btn_ours, self._btn_theirs, self._btn_open, self._btn_mark):
            file_row.addWidget(b)
        layout.addLayout(file_row)

        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # Abschluss-Aktionen
        bottom = QHBoxLayout()
        self._btn_abort = QPushButton("Merge abbrechen", self)
        self._btn_abort.clicked.connect(self._abort_merge)
        bottom.addWidget(self._btn_abort)
        bottom.addStretch()
        self._btn_finish = QPushButton("Merge abschließen", self)
        self._btn_finish.clicked.connect(self._finish_merge)
        bottom.addWidget(self._btn_finish)
        close_btn = QPushButton("Schließen", self)
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self._refresh()

    # ── Git-Hilfen ──────────────────────────────────────────────────────────
    def _run(self, args: list[str], label: str) -> bool:
        res = subprocess.run(
            ["git", "-C", self._repo, *args],
            capture_output=True,
            text=True,
            check=False,
        )
        self._main._console.append_info(f"[Git] {label}\n")
        if res.stdout.strip():
            self._main._console.append_output(res.stdout)
        if res.returncode == 0:
            return True
        self._main._console.append_error(res.stderr or f"[Git] '{label}' fehlgeschlagen.\n")
        return False

    def _current_file(self) -> str | None:
        item = self._list.currentItem()
        return item.text() if item else None

    def _refresh(self):
        files = self._main._get_conflicted_files(self._repo)
        self._list.clear()
        for f in files:
            self._list.addItem(QListWidgetItem(f))
        if files:
            self._list.setCurrentRow(0)

        merge_open = self._main._merge_in_progress(self._repo)
        if files:
            self._status.setText(f"Noch {len(files)} Datei(en) mit Konflikten.")
        elif merge_open:
            self._status.setText(
                "Alle Konflikte gelöst – jetzt kannst du den Merge abschließen."
            )
        else:
            self._status.setText("Kein offener Merge – nichts zu tun.")

        self._btn_finish.setEnabled(merge_open and not files)
        self._btn_abort.setEnabled(merge_open)
        self._update_buttons()

    def _update_buttons(self):
        has_file = self._current_file() is not None
        for b in (self._btn_ours, self._btn_theirs, self._btn_open, self._btn_mark):
            b.setEnabled(has_file)

    # ── Aktionen ────────────────────────────────────────────────────────────
    def _resolve_with_side(self, side: str):
        rel = self._current_file()
        if not rel:
            return
        label = "Meine Version" if side == "ours" else "Andere Version"
        if self._run(["checkout", f"--{side}", "--", rel], f"{label} für '{rel}' wählen"):
            self._run(["add", "--", rel], f"'{rel}' als gelöst markieren")
        self._refresh()

    def _mark_resolved(self):
        rel = self._current_file()
        if not rel:
            return
        # Sicherheitsnetz: Datei darf keine Konfliktmarker mehr enthalten.
        abs_path = os.path.join(self._repo, rel)
        try:
            with open(abs_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            content = ""
        if any(marker in content for marker in ("<<<<<<<", "=======", ">>>>>>>")):
            QMessageBox.warning(
                self,
                "Git",
                f"In '{rel}' sind noch Konfliktmarker (<<<<<<<, =======, >>>>>>>) "
                "enthalten.\nBitte zuerst im Editor entfernen und die Datei speichern.",
            )
            return
        self._run(["add", "--", rel], f"'{rel}' als gelöst markieren")
        self._refresh()

    def _open_in_editor(self):
        rel = self._current_file()
        if not rel:
            return
        abs_path = os.path.join(self._repo, rel)
        self._main._open_file_path(abs_path)
        QMessageBox.information(
            self,
            "Git",
            f"'{rel}' wurde im Editor geöffnet.\n\n"
            "Entferne die Konfliktmarker (<<<<<<<, =======, >>>>>>>), speichere die "
            "Datei und öffne dann wieder „Git → Merge-Konflikte lösen“, um sie als "
            "gelöst zu markieren.",
        )
        self.reject()

    def _abort_merge(self):
        reply = QMessageBox.question(
            self,
            "Git: Merge abbrechen",
            "Den laufenden Merge komplett abbrechen?\n"
            "Der Zustand vor dem Merge wird wiederhergestellt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self._run(["merge", "--abort"], "Merge abbrechen"):
            self._main._console.append_success("[Git] Merge wurde abgebrochen.\n")
            self.accept()

    def _finish_merge(self):
        if self._run(["commit", "--no-edit"], "Merge abschließen (Commit)"):
            self._main._console.append_success("[Git] Merge erfolgreich abgeschlossen.\n")
            self.accept()
        else:
            self._refresh()


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


class _PortScanWorker(QThread):
    """Scannt serielle Ports in einem Hintergrund-Thread.

    Der Port-Scan (``comports()``) liest unter Windows die SetupAPI/Registry und
    kann gelegentlich zehntel Sekunden dauern. Da er alle paar Sekunden läuft,
    würde er im UI-Thread ein regelmäßiges Ruckeln verursachen.
    """
    result = pyqtSignal(list)   # list[(device, description)]

    def run(self):
        try:
            import serial.tools.list_ports
            ports = [(p.device, p.description) for p in serial.tools.list_ports.comports()]
        except Exception:
            ports = []
        self.result.emit(ports)


class _DeviceDirWorker(QThread):
    """Liest die Ordnernamen im Wurzelverzeichnis des Controllers (best effort).

    Läuft im Hintergrund, damit der Datei-Upload die Oberfläche nicht einfriert,
    während mpremote die Raw-REPL betritt.
    """
    result = pyqtSignal(list)   # list[str] Ordnernamen

    def __init__(self, port: str):
        super().__init__()
        self._port = port

    def run(self):
        code = (
            "import os\n"
            "for f in os.listdir():\n"
            "    try:\n"
            "        if os.stat(f)[0] & 0x4000: print('D:' + f)\n"
            "    except: pass\n"
        )
        dirs: list[str] = []
        try:
            r = subprocess.run(
                [*tool_command("mpremote"), "connect", self._port, "exec", code],
                capture_output=True, text=True, timeout=8,
            )
            if r.returncode == 0:
                dirs = [ln.strip()[2:] for ln in r.stdout.splitlines()
                        if ln.strip().startswith("D:")]
        except Exception:
            pass
        self.result.emit(dirs)


# ──────────────────────────────────────────────────────────────────────────────
# Haupt-Fenster
# ──────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, initial_file: str | None = None):
        super().__init__()
        self._tabs: list[EditorTab] = []
        self._mode = "python"       # "python" | "micropython"
        self._board = "ESP32"
        self._process: ProcessRunner | None = None
        self._retired_threads: list = []   # hält QThread-Referenzen bis finished
        self._aux_workers: list = []   # kurzlebige Hilfs-Threads (Port-Scan, Geräte-Listing)
        self._port_scan_busy = False   # verhindert überlappende Port-Scans
        self._run_stderr_buf: list[str] = []   # stderr des laufenden Programms (für Fehlerhinweis)
        self._last_error_traceback = ""        # letzter Traceback (für „Infi erklärt")
        self._user_stopped = False             # True wenn Lauf per Stopp-Knopf beendet
        self._port_busy = False     # verhindert gleichzeitige mpremote-Prozesse
        self._settings_font_size: int = 14
        self._settings_line_numbers: bool = True
        self._settings_word_wrap: bool = False
        self._settings_highlight_line: bool = True
        self._settings_autosave_secs: int = 0
        self._settings_python_exec: str = ""
        self._settings_scrollback: int = 5000
        self._settings_blocks_enabled: bool = False   # Block-Editor (BETA), Standard: aus
        self._settings_tutor_mode: str = "none"
        self._settings_tutor_url: str = ""
        self._settings_tutor_model: str = ""
        self._settings_sketchbook: str = str(Path.home())
        self._settings_git_repo: str = ""
        self._settings_theme: str = "classic_light"
        # Serial-Plotter-Achsen (Standardwerte; im Plotter live übersteuerbar)
        self._settings_plot_y_mode: str = "auto"      # "auto" | "fixed"
        self._settings_plot_y_min: float = 0.0
        self._settings_plot_y_max: float = 100.0
        self._settings_plot_x_mode: str = "sliding"   # "sliding" | "sweep"
        self._settings_plot_x_min: int = 0
        self._settings_plot_x_max: int = 500
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
        # Beim Start übergebene Datei öffnen (z. B. Doppelklick auf .py in Windows).
        if initial_file and os.path.isfile(initial_file):
            self._open_file_path(initial_file)

    # ──────────────────────────────────────────────────────────────────────
    # Fenster
    # ──────────────────────────────────────────────────────────────────────
    def _setup_window(self):
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1280, 780)
        self.setStyleSheet(build_global_style())
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
        m_edit.addSeparator()
        self._add_action(m_edit, "Auskommentieren",      self._comment_selection,   "Ctrl+Shift+C")
        self._add_action(m_edit, "Einkommentieren",      self._uncomment_selection, "Ctrl+Shift+U")
        self._add_action(m_edit, "Kommentar umschalten", self._toggle_comment,      "Ctrl+/")

        # ── Ausführen ──
        m_run = mb.addMenu("Ausführen")
        self._add_action(m_run, "Programm starten",  self._run_program, "F5")
        self._add_action(m_run, "Stoppen",           self._stop_program, "F6")
        m_run.addSeparator()
        # Serial Plotter – nur bei Bedarf einblendbar (gemeinsame Aktion mit der Toolbar).
        self._act_plotter = QAction("📈  Serial Plotter", self)
        self._act_plotter.setCheckable(True)
        self._act_plotter.setToolTip("Zahlenausgabe eines laufenden Programms live als Graph anzeigen")
        self._act_plotter.toggled.connect(self._toggle_plotter)
        m_run.addAction(self._act_plotter)
        m_run.addSeparator()
        self._act_upload = self._add_action(
            m_run, "Auf Controller hochladen", self._upload_to_device, "F7"
        )
        self._act_upload.setVisible(False)

        # ── Blöcke (BETA, über Einstellungen aktivierbar) ──
        self._m_blocks = mb.addMenu("Blöcke")
        self._add_action(self._m_blocks, "🧩  Block-Editor öffnen …", self._open_block_editor)

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
        self._add_action(m_git, "Neuen Branch anlegen …", self._git_create_branch)
        self._add_action(m_git, "Branch mergen …", self._git_merge_branch)
        self._add_action(m_git, "Merge-Konflikte lösen …", self._git_resolve_conflicts)
        self._add_action(m_git, "Vergleichen (Diff) …", self._git_diff)
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
        tb.addAction(self._act_plotter)   # checkbarer Plotter-Umschalter (in _setup_menubar erstellt)
        tb.addSeparator()

        # Modus-Auswahl
        self._mode_lbl = QLabel("  Modus: ")
        self._mode_lbl.setStyleSheet(f"color:{THEME['text_dim']};")
        tb.addWidget(self._mode_lbl)

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
        # Breit genug, damit der Aktualisieren-Button (↻) der Controller-
        # Dateiansicht von Anfang an sichtbar ist.
        self._left_splitter.setMinimumWidth(210)
        self._left_splitter.setMaximumWidth(340)

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
        self._console.explain_requested.connect(self._explain_error_with_infi)
        self._device_panel.refresh_started.connect(self._on_device_refresh_start)
        self._device_panel.refresh_done.connect(self._on_device_refresh_done)
        self._device_panel.firmware_info.connect(
            lambda info: self._console.append_success(f"✓  MicroPython {info}\n")
        )
        self._right_splitter.addWidget(self._console)

        self._right_splitter.setSizes([520, 200])
        self._main_splitter.addWidget(self._right_splitter)

        # KI-Panel: TutorPanel (Ollama), AisChatPanel, CoderPanel im Stack
        self._ai_stack = QStackedWidget()
        self._tutor_panel    = TutorPanel()
        self._aischat_panel  = AisChatPanel()
        self._coder_panel    = CoderPanel()
        self._ai_stack.addWidget(self._tutor_panel)    # Index 0 → Infi/Ollama
        self._ai_stack.addWidget(self._aischat_panel)  # Index 1 → AIS-Chat
        self._ai_stack.addWidget(self._coder_panel)    # Index 2 → Code-Generator
        self._coder_panel.insert_code_requested.connect(self._on_insert_generated_code)
        self._coder_panel.open_as_blocks_requested.connect(self._open_blocks_from_code)
        self._ai_stack.setVisible(False)
        self._main_splitter.addWidget(self._ai_stack)

        self._main_splitter.setSizes([230, 980, 0])
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
        tab.editor.set_filepath(filepath)
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
            tab.editor.set_filepath(path)
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

    def _comment_selection(self):
        tab = self._current_tab()
        if tab:
            tab.editor.comment_selection()

    def _uncomment_selection(self):
        tab = self._current_tab()
        if tab:
            tab.editor.uncomment_selection()

    def _toggle_comment(self):
        tab = self._current_tab()
        if tab:
            tab.editor.toggle_comment()

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
    # ── Block-Editor ──────────────────────────────────────────────────────
    def _open_block_editor(self):
        """Öffnet das Blockly-Extrafenster (einmalig, dann nach vorne holen)."""
        win = getattr(self, "_block_window", None)
        if win is None:
            win = BlockEditorWindow(self)
            win.code_generated.connect(self._insert_block_code)
            self._block_window = win
        win.show()
        win.raise_()
        win.activateWindow()

    def _apply_blocks_enabled(self):
        """Blendet das Block-Editor-Feature (BETA) je nach Einstellung ein/aus."""
        enabled = self._settings_blocks_enabled
        if hasattr(self, "_m_blocks"):
            self._m_blocks.menuAction().setVisible(enabled)
        if hasattr(self, "_coder_panel"):
            self._coder_panel.set_blocks_feature_enabled(enabled)
        # Falls deaktiviert und ein Block-Fenster offen ist: schließen.
        if not enabled:
            win = getattr(self, "_block_window", None)
            if win is not None:
                win.close()

    def _open_blocks_from_code(self, code: str):
        """Coder → Blockly: erzeugten Python-Code als Blöcke im Block-Editor zeigen."""
        from .py2blockly import python_to_block_state
        try:
            state = python_to_block_state(code)
        except Exception as exc:
            self._console.append_error(f"Blöcke konnten nicht erzeugt werden: {exc}\n")
            return
        self._open_block_editor()
        win = getattr(self, "_block_window", None)
        if win is not None:
            win.load_block_state(state)

    def _insert_block_code(self, code: str):
        """Erzeugten Block-Code in den Editor schreiben.

        Wurde dasselbe Block-Programm bereits einmal umgewandelt, wird der
        bestehende Tab aktualisiert statt ein neuer geöffnet. Konvention (wie
        KI-Codegenerator): KEINE Kommentare im erzeugten Code – das Kommentieren
        ist Aufgabe der Schülerinnen und Schüler.
        """
        existing = getattr(self, "_block_tab", None)
        if existing is not None and existing in self._tabs:
            existing.editor.set_text(code)
            self._tab_widget.setCurrentWidget(existing.editor)
            self._console.append_info("🧩  Block-Code aktualisiert.\n")
        else:
            tab = self._new_tab()
            tab.editor.set_text(code)
            self._block_tab = tab
            self._console.append_info("🧩  Block-Code in neuen Tab übernommen.\n")
        self.raise_()
        self.activateWindow()

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
        # Fehler-Zustand für diesen Lauf zurücksetzen
        self._run_stderr_buf = []
        self._last_error_traceback = ""
        self._user_stopped = False
        self._console.set_explain_visible(False)

        self._retire_process()
        if self._mode == "python":
            python = self._get_python_executable()
            cmd = [python, "-u", tab.filepath]
            # Ungepufferte, UTF-8-Ausgabe erzwingen – greift auch für
            # Subprozesse, die das Schüler-Programm selbst startet, sodass
            # Ausgaben/Fehler sofort statt verzögert erscheinen.
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            self._process = ProcessRunner(cmd, cwd=os.path.dirname(tab.filepath), env=env)
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
            self._user_stopped = True   # kein Fehlerhinweis für bewussten Abbruch
            self._process.terminate_process()
            self._console.flush_now()
            self._console.append_info("\n■  Abgebrochen.\n")
        self._console.set_active_runner(None)
        if self._mode == "micropython":
            self._console.resume_shell()

    def _toggle_plotter(self, checked: bool):
        """Blendet den Serial Plotter (Live-Graph der Zahlenausgabe) ein/aus."""
        self._console.set_plotter_visible(checked)

    def _explain_error_with_infi(self):
        """Schickt den letzten Fehler mit dem Schülercode an den Tutor „Infi"."""
        tb = self._last_error_traceback
        if not tb.strip():
            return
        if self._settings_tutor_mode != "ollama":
            QMessageBox.information(
                self, "Infi",
                "Der KI-Tutor „Infi“ ist nicht aktiv.\n"
                "Aktiviere ihn unter Datei → Einstellungen → KI-Tutor (Infi).",
            )
            return
        tab = self._current_tab()
        code = tab.editor.get_text() if tab else ""
        from .error_hints import build_infi_error_prompt
        prompt = build_infi_error_prompt(code, tb)
        # Infi-Panel sicher einblenden (Index 0) – auch wenn der Splitter kollabiert war.
        self._ai_stack.setCurrentIndex(0)
        self._ai_stack.setVisible(True)
        sizes = self._main_splitter.sizes()
        if len(sizes) == 3 and sizes[2] == 0:
            total = sum(sizes)
            self._main_splitter.setSizes([sizes[0], max(200, total - sizes[0] - 320), 320])
        self._tutor_panel.ask(prompt)
        self._console.set_explain_visible(False)

    def _on_process_output(self, text: str, kind: str):
        if kind == "stderr":
            self._console.append_program_error(text)
            self._run_stderr_buf.append(text)   # für Fehlerhinweis nach Programmende
            # Fehlerzeilen im Editor markieren
            import re
            for m in re.finditer(r'File "([^"]+)", line (\d+)', text):
                fp, ln = m.group(1), int(m.group(2))
                tab = self._current_tab()
                if tab and tab.filepath and os.path.abspath(fp) == os.path.abspath(tab.filepath):
                    tab.editor.mark_error_line(ln)
        else:
            self._console.append_program_output(text)

    def _on_process_done(self, code: int):
        # Restpuffer leeren, damit die Abschlussmeldung wirklich zuletzt erscheint
        self._console.flush_now()
        self._console.set_active_runner(None)
        if self._mode == "micropython":
            self._console.resume_shell()
            # Nach Lauf/Stop im MicroPython-Modus Dateiliste automatisch aktualisieren.
            QTimer.singleShot(250, self._refresh_device_files_after_run)
        if code == 0:
            self._console.append_success(f"\n✓  Programm beendet (Code {code})\n")
        else:
            self._console.append_error(f"\n✗  Programm beendet mit Code {code}\n")
            self._handle_program_error()

    def _handle_program_error(self):
        """Nach einem Absturz: verständlichen Hinweis zeigen und (falls Infi aktiv)
        den „Infi erklärt diesen Fehler"-Knopf anbieten."""
        if self._user_stopped:
            return   # vom Nutzer abgebrochen – kein echter Programmfehler
        traceback_text = "".join(self._run_stderr_buf).strip()
        if not traceback_text:
            return
        self._last_error_traceback = traceback_text
        from .error_hints import explain
        hint = explain(traceback_text)
        if hint:
            self._console.append_hint(hint)
        # KI-Erklärung nur anbieten, wenn der Ollama-Tutor (Infi) eingerichtet ist.
        if self._settings_tutor_mode == "ollama":
            self._console.set_explain_visible(True)

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

        # Ordnerliste des Controllers im Hintergrund holen, dann Auswahl + Upload
        # fortsetzen – so friert die Oberfläche während des Raw-REPL-Zugriffs nicht ein.
        self._console.append_info("↑  Ermittle Zielordner auf dem Controller …\n")
        worker = _DeviceDirWorker(port)
        worker.result.connect(lambda dirs: self._continue_upload(tab, port, dirs))
        self._track_aux_worker(worker)
        worker.start()

    def _continue_upload(self, tab, port: str, dirs: list[str]):
        """Zweiter Teil von :meth:`_upload_to_device` – läuft nach dem Geräte-Listing."""
        folder = self._choose_device_folder(dirs)
        if folder is None:   # abgebrochen
            return

        remote_name = os.path.basename(tab.filepath)
        remote_path = f"{folder}/{remote_name}" if folder else remote_name
        ziel = f"{folder}/" if folder else "Hauptebene"
        self._console.append_info(f"↑  Lade {remote_name} nach {ziel} auf {port} hoch ...\n")

        # Zielordner ggf. anlegen (EEXIST wird ignoriert), dann kopieren.
        if folder:
            try:
                subprocess.run(
                    [*tool_command("mpremote"), "connect", port, "mkdir", f":{folder}"],
                    capture_output=True, text=True, timeout=10,
                )
            except Exception:
                pass

        cmd = [*tool_command("mpremote"), "connect", port,
               "cp", tab.filepath, f":{remote_path}"]
        self._retire_process()
        self._process = ProcessRunner(cmd)
        self._process.output.connect(self._on_process_output)
        self._process.finished_run.connect(
            lambda code: self._console.append_success("✓  Upload abgeschlossen.\n")
            if code == 0 else self._console.append_error("✗  Upload fehlgeschlagen.\n")
        )
        # Nach erfolgreichem Upload die Controller-Dateiansicht im Zielordner zeigen
        self._process.finished_run.connect(
            lambda code: self._device_panel.show_folder(port, folder) if code == 0 else None
        )
        self._process.start()

    def _choose_device_folder(self, dirs: list[str]) -> str | None:
        """Lässt den Zielordner für den Upload wählen.

        ``dirs`` ist die zuvor (im Hintergrund) gelesene Ordnerliste des Controllers.
        Rückgabe: "" für die Hauptebene, ein Ordnername, oder None bei Abbruch.
        """
        ROOT = "/ (Hauptebene)"
        NEW = "➕ Neuer Ordner …"
        items = [ROOT] + [f"📁 {d}" for d in sorted(dirs)] + [NEW]
        choice, ok = self._ask_item_input(
            "Zielordner wählen",
            "In welchen Ordner auf dem Controller hochladen?",
            items, 0, editable=False,
        )
        if not ok:
            return None
        if choice == ROOT:
            return ""
        if choice == NEW:
            name, ok2 = self._ask_text_input("Neuer Ordner", "Name des neuen Ordners:")
            name = name.strip().strip("/")
            return name if (ok2 and name) else None
        return choice[len("📁 "):]   # Emoji-Präfix entfernen

    def _track_aux_worker(self, worker: QThread):
        """Hält eine Referenz auf einen kurzlebigen Hilfs-Thread, bis er fertig ist.

        Verhindert, dass Python den QThread per GC einsammelt, während er noch läuft
        ('QThread destroyed while still running' → Absturz).
        """
        self._aux_workers.append(worker)
        worker.finished.connect(
            lambda w=worker: self._aux_workers.remove(w) if w in self._aux_workers else None
        )

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
        cmd = [*tool_command("mpremote"), "connect", port, "exec", code]
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
            *tool_command("mpremote"),
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
        # Eventuell neu installierte Bibliotheken in der Dateiansicht zeigen
        if port and self._mode == "micropython":
            self._device_panel.refresh(port)

    def _open_pip_manager(self):
        from .micropython_dialogs import PipManagerDialog
        dlg = PipManagerDialog(self, python_exec=self._get_python_executable())
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

    def _run_git_process(
        self,
        cmd: list[str],
        cwd: str,
        label: str,
        on_success=None,
        display_cmd: list[str] | None = None,
        on_finish=None,
    ):
        if shutil.which("git") is None:
            QMessageBox.critical(self, "Git", "Git wurde auf diesem System nicht gefunden.")
            return

        log_cmd = display_cmd if display_cmd is not None else cmd
        self._console.append_info(f"\n[Git] {label}\n")
        self._console.append_info(f"[Git] Arbeitsordner: {cwd}\n")
        self._console.append_info(f"[Git] Befehl: {' '.join(log_cmd)}\n")

        proc = ProcessRunner(cmd, cwd=cwd)
        # stderr puffern: Git schreibt Fortschritts-/Info-Meldungen auf stderr,
        # auch bei Erfolg. Erst nach Prozessende entscheiden ob rot (Fehler) oder normal.
        stderr_buf: list[str] = []
        proc.output.connect(
            lambda text, kind: self._console.append_output(text)
            if kind == "stdout"
            else stderr_buf.append(text)
        )

        def _on_finish(code: int):
            for chunk in stderr_buf:
                if code == 0:
                    self._console.append_output(chunk)
                else:
                    self._console.append_error(chunk)
            if code == 0:
                self._console.append_success(f"[Git] Fertig (Code {code})\n")
                if on_success is not None:
                    on_success()
            else:
                self._console.append_error(f"[Git] Fehler (Code {code})\n")
            if on_finish is not None:
                on_finish(code)

        proc.finished_run.connect(_on_finish)
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
        dlg = GitCloneDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        url = dlg.url()
        target_name = dlg.target_name()
        username = dlg.username()
        password = dlg.password()

        if not url or not target_name:
            QMessageBox.warning(self, "Git", "URL und Zielordner dürfen nicht leer sein.")
            return

        base = self._get_git_base_dir()
        target = os.path.join(base, target_name)
        if os.path.exists(target):
            QMessageBox.warning(self, "Git", f"Zielordner existiert bereits:\n{target}")
            return

        # Für HTTPS mit Credentials: URL mit eingebetteten Zugangsdaten bauen
        clone_url = url
        display_url = url
        if username and password and url.startswith(("https://", "http://")):
            parsed = urlparse(url)
            # Sonderzeichen (z. B. @ in E-Mail-Adressen) müssen URL-kodiert werden
            enc_user = urlquote(username, safe="")
            enc_pass = urlquote(password, safe="")
            host = parsed.hostname
            netloc = f"{enc_user}:{enc_pass}@{host}"
            if parsed.port:
                netloc += f":{parsed.port}"
            clone_url = urlunparse(parsed._replace(netloc=netloc))
            display_url = urlunparse(parsed._replace(netloc=f"{enc_user}:***@{host}"))

        clone_cmd = ["git", "clone", clone_url, target]
        display_cmd = ["git", "clone", display_url, target]

        def on_clone_success():
            self._set_active_repo_after_clone(target)
            if username and password and url.startswith(("https://", "http://")):
                self._store_git_credentials(target, url, username, password)

        self._run_git_process(
            clone_cmd,
            cwd=base,
            label="Repository klonen",
            on_success=on_clone_success,
            display_cmd=display_cmd,
        )

    def _secure_credential_helper(self) -> str:
        """Plattformabhängiger, sicherer git-credential-Helper.

        Speichert Zugangsdaten verschlüsselt im Betriebssystem (Windows Credential
        Manager / macOS Keychain / GNOME-Keyring via libsecret) statt im Klartext.
        Wo libsecret fehlt, wird der eingebaute, nur im Arbeitsspeicher gehaltene
        ``cache``-Helper genutzt (besser als Klartext auf der Platte).
        """
        if sys.platform == "win32":
            return "manager"
        if sys.platform == "darwin":
            return "osxkeychain"
        if shutil.which("git-credential-libsecret"):
            return "libsecret"
        # Fallback: 8 h im RAM-Cache – kein Klartext auf der Platte
        return "cache --timeout=28800"

    def _store_git_credentials(self, repo_path: str, url: str, username: str, password: str):
        """Speichert HTTPS-Credentials verschlüsselt über den OS-Credential-Manager.

        Es wird KEIN Klartext mehr in ``~/.git-credentials`` geschrieben. Ein evtl.
        vorhandener alter Klartext-Eintrag für denselben Host wird entfernt.
        """
        parsed = urlparse(url)
        helper = self._secure_credential_helper()
        # Lokalen credential.helper auf den sicheren Helper setzen
        subprocess.run(
            ["git", "-C", repo_path, "config", "credential.helper", helper],
            capture_output=True,
            check=False,
        )
        # Zugangsdaten über 'git credential approve' an den Helper übergeben –
        # dieser legt sie verschlüsselt im OS-Schlüsselspeicher ab.
        approve_input = (
            f"protocol={parsed.scheme}\n"
            f"host={parsed.hostname}\n"
            f"username={username}\n"
            f"password={password}\n\n"
        )
        try:
            res = subprocess.run(
                ["git", "-C", repo_path, "credential", "approve"],
                input=approve_input, text=True,
                capture_output=True, check=False,
            )
            if res.returncode == 0:
                self._console.append_success(
                    "[Git] Zugangsdaten sicher im System-Schlüsselspeicher abgelegt.\n")
            else:
                self._console.append_info(
                    "[Git] Zugangsdaten konnten nicht im Schlüsselspeicher abgelegt "
                    "werden – Git fragt beim nächsten Zugriff erneut nach.\n")
        except OSError as exc:
            self._console.append_error(
                f"[Git] Zugangsdaten konnten nicht gespeichert werden: {exc}\n")

        # Migration/Bereinigung: evtl. früher gespeicherten Klartext-Eintrag löschen
        self._purge_plaintext_credentials(parsed.scheme, parsed.hostname, username)

    def _purge_plaintext_credentials(self, scheme: str, hostname: str | None, username: str):
        """Entfernt einen alten Klartext-Eintrag aus ~/.git-credentials (falls vorhanden)."""
        creds_file = Path.home() / ".git-credentials"
        if not hostname or not creds_file.exists():
            return
        try:
            enc_user = urlquote(username, safe="")
            host_prefix = f"{scheme}://{enc_user}:"
            host_suffix = f"@{hostname}"
            existing = creds_file.read_text(encoding="utf-8").splitlines(keepends=True)
            kept = [
                ln for ln in existing
                if not (ln.startswith(host_prefix) and host_suffix in ln)
            ]
            if len(kept) != len(existing):
                creds_file.write_text("".join(kept), encoding="utf-8")
        except OSError:
            pass

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

    def _get_local_branches(self, repo: str) -> list[str]:
        res = subprocess.run(
            ["git", "-C", repo, "branch", "--format", "%(refname:short)"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return []
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]

    def _git_create_branch(self):
        repo = self._require_git_repo()
        if not repo:
            return

        current = self._get_current_branch(repo) or "HEAD"
        name, ok = self._ask_text_input(
            "Git: Neuen Branch anlegen",
            f"Name des neuen Branches\n(wird ausgehend von '{current}' erstellt):",
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        if name in self._get_local_branches(repo):
            QMessageBox.warning(self, "Git", f"Ein Branch mit dem Namen '{name}' existiert bereits.")
            return

        # git switch -c legt den Branch an und wechselt direkt dorthin.
        self._run_git_process(
            ["git", "switch", "-c", name],
            cwd=repo,
            label=f"Neuen Branch '{name}' anlegen",
        )

    def _git_fetch_then(self, repo: str, on_done):
        """Holt den Remote-Stand (``fetch --all --prune``) im Hintergrund-Thread
        und ruft danach ``on_done()`` im UI-Thread auf – ohne die Oberfläche
        einzufrieren. Schlägt der Fetch fehl (z. B. offline), wird trotzdem mit
        dem lokalen Stand fortgefahren.
        """
        if shutil.which("git") is None:
            on_done()
            return
        self._console.append_info("[Git] Hole Remote-Stand …\n")
        proc = ProcessRunner(["git", "-C", repo, "fetch", "--all", "--prune"], cwd=repo)
        # on_done erst nach Rückkehr aus dem finished-Slot starten (sauberer Dialog).
        proc.finished_run.connect(lambda code: QTimer.singleShot(0, on_done))
        self._retire_process()
        self._process = proc
        proc.start()

    def _git_merge_branch(self):
        repo = self._require_git_repo()
        if not repo:
            return

        current = self._get_current_branch(repo)
        if not current or current == "HEAD":
            QMessageBox.warning(
                self,
                "Git",
                "Es ist kein Branch aktiv (losgelöster HEAD). Bitte zuerst einen Branch auswählen.",
            )
            return

        # Remote-Stand im Hintergrund aktualisieren, dann die Auswahl zeigen.
        self._git_fetch_then(repo, lambda: self._merge_branch_choose(repo, current))

    def _merge_branch_choose(self, repo: str, current: str):
        """Zeigt nach dem Hintergrund-Fetch die Branch-Auswahl und startet den Merge."""
        local = [b for b in self._get_local_branches(repo) if b != current]
        remote = self._get_remote_origin_branches(repo)
        candidates = local + remote
        if not candidates:
            QMessageBox.warning(self, "Git", "Es wurde kein anderer Branch zum Mergen gefunden.")
            return

        # Upstream (z. B. origin/<current>) als Vorauswahl, falls vorhanden –
        # das ist der typische Fall „den Remote-Stand in meinen Branch holen".
        upstream = self._get_upstream_branch(repo)
        default_idx = candidates.index(upstream) if upstream in candidates else 0

        source, ok = self._ask_item_input(
            "Git: Branch mergen",
            f"Welcher Branch soll in '{current}' gemergt werden?",
            candidates,
            default_idx,
            False,
        )
        if not ok or not source.strip():
            return
        source = source.strip()

        self._run_git_process(
            ["git", "merge", source],
            cwd=repo,
            label=f"'{source}' in '{current}' mergen",
            on_finish=lambda code: self._offer_conflict_resolution(repo),
        )

    def _get_conflicted_files(self, repo: str) -> list[str]:
        res = subprocess.run(
            ["git", "-C", repo, "diff", "--name-only", "--diff-filter=U"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return []
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]

    def _merge_in_progress(self, repo: str) -> bool:
        res = subprocess.run(
            ["git", "-C", repo, "rev-parse", "-q", "--verify", "MERGE_HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0

    def _offer_conflict_resolution(self, repo: str):
        """Nach einem Merge/Pull mit Konflikten anbieten, den Konflikt-Dialog zu öffnen."""
        if not self._get_conflicted_files(repo):
            return
        reply = QMessageBox.warning(
            self,
            "Git: Merge-Konflikt",
            "Beim Mergen sind Konflikte aufgetreten – derselbe Code wurde an beiden "
            "Stellen unterschiedlich geändert.\n\n"
            "Möchtest du sie jetzt im Konflikt-Helfer lösen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._git_resolve_conflicts()

    def _git_resolve_conflicts(self):
        repo = self._require_git_repo()
        if not repo:
            return

        if not self._merge_in_progress(repo) and not self._get_conflicted_files(repo):
            QMessageBox.information(
                self,
                "Git",
                "Aktuell ist kein Merge mit Konflikten offen – es gibt nichts zu lösen.",
            )
            return

        dlg = GitConflictDialog(self, repo)
        dlg.exec()
        self._update_git_status_label()

    def _git_diff(self):
        repo = self._require_git_repo()
        if not repo:
            return
        # Remote-Stand im Hintergrund holen, dann die Vergleichsauswahl zeigen.
        self._git_fetch_then(repo, lambda: self._git_diff_choose(repo))

    def _git_diff_choose(self, repo: str):
        """Zeigt nach dem Hintergrund-Fetch die Vergleichsauswahl und erzeugt den Diff."""
        current = self._get_current_branch(repo)
        working = "Eigene Änderungen (noch nicht committet)"
        options = [working]

        upstream = self._get_upstream_branch(repo)
        remote = self._get_remote_origin_branches(repo)
        local = [b for b in self._get_local_branches(repo) if b != current]

        # Upstream nach vorne ziehen – der häufigste Vergleich.
        ordered_remote = []
        if upstream and upstream in remote:
            ordered_remote.append(upstream)
        ordered_remote += [b for b in remote if b != upstream]

        ref_map: dict[str, list[str]] = {working: ["git", "-C", repo, "--no-pager", "diff"]}
        for ref in ordered_remote + local:
            label = f"Aktueller Branch  ↔  {ref}"
            options.append(label)
            # HEAD..ref zeigt, was auf 'ref' enthalten ist, das hier (noch) fehlt.
            ref_map[label] = ["git", "-C", repo, "--no-pager", "diff", f"HEAD..{ref}"]

        choice, ok = self._ask_item_input(
            "Git: Vergleichen (Diff)",
            "Was soll verglichen werden?",
            options,
            0,
            False,
        )
        if not ok or not choice:
            return

        res = subprocess.run(
            ref_map[choice],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            self._console.append_error(res.stderr or "[Git] Vergleich konnte nicht erstellt werden.\n")
            return

        self._show_git_diff_dialog(f"Git: Vergleich – {choice}", res.stdout)

    def _show_git_diff_dialog(self, title: str, diff_text: str):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(820, 560)

        layout = QVBoxLayout(dialog)
        view = QTextEdit(dialog)
        view.setReadOnly(True)
        view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        view.setFont(QFont("JetBrains Mono, Fira Code, Consolas, monospace", 10))

        if not diff_text.strip():
            view.setPlainText("(Keine Unterschiede – alles auf dem gleichen Stand.)")
        else:
            view.setHtml(self._diff_to_html(diff_text))
        layout.addWidget(view)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    def _diff_to_html(self, diff_text: str) -> str:
        from html import escape

        add_color = "#22c55e"   # hinzugefügte Zeilen
        del_color = "#ef4444"   # entfernte Zeilen
        meta_color = "#60a5fa"  # Datei-/Hunk-Köpfe
        lines = []
        for raw in diff_text.splitlines():
            safe = escape(raw)
            if raw.startswith(("+++", "---", "@@", "diff ", "index ")):
                color = meta_color
            elif raw.startswith("+"):
                color = add_color
            elif raw.startswith("-"):
                color = del_color
            else:
                color = None
            if color:
                lines.append(f'<span style="color:{color};">{safe}</span>')
            else:
                lines.append(safe)
        # Innerhalb von <pre> bleiben Zeilenumbrüche und Einrückungen erhalten.
        body = "\n".join(lines)
        return f'<pre style="margin:0; white-space:pre; font-family:inherit;">{body}</pre>'

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
        branch = self._get_current_branch(repo)
        if branch and branch != "HEAD":
            self._run_git_process(
                ["git", "pull", "origin", branch],
                cwd=repo,
                label="Pull",
                on_finish=lambda code: self._offer_conflict_resolution(repo),
            )
        else:
            self._run_git_process(
                ["git", "pull"],
                cwd=repo,
                label="Pull",
                on_finish=lambda code: self._offer_conflict_resolution(repo),
            )

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
    # Code-Generator: generierten Code in neuen Tab einfügen
    # ──────────────────────────────────────────────────────────────────────
    def _on_insert_generated_code(self, code: str):
        tab = self._new_tab()
        tab.editor.set_text(code)
        self._update_tab_title(tab)

    # ──────────────────────────────────────────────────────────────────────
    # Hilfsfunktionen
    # ──────────────────────────────────────────────────────────────────────
    def _get_python_executable(self) -> str:
        # In den Einstellungen gewählter Interpreter hat Vorrang – sofern er
        # existiert und nicht die App selbst ist (Fork-Bomb-Schutz im Frozen-Modus).
        chosen = (self._settings_python_exec or "").strip()
        if chosen:
            # Wurde nur ein Name statt eines Pfads gewählt (z. B. "python3.14"),
            # über PATH auflösen – sonst würde fälschlich der System-Python
            # verwendet (z. B. ein Python ohne tkinter/pyserial).
            if not os.path.isfile(chosen):
                resolved = shutil.which(chosen)
                if resolved:
                    chosen = resolved
            if os.path.isfile(chosen):
                if getattr(sys, "frozen", False):
                    try:
                        if os.path.realpath(chosen) == os.path.realpath(sys.executable):
                            return python_executable()
                    except OSError:
                        pass
                return chosen
        # Sonst automatische Ermittlung (Frozen: System-Python; Dev: venv).
        return python_executable()

    def _refresh_ports(self):
        """Stößt einen Port-Scan im Hintergrund-Thread an (kein I/O im UI-Thread)."""
        if self._port_scan_busy:
            return   # vorheriger Scan läuft noch – Ergebnis abwarten
        self._port_scan_busy = True
        worker = _PortScanWorker()
        worker.result.connect(self._apply_port_scan)
        worker.finished.connect(lambda: setattr(self, "_port_scan_busy", False))
        self._track_aux_worker(worker)
        worker.start()

    def _apply_port_scan(self, ports: list):
        """Übernimmt das Ergebnis eines Port-Scans in die Toolbar-Combo.

        Baut die Liste nur neu auf, wenn sich die erkannten Geräte tatsächlich
        geändert haben – das vermeidet unnötige UI-Arbeit beim Sekunden-Polling.
        """
        current = self._port_combo.currentData()
        existing = [self._port_combo.itemData(i) for i in range(self._port_combo.count())]
        new_devices = [d for d, _ in ports] if ports else [None]
        if existing == new_devices:
            # Geräteliste unverändert – nur Trennungs-Status nachziehen.
            if current and current not in new_devices:
                self._status_mode.setText("MicroPython  –  ⚠ Gerät getrennt")
            return

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
            theme=self._settings_theme,
            blocks_enabled=self._settings_blocks_enabled,
            plot_y_mode=self._settings_plot_y_mode,
            plot_y_min=self._settings_plot_y_min,
            plot_y_max=self._settings_plot_y_max,
            plot_x_mode=self._settings_plot_x_mode,
            plot_x_min=self._settings_plot_x_min,
            plot_x_max=self._settings_plot_x_max,
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
            self._settings_theme = dlg.theme
            self._settings_blocks_enabled = dlg.blocks_enabled
            self._settings_plot_y_mode = dlg.plot_y_mode
            self._settings_plot_y_min = dlg.plot_y_min
            self._settings_plot_y_max = dlg.plot_y_max
            self._settings_plot_x_mode = dlg.plot_x_mode
            self._settings_plot_x_min = dlg.plot_x_min
            self._settings_plot_x_max = dlg.plot_x_max
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

    def _settings_float(self, key: str, default: float) -> float:
        raw = self._settings_store.value(key, default)
        try:
            return float(raw)
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
        self._settings_blocks_enabled = self._settings_bool("blocks/enabled", self._settings_blocks_enabled)
        self._settings_tutor_mode = str(self._settings_store.value("tutor/mode", self._settings_tutor_mode) or "none")
        self._settings_tutor_url = str(self._settings_store.value("tutor/url", self._settings_tutor_url) or "")
        self._settings_tutor_model = str(self._settings_store.value("tutor/model", self._settings_tutor_model) or "")
        self._settings_sketchbook = self._normalize_sketchbook_dir(
            str(self._settings_store.value("files/sketchbook_dir", self._settings_sketchbook) or "")
        )
        self._settings_git_repo = str(self._settings_store.value("git/repo_dir", self._settings_git_repo) or "")
        self._settings_theme = str(self._settings_store.value("ui/theme", self._settings_theme) or "classic_light")
        # Serial-Plotter-Achsen
        self._settings_plot_y_mode = str(self._settings_store.value("plot/y_mode", self._settings_plot_y_mode) or "auto")
        self._settings_plot_y_min = self._settings_float("plot/y_min", self._settings_plot_y_min)
        self._settings_plot_y_max = self._settings_float("plot/y_max", self._settings_plot_y_max)
        self._settings_plot_x_mode = str(self._settings_store.value("plot/x_mode", self._settings_plot_x_mode) or "sliding")
        self._settings_plot_x_min = self._settings_int("plot/x_min", self._settings_plot_x_min)
        self._settings_plot_x_max = self._settings_int("plot/x_max", self._settings_plot_x_max)
        # Theme sofort anwenden, damit alle nachfolgenden UI-Elemente korrekte Farben erhalten
        set_theme(self._settings_theme)

    def _save_persistent_settings(self):
        self._settings_store.setValue("editor/font_size", self._settings_font_size)
        self._settings_store.setValue("editor/line_numbers", self._settings_line_numbers)
        self._settings_store.setValue("editor/word_wrap", self._settings_word_wrap)
        self._settings_store.setValue("editor/highlight_line", self._settings_highlight_line)
        self._settings_store.setValue("editor/autosave_secs", self._settings_autosave_secs)
        self._settings_store.setValue("blocks/enabled", self._settings_blocks_enabled)
        self._settings_store.setValue("python/executable", self._settings_python_exec)
        self._settings_store.setValue("console/scrollback", self._settings_scrollback)
        self._settings_store.setValue("tutor/mode", self._settings_tutor_mode)
        self._settings_store.setValue("tutor/url", self._settings_tutor_url)
        self._settings_store.setValue("tutor/model", self._settings_tutor_model)
        self._settings_store.setValue("files/sketchbook_dir", self._settings_sketchbook)
        self._settings_store.setValue("git/repo_dir", self._settings_git_repo)
        self._settings_store.setValue("ui/theme", self._settings_theme)
        self._settings_store.setValue("plot/y_mode", self._settings_plot_y_mode)
        self._settings_store.setValue("plot/y_min", self._settings_plot_y_min)
        self._settings_store.setValue("plot/y_max", self._settings_plot_y_max)
        self._settings_store.setValue("plot/x_mode", self._settings_plot_x_mode)
        self._settings_store.setValue("plot/x_min", self._settings_plot_x_min)
        self._settings_store.setValue("plot/x_max", self._settings_plot_x_max)
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

    def _update_widget_styles(self):
        """Inline-Stylesheets von Toolbar-Widgets und Statusleiste nach Theme-Wechsel neu setzen."""
        t = THEME
        combo_style = (
            f"background:{t['bg_dark']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:4px; padding:3px 6px;"
        )
        if hasattr(self, "_mode_combo"):
            self._mode_combo.setStyleSheet(combo_style + " min-width:160px;")
        if hasattr(self, "_port_combo"):
            self._port_combo.setStyleSheet(combo_style + " min-width:200px;")
        if hasattr(self, "_mode_lbl"):
            self._mode_lbl.setStyleSheet(f"color:{t['text_dim']};")
        if hasattr(self, "_port_lbl"):
            self._port_lbl.setStyleSheet(f"color:{t['text_dim']};")
        if hasattr(self, "_status_mode"):
            self._status_mode.setStyleSheet(f"color:{t['accent']}; font-weight:bold; padding:0 8px;")
        if hasattr(self, "_status_git"):
            self._status_git.setStyleSheet(f"color:{t['text_dim']}; padding:0 8px;")
        if hasattr(self, "_status_board"):
            self._status_board.setStyleSheet(f"color:{t['text_dim']}; padding:0 8px;")

    def _apply_settings(self):
        """Einstellungen auf alle offenen Tabs + Konsole anwenden."""
        # Theme zuerst anwenden, damit alle Farben stimmen
        set_theme(self._settings_theme)
        self.setStyleSheet(build_global_style())
        self._update_widget_styles()

        for tab in self._tabs:
            tab.editor.set_font_size(self._settings_font_size)
            tab.editor.set_line_numbers_visible(self._settings_line_numbers)
            tab.editor.set_word_wrap(self._settings_word_wrap)
            tab.editor.set_highlight_current_line(self._settings_highlight_line)
            tab.editor.refresh_theme()
        self._file_panel.refresh_theme()
        self._device_panel.refresh_theme()
        self._console.refresh_theme()
        self._tutor_panel.refresh_theme()
        self._coder_panel.refresh_theme()
        self._aischat_panel.refresh_theme()
        self._console.set_font_size(self._settings_font_size)
        self._console.set_scrollback_limit(self._settings_scrollback)
        self._console.set_plot_defaults({
            "y_mode": self._settings_plot_y_mode,
            "y_min":  self._settings_plot_y_min,
            "y_max":  self._settings_plot_y_max,
            "x_mode": self._settings_plot_x_mode,
            "x_min":  self._settings_plot_x_min,
            "x_max":  self._settings_plot_x_max,
        })
        # Block-Editor (BETA) ein-/ausblenden
        self._apply_blocks_enabled()
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
        elif mode == "coder":
            self._ai_stack.setMinimumWidth(0)
            self._ai_stack.setMaximumWidth(16777215)
            self._ai_stack.setCurrentIndex(2)
            self._ai_stack.setVisible(True)
            self._coder_panel.apply_settings(
                self._settings_tutor_url,
                self._settings_tutor_model,
            )
            sizes = self._main_splitter.sizes()
            if sizes[2] == 0:
                total = sum(sizes)
                self._main_splitter.setSizes([sizes[0], total - sizes[0] - 360, 360])
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
        for t in list(self._aux_workers):
            if t.isRunning():
                t.wait(1000)
        self._save_persistent_settings()
        event.accept()
