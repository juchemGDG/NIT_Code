"""Vektor-Icons (24×24, Strichstil) für Toolbar und Seitenleiste.

Die Icons werden zur Laufzeit aus SVG-Pfaden in der gewünschten Farbe gerendert,
damit sie zu jedem Theme passen und auf allen Plattformen gleich aussehen
(Emoji-Glyphen fehlen auf manchen Linux-/Schulrechnern).
"""
from __future__ import annotations

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_PATHS: dict[str, str] = {
    # Wiedergabe / Steuerung
    "play":     '<path d="M7 4.5v15l12-7.5z" fill="currentColor"/>',
    "stop":     '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>',
    "refresh":  '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
    "upload":   '<path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M5 20h14"/>',
    "reset":    '<path d="M4 12a8 8 0 1 1 2.3 5.7"/><path d="M4 19v-6h6"/>',
    # Seitenleiste
    "files":    '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "ai":       '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/>'
                '<path d="M18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
    "blocks":   '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/>'
                '<rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><path d="M17 13.5v7M13.5 17h7"/>',
    "plotter":  '<path d="M4 4v16h16"/><path d="M7 15l4-5 3 3 5-6"/>',
    "flow":     '<rect x="7" y="3" width="10" height="4" rx="2"/><path d="M12 7v3"/>'
                '<path d="M12 10l5 4-5 4-5-4z"/><path d="M12 18v3"/>',
    "ibd":      '<rect x="3" y="4" width="7" height="6" rx="1.5"/><rect x="14" y="14" width="7" height="6" rx="1.5"/>'
                '<path d="M10 7h4a3 3 0 0 1 3 3v4"/><path d="M15.5 12.5L17 14l1.5-1.5"/>',
    "stats":    '<path d="M4 4v16h16"/><rect x="7" y="11" width="3" height="6" rx=".5"/>'
                '<rect x="12" y="7" width="3" height="10" rx=".5"/><rect x="17" y="13" width="3" height="4" rx=".5"/>',
    # Datenauswertung: Diagrammtypen + Aktionen
    "chart_scatter": '<path d="M4 4v16h16"/><circle cx="8.5" cy="15" r="1.4"/><circle cx="11.5" cy="10.5" r="1.4"/>'
                     '<circle cx="15" cy="13" r="1.4"/><circle cx="18" cy="7" r="1.4"/>',
    "chart_line":    '<path d="M4 4v16h16"/><path d="M7 16l4-5 3 2.5 5-6.5"/>',
    "chart_column":  '<path d="M4 4v16h16"/><rect x="7" y="11" width="3" height="6" rx=".5"/>'
                     '<rect x="12" y="7" width="3" height="10" rx=".5"/><rect x="17" y="13" width="3" height="4" rx=".5"/>',
    "chart_bar":     '<path d="M4 4v16h16"/><rect x="7" y="6" width="8" height="3" rx=".5"/>'
                     '<rect x="7" y="11" width="12" height="3" rx=".5"/><rect x="7" y="16" width="5" height="1" rx=".5"/>',
    "chart_pie":     '<path d="M11 4a8 8 0 1 0 8 8h-8z"/><path d="M14 2.5a8 8 0 0 1 7 7h-7z"/>',
    "chart_hist":    '<path d="M3 20h18"/><path d="M5 20v-5h4v5M9 20V8h4v12M13 20v-9h4v9M17 20v-3h3v3"/>',
    "chart_box":     '<path d="M12 3v4M12 17v4M9 3h6M9 21h6"/><rect x="7" y="7" width="10" height="10" rx="1"/>'
                     '<path d="M7 12h10"/>',
    "image":    '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10" r="1.5"/>'
                '<path d="M21 16l-5-5-8 8"/>',
    "chevron":  '<path d="M6 9l6 6 6-6"/>',
    "code":     '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M14 5l-4 14"/>',
    "help":'<circle cx="12" cy="12" r="9"/><path d="M9.6 9.3a2.5 2.5 0 1 1 3.6 2.2c-.8.4-1.2 1-1.2 1.8"/><path d="M12 16.8v.2"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3'
                'M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/>',
    "plus":     '<path d="M12 5v14M5 12h14"/>',
}


def make_icon(name: str, color: str = "#0f172a", size: int = 20, disabled_color: str | None = None) -> QIcon:
    """Rendert das Icon ``name`` in ``color``; optional eigene Farbe für „deaktiviert“."""
    icon = QIcon()
    icon.addPixmap(_render(name, color, size), QIcon.Mode.Normal)
    icon.addPixmap(_render(name, disabled_color or color, size, 0.4), QIcon.Mode.Disabled)
    return icon


def _render(name: str, color: str, size: int, opacity: float = 1.0) -> QPixmap:
    body = _PATHS.get(name, "")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'color="{color}">{body.replace("currentColor", color)}</svg>'
    )
    scale = 2   # scharf auf HiDPI-Bildschirmen
    img = QImage(size * scale, size * scale, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setOpacity(opacity)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(p)
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(scale)
    return pm
