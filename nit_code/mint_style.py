"""Gemeinsamer Look der Werkzeugfenster im Stil von pap.mint-checker.de /
ibd.mint-checker.de: dunkle Seitenleiste mit Karten, heller Arbeitsbereich mit
grauer Kopfleiste, dunkle Knöpfe und ein blauer Hauptknopf.

Bewusst feste Farben (unabhängig vom IDE-Theme), damit die Fenster genauso
aussehen wie die eingebetteten PAP-/IBD-Editoren.
"""
import tempfile
from pathlib import Path

from .icons import _render

C = {
    # Seitenleiste
    "side_bg": "#0f172a", "card": "#1e293b", "card_hover": "#2d3f55",
    "card_border": "#334155", "card_border_hover": "#475569",
    "side_text": "#f8fafc", "side_muted": "#94a3b8",
    # Arbeitsbereich
    "main_bg": "#f8fafc", "plot_bg": "#ffffff", "topbar": "#e2e8f0",
    "topbar_border": "#cbd5e1", "grid": "#e2e8f0", "line": "#cbd5e1",
    "text": "#0f172a", "text_dim": "#64748b",
    # Knöpfe
    "btn": "#334155", "btn_hover": "#475569", "btn_down": "#1e293b",
    "accent": "#2563eb", "accent_hover": "#1d4ed8", "accent_soft": "#eff6ff",
    "ok": "#16a34a", "warn": "#d97706",
}


MONO = '"JetBrains Mono", "Fira Code", "Cascadia Mono", Consolas, "DejaVu Sans Mono", Menlo, "Liberation Mono", monospace'


def _arrow(selector: str, color: str) -> str:
    """Klapp-Pfeil für QComboBox als PNG (Qt-Stylesheets brauchen eine Bilddatei).

    Das Symbol kommt aus icons.py und wird einmalig ins Temp-Verzeichnis gerendert.
    """
    path = Path(tempfile.gettempdir()) / f"nit_chevron_{color.lstrip('#')}.png"
    if not path.exists():
        _render("chevron", color, 12).save(str(path), "PNG")
    url = path.as_posix()
    return (
        f"{selector}::drop-down {{ border:none; width:20px; }}"
        f"{selector}::down-arrow {{ image:url({url}); width:12px; height:12px; }}"
    )


# Zahlenfelder ohne die (im flachen Stil unschönen) Pfeiltasten – Mausrad und
# Tastatur funktionieren weiterhin.
_SPIN_PLAIN = (
    "QAbstractSpinBox::up-button, QAbstractSpinBox::down-button"
    " { width:0; border:none; }"
)


def sidebar_qss(name: str) -> str:
    """Stylesheet für eine Seitenleiste mit ``objectName`` = name."""
    c = C
    return (
        f"#{name} {{ background:{c['side_bg']}; }}"
        f"#{name} QWidget {{ background:transparent; color:{c['side_text']};"
        f" font-family: Helvetica, Arial, sans-serif; }}"
        f"#{name} QLabel#sideTitle {{ font-size:19px; font-weight:bold; }}"
        f"#{name} QLabel#sideSubtitle, #{name} QLabel#sectionLabel,"
        f" #{name} QLabel#muted {{ color:{c['side_muted']}; }}"
        f"#{name} QLabel#sideSubtitle {{ font-size:10px; }}"
        f"#{name} QLabel#sectionLabel {{ font-size:10px; font-weight:bold;"
        f" letter-spacing:0.5px; padding-top:6px; }}"
        f"#{name} QLabel#fieldLabel {{ color:{c['side_muted']}; font-size:11px; }}"
        # Karten (Diagrammtypen, Datei öffnen, Hilfe)
        f"#{name} QPushButton#card {{ background:{c['card']}; color:{c['side_text']};"
        f" border:1px solid {c['card_border']}; border-radius:10px; padding:8px 10px;"
        f" text-align:left; font-size:12px; }}"
        f"#{name} QPushButton#card:hover {{ background:{c['card_hover']};"
        f" border-color:{c['card_border_hover']}; }}"
        f"#{name} QPushButton#card:checked {{ background:{c['card_hover']};"
        f" border:2px solid {c['accent']}; }}"
        f"#{name} QPushButton#helpButton {{ background:{c['card']}; color:{c['side_text']};"
        f" border:1px solid {c['card_border']}; border-radius:8px; padding:10px 12px;"
        f" font-size:13px; font-weight:bold; }}"
        f"#{name} QPushButton#helpButton:hover {{ background:{c['card_hover']};"
        f" border-color:{c['card_border_hover']}; }}"
        # Eingabefelder
        f"#{name} QComboBox, #{name} QDoubleSpinBox, #{name} QSpinBox {{"
        f" background:{c['card']}; color:{c['side_text']}; border:1px solid {c['card_border']};"
        f" border-radius:6px; padding:4px 8px; min-height:18px; combobox-popup:0; }}"
        f"#{name} QComboBox:hover, #{name} QDoubleSpinBox:hover {{"
        f" border-color:{c['card_border_hover']}; }}"
        + _arrow(f"#{name} QComboBox", c["side_muted"]) + _SPIN_PLAIN
        + f"#{name} QComboBox QAbstractItemView {{ background:{c['card']};"
        f" color:{c['side_text']}; selection-background-color:{c['accent']};"
        f" border:1px solid {c['card_border']}; }}"
        f"#{name} QCheckBox {{ spacing:8px; font-size:12px; }}"
        f"#{name} QCheckBox::indicator {{ width:14px; height:14px; border-radius:4px;"
        f" border:1px solid {c['card_border_hover']}; background:{c['card']}; }}"
        f"#{name} QCheckBox::indicator:checked {{ background:{c['accent']};"
        f" border-color:{c['accent']}; }}"
        f"#{name} QScrollBar:vertical {{ background:transparent; width:8px; }}"
        f"#{name} QScrollBar::handle:vertical {{ background:{c['card_border']};"
        f" border-radius:4px; min-height:30px; }}"
        f"#{name} QScrollBar::add-line, #{name} QScrollBar::sub-line {{ height:0; }}"
    )


def main_qss() -> str:
    """Stylesheet für den hellen Arbeitsbereich (Kopfleiste, Knöpfe, Reiter, Tabellen)."""
    c = C
    return (
        f"QWidget#mainArea {{ background:{c['main_bg']}; }}"
        f"QWidget#topbar {{ background:{c['topbar']}; border-bottom:1px solid {c['topbar_border']}; }}"
        # Labels/Reiter gegen das globale IDE-Stylesheet absichern
        f"QWidget#topbar QLabel, QWidget#mainArea QLabel {{ background:transparent; }}"
        f"QTabBar {{ background:transparent; }}"
        f"QLabel#breadcrumb {{ color:{c['text']}; font-size:14px; font-weight:bold; }}"
        f"QLabel#status {{ color:#475569; font-size:11px; }}"
        f"QPushButton#menuButton {{ background:{c['btn']}; color:#f8fafc; border:none;"
        f" border-radius:6px; padding:7px 12px; font-size:12px; }}"
        f"QPushButton#menuButton:hover {{ background:{c['btn_hover']}; }}"
        f"QPushButton#menuButton:pressed {{ background:{c['btn_down']}; }}"
        f"QPushButton#accentButton {{ background:{c['accent']}; color:#fff; border:none;"
        f" border-radius:6px; padding:7px 12px; font-size:12px; font-weight:bold; }}"
        f"QPushButton#accentButton:hover {{ background:{c['accent_hover']}; }}"
        f"QTabWidget::pane {{ border:1px solid {c['topbar_border']}; border-radius:8px;"
        f" background:{c['plot_bg']}; top:-1px; }}"
        f"QTabBar::tab {{ background:transparent; color:{c['text_dim']}; padding:6px 14px;"
        f" border:none; border-bottom:2px solid transparent; font-size:12px; }}"
        f"QTabBar::tab:selected {{ color:{c['text']}; font-weight:bold;"
        f" border-bottom:2px solid {c['accent']}; }}"
        f"QTabBar::tab:hover {{ color:{c['text']}; }}"
        f"QTableWidget {{ background:{c['plot_bg']}; color:{c['text']}; border:none;"
        f" gridline-color:{c['grid']}; selection-background-color:{c['accent_soft']};"
        f" selection-color:{c['text']}; }}"
        f"QHeaderView::section {{ background:{c['main_bg']}; color:{c['text_dim']};"
        f" border:none; border-bottom:1px solid {c['topbar_border']};"
        f" border-right:1px solid {c['grid']}; padding:4px 6px; font-weight:bold; }}"
        f"QTableCornerButton::section {{ background:{c['main_bg']}; border:none; }}"
        f"QTextBrowser {{ background:{c['plot_bg']}; color:{c['text']}; border:none; }}"
        f"QLabel#caption {{ color:{c['text_dim']}; }}"
        f"QSplitter::handle {{ background:{c['main_bg']}; }}"
        # Eingaben im hellen Bereich (Statistik-Tests)
        f"QWidget#mainArea QComboBox, QWidget#mainArea QDoubleSpinBox,"
        f" QWidget#mainArea QSpinBox {{ background:#fff; color:{c['text']};"
        f" border:1px solid {c['topbar_border']}; border-radius:6px; padding:3px 8px;"
        f" combobox-popup:0; }}"
        + _arrow("QWidget#mainArea QComboBox", c["text_dim"])
        + f"QWidget#mainArea QComboBox QAbstractItemView {{ background:#fff; color:{c['text']};"
        f" selection-background-color:{c['accent']}; selection-color:#fff; }}"
        f"QWidget#mainArea QLabel {{ color:{c['text']}; }}"
    )


def dialog_qss() -> str:
    """Helle Dialoge (Python-Code, Hilfe) mit Knöpfen im PAP-Stil."""
    c = C
    return (
        f"QDialog {{ background:{c['main_bg']}; }} QLabel {{ color:{c['text']}; }}"
        f"QPlainTextEdit, QTextBrowser {{ background:#fff; color:{c['text']};"
        f" border:1px solid {c['topbar_border']}; border-radius:8px; padding:6px; }}"
        f"QPlainTextEdit {{ font-family:{MONO}; font-size:12px; }}"
        f"QPushButton {{ background:{c['btn']}; color:#f8fafc; border:none;"
        f" border-radius:6px; padding:7px 14px; font-size:12px; }}"
        f"QPushButton:hover {{ background:{c['btn_hover']}; }}"
        f"QPushButton#accentButton {{ background:{c['accent']}; font-weight:bold; }}"
        f"QPushButton#accentButton:hover {{ background:{c['accent_hover']}; }}"
    )
