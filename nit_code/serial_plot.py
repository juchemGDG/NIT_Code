"""Leichtgewichtiger Werte-Plotter ("Serial Plotter").

Zeichnet Zahlen, die ein laufendes Programm zeilenweise ausgibt, live als Graph –
ideal für Sensorexperimente (Temperatur, Abstand, Helligkeit …) im MicroPython-
oder Python-Modus.

Bewusst ohne externe Abhängigkeit (kein pyqtgraph/numpy): ein eigenes QPainter-
Widget mit Ringpuffer ist für ein paar Serien à einige hundert Punkte völlig
ausreichend und hält das PyInstaller-Bundle schlank.

Achsen sind konfigurierbar (Standardwerte aus den Einstellungen, live in der
Plotter-Leiste übersteuerbar):
- Hochachse (Y): automatisch (gleitend) ODER feste Grenzen (Min/Max).
- Rechtsachse (X): gleitend (letzte N Werte) ODER fester Indexbereich (Sweep:
  füllt sich von Min bis Max und bleibt dann stehen).

Eingabe-Konvention (an der Arduino-IDE orientiert):
- Eine Zahl pro Zeile → eine Kurve: ``print(temp)``
- Mehrere Zahlen pro Zeile (Leerzeichen/Komma/Semikolon) → mehrere Kurven.
- ``name:wert`` bzw. ``name=wert`` benennt eine Kurve.
- Zeilen mit gemischtem Text werden ignoriert (erscheinen weiter im Ausgabe-Tab).
"""
import re
from collections import OrderedDict

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
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

_SLIDE_WINDOW = 600   # Standard-Sichtfenster im gleitenden Modus (letzte N Werte)
_HARD_CAP     = 50000  # Speichergrenze je Kurve

# Standard-Achsenkonfiguration (wird i. d. R. aus den Einstellungen überschrieben).
DEFAULT_CONFIG = {
    "y_mode": "auto",   # "auto" | "fixed"
    "y_min": 0.0,
    "y_max": 100.0,
    "x_mode": "sliding",  # "sliding" | "sweep"
    "x_min": 0,
    "x_max": 500,
}


def _parse_line(line: str):
    """Wandelt eine Ausgabezeile in ``[(name|None, wert), …]`` um – oder None."""
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


class _Series:
    """Eine Kurve: fortlaufende Werte plus absoluter Index des ersten Werts."""
    __slots__ = ("values", "start")

    def __init__(self):
        self.values: list[float] = []
        self.start = 0          # absoluter Messpunkt-Index von values[0]

    @property
    def next_index(self) -> int:
        return self.start + len(self.values)


class _PlotCanvas(QWidget):
    """Die eigentliche Zeichenfläche (Achsen, Gitter, Kurven, Legende)."""

    def __init__(self, plot: "SerialPlot", parent=None):
        super().__init__(parent)
        self._plot = plot
        self.setMinimumHeight(140)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(THEME["terminal_bg"]))

        left, right, top, bottom = 52, 12, 10, 22
        pw, ph = w - left - right, h - top - bottom
        if pw <= 10 or ph <= 10:
            return

        series = self._plot._series
        has_any = any(s.values for s in series.values())
        if not has_any:
            p.setPen(QColor(THEME["text_dim"]))
            p.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "Noch keine Messwerte …\n\nGib im Programm Zahlen aus, z. B.  print(temp, feuchte)",
            )
            return

        # ── X-Bereich bestimmen ────────────────────────────────────────────
        if self._plot._x_mode == "sweep":
            xL, xR = self._plot._x_min, self._plot._x_max
        else:
            gmax = max((s.next_index - 1 for s in series.values() if s.values), default=0)
            xR = gmax
            xL = max(0, gmax - _SLIDE_WINDOW + 1)
        if xR <= xL:
            xR = xL + 1

        # ── Y-Bereich bestimmen ────────────────────────────────────────────
        if self._plot._y_mode == "fixed":
            ymin, ymax = self._plot._y_min, self._plot._y_max
        else:
            vis = [
                v for s in series.values()
                for i, v in enumerate(s.values)
                if xL <= s.start + i <= xR
            ]
            if vis:
                ymin, ymax = min(vis), max(vis)
                if ymin == ymax:
                    ymin, ymax = ymin - 1, ymax + 1
                pad = (ymax - ymin) * 0.08
                ymin, ymax = ymin - pad, ymax + pad
            else:
                ymin, ymax = 0.0, 1.0
        if ymax <= ymin:
            ymax = ymin + 1
        yspan = ymax - ymin
        xspan = xR - xL

        def x_at(idx: float) -> float:
            return left + (idx - xL) / xspan * pw

        def y_at(val: float) -> float:
            return top + ph - (val - ymin) / yspan * ph

        # ── Gitter + y-Beschriftung ────────────────────────────────────────
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

        # x-Achsenbeschriftung (Start-/Endindex)
        p.setPen(QColor(THEME["text_dim"]))
        p.drawText(left, h - 6, _fmt(xL))
        p.drawText(left + pw - 60, h - 6, 60, 12,
                   Qt.AlignmentFlag.AlignRight, _fmt(xR))

        # ── Kurven (auf den Plotbereich begrenzt) ──────────────────────────
        p.setClipRect(left, top, pw, ph)
        for ci, s in enumerate(series.values()):
            if not s.values:
                continue
            color = QColor(_SERIES_COLORS[ci % len(_SERIES_COLORS)])
            pen = QPen(color)
            pen.setWidth(2)
            p.setPen(pen)
            prev = None
            for i, val in enumerate(s.values):
                idx = s.start + i
                if idx < xL or idx > xR:
                    prev = None   # Lücke außerhalb des Sichtbereichs
                    continue
                x, y = x_at(idx), y_at(val)
                if prev is not None:
                    p.drawLine(int(prev[0]), int(prev[1]), int(x), int(y))
                prev = (x, y)
        p.setClipping(False)

        # ── Legende mit aktuellem Wert ─────────────────────────────────────
        p.setFont(QFont("sans-serif", 9))
        lx, ly = left + 6, top + 6
        for ci, (name, s) in enumerate(series.items()):
            if not s.values:
                continue
            color = QColor(_SERIES_COLORS[ci % len(_SERIES_COLORS)])
            p.fillRect(lx, ly, 10, 10, color)
            p.setPen(QColor(THEME["text"]))
            p.drawText(lx + 16, ly + 10, f"{name} = {_fmt(s.values[-1])}")
            ly += 16


class SerialPlot(QWidget):
    """Plotter-Panel: Steuerleiste (Leeren/Pause/Achsen) + Zeichenfläche."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._series: "OrderedDict[str, _Series]" = OrderedDict()
        self._linebuf = ""
        self._paused = False
        self._dirty = False
        # Achsenkonfiguration (Standard, später per apply_config überschrieben).
        self._y_mode = DEFAULT_CONFIG["y_mode"]
        self._y_min = DEFAULT_CONFIG["y_min"]
        self._y_max = DEFAULT_CONFIG["y_max"]
        self._x_mode = DEFAULT_CONFIG["x_mode"]
        self._x_min = DEFAULT_CONFIG["x_min"]
        self._x_max = DEFAULT_CONFIG["x_max"]
        self._build_ui()

        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(50)   # max. ~20 fps, entkoppelt von der Datenrate
        self._repaint_timer.timeout.connect(self._maybe_repaint)

    # ── UI ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 4)
        bar.setSpacing(6)

        self._clear_btn = QPushButton("🧹  Leeren")
        self._clear_btn.clicked.connect(self.clear)
        bar.addWidget(self._clear_btn)

        self._pause_chk = QCheckBox("⏸  Pause")
        self._pause_chk.toggled.connect(self._on_pause)
        bar.addWidget(self._pause_chk)

        bar.addSpacing(8)

        # Y-Achse (Hochachse)
        self._y_lbl = QLabel("Y:")
        bar.addWidget(self._y_lbl)
        self._y_combo = QComboBox()
        self._y_combo.addItem("Auto", "auto")
        self._y_combo.addItem("Fest", "fixed")
        self._setup_combo(self._y_combo)
        bar.addWidget(self._y_combo)
        self._y_min_spin = self._make_double_spin()
        self._y_max_spin = self._make_double_spin()
        bar.addWidget(self._y_min_spin)
        bar.addWidget(QLabel("…"))
        bar.addWidget(self._y_max_spin)

        bar.addSpacing(8)

        # X-Achse (Rechtsachse)
        self._x_lbl = QLabel("X:")
        bar.addWidget(self._x_lbl)
        self._x_combo = QComboBox()
        self._x_combo.addItem("Gleitend", "sliding")
        self._x_combo.addItem("Sweep", "sweep")
        self._setup_combo(self._x_combo)
        bar.addWidget(self._x_combo)
        self._x_min_spin = self._make_int_spin()
        self._x_max_spin = self._make_int_spin()
        bar.addWidget(self._x_min_spin)
        bar.addWidget(QLabel("…"))
        bar.addWidget(self._x_max_spin)

        bar.addStretch()
        root.addLayout(bar)

        self._canvas = _PlotCanvas(self)
        root.addWidget(self._canvas, 1)

        # Widgets mit Startwerten füllen, dann Signale verbinden.
        self._sync_controls_from_state()
        self._y_combo.currentIndexChanged.connect(self._on_axis_controls_changed)
        self._x_combo.currentIndexChanged.connect(self._on_axis_controls_changed)
        for sp in (self._y_min_spin, self._y_max_spin, self._x_min_spin, self._x_max_spin):
            sp.valueChanged.connect(self._on_axis_controls_changed)
        self.refresh_theme()

    @staticmethod
    def _make_double_spin() -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(-1_000_000_000, 1_000_000_000)
        sp.setDecimals(2)
        sp.setFixedWidth(84)
        sp.setKeyboardTracking(False)
        return sp

    @staticmethod
    def _make_int_spin() -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(0, 100_000_000)
        sp.setFixedWidth(84)
        sp.setKeyboardTracking(False)
        return sp

    @staticmethod
    def _setup_combo(combo: QComboBox):
        """Sorgt für eine ausreichend breite Auswahl und ein lesbares Dropdown."""
        combo.setMinimumWidth(112)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.view().setMinimumWidth(120)

    # ── Konfiguration ─────────────────────────────────────────────────────────
    def apply_config(self, *, y_mode=None, y_min=None, y_max=None,
                     x_mode=None, x_min=None, x_max=None):
        """Achsenkonfiguration übernehmen (z. B. Standardwerte aus den Einstellungen)."""
        if y_mode is not None:
            self._y_mode = y_mode
        if y_min is not None:
            self._y_min = float(y_min)
        if y_max is not None:
            self._y_max = float(y_max)
        if x_mode is not None:
            self._x_mode = x_mode
        if x_min is not None:
            self._x_min = int(x_min)
        if x_max is not None:
            self._x_max = int(x_max)
        self._sync_controls_from_state()
        self._canvas.update()

    def _sync_controls_from_state(self):
        """Steuer-Widgets an den internen Zustand angleichen (ohne Rückkopplung)."""
        widgets = (self._y_combo, self._x_combo, self._y_min_spin,
                   self._y_max_spin, self._x_min_spin, self._x_max_spin)
        for wgt in widgets:
            wgt.blockSignals(True)
        self._y_combo.setCurrentIndex(max(0, self._y_combo.findData(self._y_mode)))
        self._x_combo.setCurrentIndex(max(0, self._x_combo.findData(self._x_mode)))
        self._y_min_spin.setValue(self._y_min)
        self._y_max_spin.setValue(self._y_max)
        self._x_min_spin.setValue(self._x_min)
        self._x_max_spin.setValue(self._x_max)
        for wgt in widgets:
            wgt.blockSignals(False)
        self._update_controls_enabled()

    def _update_controls_enabled(self):
        y_fixed = self._y_mode == "fixed"
        self._y_min_spin.setEnabled(y_fixed)
        self._y_max_spin.setEnabled(y_fixed)
        x_sweep = self._x_mode == "sweep"
        self._x_min_spin.setEnabled(x_sweep)
        self._x_max_spin.setEnabled(x_sweep)

    def _on_axis_controls_changed(self, *_):
        """Live-Übersteuerung über die Plotter-Leiste (nicht persistent)."""
        self._y_mode = self._y_combo.currentData()
        self._x_mode = self._x_combo.currentData()
        self._y_min = self._y_min_spin.value()
        self._y_max = self._y_max_spin.value()
        self._x_min = self._x_min_spin.value()
        self._x_max = self._x_max_spin.value()
        self._update_controls_enabled()
        self._canvas.update()

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
        if len(self._linebuf) > 4096:        # Schutz gegen unbegrenztes Wachstum
            self._linebuf = self._linebuf[-1024:]
        if self._dirty and not self._repaint_timer.isActive():
            self._repaint_timer.start()

    def _consume_line(self, line: str):
        parsed = _parse_line(line)
        if not parsed:
            return
        for i, (name, val) in enumerate(parsed):
            key = name if name else f"Serie {i + 1}"
            self._append_value(key, val)

    def _append_value(self, key: str, val: float):
        s = self._series.get(key)
        if s is None:
            s = _Series()
            self._series[key] = s
        # Im Sweep-Modus nach Erreichen von x_max einfrieren.
        if self._x_mode == "sweep" and s.next_index > self._x_max:
            return
        s.values.append(val)
        if len(s.values) > _HARD_CAP:        # Speicher begrenzen
            drop = len(s.values) - _HARD_CAP
            del s.values[:drop]
            s.start += drop
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
            f"QPushButton {{ background:{THEME['bg_panel']}; color:{THEME['text']};"
            f" border:1px solid {THEME['border']}; border-radius:4px; padding:3px 10px; }}"
            f"QPushButton:hover {{ background:{THEME['accent']}; color:#fff; }}"
        )
        self._clear_btn.setStyleSheet(btn_style)
        ctrl_style = (
            f"QComboBox, QSpinBox, QDoubleSpinBox {{ background:{THEME['bg_dark']};"
            f" color:{THEME['text']}; border:1px solid {THEME['border']};"
            f" border-radius:4px; padding:2px 4px; }}"
            # combobox-popup:0 erzwingt das Qt-eigene Popup (statt eines nativen,"
            # das den Text abschnitt) – so wird die Breite der Einträge respektiert.
            f"QComboBox {{ combobox-popup: 0; }}"
            f"QComboBox QAbstractItemView {{ background:{THEME['bg_dark']};"
            f" color:{THEME['text']}; selection-background-color:{THEME['accent']};"
            f" min-width:120px; }}"
        )
        lbl_style = f"color:{THEME['text']};"
        for c in (self._y_combo, self._x_combo, self._y_min_spin, self._y_max_spin,
                  self._x_min_spin, self._x_max_spin):
            c.setStyleSheet(ctrl_style)
        for lbl in (self._y_lbl, self._x_lbl):
            lbl.setStyleSheet(lbl_style)
        self._pause_chk.setStyleSheet(lbl_style)
        self.setStyleSheet(f"background:{THEME['terminal_bg']};")
        self._canvas.update()
