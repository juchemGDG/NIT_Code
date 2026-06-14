"""Einstellungs-Dialog für NIT_Code."""
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QCheckBox, QPushButton, QFrame,
    QComboBox, QLineEdit, QFileDialog, QWidget,
)

from .config import (
    THEME, THEMES,
    TUTOR_DEFAULT_URL, TUTOR_DEFAULT_MODEL,
    OLLAMA_WEB_PASSWORD,
    is_ollama_available, AIS_CHAT_URL,
)

# Auto-Save-Intervalle: Anzeigetext → Sekunden
_AUTOSAVE_OPTIONS = [
    ("Aus", 0),
    ("30 Sek.", 30),
    ("60 Sek.", 60),
    ("5 Min.", 300),
]


# ── Hintergrund-Thread: Ollama-Modelle abrufen ──────────────────────────────

class _OllamaFetcher(QThread):
    """Ruft verfügbare Ollama-Modelle vom API-Endpunkt ab (ohne UI zu blockieren)."""
    models_ready = pyqtSignal(list)
    error        = pyqtSignal(str)

    def __init__(self, url: str, password: str = ""):
        super().__init__()
        self._url      = url.rstrip("/")
        self._password = password

    def run(self):
        import json
        import base64
        from urllib.request import Request, urlopen

        endpoint = f"{self._url}/api/tags"

        def _fetch(headers=None):
            req = Request(endpoint, headers=headers or {})
            with urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read())
                return [m["name"] for m in data.get("models", [])]

        # 1. Ohne Auth
        try:
            self.models_ready.emit(_fetch())
            return
        except Exception:
            pass

        if not self._password:
            self.error.emit("Nicht erreichbar")
            return

        # 2. Bearer Token
        try:
            self.models_ready.emit(_fetch({"Authorization": f"Bearer {self._password}"}))
            return
        except Exception:
            pass

        # 3. Basic Auth (leerer Benutzername)
        creds = base64.b64encode(f":{self._password}".encode()).decode()
        try:
            self.models_ready.emit(_fetch({"Authorization": f"Basic {creds}"}))
            return
        except Exception:
            pass

        self.error.emit("Nicht erreichbar")


# ── Einstellungs-Dialog ──────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    """Einstellungs-Popup mit Editor-, Shell- und KI-Optionen."""

    def __init__(
        self,
        parent=None,
        font_size: int = 14,
        line_numbers: bool = True,
        word_wrap: bool = False,
        highlight_line: bool = True,
        autosave_secs: int = 0,
        python_exec: str = "",
        scrollback: int = 5000,
        tutor_mode: str = "none",
        tutor_url: str = "",
        tutor_model: str = "",
        sketchbook_dir: str = "",
        theme: str = "modern_dark",
    ):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._fetcher: _OllamaFetcher | None = None
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {THEME['bg_panel']};
                color: {THEME['text']};
            }}
            QLabel {{
                color: {THEME['text']};
            }}
            QSpinBox, QCheckBox, QComboBox, QLineEdit {{
                background: {THEME['bg_dark']};
                color: {THEME['text']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 3px 6px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {THEME['bg_panel']};
                border: none;
                width: 16px;
            }}
            QComboBox::drop-down {{
                border: none;
                background: {THEME['bg_panel']};
                width: 20px;
            }}
            QPushButton {{
                background: {THEME['accent']};
                color: #fff;
                border: none;
                border-radius: 4px;
                padding: 6px 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {THEME['accent_hover']};
            }}
            QPushButton#cancel {{
                background: {THEME['bg_dark']};
                color: {THEME['text']};
            }}
            QPushButton#cancel:hover {{
                background: {THEME['border']};
            }}
            QPushButton#browse {{
                background: {THEME['bg_dark']};
                color: {THEME['text']};
                padding: 4px 10px;
                font-weight: normal;
            }}
            QPushButton#browse:hover {{
                background: {THEME['border']};
            }}
            """
        )
        self._build_ui(font_size, line_numbers, word_wrap, highlight_line,
                       autosave_secs, python_exec, scrollback,
                       tutor_mode, tutor_url, tutor_model, sketchbook_dir, theme)

    # ── Hilfsmethode: Abschnittsüberschrift ─────────────────────────────
    @staticmethod
    def _section(label: str) -> tuple:
        title = QLabel(label)
        title.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:11px; font-weight:bold; letter-spacing:1px;"
        )
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{THEME['border']};")
        sep.setFixedHeight(1)
        return title, sep

    def _build_ui(
        self,
        font_size: int,
        line_numbers: bool,
        word_wrap: bool,
        highlight_line: bool,
        autosave_secs: int,
        python_exec: str,
        scrollback: int,
        tutor_mode: str = "none",
        tutor_url: str = "",
        tutor_model: str = "",
        sketchbook_dir: str = "",
        theme: str = "modern_dark",
    ):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        # ── Abschnitt: Editor ────────────────────────────────────────────
        title, sep = self._section("EDITOR")
        root.addWidget(title)
        root.addWidget(sep)

        form_ed = QFormLayout()
        form_ed.setSpacing(8)
        form_ed.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._spin = QSpinBox()
        self._spin.setRange(8, 32)
        self._spin.setValue(font_size)
        self._spin.setSuffix(" pt")
        self._spin.setFixedWidth(90)
        form_ed.addRow("Schriftgröße (Editor & Shell):", self._spin)

        self._chk_lineno = QCheckBox("  Zeilennummern anzeigen")
        self._chk_lineno.setChecked(line_numbers)
        form_ed.addRow("", self._chk_lineno)

        self._chk_wrap = QCheckBox("  Zeilenumbruch")
        self._chk_wrap.setChecked(word_wrap)
        form_ed.addRow("", self._chk_wrap)

        self._chk_hl = QCheckBox("  Aktuelle Zeile hervorheben")
        self._chk_hl.setChecked(highlight_line)
        form_ed.addRow("", self._chk_hl)

        root.addLayout(form_ed)
        root.addSpacing(6)

        # ── Abschnitt: Ausführen ─────────────────────────────────────────
        title2, sep2 = self._section("AUSFÜHREN")
        root.addWidget(title2)
        root.addWidget(sep2)

        form_run = QFormLayout()
        form_run.setSpacing(8)
        form_run.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._combo_as = QComboBox()
        self._combo_as.setFixedWidth(120)
        for label, secs in _AUTOSAVE_OPTIONS:
            self._combo_as.addItem(label, secs)
        idx = next((i for i, (_, s) in enumerate(_AUTOSAVE_OPTIONS) if s == autosave_secs), 0)
        self._combo_as.setCurrentIndex(idx)
        form_run.addRow("Auto-Speichern:", self._combo_as)

        root.addLayout(form_run)
        root.addSpacing(6)

        # ── Abschnitt: Shell ─────────────────────────────────────────────
        title3, sep3 = self._section("SHELL")
        root.addWidget(title3)
        root.addWidget(sep3)

        form_sh = QFormLayout()
        form_sh.setSpacing(8)
        form_sh.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._spin_sb = QSpinBox()
        self._spin_sb.setRange(500, 50000)
        self._spin_sb.setSingleStep(1000)
        self._spin_sb.setValue(scrollback)
        self._spin_sb.setSuffix(" Zeilen")
        self._spin_sb.setFixedWidth(130)
        form_sh.addRow("Scrollback-Puffer:", self._spin_sb)

        root.addLayout(form_sh)
        root.addSpacing(6)

        # ── Abschnitt: Design ────────────────────────────────────────────
        title_d, sep_d = self._section("DESIGN")
        root.addWidget(title_d)
        root.addWidget(sep_d)

        form_design = QFormLayout()
        form_design.setSpacing(8)
        form_design.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._combo_theme = QComboBox()
        self._combo_theme.addItem("Modernes Dunkel-Design", "modern_dark")
        self._combo_theme.addItem("Klassisches Hell-Design (Eclipse)", "classic_light")
        tidx = max(0, self._combo_theme.findData(theme))
        self._combo_theme.setCurrentIndex(tidx)
        form_design.addRow("Design:", self._combo_theme)

        root.addLayout(form_design)
        root.addSpacing(6)

        # ── Abschnitt: Python (lokal) ────────────────────────────────────
        title4, sep4 = self._section("PYTHON (LOKAL)")
        root.addWidget(title4)
        root.addWidget(sep4)

        form_py = QFormLayout()
        form_py.setSpacing(8)
        form_py.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        py_row = QHBoxLayout()
        py_row.setSpacing(6)
        self._edit_py = QLineEdit()
        self._edit_py.setPlaceholderText("(automatisch erkannt)")
        self._edit_py.setText(python_exec)
        py_row.addWidget(self._edit_py)
        btn_browse = QPushButton("…")
        btn_browse.setObjectName("browse")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(self._browse_python)
        py_row.addWidget(btn_browse)
        form_py.addRow("Python-Interpreter:", py_row)

        root.addLayout(form_py)
        root.addSpacing(6)

        # ── Abschnitt: Dateisystem ───────────────────────────────────────
        title_fs, sep_fs = self._section("DATEISYSTEM")
        root.addWidget(title_fs)
        root.addWidget(sep_fs)

        form_fs = QFormLayout()
        form_fs.setSpacing(8)
        form_fs.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        sb_row = QHBoxLayout()
        sb_row.setSpacing(6)
        self._edit_sketchbook = QLineEdit()
        self._edit_sketchbook.setPlaceholderText("(optional)")
        self._edit_sketchbook.setText(sketchbook_dir)
        sb_row.addWidget(self._edit_sketchbook)
        btn_sketchbook = QPushButton("…")
        btn_sketchbook.setObjectName("browse")
        btn_sketchbook.setFixedWidth(32)
        btn_sketchbook.clicked.connect(self._browse_sketchbook)
        sb_row.addWidget(btn_sketchbook)
        form_fs.addRow("Sketchbook-Ordner:", sb_row)

        root.addLayout(form_fs)
        root.addSpacing(6)

        # ── Abschnitt: KI-Tutor ─────────────────────────────────────────
        title5, sep5 = self._section("KI-TUTOR")
        root.addWidget(title5)
        root.addWidget(sep5)

        form_ai = QFormLayout()
        form_ai.setSpacing(8)
        form_ai.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._combo_tutor_mode = QComboBox()
        self._combo_tutor_mode.addItem("Kein Chatbot", "none")
        self._combo_tutor_mode.addItem("KI-Tutor: Infi (Ollama)", "ollama")
        self._combo_tutor_mode.addItem("Code-Generator (Ollama)", "coder")
        self._combo_tutor_mode.addItem("AIS-Chat (Schule)", "aischat")
        idx = max(0, self._combo_tutor_mode.findData(tutor_mode))
        self._combo_tutor_mode.setCurrentIndex(idx)
        form_ai.addRow("Chatbot:", self._combo_tutor_mode)
        root.addLayout(form_ai)

        # Ollama-spezifische Felder (immer sichtbar, wenn Ollama-Modus aktiv)
        self._ollama_container = QWidget()
        form_ollama = QFormLayout(self._ollama_container)
        form_ollama.setSpacing(8)
        form_ollama.setContentsMargins(0, 4, 0, 0)
        form_ollama.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # URL
        self._edit_tutor_url = QLineEdit()
        self._edit_tutor_url.setPlaceholderText(TUTOR_DEFAULT_URL)
        self._edit_tutor_url.setText(tutor_url)
        form_ollama.addRow("Ollama-URL:", self._edit_tutor_url)

        # Modell-Auswahl: editierbare ComboBox + Laden-Schaltfläche
        model_row_w = QWidget()
        model_row_lay = QHBoxLayout(model_row_w)
        model_row_lay.setContentsMargins(0, 0, 0, 0)
        model_row_lay.setSpacing(4)

        self._combo_tutor_model = QComboBox()
        self._combo_tutor_model.setEditable(True)
        self._combo_tutor_model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._combo_tutor_model.lineEdit().setPlaceholderText(TUTOR_DEFAULT_MODEL)
        if tutor_model:
            self._combo_tutor_model.addItem(tutor_model)
            self._combo_tutor_model.setCurrentText(tutor_model)
        model_row_lay.addWidget(self._combo_tutor_model)

        self._btn_refresh_models = QPushButton("↻")
        self._btn_refresh_models.setObjectName("browse")
        self._btn_refresh_models.setFixedWidth(32)
        self._btn_refresh_models.setToolTip(
            "Verfügbare Ollama-Modelle von der URL abrufen\n"
            "(lokal oder Web mit Passwort)"
        )
        self._btn_refresh_models.clicked.connect(self._fetch_ollama_models)
        model_row_lay.addWidget(self._btn_refresh_models)
        form_ollama.addRow("Modell:", model_row_w)

        if not is_ollama_available():
            hint = QLabel(
                "Ollama nicht lokal installiert — "
                "Web-URL eingeben und ↻ klicken."
            )
            hint.setStyleSheet(
                f"color:{THEME['text_dim']}; font-size:11px; padding:2px 0;"
            )
            hint.setWordWrap(True)
            form_ollama.addRow("", hint)

        root.addWidget(self._ollama_container)
        self._ollama_container.setVisible(tutor_mode in ("ollama", "coder"))
        self._combo_tutor_mode.currentIndexChanged.connect(self._on_tutor_mode_changed)

        root.addStretch()

        # ── Buttons ─────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.setObjectName("cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton("Übernehmen")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        root.addLayout(btn_row)

    # ── Ollama-Modelle laden ─────────────────────────────────────────────────

    def _fetch_ollama_models(self):
        if self._fetcher and self._fetcher.isRunning():
            return
        url = self._edit_tutor_url.text().strip() or TUTOR_DEFAULT_URL
        self._btn_refresh_models.setEnabled(False)
        self._btn_refresh_models.setText("…")
        self._fetcher = _OllamaFetcher(url, OLLAMA_WEB_PASSWORD)
        self._fetcher.models_ready.connect(self._on_models_ready)
        self._fetcher.error.connect(self._on_models_error)
        self._fetcher.start()

    def _on_models_ready(self, models: list):
        current = self._combo_tutor_model.currentText().strip()
        self._combo_tutor_model.clear()
        for m in sorted(models):
            self._combo_tutor_model.addItem(m)
        if current:
            idx = self._combo_tutor_model.findText(current)
            if idx >= 0:
                self._combo_tutor_model.setCurrentIndex(idx)
            else:
                self._combo_tutor_model.setCurrentText(current)
        self._btn_refresh_models.setEnabled(True)
        self._btn_refresh_models.setText("↻")

    def _on_models_error(self, msg: str):
        self._btn_refresh_models.setEnabled(True)
        self._btn_refresh_models.setText("↻")
        le = self._combo_tutor_model.lineEdit()
        if le:
            le.setPlaceholderText(f"⚠ {msg}")

    def done(self, result: int):
        if self._fetcher and self._fetcher.isRunning():
            self._fetcher.quit()
            self._fetcher.wait(500)
        super().done(result)

    # ── Hilfsmethoden ───────────────────────────────────────────────────────

    def _browse_python(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Python-Interpreter wählen",
            "/usr/bin",
            "Ausführbare Dateien (*python* *python3*);; Alle Dateien (*)",
        )
        if path:
            self._edit_py.setText(path)

    def _browse_sketchbook(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Sketchbook-Ordner wählen",
            self._edit_sketchbook.text().strip() or "/home",
        )
        if folder:
            self._edit_sketchbook.setText(folder)

    def _on_tutor_mode_changed(self, _index: int):
        self._ollama_container.setVisible(
            self._combo_tutor_mode.currentData() in ("ollama", "coder")
        )

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def font_size(self) -> int:
        return self._spin.value()

    @property
    def line_numbers(self) -> bool:
        return self._chk_lineno.isChecked()

    @property
    def word_wrap(self) -> bool:
        return self._chk_wrap.isChecked()

    @property
    def highlight_line(self) -> bool:
        return self._chk_hl.isChecked()

    @property
    def autosave_secs(self) -> int:
        return self._combo_as.currentData()

    @property
    def python_exec(self) -> str:
        return self._edit_py.text().strip()

    @property
    def scrollback_lines(self) -> int:
        return self._spin_sb.value()

    @property
    def theme(self) -> str:
        return self._combo_theme.currentData()

    @property
    def tutor_mode(self) -> str:
        return self._combo_tutor_mode.currentData()

    @property
    def tutor_url(self) -> str:
        return self._edit_tutor_url.text().strip()

    @property
    def tutor_model(self) -> str:
        return self._combo_tutor_model.currentText().strip()

    @property
    def sketchbook_dir(self) -> str:
        return self._edit_sketchbook.text().strip()
