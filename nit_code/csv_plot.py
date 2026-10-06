"""Datenauswertung (CSV) – Tabelle, Diagramme und Kennwerte.

Didaktisches Werkzeug im Stil von Orange Data Mining / numiqo: eine CSV-Datei
wird als Tabelle gezeigt und als Streu-, Linien-, Säulen-, Balkendiagramm,
Histogramm oder Boxplot dargestellt. Eine beliebige Spalte kann als
*kategoriale Variable* dienen – Punkte werden je Kategorie eingefärbt, Säulen
und Boxplots je Kategorie gebildet. Dazu gibt es Reiter mit Kennwerten
(Median, Quartile, Mittelwert …) und einer Häufigkeitstabelle.

Bewusst ohne externe Abhängigkeiten (kein pandas/matplotlib): Einlesen mit dem
stdlib-Modul ``csv`` (inkl. Erkennung von ``;``/``,`` und deutschem
Dezimalkomma), Rechnen in ``csv_stats.py``, Zeichnen mit einem eigenen
QPainter-Canvas – analog zu ``serial_plot.py`` und schlank im
PyInstaller-Bundle.
"""
import csv
import math
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QAction, QColor, QFont, QFontDatabase, QFontMetrics, QKeySequence, QPainter, QPen,
    QPolygonF, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QHBoxLayout, QLabel, QMainWindow, QPlainTextEdit, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QTabWidget, QToolBar, QVBoxLayout, QWidget,
)

from .config import THEME
from .csv_codegen import generate_code
from .stat_tests_panel import StatTestsPanel
from .csv_stats import (
    AGGREGATIONS, STAT_LABELS, aggregate, cumulate, describe, fmt_num,
    histogram_bins, linear_regression, nice_step, regression_text,
    tukey_whiskers,
)

# Gut unterscheidbare Farbpalette für die Kategorien (wie im Serial-Plotter).
_CAT_COLORS = [
    "#3b82f6", "#ef4444", "#22c55e", "#f59e0b",
    "#a855f7", "#06b6d4", "#ec4899", "#84cc16",
    "#eab308", "#14b8a6", "#f43f5e", "#8b5cf6",
]
_NO_CATEGORY = "— keine —"
_COUNT = "— Anzahl —"
_MAX_POINTS = 20000        # Schutz vor zu vielen Punkten (Performance)
_MAX_GROUPS = 60           # höchstens so viele Säulen/Boxplots
_MAX_FREQ_ROWS = 100       # Häufigkeitstabelle nur für überschaubare Werte

SCATTER, LINE, COLUMN, BAR, PIE, HIST, BOX = (
    "Streudiagramm", "Liniendiagramm", "Säulendiagramm", "Balkendiagramm",
    "Kreisdiagramm", "Histogramm", "Boxplot",
)
CHART_TYPES = [SCATTER, LINE, COLUMN, BAR, PIE, HIST, BOX]
GROUP_CHARTS = (COLUMN, BAR, PIE)      # je Kategorie ein Wert


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
    """Liest eine CSV-Datei → (headers, rows, info). Erkennt Trennzeichen automatisch.

    ``info`` = {"delimiter": …, "header": bool} – für den Python-Code-Export.
    """
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

    info = {"delimiter": dialect.delimiter, "header": True}
    if not rows:
        return [], [], info

    first = rows[0]
    # Kopfzeile annehmen, wenn die erste Zeile nicht rein numerisch ist.
    if all(_to_float(c) is not None for c in first):
        headers = [f"Spalte {i + 1}" for i in range(len(first))]
        data = rows
        info["header"] = False
    else:
        headers = [h.strip() or f"Spalte {i + 1}" for i, h in enumerate(first)]
        data = rows[1:]
    # Auf gleiche Spaltenzahl normalisieren.
    width = len(headers)
    data = [(r + [""] * width)[:width] for r in data]
    return headers, data, info


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


def _nice_ticks(lo, hi, count=5, pad=0.0):
    """Achsenbereich auf „schöne“ Werte erweitern → (lo, hi, ticks).

    ``pad`` (Anteil der Spannweite) hält Randpunkte vom Rahmen fern.
    """
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    lo, hi = lo - (hi - lo) * pad, hi + (hi - lo) * pad
    step = nice_step((hi - lo) / count)
    start = math.floor(lo / step + 1e-9) * step
    end = math.ceil(hi / step - 1e-9) * step
    n = round((end - start) / step)
    return start, end, [round(start + i * step, 10) for i in range(n + 1)]


class _PlotCanvas(QWidget):
    """Zeichenfläche für alle Diagrammtypen (Achsen, Gitter, Marken, Legende)."""

    _AXIS_FONT = ("sans-serif", 8)
    _TITLE_FONT = ("sans-serif", 9)

    def __init__(self, window: "CsvPlotWindow", parent=None):
        super().__init__(parent)
        self._win = window
        self.setMinimumHeight(220)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(THEME["terminal_bg"]))
        if not self._win.headers:
            self._center_text(p, "Bitte eine CSV-Datei öffnen.")
            return
        draw = {
            SCATTER: self._draw_xy, LINE: self._draw_xy,
            COLUMN: self._draw_bars, BAR: self._draw_bars, PIE: self._draw_pie,
            HIST: self._draw_hist, BOX: self._draw_box,
        }[self._win.chart_type]
        msg = draw(p)
        if msg:
            self._center_text(p, msg)

    # ── Hilfen ────────────────────────────────────────────────────────────────
    def _center_text(self, p, text):
        p.setPen(QColor(THEME["text_dim"]))
        p.setFont(QFont(*self._TITLE_FONT))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def _area(self, y_labels, bottom=34):
        """Zeichenbereich (left, top, pw, ph) – links Platz für die Y-Beschriftung."""
        fm = QFontMetrics(QFont(*self._AXIS_FONT))
        lw = max((fm.horizontalAdvance(s) for s in y_labels), default=20)
        left, right, top = lw + 28, 14, 14
        pw, ph = self.width() - left - right, self.height() - top - bottom
        if pw <= 20 or ph <= 20:
            return None
        return left, top, pw, ph

    def _grid_y(self, p, area, lo, hi, ticks):
        left, top, pw, ph = area
        p.setFont(QFont(*self._AXIS_FONT))
        for t in ticks:
            y = top + ph - (t - lo) / (hi - lo) * ph
            p.setPen(QPen(QColor(THEME["border"]), 1))
            p.drawLine(QPointF(left, y), QPointF(left + pw, y))
            p.setPen(QColor(THEME["text_dim"]))
            p.drawText(QRectF(18, y - 7, left - 24, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       fmt_num(t))

    def _grid_x(self, p, area, lo, hi, ticks):
        left, top, pw, ph = area
        p.setFont(QFont(*self._AXIS_FONT))
        for t in ticks:
            x = left + (t - lo) / (hi - lo) * pw
            p.setPen(QPen(QColor(THEME["border"]), 1))
            p.drawLine(QPointF(x, top), QPointF(x, top + ph))
            p.setPen(QColor(THEME["text_dim"]))
            p.drawText(QRectF(x - 40, top + ph + 3, 80, 14),
                       Qt.AlignmentFlag.AlignHCenter, fmt_num(t))

    def _titles(self, p, area, x_title, y_title):
        left, top, pw, ph = area
        p.setPen(QColor(THEME["text"]))
        p.setFont(QFont(self._TITLE_FONT[0], self._TITLE_FONT[1], QFont.Weight.Bold))
        if x_title:
            p.drawText(QRectF(left, self.height() - 16, pw, 14),
                       Qt.AlignmentFlag.AlignHCenter, x_title)
        if y_title:
            p.save()
            p.translate(4, top + ph)
            p.rotate(-90)
            p.drawText(QRectF(0, 0, ph, 14), Qt.AlignmentFlag.AlignHCenter, y_title)
            p.restore()

    def _legend(self, p, area, items):
        left, top, _, _ = area
        p.setFont(QFont(*self._TITLE_FONT))
        lx, ly = left + 8, top + 6
        # Halbtransparenter Hintergrund, damit die Legende über Punkten lesbar bleibt.
        fm = QFontMetrics(p.font())
        shown = items[:15]
        width = max(fm.horizontalAdvance(name or "(leer)") for name, _ in shown) + 24
        bg = QColor(THEME["terminal_bg"])
        bg.setAlpha(200)
        p.fillRect(QRectF(lx - 4, ly - 3, width, len(shown) * 16 + 4), bg)
        for name, color in shown:
            p.fillRect(QRectF(lx, ly, 10, 10), color)
            p.setPen(QColor(THEME["text"]))
            p.drawText(QPointF(lx + 16, ly + 10), name if name else "(leer)")
            ly += 16

    def _note(self, p, text):
        p.setPen(QColor(THEME["text_dim"]))
        p.setFont(QFont(*self._AXIS_FONT))
        p.drawText(QRectF(0, 2, self.width() - 16, 14), Qt.AlignmentFlag.AlignRight, text)

    # ── Streu- / Liniendiagramm ───────────────────────────────────────────────
    def _draw_xy(self, p):
        win = self._win
        if win.x_col is None or win.y_col is None:
            return "Bitte zwei numerische Spalten für X und Y wählen."
        pts = win.xy_points()
        if not pts:
            return "Keine gültigen Zahlenpaare in den gewählten Spalten."
        xs = [x for x, _, _ in pts]
        ys = [y for _, y, _ in pts]
        xlo, xhi, xt = _nice_ticks(min(xs), max(xs), pad=0.03)
        ylo, yhi, yt = _nice_ticks(min(ys), max(ys), pad=0.03)
        area = self._area([fmt_num(t) for t in yt])
        if area is None:
            return None
        left, top, pw, ph = area
        self._grid_y(p, area, ylo, yhi, yt)
        self._grid_x(p, area, xlo, xhi, xt)
        self._titles(p, area, win.headers[win.x_col], win.headers[win.y_col])

        def at(x, y):
            return QPointF(left + (x - xlo) / (xhi - xlo) * pw,
                           top + ph - (y - ylo) / (yhi - ylo) * ph)

        cat_color = win.category_color_map()
        single = QColor(THEME["accent"])
        p.setClipRect(QRectF(left, top, pw, ph))
        if win.chart_type == LINE:
            series = {}
            for x, y, cat in pts:
                series.setdefault(cat, []).append((x, y))
            for cat, sp in series.items():
                color = cat_color.get(cat, single)
                p.setPen(QPen(color, 2))
                p.drawPolyline(QPolygonF([at(x, y) for x, y in sorted(sp)]))
        r = 2.5 if win.chart_type == LINE else 3
        for x, y, cat in pts:
            color = cat_color.get(cat, single)
            p.setPen(QPen(color.darker(120)))
            p.setBrush(color)
            p.drawEllipse(at(x, y), r, r)
        legend = list(cat_color.items())
        if win.chart_type == SCATTER and win.regression:
            legend = []
            for cat, (m, b, r2), x0, x1 in win.regression_lines():
                color = cat_color.get(cat, single)
                pen = QPen(color, 2, Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.drawLine(at(x0, m * x0 + b), at(x1, m * x1 + b))
                eq = regression_text(m, b, r2)
                legend.append((f"{cat or '(leer)'}: {eq}" if cat is not None else eq, color))
        p.setClipping(False)
        if legend:
            self._legend(p, area, legend)
        return None

    # ── Säulen- / Balkendiagramm ──────────────────────────────────────────────
    def _draw_bars(self, p):
        win = self._win
        if win.cat_col is None:
            return "Bitte eine Kategorie-Spalte wählen – je Kategorie entsteht eine Säule."
        data = win.bar_data()
        if not data:
            return "Keine gültigen Werte für die gewählten Spalten."
        if len(data) > _MAX_GROUPS:
            data = data[:_MAX_GROUPS]
            self._note(p, f"nur die ersten {_MAX_GROUPS} Kategorien")
        vals = [v for _, v in data]
        lo, hi, ticks = _nice_ticks(min(0, min(vals)), max(0, max(vals)))
        cat_color = win.category_color_map()
        single = QColor(THEME["accent"])
        fm = QFontMetrics(QFont(*self._AXIS_FONT))
        n = len(data)

        if win.chart_type == COLUMN:
            area = self._area([fmt_num(t) for t in ticks])
            if area is None:
                return None
            left, top, pw, ph = area
            self._grid_y(p, area, lo, hi, ticks)
            self._titles(p, area, win.headers[win.cat_col], win.value_title())

            def y_at(v):
                return top + ph - (v - lo) / (hi - lo) * ph

            slot = pw / n
            for i, (name, v) in enumerate(data):
                x0 = left + i * slot
                bw = slot * 0.7
                y0, y1 = sorted((y_at(0), y_at(v)))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(cat_color.get(name, single))
                p.drawRect(QRectF(x0 + (slot - bw) / 2, y0, bw, y1 - y0))
                p.setFont(QFont(*self._AXIS_FONT))
                p.setPen(QColor(THEME["text_dim"]))
                label = fm.elidedText(name or "(leer)", Qt.TextElideMode.ElideRight,
                                      int(slot) - 2)
                p.drawText(QRectF(x0, top + ph + 3, slot, 14),
                           Qt.AlignmentFlag.AlignHCenter, label)
                if slot >= 28:
                    p.setPen(QColor(THEME["text"]))
                    ty = y0 - 14 if v >= 0 else y1
                    p.drawText(QRectF(x0, ty, slot, 14),
                               Qt.AlignmentFlag.AlignHCenter, fmt_num(v, 2))
            return None

        # Balkendiagramm (waagrecht): Kategorien links, Werte unten
        lw = min(160, max(fm.horizontalAdvance(name or "(leer)") for name, _ in data))
        left, right, top, bottom = lw + 14, 40, 14, 34
        pw, ph = self.width() - left - right, self.height() - top - bottom
        if pw <= 20 or ph <= 20:
            return None
        area = (left, top, pw, ph)
        self._grid_x(p, area, lo, hi, ticks)
        self._titles(p, area, win.value_title(), None)

        def x_at(v):
            return left + (v - lo) / (hi - lo) * pw

        slot = ph / n
        for i, (name, v) in enumerate(data):
            y0 = top + i * slot
            bh = slot * 0.7
            x0, x1 = sorted((x_at(0), x_at(v)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(cat_color.get(name, single))
            p.drawRect(QRectF(x0, y0 + (slot - bh) / 2, x1 - x0, bh))
            p.setFont(QFont(*self._AXIS_FONT))
            p.setPen(QColor(THEME["text_dim"]))
            label = fm.elidedText(name or "(leer)", Qt.TextElideMode.ElideRight, lw)
            p.drawText(QRectF(4, y0, left - 10, slot),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)
            if slot >= 14:
                p.setPen(QColor(THEME["text"]))
                p.drawText(QRectF(x1 + 4, y0, 80, slot),
                           Qt.AlignmentFlag.AlignVCenter, fmt_num(v, 2))
        return None

    def _label_box(self, p, cx, bw, slot, s, y_at):
        """Fünf Kennwerte rechts neben dem Kasten, x̄ als Raute im Kasten."""
        p.setFont(QFont(*self._AXIS_FONT))
        p.setPen(QColor(THEME["text"]))
        x = cx + bw / 2 + 6
        width = max(20, slot / 2 - bw / 2 - 8)
        fm = QFontMetrics(p.font())
        last_y = None
        for v, text in _box_label_items(s):
            y = y_at(v)
            if last_y is not None and y - last_y < 12:   # nicht überlappen
                continue
            p.drawText(QRectF(x, y - 7, width, 14), Qt.AlignmentFlag.AlignVCenter,
                       fm.elidedText(text, Qt.TextElideMode.ElideRight, int(width)))
            last_y = y
        # Mittelwert als Raute + Beschriftung links
        ym = y_at(s["mean"])
        p.setBrush(QColor(THEME["text"]))
        p.drawPolygon(QPolygonF([QPointF(cx, ym - 5), QPointF(cx + 5, ym),
                                 QPointF(cx, ym + 5), QPointF(cx - 5, ym)]))
        p.drawText(QRectF(cx - slot / 2 + 2, ym - 7, slot / 2 - bw / 2 - 6, 14),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"x̄ {fmt_num(s['mean'])}")

    # ── Kreisdiagramm ─────────────────────────────────────────────────────────
    def _draw_pie(self, p):
        win = self._win
        if win.cat_col is None:
            return "Bitte eine Kategorie-Spalte wählen – je Kategorie entsteht ein Kreisausschnitt."
        data = [(name, v) for name, v in win.bar_data() if v]
        if not data:
            return "Keine gültigen Werte für die gewählten Spalten."
        if any(v < 0 for _, v in data):
            return "Ein Kreisdiagramm geht nur mit Werten ≥ 0."
        if len(data) > _MAX_GROUPS:
            data = data[:_MAX_GROUPS]
            self._note(p, f"nur die ersten {_MAX_GROUPS} Kategorien")
        total = sum(v for _, v in data)
        cat_color = win.category_color_map()

        # Kreis links, Legende (Name, Wert, Anteil) rechts daneben
        fm = QFontMetrics(QFont(*self._TITLE_FONT))
        legend = [f"{name or '(leer)'}: {fmt_num(v, 2)} ({fmt_num(v / total * 100, 1)} %)"
                  for name, v in data]
        lw = min(260, max(fm.horizontalAdvance(s) for s in legend) + 30)
        d = min(self.width() - lw - 40, self.height() - 40)
        if d < 40:
            return None
        cx0, cy0 = 20, (self.height() - d) / 2
        rect = QRectF(cx0, cy0, d, d)
        start = 90 * 16                       # 12 Uhr, dann im Uhrzeigersinn
        p.setPen(QPen(QColor(THEME["terminal_bg"]), 1.5))
        p.setFont(QFont(self._TITLE_FONT[0], self._TITLE_FONT[1], QFont.Weight.Bold))
        for name, v in data:
            span = -v / total * 360 * 16
            p.setBrush(cat_color.get(name, QColor(THEME["accent"])))
            p.drawPie(rect, int(start), int(round(span)))
            share = v / total
            if share >= 0.05:                 # Prozentangabe nur bei genug Platz
                mid = math.radians((start + span / 2) / 16)
                tx = cx0 + d / 2 + math.cos(mid) * d * 0.33
                ty = cy0 + d / 2 - math.sin(mid) * d * 0.33
                p.setPen(QColor("#ffffff"))
                p.drawText(QRectF(tx - 30, ty - 8, 60, 16), Qt.AlignmentFlag.AlignCenter,
                           f"{fmt_num(share * 100, 1)} %")
                p.setPen(QPen(QColor(THEME["terminal_bg"]), 1.5))
            start += span

        p.setFont(QFont(*self._TITLE_FONT))
        lx = cx0 + d + 24
        ly = max(10, (self.height() - len(data[:20]) * 18) / 2)
        for (name, _), text in list(zip(data, legend))[:20]:
            p.fillRect(QRectF(lx, ly + 2, 10, 10), cat_color.get(name, QColor(THEME["accent"])))
            p.setPen(QColor(THEME["text"]))
            p.drawText(QRectF(lx + 16, ly, self.width() - lx - 20, 16),
                       Qt.AlignmentFlag.AlignVCenter,
                       fm.elidedText(text, Qt.TextElideMode.ElideRight, int(lw)))
            ly += 18
        p.setPen(QColor(THEME["text_dim"]))
        p.drawText(QRectF(lx, 4, self.width() - lx - 8, 16), Qt.AlignmentFlag.AlignLeft,
                   win.value_title())
        return None

    # ── Histogramm ────────────────────────────────────────────────────────────
    def _draw_hist(self, p):
        win = self._win
        if win.y_col is None:
            return "Bitte eine numerische Variable wählen."
        bins = win.hist_bins()
        if not bins:
            return "Keine Zahlenwerte in der gewählten Spalte."
        total = sum(c for _, _, c in bins)
        heights = [c / total if win.hist_relative else c for _, _, c in bins]
        ylo, yhi, yt = _nice_ticks(0, max(heights))
        y_labels = [fmt_num(t * 100, 1) + " %" if win.hist_relative else fmt_num(t)
                    for t in yt]
        area = self._area(y_labels)
        if area is None:
            return None
        left, top, pw, ph = area
        xlo, xhi = bins[0][0], bins[-1][1]
        if len(bins) <= 12:
            xt = [b[0] for b in bins] + [xhi]
        else:
            _, _, xt = _nice_ticks(xlo, xhi, 8)
            xt = [t for t in xt if xlo - 1e-9 <= t <= xhi + 1e-9]
        p.setFont(QFont(*self._AXIS_FONT))
        for t, lab in zip(yt, y_labels):
            y = top + ph - (t - ylo) / (yhi - ylo) * ph
            p.setPen(QPen(QColor(THEME["border"]), 1))
            p.drawLine(QPointF(left, y), QPointF(left + pw, y))
            p.setPen(QColor(THEME["text_dim"]))
            p.drawText(QRectF(18, y - 7, left - 24, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, lab)
        for t in xt:
            x = left + (t - xlo) / (xhi - xlo) * pw
            p.drawText(QRectF(x - 40, top + ph + 3, 80, 14),
                       Qt.AlignmentFlag.AlignHCenter, fmt_num(t))
        self._titles(p, area, win.headers[win.y_col],
                     "relative Häufigkeit" if win.hist_relative else "absolute Häufigkeit")

        color = QColor(THEME["accent"])
        p.setPen(QPen(QColor(THEME["terminal_bg"]), 1))
        p.setBrush(color)
        for (a, b, _), hgt in zip(bins, heights):
            x0 = left + (a - xlo) / (xhi - xlo) * pw
            x1 = left + (b - xlo) / (xhi - xlo) * pw
            y = top + ph - (hgt - ylo) / (yhi - ylo) * ph
            p.drawRect(QRectF(x0, y, x1 - x0, top + ph - y))
        return None

    # ── Boxplot ───────────────────────────────────────────────────────────────
    def _draw_box(self, p):
        win = self._win
        if win.y_col is None:
            return "Bitte eine numerische Variable wählen."
        groups = []
        for name, vals in win.box_groups():
            if not vals:
                continue
            s = describe(vals)
            s["w_lo"], s["w_hi"], s["outliers"] = (
                tukey_whiskers(vals, s["q1"], s["q3"]) if win.outliers
                else (s["min"], s["max"], []))
            groups.append((name, s))
        if not groups:
            return "Keine Zahlenwerte in der gewählten Spalte."
        if len(groups) > _MAX_GROUPS:
            groups = groups[:_MAX_GROUPS]
            self._note(p, f"nur die ersten {_MAX_GROUPS} Gruppen")
        lo, hi, ticks = _nice_ticks(min(s["min"] for _, s in groups),
                                    max(s["max"] for _, s in groups), pad=0.03)
        area = self._area([fmt_num(t) for t in ticks])
        if area is None:
            return None
        left, top, pw, ph = area
        self._grid_y(p, area, lo, hi, ticks)
        x_title = win.headers[win.cat_col] if win.cat_col is not None else None
        self._titles(p, area, x_title, win.headers[win.y_col])

        def y_at(v):
            return top + ph - (v - lo) / (hi - lo) * ph

        cat_color = win.category_color_map()
        single = QColor(THEME["accent"])
        fm = QFontMetrics(QFont(*self._AXIS_FONT))
        slot = pw / len(groups)
        bw = min(slot * 0.5, 90)
        for i, (name, s) in enumerate(groups):
            cx = left + (i + 0.5) * slot
            color = cat_color.get(name, single)
            pen = QPen(color, 2)
            p.setPen(pen)
            # Antennen + Endstriche (bis Min/Max oder nach 1,5·IQR-Regel)
            p.drawLine(QPointF(cx, y_at(s["w_lo"])), QPointF(cx, y_at(s["q1"])))
            p.drawLine(QPointF(cx, y_at(s["q3"])), QPointF(cx, y_at(s["w_hi"])))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for v in s["outliers"]:
                p.drawEllipse(QPointF(cx, y_at(v)), 3.5, 3.5)
            for key in ("w_lo", "w_hi"):
                y = y_at(s[key])
                p.drawLine(QPointF(cx - bw / 4, y), QPointF(cx + bw / 4, y))
            # Kasten q1..q3 mit Median
            fill = QColor(color)
            fill.setAlpha(70)
            p.setBrush(fill)
            y3, y1 = y_at(s["q3"]), y_at(s["q1"])
            p.drawRect(QRectF(cx - bw / 2, y3, bw, y1 - y3))
            p.setPen(QPen(QColor(THEME["text"]), 2.5))
            ym = y_at(s["median"])
            p.drawLine(QPointF(cx - bw / 2, ym), QPointF(cx + bw / 2, ym))
            if win.box_labels:
                self._label_box(p, cx, bw, slot, s, y_at)
            # Beschriftung
            p.setFont(QFont(*self._AXIS_FONT))
            p.setPen(QColor(THEME["text_dim"]))
            label = f"{name or '(leer)'} (n={s['n']})"
            label = fm.elidedText(label, Qt.TextElideMode.ElideRight, int(slot) - 2)
            p.drawText(QRectF(cx - slot / 2, top + ph + 3, slot, 14),
                       Qt.AlignmentFlag.AlignHCenter, label)
        return None


def _box_label_items(s):
    """(Wert, Text) für die Boxplot-Beschriftung, von oben nach unten."""
    items = [(s["w_hi"], f"Max {fmt_num(s['w_hi'])}" if not s["outliers"]
              else f"{fmt_num(s['w_hi'])}"),
             (s["q3"], f"q₃ {fmt_num(s['q3'])}"),
             (s["median"], f"Median {fmt_num(s['median'])}"),
             (s["q1"], f"q₁ {fmt_num(s['q1'])}"),
             (s["w_lo"], f"Min {fmt_num(s['w_lo'])}" if not s["outliers"]
              else f"{fmt_num(s['w_lo'])}")]
    return items


class CsvPlotWindow(QMainWindow):
    """Fenster: Tabelle/Kennwerte/Häufigkeiten (oben) + Diagramm (unten)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NIT Datenauswertung")
        self.resize(960, 760)
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self._path = ""
        self.chart_type = SCATTER
        self.x_col = None
        self.y_col = None
        self.value_col = None          # Säulen/Balken: None = Anzahl
        self.cat_col = None
        self.agg = "Mittelwert"
        self.bin_width = 0.0
        self.hist_relative = False
        self.regression = False
        self.outliers = False
        self.box_labels = False
        self._num_cols: list[int] = []
        self._csv_info = {"delimiter": ";", "header": True}
        self._code_sink = None         # Callback: Code in neuen Editor-Tab
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        tb = QToolBar("Aktionen")
        tb.setMovable(False)
        self.addToolBar(tb)
        self._act_open = QAction("📂  CSV öffnen …", self)
        self._act_open.triggered.connect(self._choose_file)
        tb.addAction(self._act_open)
        self._act_png = QAction("🖼  Diagramm als PNG …", self)
        self._act_png.triggered.connect(self._export_png)
        tb.addAction(self._act_png)
        self._act_code = QAction("🐍  Als Python-Code …", self)
        self._act_code.setToolTip("Zeigt ein Python-Programm (csv + matplotlib), "
                                  "das genau dieses Diagramm zeichnet")
        self._act_code.triggered.connect(self._show_code)
        tb.addAction(self._act_code)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(6)

        # Diagrammtyp + Spaltenauswahl (je nach Typ werden Felder ausgeblendet)
        bar = QHBoxLayout()
        bar.setSpacing(10)
        self._type_combo = QComboBox()
        self._type_combo.addItems(CHART_TYPES)
        self._type_combo.currentIndexChanged.connect(self._on_selection_changed)
        self._x_combo = QComboBox()
        self._y_combo = QComboBox()
        self._value_combo = QComboBox()
        self._agg_combo = QComboBox()
        self._agg_combo.addItems(list(AGGREGATIONS))
        self._cat_combo = QComboBox()
        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(0, 1e9)
        self._width_spin.setDecimals(3)
        self._width_spin.setSpecialValueText("automatisch")
        self._width_spin.setToolTip("Klassenbreite des Histogramms (0 = automatisch)")
        self._width_spin.valueChanged.connect(self._on_selection_changed)
        self._rel_check = QCheckBox("relativ")
        self._rel_check.setToolTip("relative statt absoluter Häufigkeit")
        self._rel_check.toggled.connect(self._on_selection_changed)
        self._reg_check = QCheckBox("Ausgleichsgerade")
        self._reg_check.setToolTip("Lineare Regression (Methode der kleinsten Quadrate) "
                                   "mit Geradengleichung und Bestimmtheitsmaß R²")
        self._reg_check.toggled.connect(self._on_selection_changed)
        self._outlier_check = QCheckBox("Ausreißer (1,5·IQR)")
        self._outlier_check.setToolTip(
            "Antennen höchstens 1,5 Quartilsabstände lang, weiter entfernte Werte "
            "als Kreise – sonst reichen die Antennen bis Minimum/Maximum")
        self._outlier_check.toggled.connect(self._on_selection_changed)
        self._boxlabel_check = QCheckBox("Werte beschriften")
        self._boxlabel_check.setToolTip("Minimum, Quartile, Median, Maximum und "
                                        "Mittelwert x̄ (◆) direkt am Boxplot anzeigen")
        self._boxlabel_check.toggled.connect(self._on_selection_changed)
        for combo in (self._x_combo, self._y_combo, self._value_combo,
                      self._agg_combo, self._cat_combo):
            combo.setMinimumWidth(120)
            combo.currentIndexChanged.connect(self._on_selection_changed)

        self._field(bar, "Diagramm:", self._type_combo)
        self._f_x, _ = self._field(bar, "X:", self._x_combo)
        self._f_y, self._y_label = self._field(bar, "Y:", self._y_combo)
        self._f_value, _ = self._field(bar, "Wert:", self._value_combo)
        self._f_agg, _ = self._field(bar, "als:", self._agg_combo)
        self._f_cat, _ = self._field(bar, "Kategorie:", self._cat_combo)
        self._f_width, _ = self._field(bar, "Klassenbreite:", self._width_spin)
        bar.addWidget(self._rel_check)
        bar.addWidget(self._reg_check)
        bar.addWidget(self._outlier_check)
        bar.addWidget(self._boxlabel_check)
        bar.addStretch()
        root.addLayout(bar)

        split = self._split = QSplitter(Qt.Orientation.Vertical)
        self._tabs = QTabWidget()
        self._table = QTableWidget()
        self._tabs.addTab(self._table, "Tabelle")
        self._stats_caption = QLabel("")
        self._stats_caption.setWordWrap(True)
        self._stats_table = QTableWidget()
        self._tabs.addTab(self._captioned(self._stats_caption, self._stats_table),
                          "Kennwerte")
        self._freq_caption = QLabel("")
        self._freq_table = QTableWidget()
        self._tabs.addTab(self._captioned(self._freq_caption, self._freq_table),
                          "Häufigkeiten")
        self._tests = StatTestsPanel(self)
        self._tabs.addTab(self._tests, "Statistik-Tests")
        for t in (self._table, self._stats_table, self._freq_table):
            t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            t.setSelectionMode(QTableWidget.SelectionMode.ContiguousSelection)
            sc = QShortcut(QKeySequence.StandardKey.Copy, t)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(lambda t=t: self._copy_table(t))
        split.addWidget(self._tabs)
        self._canvas = _PlotCanvas(self)
        split.addWidget(self._canvas)
        split.setSizes([260, 460])
        root.addWidget(split, 1)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(central)
        self.statusBar().setSizeGripEnabled(True)
        self.apply_theme()
        self._update_field_visibility()

    def _on_tab_changed(self, index):
        """Statistik-Tests brauchen mehr Platz für das Ergebnis als die Tabellen."""
        if self._tabs.widget(index) is self._tests:
            top, bottom = self._split.sizes()
            if top < 440 and top + bottom > 600:
                self._split.setSizes([440, top + bottom - 440])

    @staticmethod
    def _field(bar, text, widget):
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        label = QLabel(text)
        lay.addWidget(label)
        lay.addWidget(widget)
        bar.addWidget(box)
        return box, label

    @staticmethod
    def _captioned(caption, table):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        lay.addWidget(caption)
        lay.addWidget(table, 1)
        return box

    def _update_field_visibility(self):
        t = self.chart_type
        self._f_x.setVisible(t in (SCATTER, LINE))
        self._f_y.setVisible(t in (SCATTER, LINE, HIST, BOX))
        self._y_label.setText("Y:" if t in (SCATTER, LINE) else "Variable:")
        self._f_value.setVisible(t in GROUP_CHARTS)
        # Beim Kreisdiagramm sind nur Anteile an einer Summe sinnvoll.
        self._f_agg.setVisible(t in (COLUMN, BAR) and self.value_col is not None)
        self._f_cat.setVisible(t != HIST)
        self._f_width.setVisible(t == HIST)
        self._rel_check.setVisible(t == HIST)
        self._reg_check.setVisible(t == SCATTER)
        self._outlier_check.setVisible(t == BOX)
        self._boxlabel_check.setVisible(t == BOX)

    # ── Laden ───────────────────────────────────────────────────────────────
    def load_file(self, path: str):
        try:
            headers, rows, self._csv_info = read_csv(path)
        except Exception as e:
            self.statusBar().showMessage(f"Fehler beim Lesen: {e}")
            return
        self.headers, self.rows, self._path = headers, rows, path
        if not headers:
            self.statusBar().showMessage("Leere oder unlesbare CSV-Datei.")
            self._fill_table()
            self._fill_combos()
            self._tests.refresh_columns()
            self._refresh()
            return
        self.setWindowTitle(f"NIT Datenauswertung – {Path(path).name}")
        self._fill_table()
        self._fill_combos()
        self._tests.refresh_columns()
        self.statusBar().showMessage(f"{len(rows)} Zeilen · {len(headers)} Spalten")
        self._refresh()

    def _fill_table(self):
        self._table.clear()
        self._table.setColumnCount(len(self.headers))
        self._table.setHorizontalHeaderLabels(self.headers)
        shown = self.rows[:2000]          # Tabelle nicht endlos befüllen
        self._table.setRowCount(len(shown))
        for r, row in enumerate(shown):
            for c, val in enumerate(row):
                self._table.setItem(r, c, QTableWidgetItem(val))
        self._table.resizeColumnsToContents()

    def _fill_combos(self):
        num = self._num_cols = numeric_columns(self.headers, self.rows)
        combos = (self._x_combo, self._y_combo, self._value_combo, self._cat_combo)
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
        for c in num:
            self._x_combo.addItem(self.headers[c], c)
            self._y_combo.addItem(self.headers[c], c)
        self._value_combo.addItem(_COUNT, None)
        for c in num:
            self._value_combo.addItem(self.headers[c], c)
        self._cat_combo.addItem(_NO_CATEGORY, None)
        for c in range(len(self.headers)):
            self._cat_combo.addItem(self.headers[c], c)
        # Sinnvolle Vorauswahl: erste zwei numerischen Spalten
        if num:
            self._x_combo.setCurrentIndex(0)
            self._y_combo.setCurrentIndex(1 if len(num) > 1 else 0)
        for combo in combos:
            combo.blockSignals(False)
        self._sync_selection()

    def _on_selection_changed(self, *_):
        self._sync_selection()
        self._refresh()

    def _sync_selection(self):
        self.chart_type = self._type_combo.currentText()
        self.x_col = self._x_combo.currentData()
        self.y_col = self._y_combo.currentData()
        self.value_col = self._value_combo.currentData()
        self.cat_col = self._cat_combo.currentData()
        self.agg = self._agg_combo.currentText()
        self.bin_width = self._width_spin.value()
        self.hist_relative = self._rel_check.isChecked()
        self.regression = self._reg_check.isChecked()
        self.outliers = self._outlier_check.isChecked()
        self.box_labels = self._boxlabel_check.isChecked()

    def _refresh(self):
        self._update_field_visibility()
        self._fill_stats()
        self._fill_freq()
        self._canvas.update()

    # ── Daten für die Diagramme ────────────────────────────────────────────────
    to_float = staticmethod(_to_float)

    def numeric_column_indices(self) -> list[int]:
        return list(self._num_cols)

    def column_values(self, col) -> list[float]:
        vals = (_to_float(r[col]) for r in self.rows)
        return [v for v in vals if v is not None]

    def category_order(self) -> list[str]:
        """Vorkommende Kategorien – numerisch sortiert, falls alle Zahlen sind."""
        if self.cat_col is None:
            return []
        order, seen = [], set()
        for r in self.rows:
            v = r[self.cat_col].strip()
            if v not in seen:
                seen.add(v)
                order.append(v)
        if order and all(_to_float(v) is not None for v in order):
            order.sort(key=_to_float)
        return order

    def category_color_map(self) -> dict:
        """Ordnet jeder vorkommenden Kategorie (in Reihenfolge) eine Farbe zu."""
        return {name: QColor(_CAT_COLORS[i % len(_CAT_COLORS)])
                for i, name in enumerate(self.category_order())}

    def grouped_values(self, col) -> list[tuple[str, list[float]]]:
        """Zahlenwerte einer Spalte je Kategorie (in Kategorie-Reihenfolge)."""
        groups = {name: [] for name in self.category_order()}
        for r in self.rows:
            v = _to_float(r[col])
            if v is not None:
                groups[r[self.cat_col].strip()].append(v)
        return list(groups.items())

    def xy_points(self):
        pts = []
        for r in self.rows:
            x = _to_float(r[self.x_col])
            y = _to_float(r[self.y_col])
            if x is None or y is None:
                continue
            cat = r[self.cat_col].strip() if self.cat_col is not None else None
            pts.append((x, y, cat))
            if len(pts) >= _MAX_POINTS:
                break
        return pts

    def bar_data(self) -> list[tuple[str, float]]:
        """(Kategorie, Höhe) – Anzahl der Zeilen oder aggregierte Werte."""
        if self.value_col is None:
            counts = {name: 0 for name in self.category_order()}
            for r in self.rows:
                counts[r[self.cat_col].strip()] += 1
            return list(counts.items())
        how = "Summe" if self.chart_type == PIE else self.agg
        out = []
        for name, vals in self.grouped_values(self.value_col):
            v = aggregate(vals, how)
            if v is not None:
                out.append((name, v))
        return out

    def value_title(self) -> str:
        if self.value_col is None:
            return "Anzahl"
        how = "Summe" if self.chart_type == PIE else self.agg
        return f"{how} von {self.headers[self.value_col]}"

    def regression_lines(self):
        """[(kategorie, (m, b, r²), x_min, x_max)] – je Kategorie oder gesamt."""
        groups = {}
        for x, y, cat in self.xy_points():
            groups.setdefault(cat, []).append((x, y))
        out = []
        for cat, pts in groups.items():
            xs = [x for x, _ in pts]
            reg = linear_regression(xs, [y for _, y in pts])
            if reg is not None:
                out.append((cat, reg, min(xs), max(xs)))
        return out

    def hist_bins(self):
        return histogram_bins(self.column_values(self.y_col), self.bin_width)

    def box_groups(self):
        if self.cat_col is None:
            return [(self.headers[self.y_col], self.column_values(self.y_col))]
        return self.grouped_values(self.y_col)

    # ── Kennwerte / Häufigkeiten ──────────────────────────────────────────────
    def _fill_stats(self):
        t = self.chart_type
        columns, caption = [], ""
        if not self.headers:
            pass
        elif t in (SCATTER, LINE):
            columns = [(self.headers[c], self.column_values(c))
                       for c in (self.x_col, self.y_col) if c is not None]
            caption = "Kennwerte der X- und Y-Spalte"
            if t == SCATTER and self.regression:
                lines = [(f"{cat or '(leer)'}: " if cat is not None else "")
                         + regression_text(*reg)
                         for cat, reg, _, _ in self.regression_lines()]
                caption += " · Ausgleichsgerade " + "; ".join(lines or ["–"])
        elif t in GROUP_CHARTS and self.value_col is None:
            caption = "Bei „Anzahl“ gibt es keine Kennwerte – siehe Reiter Häufigkeiten."
        else:
            col = self.value_col if t in GROUP_CHARTS else self.y_col
            if col is not None:
                caption = f"Kennwerte für „{self.headers[col]}“"
                columns = [("Gesamt", self.column_values(col))]
                if self.cat_col is not None and t != HIST:
                    caption += f", gruppiert nach „{self.headers[self.cat_col]}“"
                    columns += [(name or "(leer)", v)
                                for name, v in self.grouped_values(col)[:_MAX_GROUPS]]
        self._stats_caption.setText(caption)
        tab = self._stats_table
        tab.clear()
        tab.setColumnCount(len(columns))
        tab.setRowCount(len(STAT_LABELS) if columns else 0)
        tab.setHorizontalHeaderLabels([name for name, _ in columns])
        tab.setVerticalHeaderLabels([label for _, label in STAT_LABELS])
        for c, (_, vals) in enumerate(columns):
            stats = describe(vals)
            for r, (key, _) in enumerate(STAT_LABELS):
                item = QTableWidgetItem(fmt_num(stats[key]))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                      | Qt.AlignmentFlag.AlignVCenter)
                tab.setItem(r, c, item)
        tab.resizeColumnsToContents()

    def _fill_freq(self):
        t = self.chart_type
        rows, first_header, caption = [], "", ""
        if not self.headers:
            pass
        elif t == HIST and self.y_col is not None:
            bins = self.hist_bins()
            pairs = []
            for i, (a, b, c) in enumerate(bins):
                close = "]" if i == len(bins) - 1 else "["
                pairs.append((f"[{fmt_num(a)}; {fmt_num(b)}{close}", c))
            rows = cumulate(pairs)
            first_header = "Klasse"
            if bins:
                caption = (f"Klassen von „{self.headers[self.y_col]}“, "
                           f"Klassenbreite {fmt_num(bins[0][1] - bins[0][0])}")
        elif self.cat_col is not None:
            counts = {name: 0 for name in self.category_order()}
            for r in self.rows:
                counts[r[self.cat_col].strip()] += 1
            rows = cumulate([(k or "(leer)", v) for k, v in counts.items()])
            first_header = self.headers[self.cat_col]
            caption = f"Häufigkeiten der Kategorie „{first_header}“"
        else:
            col = self.value_col if t in GROUP_CHARTS else self.y_col
            if col is not None:
                counts = {}
                for v in self.column_values(col):
                    counts[v] = counts.get(v, 0) + 1
                first_header = self.headers[col]
                if len(counts) > _MAX_FREQ_ROWS:
                    caption = (f"„{first_header}“ hat {len(counts)} verschiedene Werte – "
                               "für eine Übersicht das Histogramm verwenden.")
                else:
                    rows = cumulate([(fmt_num(k), c) for k, c in sorted(counts.items())])
                    caption = f"Häufigkeiten der Werte von „{first_header}“"
        if len(rows) > _MAX_FREQ_ROWS:
            caption += f" (nur die ersten {_MAX_FREQ_ROWS})"
            rows = rows[:_MAX_FREQ_ROWS]
        self._freq_caption.setText(caption)
        tab = self._freq_table
        tab.clear()
        tab.setColumnCount(4)
        tab.setHorizontalHeaderLabels([first_header or "Wert", "absolute H.",
                                       "relative H.", "kumuliert (rel.)"])
        tab.setRowCount(len(rows))
        for r, (name, a, rel, cum) in enumerate(rows):
            cells = (name, str(a), fmt_num(rel * 100, 1) + " %",
                     fmt_num(cum * 100, 1) + " %")
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                          | Qt.AlignmentFlag.AlignVCenter)
                tab.setItem(r, c, item)
        tab.verticalHeader().setVisible(False)
        tab.resizeColumnsToContents()

    @staticmethod
    def _copy_table(table):
        """Markierte Zellen (oder alles) tabulatorgetrennt in die Zwischenablage."""
        ranges = table.selectedRanges()
        if ranges:
            rg = ranges[0]
            rows = range(rg.topRow(), rg.bottomRow() + 1)
            cols = range(rg.leftColumn(), rg.rightColumn() + 1)
        else:
            rows, cols = range(table.rowCount()), range(table.columnCount())

        def header(h, i):
            item = h(i)
            return item.text() if item else ""

        lines = ["\t".join([""] + [header(table.horizontalHeaderItem, c) for c in cols])]
        for r in rows:
            cells = [table.item(r, c).text() if table.item(r, c) else "" for c in cols]
            lines.append("\t".join([header(table.verticalHeaderItem, r)] + cells))
        QApplication.clipboard().setText("\n".join(lines))

    # ── Python-Code ───────────────────────────────────────────────────────────
    def set_code_sink(self, sink):
        """Callback, der Code in einen neuen Editor-Tab übernimmt (vom Hauptfenster)."""
        self._code_sink = sink

    def code_spec(self) -> dict:
        """Aktuelle Auswahl als Beschreibung für ``csv_codegen.generate_code``."""
        order = self.category_order()
        return {
            "path": self._path, "headers": self.headers,
            "delimiter": self._csv_info["delimiter"], "header": self._csv_info["header"],
            "chart_type": self.chart_type, "x_col": self.x_col, "y_col": self.y_col,
            "value_col": self.value_col, "cat_col": self.cat_col, "agg": self.agg,
            "numeric_categories": bool(order) and all(_to_float(v) is not None
                                                      for v in order),
            "bins": self._bin_edges(),
            "relative": self.hist_relative, "regression": self.regression,
            "outliers": self.outliers,
        }

    def _bin_edges(self) -> list[float]:
        if self.chart_type != HIST or self.y_col is None:
            return []
        bins = self.hist_bins()
        return [a for a, _, _ in bins] + [bins[-1][1]] if bins else []

    def _code_problem(self) -> str | None:
        """Grund, warum (noch) kein Code erzeugt werden kann – oder None."""
        t = self.chart_type
        if not self.headers:
            return "Erst eine CSV-Datei öffnen."
        if t in (SCATTER, LINE) and (self.x_col is None or self.y_col is None):
            return "Bitte zwei numerische Spalten für X und Y wählen."
        if t in GROUP_CHARTS and self.cat_col is None:
            return "Bitte eine Kategorie-Spalte wählen."
        if t in (HIST, BOX) and self.y_col is None:
            return "Bitte eine numerische Variable wählen."
        return None

    def _show_code(self):
        problem = self._code_problem()
        if problem:
            self.statusBar().showMessage(problem)
            return
        code = generate_code(self.code_spec())

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Python-Code: {self.chart_type}")
        dlg.resize(760, 640)
        lay = QVBoxLayout(dlg)
        hint = QLabel("Dieses Programm zeichnet das gleiche Diagramm mit matplotlib. "
                      "Es liest die CSV-Datei Zeile für Zeile ein – probiere aus, "
                      "Spalten, Farben oder Beschriftungen zu ändern!")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        view = QPlainTextEdit(code)
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        lay.addWidget(view, 1)
        buttons = QHBoxLayout()
        buttons.addStretch()
        if self._code_sink is not None:
            to_tab = QPushButton("📝  In neuen Editor-Tab")

            def _to_tab():
                self._code_sink(code)
                dlg.accept()
            to_tab.clicked.connect(_to_tab)
            buttons.addWidget(to_tab)
        copy = QPushButton("📋  Kopieren")
        copy.clicked.connect(lambda: (QApplication.clipboard().setText(code),
                                      copy.setText("✔  Kopiert")))
        buttons.addWidget(copy)
        close = QPushButton("Schließen")
        close.clicked.connect(dlg.reject)
        buttons.addWidget(close)
        lay.addLayout(buttons)
        t = THEME
        dlg.setStyleSheet(
            f"QDialog {{ background:{t['bg_dark']}; }} QLabel {{ color:{t['text']}; }}"
            f"QPlainTextEdit {{ background:{t['bg_editor']}; color:{t['text']};"
            f" border:1px solid {t['border']}; }}"
            f"QPushButton {{ background:{t['bg_panel']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:6px; padding:4px 12px; }}"
            f"QPushButton:hover {{ background:{t['accent']}; color:#fff; }}"
        )
        dlg.exec()

    # ── Dateien ───────────────────────────────────────────────────────────────
    def _choose_file(self):
        start = str(Path(self._path).parent) if self._path else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "CSV-Datei öffnen", start,
            "CSV-Dateien (*.csv *.tsv *.txt);;Alle Dateien (*)"
        )
        if path:
            self.load_file(path)

    def _export_png(self):
        if not self.headers:
            self.statusBar().showMessage("Erst eine CSV-Datei öffnen.")
            return
        src = Path(self._path)
        default = src.with_name(f"{src.stem}_{self.chart_type}.png")
        path, _ = QFileDialog.getSaveFileName(
            self, "Diagramm als PNG speichern", str(default), "PNG-Bild (*.png)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        if self._canvas.grab().save(path, "PNG"):
            self.statusBar().showMessage(f"Gespeichert: {path}")
        else:
            self.statusBar().showMessage(f"Speichern fehlgeschlagen: {path}")

    # ── Theme ─────────────────────────────────────────────────────────────────
    def apply_theme(self):
        t = THEME
        self.setStyleSheet(
            f"QMainWindow, QWidget {{ background:{t['bg_dark']}; color:{t['text']}; }}"
            f"QTableWidget {{ background:{t['bg_editor']}; color:{t['text']};"
            f" gridline-color:{t['border']}; border:1px solid {t['border']};"
            f" selection-background-color:{t['accent']}; }}"
            f"QHeaderView::section {{ background:{t['bg_panel']}; color:{t['text']};"
            f" border:1px solid {t['border']}; padding:3px; }}"
            f"QTableCornerButton::section {{ background:{t['bg_panel']};"
            f" border:1px solid {t['border']}; }}"
            f"QTabWidget::pane {{ border:1px solid {t['border']}; }}"
            f"QTabBar::tab {{ background:{t['bg_panel']}; color:{t['text_dim']};"
            f" border:1px solid {t['border']}; padding:4px 12px; }}"
            f"QTabBar::tab:selected {{ background:{t['bg_editor']}; color:{t['text']}; }}"
            f"QTextBrowser {{ background:{t['bg_editor']}; color:{t['text']};"
            f" border:1px solid {t['border']}; }}"
            f"QComboBox, QDoubleSpinBox, QSpinBox {{ background:{t['bg_dark']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:4px; padding:2px 6px;"
            f" combobox-popup:0; }}"
            f"QComboBox QAbstractItemView {{ background:{t['bg_dark']};"
            f" color:{t['text']}; selection-background-color:{t['accent']}; }}"
            f"QStatusBar {{ color:{t['text_dim']}; }}"
        )
        self._stats_caption.setStyleSheet(f"color:{t['text_dim']};")
        self._freq_caption.setStyleSheet(f"color:{t['text_dim']};")
        self._tests.refresh_theme()
        self._canvas.update()
