"""Stände einer Datei sichern und zurückgehen (Debugging-Landkarte, Schritt „Zurück“).

Bei jedem Programmstart legt NIT_Code einen Stand der Datei an und trägt nach
dem Lauf das Ergebnis ein (✓ ohne Fehler, ✗ mit Meldung, ■ gestoppt). Zusätzlich
kann ein Stand von Hand gemerkt werden (📌, mit Notiz). Daraus ergibt sich
„Zurück zum letzten funktionierenden Stand“ ohne Git.

Gespeichert wird im Benutzerprofil (nicht im Projektordner), damit Netzlaufwerke
und Git-Repositories der SuS sauber bleiben.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_STAENDE = 50

ERGEBNIS_SYMBOL = {"run": "…", "ok": "✓", "error": "✗", "stopped": "■"}


@dataclass
class Stand:
    id: str
    zeit: float
    ergebnis: str = "run"       # run | ok | error | stopped
    gemerkt: bool = False
    notiz: str = ""
    meldung: str = ""           # letzte Zeile der Fehlermeldung
    hash: str = ""

    @property
    def symbol(self) -> str:
        return "📌" if self.gemerkt else ERGEBNIS_SYMBOL.get(self.ergebnis, "?")

    @property
    def funktioniert(self) -> bool:
        return self.gemerkt or self.ergebnis == "ok"

    def label(self) -> str:
        t = time.strftime("%d.%m. %H:%M:%S", time.localtime(self.zeit))
        extra = self.notiz or self.meldung
        return f"{self.symbol}  {t}" + (f"  –  {extra}" if extra else "")


def _default_root() -> Path:
    from .config import _user_config_dir
    return _user_config_dir() / "staende"


class SnapshotStore:
    """Stände je Datei in ``<root>/<hash>_<name>/`` (index.json + Textdateien)."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else _default_root()

    # ── intern ───────────────────────────────────────────────────────────
    def _dir(self, filepath: str) -> Path:
        absp = os.path.abspath(filepath)
        h = hashlib.sha1(absp.encode("utf-8")).hexdigest()[:12]
        name = re.sub(r"[^\w.-]", "_", os.path.basename(absp))[:40]
        return self.root / f"{h}_{name}"

    def _load(self, filepath: str) -> list[Stand]:
        idx = self._dir(filepath) / "index.json"
        try:
            raw = json.loads(idx.read_text(encoding="utf-8"))
            return [Stand(**e) for e in raw]
        except (OSError, ValueError, TypeError):
            return []

    def _save(self, filepath: str, staende: list[Stand]) -> None:
        d = self._dir(filepath)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.json").write_text(
            json.dumps([asdict(s) for s in staende], ensure_ascii=False, indent=1),
            encoding="utf-8")

    def _prune(self, filepath: str, staende: list[Stand]) -> list[Stand]:
        """Älteste ungemerkte Stände über MAX_STAENDE löschen."""
        d = self._dir(filepath)
        while len(staende) > MAX_STAENDE:
            victim = next((s for s in staende if not s.gemerkt), None)
            if victim is None:
                break
            staende.remove(victim)
            try:
                (d / f"{victim.id}.txt").unlink()
            except OSError:
                pass
        return staende

    # ── öffentlich ───────────────────────────────────────────────────────
    def list(self, filepath: str) -> list[Stand]:
        """Alle Stände, neueste zuerst."""
        return list(reversed(self._load(filepath)))

    def read(self, filepath: str, stand_id: str) -> str | None:
        try:
            return (self._dir(filepath) / f"{stand_id}.txt").read_text(encoding="utf-8")
        except OSError:
            return None

    def add(self, filepath: str, text: str, gemerkt: bool = False, notiz: str = "") -> Stand:
        """Neuen Stand anlegen. Bei gleichem Inhalt wie der letzte Stand wird
        kein Duplikat gespeichert, sondern dieser Stand weiterverwendet."""
        staende = self._load(filepath)
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if staende and staende[-1].hash == h:
            last = staende[-1]
            if gemerkt:
                last.gemerkt = True
                last.notiz = notiz or last.notiz
            else:
                last.ergebnis = "run"
                last.meldung = ""
                last.zeit = time.time()
            self._save(filepath, staende)
            return last
        stand = Stand(id=time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}",
                      zeit=time.time(), gemerkt=gemerkt, notiz=notiz, hash=h,
                      ergebnis="ok" if gemerkt else "run")
        d = self._dir(filepath)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{stand.id}.txt").write_text(text, encoding="utf-8")
        staende.append(stand)
        self._save(filepath, self._prune(filepath, staende))
        return stand

    def set_result(self, filepath: str, stand_id: str, ergebnis: str, meldung: str = "") -> None:
        staende = self._load(filepath)
        for s in staende:
            if s.id == stand_id:
                s.ergebnis = ergebnis
                s.meldung = meldung
                self._save(filepath, staende)
                return

    def last_good(self, filepath: str, exclude_hash: str = "") -> Stand | None:
        """Neuester funktionierender Stand (✓ oder 📌), optional ohne den aktuellen Inhalt."""
        for s in self.list(filepath):
            if s.funktioniert and s.hash != exclude_hash:
                return s
        return None

    def previous(self, filepath: str) -> Stand | None:
        """Stand des letzten Laufs (neuester Eintrag)."""
        staende = self._load(filepath)
        return staende[-1] if staende else None


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def change_summary(old: str, new: str) -> list[int]:
    """Zeilennummern (1-basiert, im neuen Text) der geänderten Stellen.
    Jede zusammenhängende Änderung zählt als eine Stelle."""
    sm = difflib.SequenceMatcher(None, old.splitlines(), new.splitlines(), autojunk=False)
    return [j1 + 1 for tag, _i1, _i2, j1, _j2 in sm.get_opcodes() if tag != "equal"]


def diff_html(old: str, new: str, theme: dict) -> str:
    """Vergleich als HTML (Zeilen von „alt“ rot, „neu“ grün)."""
    import html
    lines = difflib.unified_diff(old.splitlines(), new.splitlines(),
                                 "gesicherter Stand", "aktueller Code", lineterm="", n=2)
    out = []
    for ln in lines:
        esc = html.escape(ln) or "&nbsp;"
        if ln.startswith(("+++", "---")):
            out.append(f'<span style="color:{theme["text_dim"]}">{esc}</span>')
        elif ln.startswith("@@"):
            out.append(f'<span style="color:{theme["info"]}">{esc}</span>')
        elif ln.startswith("+"):
            out.append(f'<span style="color:{theme["success"]}">{esc}</span>')
        elif ln.startswith("-"):
            out.append(f'<span style="color:{theme["error"]}">{esc}</span>')
        else:
            out.append(esc)
    if not out:
        out = [f'<span style="color:{theme["text_dim"]}">Kein Unterschied zum aktuellen Code.</span>']
    return ('<pre style="font-family:JetBrains Mono,Consolas,monospace; font-size:11px;">'
            + "<br>".join(out) + "</pre>")


# ──────────────────────────────────────────────────────────────────────────────
# Dialog „Stände anzeigen“
# ──────────────────────────────────────────────────────────────────────────────
def show_snapshot_dialog(parent, store: SnapshotStore, filepath: str, current_text: str) -> str | None:
    """Zeigt die Stände einer Datei mit Vergleich zum aktuellen Code.
    Gibt den wiederherzustellenden Text zurück oder None."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QDialog, QDialogButtonBox, QLabel, QListWidget,
        QListWidgetItem, QPushButton, QSplitter, QTextEdit, QVBoxLayout,
    )
    from .config import THEME

    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Stände – {os.path.basename(filepath)}")
    dlg.resize(900, 520)
    lay = QVBoxLayout(dlg)
    info = QLabel("✓ ohne Fehler beendet · ✗ mit Fehlermeldung · ■ gestoppt · 📌 gemerkt.  "
                  "Rechts: was sich gegenüber dem aktuellen Code unterscheidet.")
    info.setWordWrap(True)
    info.setStyleSheet(f"color:{THEME['text_dim']};")
    lay.addWidget(info)

    split = QSplitter(Qt.Orientation.Horizontal)
    lst = QListWidget()
    view = QTextEdit()
    view.setReadOnly(True)
    split.addWidget(lst)
    split.addWidget(view)
    split.setSizes([330, 570])
    lay.addWidget(split, 1)

    staende = store.list(filepath)
    for s in staende:
        it = QListWidgetItem(s.label())
        it.setData(Qt.ItemDataRole.UserRole, s.id)
        lst.addItem(it)
    if not staende:
        view.setHtml(f'<p style="color:{THEME["text_dim"]}">Noch keine Stände. '
                     "Sie entstehen bei jedem Programmstart oder über „📌 Stand merken“.</p>")

    def on_select():
        it = lst.currentItem()
        if not it:
            return
        old = store.read(filepath, it.data(Qt.ItemDataRole.UserRole)) or ""
        view.setHtml(diff_html(old, current_text, THEME))

    lst.currentItemChanged.connect(lambda *_: on_select())

    chosen: dict[str, str] = {}
    buttons = QDialogButtonBox()
    btn_restore = QPushButton("⏪  Diesen Stand wiederherstellen")
    buttons.addButton(btn_restore, QDialogButtonBox.ButtonRole.AcceptRole)
    buttons.addButton("Schließen", QDialogButtonBox.ButtonRole.RejectRole)
    lay.addWidget(buttons)

    def on_restore():
        it = lst.currentItem()
        if it:
            text = store.read(filepath, it.data(Qt.ItemDataRole.UserRole))
            if text is not None:
                chosen["text"] = text
                dlg.accept()

    btn_restore.clicked.connect(on_restore)
    buttons.rejected.connect(dlg.reject)
    if staende:
        lst.setCurrentRow(0)
    dlg.exec()
    return chosen.get("text")
