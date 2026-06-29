"""Parsons-Puzzle – Lernmodus: Programmzeilen in die richtige Reihenfolge bringen.

Ein Parsons-Problem zeigt die Zeilen eines korrekten Programms in zufälliger
Reihenfolge. Die Schüler:innen sortieren sie per Drag&Drop – der Fokus liegt auf
Algorithmus und Sequenz statt auf dem fehlerfreien Tippen von Syntax.

Wichtig: *Autor* und *Löser* sind getrennt. Eine Lehrkraft erstellt aus einem
Referenzprogramm eine **Puzzle-Datei** (JSON); die Schüler:innen lösen das Puzzle,
ohne den Quelltext im Editor zu sehen. Das Format unterstützt:

- ``solution``    – die korrekten Zeilen (mit Einrückung)
- ``distractors`` – Ablenker-Zeilen, die *nicht* gebraucht werden
- ``indent_mode`` – wenn True, müssen die Lernenden die Einrückung selbst setzen
                    (2D-Parsons; trainiert die Blockstruktur)

Gelöst wird in zwei Listen: links die „Bausteine" (gemischt, inkl. Ablenker),
rechts „Dein Programm". Ablenker bleiben einfach links liegen.
"""
import json
import random
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QToolBar, QVBoxLayout,
    QWidget,
)

from .config import THEME

_MONO = "JetBrains Mono, Fira Code, Consolas, monospace"
_ROLE_CANON = Qt.ItemDataRole.UserRole        # Originalzeile (mit Einrückung)
_ROLE_LEVEL = Qt.ItemDataRole.UserRole + 1    # gesetzte Einrückungsstufe (2D)
_FILE_FILTER = "Parsons-Puzzle (*.json);;Alle Dateien (*)"


def code_lines(code: str) -> list[str]:
    """Nicht-leere Zeilen (mit Einrückung, Tabs → 4 Leerzeichen) als Bausteine."""
    out = []
    for raw in code.replace("\t", "    ").splitlines():
        if raw.strip():
            out.append(raw.rstrip())
    return out


def _indent_level(line: str) -> int:
    return (len(line) - len(line.lstrip(" "))) // 4


def load_puzzle(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "title": str(data.get("title") or Path(path).stem),
        "description": str(data.get("description") or ""),
        "solution": [str(s).rstrip() for s in data.get("solution", []) if str(s).strip()],
        "distractors": [str(s).rstrip() for s in data.get("distractors", []) if str(s).strip()],
        "indent_mode": bool(data.get("indent_mode", False)),
    }


def save_puzzle(path: str, puzzle: dict):
    payload = {"type": "nit-parsons", "version": 1, **puzzle}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────────────────────────────────
# Autor-Dialog (Lehrkraft): aus aktuellem Code ein Puzzle bauen
# ──────────────────────────────────────────────────────────────────────────
class PuzzleAuthorDialog(QDialog):
    """Erstellt aus dem aktuellen Code eine Puzzle-Definition (Lehrkraft-Werkzeug)."""

    def __init__(self, code: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Parsons-Puzzle erstellen")
        self.resize(580, 600)
        self._solution = code_lines(code)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("Titel:"))
        self._title = QLineEdit()
        lay.addWidget(self._title)

        lay.addWidget(QLabel("Aufgabenstellung (wird den Lernenden gezeigt):"))
        self._desc = QPlainTextEdit()
        self._desc.setFixedHeight(70)
        lay.addWidget(self._desc)

        lay.addWidget(QLabel(f"Lösung ({len(self._solution)} Zeilen, aus dem aktuellen Code):"))
        self._preview = QPlainTextEdit("\n".join(self._solution))
        self._preview.setReadOnly(True)
        self._preview.setFont(QFont(_MONO, 11))
        self._preview.setFixedHeight(150)
        lay.addWidget(self._preview)

        lay.addWidget(QLabel("Ablenker-Zeilen (eine pro Zeile, optional) – plausibel, aber falsch:"))
        self._distractors = QPlainTextEdit()
        self._distractors.setFont(QFont(_MONO, 11))
        self._distractors.setFixedHeight(90)
        lay.addWidget(self._distractors)

        self._indent_chk = QCheckBox(
            "Einrückung von den Lernenden selbst setzen lassen (2D-Parsons)"
        )
        lay.addWidget(self._indent_chk)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setText("Speichern …")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        t = THEME
        self.setStyleSheet(f"background:{t['bg_dark']}; color:{t['text']};")
        field = (
            f"background:{t['bg_editor']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:4px;"
        )
        for w in (self._title, self._desc, self._preview, self._distractors):
            w.setStyleSheet(field)

    def puzzle(self) -> dict:
        return {
            "title": self._title.text().strip() or "Parsons-Puzzle",
            "description": self._desc.toPlainText().strip(),
            "solution": self._solution,
            "distractors": code_lines(self._distractors.toPlainText()),
            "indent_mode": self._indent_chk.isChecked(),
        }


# ──────────────────────────────────────────────────────────────────────────
# Löser-Fenster
# ──────────────────────────────────────────────────────────────────────────
class ParsonsWindow(QMainWindow):
    """Zwei-Listen-Puzzle: Bausteine (links) in „Dein Programm" (rechts) sortieren."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NIT Parsons-Puzzle")
        self.resize(820, 640)
        self._puzzle: dict | None = None
        self._code_provider = None
        self._build_ui()

    def set_code_provider(self, fn):
        """Callback, der den aktuellen Editor-Code liefert (für „Aus Code erstellen")."""
        self._code_provider = fn

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        tb = QToolBar("Aktionen")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._act_open = QAction("📂  Puzzle öffnen …", self)
        self._act_open.triggered.connect(self._open_puzzle_file)
        tb.addAction(self._act_open)
        self._act_create = QAction("🛠  Aus aktuellem Code erstellen …", self)
        self._act_create.setToolTip("Lehrkraft: aktuelles Programm zu einem Puzzle machen")
        self._act_create.triggered.connect(self._create_puzzle)
        tb.addAction(self._act_create)
        tb.addSeparator()
        self._act_check = QAction("✓  Prüfen", self)
        self._act_check.triggered.connect(self._check)
        tb.addAction(self._act_check)
        self._act_shuffle = QAction("🔀  Neu mischen", self)
        self._act_shuffle.triggered.connect(self._shuffle)
        tb.addAction(self._act_shuffle)
        self._act_solution = QAction("💡  Lösung zeigen", self)
        self._act_solution.triggered.connect(self._show_solution)
        tb.addAction(self._act_solution)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        self._title_lbl = QLabel("Kein Puzzle geladen")
        self._title_lbl.setStyleSheet("font-weight:bold; font-size:15px;")
        root.addWidget(self._title_lbl)
        self._desc_lbl = QLabel(
            "Öffne eine Puzzle-Datei (📂) – oder erstelle als Lehrkraft eines aus "
            "dem aktuellen Code (🛠)."
        )
        self._desc_lbl.setWordWrap(True)
        root.addWidget(self._desc_lbl)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._make_column("Bausteine", source=True))
        split.addWidget(self._make_column("Dein Programm", source=False))
        split.setSizes([400, 400])
        root.addWidget(split, 1)

        self._status = QLabel("")
        self._status.setStyleSheet("font-weight:bold;")
        root.addWidget(self._status)

        self.setCentralWidget(central)
        self.apply_theme()
        self._set_enabled(False)

    def _make_column(self, title: str, *, source: bool) -> QWidget:
        col = QWidget()
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        v.addWidget(QLabel(title))

        lw = QListWidget()
        lw.setDragEnabled(True)
        lw.setAcceptDrops(True)
        lw.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        lw.setDefaultDropAction(Qt.DropAction.MoveAction)
        lw.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        lw.setFont(QFont(_MONO, 12))
        lw.setSpacing(2)
        v.addWidget(lw, 1)

        if source:
            self._source = lw
        else:
            self._target = lw
            # Einrückungsknöpfe nur im 2D-Modus sichtbar
            row = QHBoxLayout()
            self._dedent_btn = QPushButton("⇤  Ausrücken")
            self._dedent_btn.clicked.connect(lambda: self._indent(-1))
            self._indent_btn = QPushButton("⇥  Einrücken")
            self._indent_btn.clicked.connect(lambda: self._indent(+1))
            row.addWidget(self._dedent_btn)
            row.addWidget(self._indent_btn)
            row.addStretch()
            v.addLayout(row)
        return col

    def _set_enabled(self, on: bool):
        for act in (self._act_check, self._act_shuffle, self._act_solution):
            act.setEnabled(on)

    # ── Puzzle laden / erstellen ────────────────────────────────────────────
    def _open_puzzle_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Puzzle öffnen", str(Path.home()), _FILE_FILTER
        )
        if not path:
            return
        try:
            puzzle = load_puzzle(path)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Puzzle konnte nicht geladen werden:\n{e}")
            return
        if len(puzzle["solution"]) < 2:
            QMessageBox.warning(self, "Puzzle", "Das Puzzle enthält zu wenige Lösungszeilen.")
            return
        self.load(puzzle)

    def _create_puzzle(self):
        code = self._code_provider() if self._code_provider else ""
        if len(code_lines(code)) < 2:
            QMessageBox.warning(
                self, "Aus Code erstellen",
                "Im aktuellen Editor stehen zu wenige Codezeilen. Öffne ein "
                "Programm mit mehreren Zeilen.",
            )
            return
        dlg = PuzzleAuthorDialog(code, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        puzzle = dlg.puzzle()
        path, _ = QFileDialog.getSaveFileName(
            self, "Puzzle speichern", str(Path.home() / f"{puzzle['title']}.json"),
            _FILE_FILTER,
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            save_puzzle(path, puzzle)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Konnte nicht speichern:\n{e}")
            return
        self.load(puzzle)
        self._status.setText(f"Gespeichert: {Path(path).name} – und zum Testen geladen.")

    def load(self, puzzle: dict):
        self._puzzle = puzzle
        self._title_lbl.setText(puzzle["title"])
        self._desc_lbl.setText(
            puzzle["description"]
            or "Ziehe die Bausteine nach rechts und bringe sie in die richtige Reihenfolge."
        )
        indent = puzzle["indent_mode"]
        self._indent_btn.setVisible(indent)
        self._dedent_btn.setVisible(indent)
        self._set_enabled(True)
        self._shuffle()

    # ── Bausteine / Mischen ─────────────────────────────────────────────────
    def _new_item(self, line: str) -> QListWidgetItem:
        it = QListWidgetItem()
        it.setData(_ROLE_CANON, line)
        if self._puzzle["indent_mode"]:
            it.setData(_ROLE_LEVEL, 0)
            it.setText(line.strip())          # flach – Einrückung selbst setzen
        else:
            it.setText(line)                  # mit Original-Einrückung
        return it

    def _shuffle(self):
        if not self._puzzle:
            return
        blocks = list(self._puzzle["solution"]) + list(self._puzzle["distractors"])
        random.shuffle(blocks)
        self._source.clear()
        self._target.clear()
        for line in blocks:
            self._source.addItem(self._new_item(line))
        self._status.setText("")

    # ── Einrückung (2D) ─────────────────────────────────────────────────────
    def _indent(self, delta: int):
        it = self._target.currentItem()
        if it is None or not self._puzzle or not self._puzzle["indent_mode"]:
            return
        level = max(0, int(it.data(_ROLE_LEVEL) or 0) + delta)
        it.setData(_ROLE_LEVEL, level)
        it.setText("    " * level + it.data(_ROLE_CANON).strip())

    # ── Prüfen / Lösung ─────────────────────────────────────────────────────
    def _check(self):
        if not self._puzzle:
            return
        sol = self._puzzle["solution"]
        indent = self._puzzle["indent_mode"]
        items = [self._target.item(i) for i in range(self._target.count())]
        correct = 0
        for i, it in enumerate(items):
            if indent:
                got = (int(it.data(_ROLE_LEVEL) or 0), it.data(_ROLE_CANON).strip())
                want = (_indent_level(sol[i]), sol[i].strip()) if i < len(sol) else None
                ok = got == want
            else:
                ok = i < len(sol) and it.data(_ROLE_CANON) == sol[i]
            self._color(it, ok)
            if ok:
                correct += 1
        n = len(sol)
        if correct == n and len(items) == n:
            self._status.setText(f"🎉  Perfekt – alle {n} Zeilen richtig!")
        else:
            extra = "" if len(items) == n else f" · {len(items)} statt {n} Zeilen rechts"
            self._status.setText(f"{correct} von {n} Zeilen richtig{extra}.")

    def _show_solution(self):
        if not self._puzzle:
            return
        indent = self._puzzle["indent_mode"]
        self._source.clear()
        self._target.clear()
        for line in self._puzzle["solution"]:
            it = self._new_item(line)
            if indent:
                lvl = _indent_level(line)
                it.setData(_ROLE_LEVEL, lvl)
                it.setText("    " * lvl + line.strip())
            self._target.addItem(it)
            self._color(it, True)
        self._status.setText('Lösung – „Neu mischen" für einen neuen Versuch.')

    # ── Einfärben / Theme ─────────────────────────────────────────────────────
    def _color(self, it: QListWidgetItem, ok: bool):
        tint = QColor(THEME["success"] if ok else THEME["error"])
        tint.setAlpha(56)
        it.setBackground(QBrush(tint))
        it.setForeground(QBrush(QColor(THEME["text"])))

    def apply_theme(self):
        t = THEME
        self.setStyleSheet(f"background:{t['bg_dark']}; color:{t['text']};")
        list_style = (
            f"QListWidget {{ background:{t['bg_editor']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:6px; padding:4px; }}"
            f"QListWidget::item {{ padding:4px 6px; }}"
            f"QListWidget::item:selected {{ background:{t['selection']}; color:{t['text']}; }}"
        )
        for lw in (self._source, self._target):
            lw.setStyleSheet(list_style)
        btn = (
            f"QPushButton {{ background:{t['bg_dark']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:4px; padding:3px 10px; }}"
            f"QPushButton:hover {{ background:{t['accent']}; color:#fff; }}"
        )
        for b in (self._indent_btn, self._dedent_btn):
            b.setStyleSheet(btn)
