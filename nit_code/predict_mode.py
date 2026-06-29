"""Vorhersage-Modus – vor dem Programmlauf die Ausgabe vorhersagen.

Didaktische Idee: Statt „ausführen und schauen" sagt die Schüler:in zuerst
voraus, was das Programm ausgeben wird. Nach dem Lauf wird die Vorhersage mit
der tatsächlichen Ausgabe verglichen. Das fördert ein mentales Modell der
Programmausführung statt Trial-and-Error. Vollständig offline (reiner
Textvergleich, kein KI-Modell nötig).
"""
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout,
    QWidget,
)

from .config import THEME

_MONO = "JetBrains Mono, Fira Code, Consolas, monospace"


def _normalize(text: str) -> list[str]:
    """Zeilen ohne nachlaufende Leerzeichen; leere Zeilen am Ende entfernt."""
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def compare_outputs(predicted: str, actual: str):
    """Vergleicht Vorhersage und Ausgabe (zeilenweise, ohne Rand-Leerraum).

    Gibt (stimmt_überein, vorhersage_zeilen, ausgabe_zeilen) zurück.
    """
    p = _normalize(predicted)
    a = _normalize(actual)
    return p == a, p, a


class PredictionDialog(QDialog):
    """Fragt vor dem Lauf die erwartete Ausgabe ab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vorhersage-Modus")
        self.resize(480, 340)
        lay = QVBoxLayout(self)
        info = QLabel(
            "Bevor das Programm läuft: Was wird es ausgeben?\n"
            "Tippe deine Vorhersage – danach vergleichen wir sie mit der "
            "tatsächlichen Ausgabe."
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        self._edit = QPlainTextEdit()
        self._edit.setFont(QFont(_MONO, 11))
        self._edit.setPlaceholderText("Erwartete Ausgabe …")
        lay.addWidget(self._edit, 1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Starten")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        t = THEME
        self.setStyleSheet(f"background:{t['bg_dark']}; color:{t['text']};")
        self._edit.setStyleSheet(
            f"background:{t['bg_editor']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:4px;"
        )
        info.setStyleSheet(f"color:{t['text']};")
        self._edit.setFocus()

    def prediction(self) -> str:
        return self._edit.toPlainText()


class ResultDialog(QDialog):
    """Zeigt Vorhersage und tatsächliche Ausgabe nebeneinander + Urteil."""

    def __init__(self, predicted: str, actual: str, matches: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vorhersage – Vergleich")
        self.resize(760, 440)
        lay = QVBoxLayout(self)

        if matches:
            msg = "✓  Deine Vorhersage stimmt mit der Ausgabe überein!"
            color = THEME["success"]
        else:
            msg = "✗  Es gibt Abweichungen – vergleiche die beiden Spalten genau."
            color = THEME["warning"]
        verdict = QLabel(msg)
        verdict.setWordWrap(True)
        verdict.setStyleSheet(f"color:{color}; font-weight:bold; font-size:14px;")
        lay.addWidget(verdict)

        cols = QHBoxLayout()
        cols.addWidget(self._column("Deine Vorhersage", predicted))
        cols.addWidget(self._column("Tatsächliche Ausgabe", actual))
        lay.addLayout(cols, 1)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        lay.addWidget(btns)

        self.setStyleSheet(f"background:{THEME['bg_dark']}; color:{THEME['text']};")

    def _column(self, title: str, text: str) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color:{THEME['text']}; font-weight:bold;")
        v.addWidget(lbl)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setFont(QFont(_MONO, 11))
        box.setPlainText(text)
        box.setStyleSheet(
            f"background:{THEME['bg_editor']}; color:{THEME['text']};"
            f" border:1px solid {THEME['border']}; border-radius:4px;"
        )
        v.addWidget(box, 1)
        return w
