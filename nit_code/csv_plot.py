"""CSV-Streudiagramm – Tabelle anzeigen und Werte als Streuplot darstellen.

Didaktisches Werkzeug im Stil von Orange Data Mining: eine CSV-Datei wird als
Tabelle gezeigt und gleichzeitig als Streudiagramm geplottet. Zwei numerische
Spalten werden als X-/Y-Achse gewählt; eine beliebige Spalte kann als
*kategoriale Variable* dienen – die Punkte werden dann je Kategorie eingefärbt
(mit Legende).

Bewusst ohne externe Abhängigkeiten (kein pandas/matplotlib): Einlesen mit dem
stdlib-Modul ``csv`` (inkl. Erkennung von ``;``/``,`` und deutschem
Dezimalkomma), Zeichnen mit einem eigenen QPainter-Canvas – analog zu
``serial_plot.py`` und schlank im PyInstaller-Bundle.
"""
import csv

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow, QSplitter, QTableWidget,
    QTableWidgetItem, QToolBar, QVBoxLayout, QWidget,
)

from .config import THEME

# Gut unterscheidbare Farbpalette für die Kategorien (wie im Serial-Plotter).
_CAT_COLORS = [
    "#3b82f6", "#ef4444", "#22c55e", "#f59e0b",
    "#a855f7", "#06b6d4", "#ec4899", "#84cc16",
    "#eab308", "#14b8a6", "#f43f5e", "#8b5cf6",
]
_NO_CATEGORY = "— keine —"
_MAX_POINTS = 20000        # Schutz vor zu vielen Punkten (Performance)


def _to_float(s: str):
    """Wandelt eine Zelle in eine Zahl um – oder None.

    Erkennt auch deutsches Format (Tausenderpunkt + Dezimalkomma): „1.234,56".
    """
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    if "," in s:                       # deutsches Dezimalkomma
        try:
            return float(s.replace(".", "").replace(",", "."))
        except ValueError:
            return None
    return None


def read_csv(path: str):
    """Liest eine CSV-Datei → (headers, rows). Erkennt Trennzeichen automatisch."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        except csv.Error:
            class _D(csv.excel):
                delimiter = ";" if sample.count(";") >= sample.count(",") else ","
            dialect = _D
        rows = [r for r in csv.reader(f, dialect) if any(c.strip() for c in r)]

    if not rows:
        return [], []

    first = rows[0]
    # Kopfzeile annehmen, wenn die erste Zeile nicht rein numerisch ist.
    if all(_to_float(c) is not None for c in first):
        headers = [f"Spalte {i + 1}" for i in range(len(first))]
        data = rows
    else:
        headers = [h.strip() or f"Spalte {i + 1}" for i, h in enumerate(first)]
        data = rows[1:]
    # Auf gleiche Spaltenzahl normalisieren.
    width = len(headers)
    data = [(r + [""] * width)[:width] for r in data]
    return headers, data


def numeric_columns(headers, rows) -> list[int]:
    """Indizes der Spalten, die überwiegend (≥60 %) numerisch sind."""
    result = []
    for c in range(len(headers)):
        cells = [r[c] for r in rows if r[c].strip()]
        if not cells:
            continue
        num = sum(1 for v in cells if _to_float(v) is not None)
        if num >= 0.6 * len(cells):
            result.append(c)
    return result


class _ScatterCanvas(QWidget):
    """Zeichenfläche für das Streudiagramm (Achsen, Gitter, Punkte, Legende)."""

    def __init__(self, window: "CsvPlotWindow", parent=None):
        super().__init__(parent)
        self._win = window
        self.setMinimumHeight(220)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(THEME["terminal_bg"]))

        win = self._win
        xc, yc, catc = win.x_col, win.y_col, win.cat_col
        if xc is None or yc is None:
            self._center_text(p, "Bitte zwei numerische Spalten für X und Y wählen.")
            return

        # Punkte sammeln: (x, y, kategorie)
        pts = []
        for r in win.rows:
            x = _to_float(r[xc])
            y = _to_float(r[yc])
            if x is None or y is None:
                continue
            cat = r[catc].strip() if catc is not None else None
            pts.append((x, y, cat))
            if len(pts) >= _MAX_POINTS:
                break
        if not pts:
            self._center_text(p, "Keine gültigen Zahlenpaare in den gewählten Spalten.")
            return

        left, right, top, bottom = 56, 14, 14, 34
        pw, ph = w - left - right, h - top - bottom
        if pw <= 10 or ph <= 10:
            return

        xs = [x for x, _, _ in pts]
        ys = [y for _, y, _ in pts]
        xmin, xmax = self._padded(min(xs), max(xs))
        ymin, ymax = self._padded(min(ys), max(ys))
        xspan, yspan = xmax - xmin, ymax - ymin

        def x_at(v): return left + (v - xmin) / xspan * pw
        def y_at(v): return top + ph - (v - ymin) / yspan * ph

        # ── Gitter + Achsenbeschriftung ──
        grid = QPen(QColor(THEME["border"]))
        grid.setWidth(1)
        p.setFont(QFont("sans-serif", 8))
        for i in range(5):
            yv = ymax - yspan * i / 4
            y = top + ph * i / 4
            p.setPen(grid)
            p.drawLine(left, int(y), left + pw, int(y))
            p.setPen(QColor(THEME["text_dim"]))
            p.drawText(2, int(y) + 4, left - 8, 12, Qt.AlignmentFlag.AlignRight, self._fmt(yv))
        for i in range(5):
            xv = xmin + xspan * i / 4
            x = left + pw * i / 4
            p.setPen(grid)
            p.drawLine(int(x), top, int(x), top + ph)
            p.setPen(QColor(THEME["text_dim"]))
            p.drawText(int(x) - 30, top + ph + 4, 60, 12,
                       Qt.AlignmentFlag.AlignHCenter, self._fmt(xv))

        # Achsentitel
        p.setPen(QColor(THEME["text"]))
        p.setFont(QFont("sans-serif", 9, QFont.Weight.Bold))
        p.drawText(left, h - 4, win.headers[xc])
        p.save()
        p.translate(12, top + ph)
        p.rotate(-90)
        p.drawText(0, 0, win.headers[yc])
        p.restore()

        # ── Punkte ──
        cat_color = win.category_color_map()
        p.setClipRect(left, top, pw, ph)
        single = QColor(THEME["accent"])
        for x, y, cat in pts:
            color = cat_color.get(cat, single) if catc is not None else single
            p.setPen(QPen(color.darker(120)))
            p.setBrush(color)
            p.drawEllipse(int(x_at(x)) - 3, int(y_at(y)) - 3, 6, 6)
        p.setClipping(False)

        # ── Legende (nur mit Kategorie) ──
        if catc is not None and cat_color:
            p.setFont(QFont("sans-serif", 9))
            lx, ly = left + 8, top + 6
            for name, color in cat_color.items():
                p.fillRect(lx, ly, 10, 10, color)
                p.setPen(QColor(THEME["text"]))
                p.drawText(lx + 16, ly + 10, name if name else "(leer)")
                ly += 16

    def _center_text(self, p, text):
        p.setPen(QColor(THEME["text_dim"]))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    @staticmethod
    def _padded(lo, hi):
        if lo == hi:
            return lo - 1, hi + 1
        pad = (hi - lo) * 0.06
        return lo - pad, hi + pad

    @staticmethod
    def _fmt(v):
        if abs(v) < 1e6 and v == int(v):
            return str(int(v))
        return f"{v:.2f}"


class CsvPlotWindow(QMainWindow):
    """Fenster: CSV-Tabelle (oben) + Streudiagramm (unten) mit Spaltenauswahl."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NIT CSV-Streudiagramm")
        self.resize(880, 720)
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self.x_col = None
        self.y_col = None
        self.cat_col = None
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        tb = QToolBar("Aktionen")
        tb.setMovable(False)
        self.addToolBar(tb)
        self._act_open = QAction("📂  CSV öffnen …", self)
        self._act_open.triggered.connect(self._choose_file)
        tb.addAction(self._act_open)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(6)

        # Spaltenauswahl
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self._x_combo = QComboBox()
        self._y_combo = QComboBox()
        self._cat_combo = QComboBox()
        for lbl, combo in (("X:", self._x_combo), ("Y:", self._y_combo),
                           ("Kategorie:", self._cat_combo)):
            label = QLabel(lbl)
            label.setStyleSheet(f"color:{THEME['text']};")
            bar.addWidget(label)
            combo.setMinimumWidth(140)
            combo.currentIndexChanged.connect(self._on_selection_changed)
            bar.addWidget(combo)
        bar.addStretch()
        self._info = QLabel("")
        self._info.setStyleSheet(f"color:{THEME['text_dim']};")
        bar.addWidget(self._info)
        root.addLayout(bar)

        split = QSplitter(Qt.Orientation.Vertical)
        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        split.addWidget(self._table)
        self._canvas = _ScatterCanvas(self)
        split.addWidget(self._canvas)
        split.setSizes([260, 420])
        root.addWidget(split, 1)

        self.setCentralWidget(central)
        self.apply_theme()

    # ── Laden ───────────────────────────────────────────────────────────────
    def load_file(self, path: str):
        try:
            headers, rows = read_csv(path)
        except Exception as e:
            self._info.setText(f"Fehler beim Lesen: {e}")
            return
        self.headers, self.rows = headers, rows
        if not headers:
            self._info.setText("Leere oder unlesbare CSV-Datei.")
            self._table.clear()
            return
        self._fill_table()
        self._fill_combos()
        self._info.setText(f"{len(rows)} Zeilen · {len(headers)} Spalten")
        self._canvas.update()

    def _fill_table(self):
        self._table.setColumnCount(len(self.headers))
        self._table.setHorizontalHeaderLabels(self.headers)
        shown = self.rows[:2000]          # Tabelle nicht endlos befüllen
        self._table.setRowCount(len(shown))
        for r, row in enumerate(shown):
            for c, val in enumerate(row):
                self._table.setItem(r, c, QTableWidgetItem(val))
        self._table.resizeColumnsToContents()

    def _fill_combos(self):
        num = numeric_columns(self.headers, self.rows)
        for combo in (self._x_combo, self._y_combo, self._cat_combo):
            combo.blockSignals(True)
            combo.clear()
        for c in num:
            self._x_combo.addItem(self.headers[c], c)
            self._y_combo.addItem(self.headers[c], c)
        self._cat_combo.addItem(_NO_CATEGORY, None)
        for c in range(len(self.headers)):
            self._cat_combo.addItem(self.headers[c], c)
        # Sinnvolle Vorauswahl: erste zwei numerischen Spalten
        if num:
            self._x_combo.setCurrentIndex(0)
            self._y_combo.setCurrentIndex(1 if len(num) > 1 else 0)
        for combo in (self._x_combo, self._y_combo, self._cat_combo):
            combo.blockSignals(False)
        self._sync_selection()

    def _on_selection_changed(self, *_):
        self._sync_selection()
        self._canvas.update()

    def _sync_selection(self):
        self.x_col = self._x_combo.currentData()
        self.y_col = self._y_combo.currentData()
        self.cat_col = self._cat_combo.currentData()

    def category_color_map(self) -> dict:
        """Ordnet jeder vorkommenden Kategorie (in Reihenfolge) eine Farbe zu."""
        if self.cat_col is None:
            return {}
        order = []
        seen = set()
        for r in self.rows:
            v = r[self.cat_col].strip()
            if v not in seen:
                seen.add(v)
                order.append(v)
        return {name: QColor(_CAT_COLORS[i % len(_CAT_COLORS)])
                for i, name in enumerate(order)}

    def _choose_file(self):
        from pathlib import Path
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "CSV-Datei öffnen", str(Path.home()),
            "CSV-Dateien (*.csv *.tsv *.txt);;Alle Dateien (*)"
        )
        if path:
            self.load_file(path)

    # ── Theme ─────────────────────────────────────────────────────────────────
    def apply_theme(self):
        t = THEME
        self.setStyleSheet(f"background:{t['bg_dark']};")
        self._table.setStyleSheet(
            f"QTableWidget {{ background:{t['bg_editor']}; color:{t['text']};"
            f" gridline-color:{t['border']}; border:1px solid {t['border']}; }}"
            f"QHeaderView::section {{ background:{t['bg_panel']}; color:{t['text']};"
            f" border:1px solid {t['border']}; padding:3px; }}"
        )
        combo_style = (
            f"QComboBox {{ background:{t['bg_dark']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:4px; padding:2px 6px;"
            f" combobox-popup:0; }}"
            f"QComboBox QAbstractItemView {{ background:{t['bg_dark']};"
            f" color:{t['text']}; selection-background-color:{t['accent']}; }}"
        )
        for combo in (self._x_combo, self._y_combo, self._cat_combo):
            combo.setStyleSheet(combo_style)
        self._canvas.update()
