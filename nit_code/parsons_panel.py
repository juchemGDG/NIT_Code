"""Parsons-Puzzle – Lernmodus: Programmzeilen in die richtige Reihenfolge bringen.

Ein Parsons-Problem zeigt die Zeilen eines korrekten Programms in zufälliger
Reihenfolge. Die Schüler:innen sortieren sie per Drag&Drop – der Fokus liegt auf
Algorithmus und Sequenz statt auf dem fehlerfreien Tippen von Syntax. Das Puzzle
wird hier direkt aus dem aktuell geöffneten Code erzeugt (keine externe Vorlage,
offline-fähig).

Variante: 1D-Sortieren mit sichtbarer Einrückung – jede Zeile trägt ihre eigene
Einrückung, es muss nur die Reihenfolge stimmen.
"""
import random

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QLabel, QListWidget, QListWidgetItem, QMainWindow, QToolBar, QVBoxLayout,
    QWidget,
)

from .config import THEME

_MONO = "JetBrains Mono, Fira Code, Consolas, monospace"
_HINT = 'Ziehe die Zeilen in die richtige Reihenfolge und klicke „Prüfen“.'


def _puzzle_lines(code: str) -> list[str]:
    """Nicht-leere Zeilen (mit Einrückung) als Puzzle-Bausteine."""
    lines = []
    for raw in code.replace("\t", "    ").splitlines():
        if raw.strip():
            lines.append(raw.rstrip())
    return lines


class ParsonsWindow(QMainWindow):
    """Fenster mit gemischten Codezeilen, die korrekt sortiert werden sollen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NIT Parsons-Puzzle")
        self.resize(640, 640)
        self._solution: list[str] = []
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        tb = QToolBar("Aktionen")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._act_check = QAction("✓  Prüfen", self)
        self._act_check.setToolTip("Reihenfolge mit der Lösung vergleichen")
        self._act_check.triggered.connect(self._check)
        tb.addAction(self._act_check)

        self._act_shuffle = QAction("🔀  Neu mischen", self)
        self._act_shuffle.setToolTip("Zeilen erneut zufällig anordnen")
        self._act_shuffle.triggered.connect(self._shuffle)
        tb.addAction(self._act_shuffle)

        tb.addSeparator()
        self._act_solution = QAction("💡  Lösung zeigen", self)
        self._act_solution.triggered.connect(self._show_solution)
        tb.addAction(self._act_solution)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        self._hint = QLabel(_HINT)
        self._hint.setWordWrap(True)
        lay.addWidget(self._hint)

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setFont(QFont(_MONO, 12))
        self._list.setSpacing(2)
        lay.addWidget(self._list, 1)

        self._status = QLabel("")
        lay.addWidget(self._status)

        self.setCentralWidget(central)
        self.apply_theme()

    # ── Laden / Mischen ─────────────────────────────────────────────────────
    def load_code(self, code: str):
        """Erzeugt ein neues Puzzle aus dem übergebenen Code."""
        self._solution = _puzzle_lines(code)
        if len(self._solution) < 2:
            self._hint.setText(
                "Zu wenige Codezeilen für ein Puzzle – öffne eine Datei mit "
                "mehreren Zeilen und starte das Puzzle erneut."
            )
            self._list.clear()
            self._status.setText("")
            return
        self._hint.setText(_HINT)
        self._shuffle()

    def _shuffle(self):
        if len(self._solution) < 2:
            return
        order = list(self._solution)
        # Nicht zufällig die fertige Lösung präsentieren
        while order == self._solution:
            random.shuffle(order)
        self._populate(order)
        self._status.setText("")

    def _populate(self, lines: list[str]):
        self._list.clear()
        for text in lines:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, text)
            self._list.addItem(item)
        self._reset_colors()

    def _current_order(self) -> list[str]:
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]

    # ── Prüfen / Lösung ─────────────────────────────────────────────────────
    def _check(self):
        if len(self._solution) < 2:
            return
        order = self._current_order()
        correct = 0
        for i, text in enumerate(order):
            ok = i < len(self._solution) and text == self._solution[i]
            self._color_item(i, ok)
            if ok:
                correct += 1
        n = len(self._solution)
        if correct == n:
            self._status.setText(f"🎉  Perfekt – alle {n} Zeilen an der richtigen Stelle!")
        else:
            self._status.setText(f"{correct} von {n} Zeilen richtig platziert.")

    def _show_solution(self):
        if len(self._solution) < 2:
            return
        self._populate(self._solution)
        for i in range(self._list.count()):
            self._color_item(i, True)
        self._status.setText('Lösung – „Neu mischen“ für einen neuen Versuch.')

    # ── Einfärben ───────────────────────────────────────────────────────────
    def _color_item(self, i: int, ok: bool):
        item = self._list.item(i)
        if item is None:
            return
        tint = QColor(THEME["success"] if ok else THEME["error"])
        tint.setAlpha(56)
        item.setBackground(QBrush(tint))
        item.setForeground(QBrush(QColor(THEME["text"])))

    def _reset_colors(self):
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setBackground(QBrush(QColor(0, 0, 0, 0)))
            item.setForeground(QBrush(QColor(THEME["text"])))

    # ── Theme ─────────────────────────────────────────────────────────────────
    def apply_theme(self):
        t = THEME
        self.setStyleSheet(f"background:{t['bg_dark']};")
        self._list.setStyleSheet(
            f"QListWidget {{ background:{t['bg_editor']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:6px; padding:4px; }}"
            f"QListWidget::item {{ padding:4px 6px; }}"
            f"QListWidget::item:selected {{ background:{t['selection']}; color:{t['text']}; }}"
        )
        self._hint.setStyleSheet(f"color:{t['text']};")
        self._status.setStyleSheet(f"color:{t['text']}; font-weight:bold;")
