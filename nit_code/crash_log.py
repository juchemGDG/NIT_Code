"""Absturzprotokoll: hält fest, wenn NIT_Code unerwartet beendet wird.

Hintergrund: Stürzt ein Programm auf Qt-/C-Ebene ab (Segfault, ``abort``), verschwindet das
Fenster ohne Meldung, und bei der installierten App gibt es kein Terminal, in dem man den
Grund lesen könnte. Dieses Modul schreibt deshalb in eine Datei:

* bei **harten Abstürzen** den Python-Stack aller Threads (``faulthandler``),
* bei **Python-Fehlern**, die NIT_Code abfängt und als Dialog zeigt, die Fehlermeldung,
* je Sitzung eine Kopfzeile (Zeit, Version, System) und beim regulären Beenden ``ENDE``.

Datei: ``<Konfigordner>/nit_code/crash.log`` (Windows ``%APPDATA%``, macOS
``~/Library/Application Support``, Linux ``~/.config``). Sie bleibt klein (Kürzen ab 256 KB).

Beim nächsten Start erkennt :func:`start`, ob die **letzte Sitzung hart abgestürzt** ist
(``faulthandler`` hat eingetragen). Erzwungenes Beenden (SIGTERM, Task-Manager) hinterlässt
keinen solchen Eintrag und löst deshalb keinen Hinweis aus.
"""
from __future__ import annotations

import atexit
import faulthandler
import platform
import time
from pathlib import Path

MAX_BYTES = 256_000        # darüber wird die Datei auf KEEP_BYTES gekürzt
KEEP_BYTES = 100_000
_HEADER = "=== START"
_FATAL_MARKERS = ("Fatal Python error", "Windows fatal exception")

_file = None               # offen halten, solange das Programm läuft (faulthandler braucht es)


def log_path() -> Path:
    from .config import _user_config_dir
    return _user_config_dir() / "crash.log"


def _trim(path: Path) -> None:
    """Hält die Datei klein: nur das Ende behalten, ab dem nächsten Sitzungsbeginn."""
    try:
        if path.stat().st_size <= MAX_BYTES:
            return
        data = path.read_bytes()[-KEEP_BYTES:].decode("utf-8", errors="replace")
        i = data.find(_HEADER)
        path.write_text(data[i:] if i >= 0 else data, encoding="utf-8")
    except OSError:
        pass


def last_session_crashed(path: Path | None = None) -> bool:
    """True, wenn die zuletzt protokollierte Sitzung hart abgestürzt ist."""
    try:
        text = (path or log_path()).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    block = text[text.rfind(_HEADER):] if _HEADER in text else text
    return any(m in block for m in _FATAL_MARKERS)


def start() -> bool:
    """Protokoll einschalten (früh im Start aufrufen). Gibt True zurück, wenn die vorige
    Sitzung hart abgestürzt ist. Ohne schreibbaren Ordner läuft faulthandler wie bisher
    nach stderr – der Start scheitert daran nie."""
    global _file
    crashed = False
    try:
        from .config import APP_VERSION
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _trim(path)
        crashed = last_session_crashed(path)
        _file = open(path, "a", encoding="utf-8", buffering=1)
        _file.write(f"\n{_HEADER} {time.strftime('%Y-%m-%d %H:%M:%S')} · NIT_Code {APP_VERSION} · "
                    f"{platform.platform()} · Python {platform.python_version()} ===\n")
        faulthandler.enable(file=_file, all_threads=True)
        atexit.register(_write_end)
    except (OSError, ImportError):
        _file = None
        try:
            faulthandler.enable()
        except Exception:
            pass
    return crashed


def _write_end() -> None:
    try:
        if _file is not None and not _file.closed:
            _file.write(f"=== ENDE {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            _file.flush()
    except (OSError, ValueError):
        pass


def log_exception(text: str) -> None:
    """Von NIT_Code abgefangenen Python-Fehler (der als Dialog erscheint) mitschreiben."""
    try:
        if _file is not None and not _file.closed:
            _file.write(f"--- Python-Fehler {time.strftime('%H:%M:%S')} ---\n{text.rstrip()}\n")
            _file.flush()
    except (OSError, ValueError):
        pass


def read_tail(max_chars: int = 6000) -> str:
    """Das Ende der Datei (für die Anzeige und für „Fehler melden“)."""
    try:
        text = log_path().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text if len(text) <= max_chars else "… (gekürzt) …\n" + text[-max_chars:]


# ── Oberfläche ────────────────────────────────────────────────────────────────
def show_dialog(parent=None) -> None:
    """Zeigt das Absturzprotokoll mit „Ordner öffnen“ und „Kopieren“."""
    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtGui import QDesktopServices, QFont, QGuiApplication
    from PyQt6.QtWidgets import (
        QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
    )
    dlg = QDialog(parent)
    dlg.setWindowTitle("Absturzprotokoll")
    dlg.resize(760, 520)
    lay = QVBoxLayout(dlg)
    path = log_path()
    info = QLabel(
        "Hier hält NIT_Code fest, wenn es unerwartet beendet wurde oder ein Fehler aufgetreten "
        "ist.\nWenn du einen Absturz melden willst, kopiere den Text und schicke ihn mit.\n"
        f"Datei: {path}")
    info.setWordWrap(True)
    info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lay.addWidget(info)
    box = QPlainTextEdit()
    box.setReadOnly(True)
    box.setFont(QFont("JetBrains Mono, Fira Code, Consolas, monospace", 10))
    box.setPlainText(read_tail(20000) or "(Noch nichts protokolliert – das ist gut.)")
    box.verticalScrollBar().setValue(box.verticalScrollBar().maximum())
    lay.addWidget(box, 1)
    row = QHBoxLayout()
    btn_folder = QPushButton("Ordner öffnen")
    btn_copy = QPushButton("In die Zwischenablage kopieren")
    btn_close = QPushButton("Schließen")
    row.addWidget(btn_folder)
    row.addWidget(btn_copy)
    row.addStretch()
    row.addWidget(btn_close)
    lay.addLayout(row)
    btn_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent))))
    btn_copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(box.toPlainText()))
    btn_close.clicked.connect(dlg.accept)
    dlg.exec()


def announce_previous_crash(parent=None) -> None:
    """Einmaliger Hinweis nach einem harten Absturz der vorigen Sitzung."""
    from PyQt6.QtWidgets import QMessageBox
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("NIT_Code wurde unerwartet beendet")
    box.setText("Beim letzten Mal ist NIT_Code unerwartet beendet worden.")
    box.setInformativeText(
        "Der Grund ist im Absturzprotokoll festgehalten. Wenn du ihn melden möchtest, "
        "öffne es hier und kopiere den Text.\n(Das findest du auch unter Hilfe → Absturzprotokoll.)")
    btn_show = box.addButton("Absturzprotokoll ansehen …", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Später", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is btn_show:
        show_dialog(parent)

