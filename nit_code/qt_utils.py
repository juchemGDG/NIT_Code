"""Kleine Qt-Hilfsfunktionen, die mehrere Module gemeinsam nutzen."""
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
