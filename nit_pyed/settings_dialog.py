"""Einstellungs-Dialog für NIT_Code."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QCheckBox, QPushButton, QFrame,
    QComboBox, QLineEdit, QFileDialog,
)

from .config import THEME, TUTOR_DEFAULT_URL, TUTOR_DEFAULT_MODEL, is_ollama_available

# Auto-Save-Intervalle: Anzeigetext → Sekunden
_AUTOSAVE_OPTIONS = [
    ("Aus", 0),
    ("30 Sek.", 30),
    ("60 Sek.", 60),
    ("5 Min.", 300),
]


class SettingsDialog(QDialog):
    """Einstellungs-Popup mit Editor- und Shell-Optionen."""

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
        tutor_enabled: bool = False,
        tutor_url: str = "",
        tutor_model: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        self.setMinimumWidth(420)
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
                       tutor_enabled, tutor_url, tutor_model)

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
        tutor_enabled: bool = False,
        tutor_url: str = "",
        tutor_model: str = "",
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
        # Aktuellen Wert vorauswählen
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

        # ── Abschnitt: KI-Tutor (nur wenn Ollama installiert ist) ───────────
        self._tutor_available = is_ollama_available()
        title5, sep5 = self._section("KI-TUTOR (INFI)")
        root.addWidget(title5)
        root.addWidget(sep5)

        form_ai = QFormLayout()
        form_ai.setSpacing(8)
        form_ai.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        if self._tutor_available:
            self._chk_tutor = QCheckBox("  Infi-Tutor aktivieren")
            self._chk_tutor.setChecked(tutor_enabled)
            form_ai.addRow("", self._chk_tutor)

            self._edit_tutor_url = QLineEdit()
            self._edit_tutor_url.setPlaceholderText(TUTOR_DEFAULT_URL)
            self._edit_tutor_url.setText(tutor_url)
            form_ai.addRow("Ollama-URL:", self._edit_tutor_url)

            self._edit_tutor_model = QLineEdit()
            self._edit_tutor_model.setPlaceholderText(TUTOR_DEFAULT_MODEL)
            self._edit_tutor_model.setText(tutor_model)
            form_ai.addRow("Modell:", self._edit_tutor_model)
        else:
            not_found = QLabel(
                "Ollama ist nicht installiert.\n"
                "Bitte Ollama installieren, um den KI-Tutor zu nutzen.\n"
                "→ https://ollama.com/download"
            )
            not_found.setStyleSheet(
                f"color:{THEME['text_dim']}; font-size:11px; padding:2px 0;"
            )
            not_found.setWordWrap(True)
            form_ai.addRow("", not_found)

        root.addLayout(form_ai)

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

    def _browse_python(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Python-Interpreter wählen",
            "/usr/bin",
            "Ausführbare Dateien (*python* *python3*);; Alle Dateien (*)",
        )
        if path:
            self._edit_py.setText(path)

    # ── Ergebnis abrufen ────────────────────────────────────────────────
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
    def tutor_enabled(self) -> bool:
        if not self._tutor_available:
            return False
        return self._chk_tutor.isChecked()

    @property
    def tutor_url(self) -> str:
        if not self._tutor_available:
            return ""
        return self._edit_tutor_url.text().strip()

    @property
    def tutor_model(self) -> str:
        if not self._tutor_available:
            return ""
        return self._edit_tutor_model.text().strip()
