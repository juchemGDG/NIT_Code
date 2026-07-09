"""Dialog „NiT_Coder (ais.chat)" (Hilfe-Menü).

Zeigt die Vorlage, mit der Lehrkräfte den Code-Generator als eigenen
Dialogpartner auf ais.chat anlegen können. Die Felder entsprechen der
Eingabemaske von ais.chat (Name, Kurzbeschreibung, Sprachmodell,
Instruktionen, Einstiegsfrage, Hintergrundwissen); jedes Feld lässt sich
einzeln in die Zwischenablage kopieren. Die Instruktionen sind identisch
mit dem System-Prompt des eingebauten Code-Generators (coder_panel.py),
damit sich beide Varianten gleich verhalten.
"""
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QWidget,
)

from .config import AIS_CHAT_URL, THEME
from .coder_panel import CODER_SYSTEM_PROMPT

_NAME = "NiT_Coder"

_KURZBESCHREIBUNG = (
    "Code-Generator für den Informatikunterricht: setzt vollständige "
    "Spezifikationen (EINGABE, ABLAUF, AUSGABE, VARIABLEN) in "
    "MicroPython-Code für den ESP32 um – entwirft aber nie selbst den "
    "Algorithmus."
)

_SPRACHMODELL = (
    "Empfehlung: mindestens GPT-5 mini. Kleinere Modelle (z. B. GPT-5 nano) "
    "halten die Regeln – kein eigener Algorithmus-Entwurf, keine doppelten "
    "Rückfragen – weniger zuverlässig ein."
)

_EINSTIEGSFRAGE = (
    "Hallo! Ich bin der NiT_Coder. Beschreibe mir deine Spezifikation – "
    "EINGABE, ABLAUF, AUSGABE und VARIABLEN – und ich setze sie in "
    "Python-Code um."
)

_HINTERGRUNDWISSEN = (
    "Dateien sind nicht nötig – die Bibliotheks-Referenz steht bereits in den "
    "Instruktionen. Optional kann als Webseite das Bibliotheks-Repository "
    "angegeben werden:\n"
    "https://github.com/juchemGDG/NIT_Bibliotheken"
)


class AisChatPromptDialog(QDialog):
    """Zeigt die ais.chat-Dialogpartner-Vorlage mit Kopier-Knöpfen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NiT_Coder als Dialogpartner auf ais.chat")
        self.setMinimumSize(640, 640)
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)

        intro = QLabel(
            f"So legst du den Code-Generator als Dialogpartner auf ais.chat an "
            f"({AIS_CHAT_URL}): Neuen Dialogpartner erstellen und die Felder "
            f"unten hineinkopieren."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(10)

        self._add_field(layout, "Name des Dialogpartners", _NAME, single_line=True)
        self._add_field(layout, "Kurzbeschreibung", _KURZBESCHREIBUNG, height=64)
        self._add_hint(layout, "Sprachmodell", _SPRACHMODELL)
        self._add_field(layout, "Instruktionen", CODER_SYSTEM_PROMPT, height=260)
        self._add_field(layout, "Einstiegsfrage", _EINSTIEGSFRAGE, height=56)
        self._add_hint(layout, "Hintergrundwissen", _HINTERGRUNDWISSEN)

        layout.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)

    def _add_field(self, layout, title: str, text: str,
                   height: int = 80, single_line: bool = False):
        """Überschrift + (nur lesbares) Textfeld + Kopieren-Knopf."""
        layout.addLayout(self._header_row(title, text))
        if single_line:
            field = QLineEdit(text)
            field.setReadOnly(True)
        else:
            field = QPlainTextEdit(text)
            field.setReadOnly(True)
            field.setFixedHeight(height)
        layout.addWidget(field)

    def _add_hint(self, layout, title: str, text: str):
        """Überschrift + Hinweistext (Feld, das man nicht 1:1 kopiert)."""
        layout.addLayout(self._header_row(title, text))
        hint = QLabel(text)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{THEME['text_dim']};")
        layout.addWidget(hint)

    def _header_row(self, title: str, text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(f"<b>{title}</b>")
        row.addWidget(lbl)
        row.addStretch(1)
        btn = QPushButton("Kopieren")
        btn.setFixedWidth(90)
        btn.clicked.connect(lambda _, t=text, b=btn: self._copy(t, b))
        row.addWidget(btn)
        return row

    @staticmethod
    def _copy(text: str, btn: QPushButton):
        QApplication.clipboard().setText(text)
        btn.setText("Kopiert ✓")
