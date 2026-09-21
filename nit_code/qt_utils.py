"""Kleine Qt-Hilfsfunktionen, die mehrere Module gemeinsam nutzen."""
import re
import sys
from pathlib import Path

from PyQt6.QtCore import QThread
from PyQt6.QtGui import QIcon, QPixmap


def retain_thread(registry: list, thread: QThread) -> None:
    """Hält eine Referenz auf einen QThread, bis sein ``finished``-Signal feuert.

    Verhindert, dass Python den QThread per GC einsammelt, während er noch
    läuft ('QThread destroyed while still running' → Absturz). Der Thread wird
    sofort in ``registry`` aufgenommen und beim Beenden automatisch entfernt.
    """
    registry.append(thread)
    thread.finished.connect(
        lambda t=thread: registry.remove(t) if t in registry else None
    )


# ──────────────────────────────────────────────────────────────────────────────
# Skalierung der Oberflächenschrift (nicht Editor/Shell/Terminal)
# ──────────────────────────────────────────────────────────────────────────────
UI_FONT_PT_DEFAULT = 10      # entspricht der bisherigen Größe (13 px) → Faktor 1.0
UI_FONT_PT_RANGE = (9, 16)

_ui_scale = 1.0
_FONT_SIZE_PX = re.compile(r"(font-size\s*:\s*)(\d+(?:\.\d+)?)px", re.IGNORECASE)


def ui_scale() -> float:
    return _ui_scale


def scale_px(value: int) -> int:
    """Skaliert eine Pixelangabe (Mindestgrößen ≤ 2 px bleiben, z. B. Trennlinien)."""
    if _ui_scale == 1.0 or value <= 2:
        return value
    return max(1, round(value * _ui_scale))


def scale_css_px(css: str) -> str:
    """Skaliert alle ``font-size: Npx``-Angaben in einem CSS-/HTML-Text."""
    if _ui_scale == 1.0 or "font-size" not in css:
        return css
    return _FONT_SIZE_PX.sub(
        lambda m: f"{m.group(1)}{round(float(m.group(2)) * _ui_scale, 1):g}px", css
    )


def install_ui_scale(pt: int) -> None:
    """Aktiviert die Oberflächen-Skalierung (einmal, vor dem Bauen der Widgets).

    Die Stylesheets im Code nennen ihre Schriftgrößen fest in ``px``. Statt jede
    der vielen Stellen anzufassen, skalieren wir zentral: ``setStyleSheet`` rechnet
    ``font-size``-Angaben um, und feste Widget-Größen (Kopfzeilen, Icon-Buttons)
    wachsen im gleichen Verhältnis mit – so verschiebt sich das Layout nicht.
    """
    global _ui_scale
    lo, hi = UI_FONT_PT_RANGE
    _ui_scale = max(lo, min(hi, int(pt))) / UI_FONT_PT_DEFAULT
    if _ui_scale == 1.0:
        return

    from PyQt6.QtCore import QSize
    from PyQt6.QtWidgets import QApplication, QWidget

    orig_qw_style = QWidget.setStyleSheet
    orig_app_style = QApplication.setStyleSheet
    orig_fixed_w = QWidget.setFixedWidth
    orig_fixed_h = QWidget.setFixedHeight
    orig_fixed_size = QWidget.setFixedSize

    QWidget.setStyleSheet = lambda self, css: orig_qw_style(self, scale_css_px(css))
    QApplication.setStyleSheet = lambda self, css: orig_app_style(self, scale_css_px(css))
    QWidget.setFixedWidth = lambda self, w: orig_fixed_w(self, scale_px(w))
    QWidget.setFixedHeight = lambda self, h: orig_fixed_h(self, scale_px(h))

    def _fixed_size(self, *args):
        if len(args) == 2:
            return orig_fixed_size(self, scale_px(args[0]), scale_px(args[1]))
        size = args[0]
        return orig_fixed_size(self, QSize(scale_px(size.width()), scale_px(size.height())))

    QWidget.setFixedSize = _fixed_size


def find_logo() -> QIcon:
    """Sucht logo.png im Paket- oder Projektordner (Dev- wie Frozen-Modus)."""
    candidates = []
    if getattr(sys, "frozen", False):
        # PyInstaller-Bundle: logo.png liegt neben der EXE in nit_code/
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "nit_code" / "logo.png")
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "nit_code" / "logo.png")
    candidates += [
        Path(__file__).resolve().parent / "logo.png",           # nit_code/logo.png
        Path(__file__).resolve().parent.parent / "logo.png",    # Projektordner/logo.png
    ]
    for p in candidates:
        if p.exists():
            px = QPixmap(str(p))
            if not px.isNull():
                return QIcon(px)
    return QIcon()
