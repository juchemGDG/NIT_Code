"""Leichtgewichtiger Werte-Plotter ("Serial Plotter").

Zeichnet Zahlen, die ein laufendes Programm zeilenweise ausgibt, live als Graph –
ideal für Sensorexperimente (Temperatur, Abstand, Helligkeit …) im MicroPython-
oder Python-Modus.

Bewusst ohne externe Abhängigkeit (kein pyqtgraph/numpy): ein eigenes QPainter-
Widget mit Ringpuffer ist für ein paar Serien à einige hundert Punkte völlig
ausreichend und hält das PyInstaller-Bundle schlank.

Eingabe-Konvention (an der Arduino-IDE orientiert):
- Eine Zeile mit nur Zahlen (durch Leerzeichen/Komma/Semikolon getrennt) ergibt
  je Zahl eine Kurve – ``print(temp, feuchte)`` → zwei Kurven.
- ``name:wert`` bzw. ``name=wert`` benennt eine Kurve – ``print(f"temp:{t}")``.
- Zeilen mit gemischtem Text werden ignoriert (erscheinen weiter im Ausgabe-Tab).
"""
import re
from collections import OrderedDict, deque

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from .config import THEME

# Feste, gut unterscheidbare Farbpalette für die Kurven.
_SERIES_COLORS = [
    "#3b82f6", "#ef4444", "#22c55e", "#f59e0b",
    "#a855f7", "#06b6d4", "#ec4899", "#84cc16",
]

_NAMED_RE = re.compile(r"([A-Za-z_]\w*)\s*[:=]\s*(-?\d+(?:\.\d+)?)")
_NUM_RE   = re.compile(r"^-?\d+(?:\.\d+)?$")
_SPLIT_RE = re.compile(r"[\s,;]+")

_MAX_POINTS = 600   # Sichtfenster: nur die letzten N Messwerte je Kurve


def _parse_line(line: str):
    """Wandelt eine Ausgabezeile in ``[(name|None, wert), …]`` um – oder None.

    None bedeutet: keine plot-baren Zahlen (Zeile wird ignoriert).
    """
    line = line.strip()
    if not line:
        return None
    named = _NAMED_RE.findall(line)
    if named:
        return [(n, float(v)) for n, v in named]
    parts = [p for p in _SPLIT_RE.split(line) if p]
    values = []
    for p in parts:
        if _NUM_RE.match(p):
            values.append(float(p))
        else:
            return None   # gemischter Text → ganze Zeile ignorieren
    return [(None, v) for v in values] if values else None


def _fmt(v: float) -> str:
    """Kompakte Achsen-/Legendenbeschriftung."""
    if v == int(v) and abs(v) < 1e6:
        return str(int(v))
    return f"{v:.2f}"


class _PlotCanvas(QWidget):
    """Die eigentliche Zeichenfläche (Achsen, Gitter, Kurven, Legende)."""

    def __init__(self, series: "OrderedDict[str, deque]", parent=None):
        super().__init__(parent)
        self._series = series
        self.setMinimumHeight(140)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(THEME["terminal_bg"]))

        # Plotbereich (Ränder für Achsenbeschriftung).
        left, right, top, bottom = 52, 12, 10, 22
        pw, ph = w - left - right, h - top - bottom
        if pw <= 10 or ph <= 10:
            return

        # Wertebereich über alle Kurven bestimmen.
        all_vals = [v for dq in self._series.values() for v in dq]
        if not all_vals:
            p.setPen(QColor(THEME["text_dim"]))
            p.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "Noch keine Messwerte …\n\nGib im Programm Zahlen aus, z. B.  print(temp, feuchte)",
            )
            return

        ymin, ymax = min(all_vals), max(all_vals)
        if ymin == ymax:        # konstante Werte → Bereich künstlich aufspannen
            ymin, ymax = ymin - 1, ymax + 1
        pad = (ymax - ymin) * 0.08
        ymin, ymax = ymin - pad, ymax + pad
        yspan = ymax - ymin

        def x_at(idx_from_left: int, n: int) -> float:
            dx = pw / max(1, n - 1)
            return left + idx_from_left * dx

        def y_at(val: float) -> float:
            return top + ph - (val - ymin) / yspan * ph

        # Gitter + y-Beschriftung (5 Linien).
        grid_pen = QPen(QColor(THEME["border"]))
        grid_pen.setWidth(1)
        p.setFont(QFont("sans-serif", 8))
        for i in range(5):
            val = ymax - (ymax - ymin) * i / 4
            y = top + ph * i / 4
            p.setPen(grid_pen)
            p.drawLine(left, int(y), left + pw, int(y))
            p.setPen(QColor(THEME["text_dim"]))
            p.drawText(2, int(y) + 4, left - 8, 12,
                       Qt.AlignmentFlag.AlignRight, _fmt(val))

        # Kurven (rechtsbündig: neuester Wert am rechten Rand).
        L = max(len(dq) for dq in self._series.values())
        for ci, (name, dq) in enumerate(self._series.items()):
            color = QColor(_SERIES_COLORS[ci % len(_SERIES_COLORS)])
            pen = QPen(color)
            pen.setWidth(2)
            p.setPen(pen)
            n = len(dq)
            if n == 0:
                continue
            offset = L - n     # ältere/kürzere Serien rechtsbündig ausrichten
            prev = None
            for i, val in enumerate(dq):
                x = x_at(offset + i, L)
                y = y_at(val)
                if prev is not None:
                    p.drawLine(int(prev[0]), int(prev[1]), int(x), int(y))
                prev = (x, y)

        # Legende (oben links) mit aktuellem Wert.
        p.setFont(QFont("sans-serif", 9))
        lx, ly = left + 6, top + 6
        for ci, (name, dq) in enumerate(self._series.items()):
            if not dq:
                continue
            color = QColor(_SERIES_COLORS[ci % len(_SERIES_COLORS)])
            p.fillRect(lx, ly, 10, 10, color)
            p.setPen(QColor(THEME["text"]))
            label = f"{name} = {_fmt(dq[-1])}"
            p.drawText(lx + 16, ly + 10, label)
            ly += 16


class SerialPlot(QWidget):
    """Plotter-Panel: Steuerleiste (Leeren/Pause) + Zeichenfläche."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._series: "OrderedDict[str, deque]" = OrderedDict()
        self._linebuf = ""
        self._paused = False
        self._dirty = False
        self._build_ui()

        # Neuzeichnen entkoppelt von der Datenrate (max. ~20 fps).
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(50)
        self._repaint_timer.timeout.connect(self._maybe_repaint)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 4)
        bar.setSpacing(8)

        self._clear_btn = QPushButton("🧹  Leeren")
        self._clear_btn.clicked.connect(self.clear)
        bar.addWidget(self._clear_btn)

        self._pause_chk = QCheckBox("⏸  Pause")
        self._pause_chk.toggled.connect(self._on_pause)
        bar.addWidget(self._pause_chk)

        bar.addStretch()
        self._hint = QLabel("Zahlen pro Zeile ausgeben – z. B.  print(temp, feuchte)")
        bar.addWidget(self._hint)
        root.addLayout(bar)

        self._canvas = _PlotCanvas(self._series)
        root.addWidget(self._canvas, 1)
        self.refresh_theme()

    # ── Steuerung ───────────────────────────────────────────────────────────
    def _on_pause(self, paused: bool):
        self._paused = paused

    def clear(self):
        """Alle Kurven und Puffer zurücksetzen (z. B. bei Programmstart)."""
        self._series.clear()
        self._linebuf = ""
        self._dirty = False
        self._canvas.update()

    # ── Dateneingabe ──────────────────────────────────────────────────────────
    def feed(self, text: str):
        """Roh-Ausgabe (stdout-Chunk) entgegennehmen und vollständige Zeilen plotten."""
        if self._paused:
            return
        self._linebuf += text
        while "\n" in self._linebuf:
            line, self._linebuf = self._linebuf.split("\n", 1)
            self._consume_line(line)
        # Schutz gegen unbegrenztes Wachstum, falls nie ein Zeilenumbruch kommt.
        if len(self._linebuf) > 4096:
            self._linebuf = self._linebuf[-1024:]
        if self._dirty and not self._repaint_timer.isActive():
            self._repaint_timer.start()

    def _consume_line(self, line: str):
        parsed = _parse_line(line)
        if not parsed:
            return
        for i, (name, val) in enumerate(parsed):
            key = name if name else f"Serie {i + 1}"
            dq = self._series.get(key)
            if dq is None:
                dq = deque(maxlen=_MAX_POINTS)
                self._series[key] = dq
            dq.append(val)
        self._dirty = True

    def _maybe_repaint(self):
        if self._dirty:
            self._dirty = False
            self._canvas.update()
        else:
            self._repaint_timer.stop()

    # ── Theme ─────────────────────────────────────────────────────────────────
    def refresh_theme(self):
        btn_style = (
            f"QPushButton, QCheckBox {{ color:{THEME['text']}; }}"
            f"QPushButton {{ background:{THEME['bg_panel']}; border:1px solid {THEME['border']};"
            f" border-radius:4px; padding:3px 10px; }}"
            f"QPushButton:hover {{ background:{THEME['accent']}; color:#fff; }}"
        )
        self._clear_btn.setStyleSheet(btn_style)
        self._pause_chk.setStyleSheet(f"color:{THEME['text']};")
        self._hint.setStyleSheet(f"color:{THEME['text_dim']}; font-size:11px;")
        self.setStyleSheet(f"background:{THEME['terminal_bg']};")
        self._canvas.update()
