"""Einstellungs-Dialog für NIT PyEd."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QCheckBox, QPushButton, QFrame,
)

from .config import THEME


class SettingsDialog(QDialog):
    """Einstellungs-Popup mit Editor- und Shell-Optionen."""

    def __init__(self, parent=None, font_size: int = 14, line_numbers: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        self.setMinimumWidth(340)
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {THEME['bg_panel']};
                color: {THEME['text']};
            }}
            QLabel {{
                color: {THEME['text']};
            }}
            QSpinBox, QCheckBox {{
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
            """
        )
        self._build_ui(font_size, line_numbers)

    def _build_ui(self, font_size: int, line_numbers: bool):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # ── Abschnittstitel ─────────────────────────────────────────────
        title = QLabel("Editor")
        title.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:11px; font-weight:bold; letter-spacing:1px;"
        )
        root.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{THEME['border']};")
        sep.setFixedHeight(1)
        root.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Schriftgröße
        self._spin = QSpinBox()
        self._spin.setRange(8, 32)
        self._spin.setValue(font_size)
        self._spin.setSuffix(" pt")
        self._spin.setFixedWidth(90)
        form.addRow("Schriftgröße (Editor & Shell):", self._spin)

        # Zeilennummern
        self._chk_lineno = QCheckBox()
        self._chk_lineno.setChecked(line_numbers)
        self._chk_lineno.setText("  Zeilennummern anzeigen")
        form.addRow("", self._chk_lineno)

        root.addLayout(form)

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

    # ── Ergebnis abrufen ────────────────────────────────────────────────
    @property
    def font_size(self) -> int:
        return self._spin.value()

    @property
    def line_numbers(self) -> bool:
        return self._chk_lineno.isChecked()
