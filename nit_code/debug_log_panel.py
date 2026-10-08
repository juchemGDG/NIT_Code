"""Fehlerprotokoll als Seitenleiste (Cheatsheet „Fehler finden: Schritt für Schritt“).

Eine Zeile pro Runde, Spalten wie im Heft: Nr., Soll / Ist, Eingrenzen, Vermutung,
Änderung, Ergebnis. Im Panel führen farbige Schrittkarten (2 Beobachten, 3 Eingrenzen,
4 Vermuten, 5 Ändern und testen, 6 Geklappt?) durch die Runde – gleiche Wörter und
Farben wie auf dem Cheatsheet.

Grundsatz: NIT_Code trägt nur Fakten ein (Meldung, Läufe mit Änderungen, Scan-Ergebnis
auf Knopfdruck). Fall, Vermutung und Ergebnis schreiben die SuS selbst.

Gespeichert wird als ``<programm>.fehlerprotokoll.md`` neben dem Programm (Obsidian-
Tabelle). Die Rohdaten stehen als HTML-Kommentar am Dateiende, damit das Protokoll
wieder geladen werden kann; in Obsidian sind sie unsichtbar. Protokolle aus beta.1/2
(Ebene/Karte/Hypothese/Test) werden beim Laden übernommen.
"""
from __future__ import annotations

import html
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSplitter,
    QVBoxLayout, QWidget,
)

from . import debug_guide as guide
from .config import THEME
from .debug_guide import LEVEL_KL10, LEVEL_KL89

_DATA_RE = re.compile(r"<!--\s*nit-fehlerprotokoll\s*(\{.*\})\s*-->", re.S)
_FORMAT_VERSION = 2


@dataclass
class Runde:
    nr: int
    zeit: float = field(default_factory=time.time)
    soll_ist: str = ""
    fall: str = ""            # Fall aus Schritt 3 (code | hardware | wert | nichts)
    eingrenzen: str = ""
    vermutung: str = ""
    aenderung: str = ""
    geklappt: str = ""        # "" | "ja" | "nein"
    ergebnis: str = ""
    laeufe: list = field(default_factory=list)   # [{zeit, ergebnis, aenderung, kp}]


def protocol_path(program_path: str) -> str:
    base, _ = os.path.splitext(program_path)
    return base + ".fehlerprotokoll.md"


def _cell(text: str) -> str:
    return (text or "").strip().replace("|", "\\|").replace("\n", "<br>")


def laeufe_text(r: Runde) -> str:
    parts = []
    for lauf in r.laeufe:
        t = time.strftime("%H:%M", time.localtime(lauf.get("zeit", 0)))
        sym = {"ok": "✓", "error": "✗", "stopped": "■"}.get(lauf.get("ergebnis"), "…")
        extra = [x for x in (lauf.get("aenderung", ""),
                             f"bis K{lauf['kp']}" if lauf.get("kp") else "") if x]
        parts.append(f"{t} {sym}" + (f" ({'; '.join(extra)})" if extra else ""))
    return " · ".join(parts)


def to_markdown(name: str, runden: list[Runde], level: str) -> str:
    out = [f"# Fehlerprotokoll – {name}", "",
           f"*{guide.LEVEL_LABEL.get(level, '')} · eine Zeile pro Runde · "
           f"Stand {time.strftime('%d.%m.%Y %H:%M')}*", "",
           "| " + " | ".join(guide.PROTOCOL_COLUMNS) + " |",
           "|" + "---|" * len(guide.PROTOCOL_COLUMNS)]
    for r in runden:
        label = guide.case_label(r.fall, level) if r.fall else ""
        eingrenzen = "; ".join(x for x in (f"**{label}**" if label else "", _cell(r.eingrenzen)) if x)
        aend = _cell(r.aenderung)
        if r.laeufe:
            aend += ("<br>" if aend else "") + "*Läufe: " + _cell(laeufe_text(r)) + "*"
        sym = {"ja": "✓", "nein": "✗"}.get(r.geklappt, "")
        ergebnis = " ".join(x for x in (sym, _cell(r.ergebnis)) if x)
        out.append(f"| {r.nr} | {_cell(r.soll_ist)} | {eingrenzen} | {_cell(r.vermutung)} | "
                   f"{aend} | {ergebnis} |")
    data = json.dumps({"version": _FORMAT_VERSION, "level": level,
                       "runden": [asdict(r) for r in runden]}, ensure_ascii=False)
    out += ["", f"<!-- nit-fehlerprotokoll {data} -->", ""]
    return "\n".join(out)


def _migrate_v1(e: dict) -> dict:
    """Eintrag aus beta.1/2 (Ebene, Karte, Hypothese, Test, Lösung) → Runde."""
    out = {k: e[k] for k in ("nr", "zeit", "soll_ist", "laeufe") if k in e}
    out["vermutung"] = e.get("hypothese", "")
    out["aenderung"] = e.get("test", "")
    out["eingrenzen"] = " / ".join(x for x in (
        f"Ebene {e['ebene']}" if e.get("ebene") else "", e.get("karte", "")) if x)
    out["ergebnis"] = " – ".join(x for x in (e.get("ergebnis", ""), e.get("loesung", "")) if x)
    return out


def from_markdown(text: str) -> tuple[list[Runde], str | None]:
    m = _DATA_RE.search(text or "")
    if not m:
        return [], None
    try:
        raw = json.loads(m.group(1))
        known = set(Runde.__dataclass_fields__)
        if "runden" in raw:
            items = raw["runden"]
        else:                                   # beta.1/2
            items = [_migrate_v1(e) for e in raw.get("eintraege", [])]
        return ([Runde(**{k: v for k, v in e.items() if k in known}) for e in items],
                raw.get("level"))
    except (ValueError, TypeError):
        return [], None


# ──────────────────────────────────────────────────────────────────────────────
# Schrittkarte
# ──────────────────────────────────────────────────────────────────────────────
class _StepCard(QFrame):
    """Farbiger Block mit Schrittnummer links (wie auf dem Cheatsheet) und Inhalt rechts."""

    def __init__(self, nr: int, parent=None):
        super().__init__(parent)
        self.setObjectName("stepCard")
        self._step = guide.STEP[nr]
        self._leads: list[tuple[QLabel, str, str]] = []
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._badge = QLabel()
        self._badge.setFixedWidth(104)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._badge.setWordWrap(True)
        self._badge.setTextFormat(Qt.TextFormat.RichText)
        title = html.escape(self._step.title)
        self._badge.setText(
            f"<div style='font-size:22px; font-weight:bold; color:{guide.YELLOW}'>{nr}</div>"
            f"<div style='font-weight:bold; font-size:11px'>{title}</div>")
        outer.addWidget(self._badge)
        bodyw = QWidget()
        bodyw.setObjectName("stepBody")
        self.body = QVBoxLayout(bodyw)
        self.body.setContentsMargins(10, 8, 10, 8)
        self.body.setSpacing(5)
        outer.addWidget(bodyw, 1)
        self.apply_theme()

    def add_lead(self, lead: str, detail: str = "") -> QLabel:
        lbl = QLabel()
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        self._leads.append((lbl, lead, detail))
        self.body.addWidget(lbl)
        self._render_lead(lbl, lead, detail)
        return lbl

    @staticmethod
    def _render_lead(lbl: QLabel, lead: str, detail: str):
        text = f"<b>{guide.inline_html(lead)}</b>" if lead else ""
        if detail:
            text += (("<br>" if text else "")
                     + f"<span style='color:{THEME['text_dim']}; font-size:11px'>"
                       f"{guide.inline_html(detail)}</span>")
        lbl.setText(text)

    def apply_theme(self):
        c = self._step.color
        self.setStyleSheet(
            f"QFrame#stepCard {{ border:1px solid {c}; border-radius:8px; "
            f"background:{THEME['bg_panel']}; }}")
        self._badge.setStyleSheet(
            f"background:{c}; color:#ffffff; border:none; "
            f"border-top-left-radius:7px; border-bottom-left-radius:7px; padding:8px 4px 8px 8px;")
        for lbl, lead, detail in self._leads:
            self._render_lead(lbl, lead, detail)


def _amber_label() -> QLabel:
    lbl = QLabel()
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setStyleSheet(f"background:{guide.CREAM}; color:{guide.CREAM_TEXT}; "
                      f"border:1px solid #e0c96a; border-radius:6px; padding:6px 8px;")
    return lbl


# ──────────────────────────────────────────────────────────────────────────────
# Panel
# ──────────────────────────────────────────────────────────────────────────────
class DebugLogPanel(QWidget):
    """Seitliches Panel „📝 Fehlerprotokoll“."""

    close_requested = pyqtSignal()
    restore_requested = pyqtSignal()   # „⏪ Zurück zum letzten funktionierenden Stand“
    pin_requested = pyqtSignal()       # „📌 Stand merken“

    def __init__(self, parent=None):
        super().__init__(parent)
        self._program: str | None = None
        self._runden: list[Runde] = []
        self._level = LEVEL_KL10
        self._loading = False
        self._chips: dict[str, QPushButton] = {}
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self.save)
        self._build_ui()
        self._apply_styles()
        self._update_enabled()

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(36)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 0, 4, 0)
        self._title = QLabel("📝  Fehlerprotokoll")
        hl.addWidget(self._title, 1)
        self._form_combo = QComboBox()
        for lv in guide.LEVELS:
            self._form_combo.addItem(guide.LEVEL_LABEL[lv], lv)
        self._form_combo.currentIndexChanged.connect(
            lambda _i: self.set_level(self._form_combo.currentData()))
        hl.addWidget(self._form_combo)
        close = QPushButton("✕")
        close.setFixedWidth(28)
        close.setToolTip("Schließen")
        close.clicked.connect(self.close_requested.emit)
        hl.addWidget(close)
        lay.addWidget(header)

        split = QSplitter(Qt.Orientation.Vertical)
        lay.addWidget(split, 1)
        self._split = split

        # ── oben: Schritt 0, Liste der Runden ──
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(8, 4, 8, 4)
        tl.setSpacing(6)
        s0 = guide.STEP[0]
        self._banner = QLabel(
            f"<b>SCHRITT 0 · STOPP</b> &nbsp;{html.escape(s0.lead)}<br>"
            f"→ {html.escape(guide.plain(s0.detail))}")
        self._banner.setWordWrap(True)
        self._banner.setTextFormat(Qt.TextFormat.RichText)
        tl.addWidget(self._banner)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        tl.addWidget(self._list, 1)
        row = QHBoxLayout()
        self._btn_new = QPushButton("➕  Neue Runde")
        self._btn_new.clicked.connect(lambda: self.new_round())
        self._btn_del = QPushButton("Löschen")
        self._btn_del.setToolTip("Runde löschen")
        self._btn_del.clicked.connect(self._delete)
        self._btn_export = QPushButton("PDF …")
        self._btn_export.setToolTip("Protokoll als PDF speichern (zur Abgabe)")
        self._btn_export.clicked.connect(self._export_pdf)
        row.addWidget(self._btn_new)
        row.addWidget(self._btn_del)
        row.addStretch()
        row.addWidget(self._btn_export)
        tl.addLayout(row)
        self._three = _amber_label()
        self._three.setText(f"⚠ <b>{html.escape(guide.STEP6_NOTE)}</b>")
        tl.addWidget(self._three)
        self._file_lbl = QLabel("")
        self._file_lbl.setWordWrap(True)
        tl.addWidget(self._file_lbl)
        self._empty_hint = QLabel("")
        self._empty_hint.setWordWrap(True)
        tl.addWidget(self._empty_hint)
        split.addWidget(top)

        # ── unten: Schrittkarten der geöffneten Runde ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._form_scroll = scroll   # nur sichtbar, solange eine Runde geöffnet ist
        cards_w = QWidget()
        cl = QVBoxLayout(cards_w)
        cl.setContentsMargins(8, 6, 8, 8)
        cl.setSpacing(8)
        self._cards: list[_StepCard] = []

        def text_field(h: int) -> QPlainTextEdit:
            w = QPlainTextEdit()
            w.setFixedHeight(h)
            w.setTabChangesFocus(True)
            w.textChanged.connect(self._on_edit)
            return w

        # 2 Beobachten
        c2 = self._card(2, cl)
        c2.add_lead(guide.STEP[2].lead, guide.STEP[2].detail)
        self._f_soll = text_field(62)
        self._f_soll.setPlaceholderText("Soll: …\nIst: …  (Meldung wörtlich, mit Zeilennummer)")
        c2.body.addWidget(self._f_soll)

        # 3 Eingrenzen
        c3 = self._card(3, cl)
        c3.add_lead(guide.STEP[3].lead)
        chips_w = QWidget()
        self._chip_grid = QGridLayout(chips_w)
        self._chip_grid.setContentsMargins(0, 0, 0, 0)
        self._chip_grid.setSpacing(5)
        c3.body.addWidget(chips_w)
        self._case_box = _amber_label()
        c3.body.addWidget(self._case_box)
        self._f_eingr = text_field(62)
        c3.body.addWidget(self._f_eingr)

        # 4 Vermuten
        c4 = self._card(4, cl)
        c4.add_lead(guide.STEP[4].lead, guide.STEP[4].detail)
        self._f_verm = text_field(62)
        self._f_verm.setPlaceholderText("Ich vermute …, weil …")
        c4.body.addWidget(self._f_verm)
        self._weil_hint = QLabel("")
        self._weil_hint.setWordWrap(True)
        c4.body.addWidget(self._weil_hint)

        # 5 Ändern und testen
        c5 = self._card(5, cl)
        c5.add_lead(guide.STEP[5].lead, guide.STEP[5].detail)
        self._f_aend = text_field(54)
        self._f_aend.setPlaceholderText("Genau eine Änderung, z. B. „Zeile 6: address=0x77“")
        c5.body.addWidget(self._f_aend)
        self._facts = QLabel("")
        self._facts.setWordWrap(True)
        self._facts.setTextFormat(Qt.TextFormat.RichText)
        c5.body.addWidget(self._facts)
        r5 = QHBoxLayout()
        self._btn_pin = QPushButton("📌  Stand merken")
        self._btn_pin.setToolTip("Eine Kopie vor der Änderung – NIT_Code sichert aber auch "
                                 "bei jedem Start automatisch einen Stand")
        self._btn_pin.clicked.connect(self.pin_requested.emit)
        r5.addWidget(self._btn_pin)
        r5.addStretch()
        c5.body.addLayout(r5)

        # 6 Geklappt?
        c6 = self._card(6, cl)
        self._c6 = c6
        r6 = QHBoxLayout()
        self._btn_ja = QPushButton("✓  Ja")
        self._btn_nein = QPushButton("✗  Nein")
        for b in (self._btn_ja, self._btn_nein):
            b.setCheckable(True)
        self._btn_ja.toggled.connect(lambda on: self._on_result_btn("ja", on))
        self._btn_nein.toggled.connect(lambda on: self._on_result_btn("nein", on))
        r6.addWidget(self._btn_ja)
        r6.addWidget(self._btn_nein)
        r6.addStretch()
        c6.body.addLayout(r6)
        self._res_hint = QLabel("")
        self._res_hint.setWordWrap(True)
        self._res_hint.setTextFormat(Qt.TextFormat.RichText)
        c6.body.addWidget(self._res_hint)
        self._f_erg = text_field(50)
        self._f_erg.setPlaceholderText("Ergebnis, z. B. „blinkt im Sekundentakt“")
        c6.body.addWidget(self._f_erg)
        self._nein_row = QWidget()
        nr = QVBoxLayout(self._nein_row)
        nr.setContentsMargins(0, 0, 0, 0)
        nr.setSpacing(4)
        btn_back = QPushButton("⏪  Letzter funktionierender Stand")
        btn_back.setToolTip("Zurück zum letzten funktionierenden Stand: Änderung rückgängig machen")
        btn_back.clicked.connect(self.restore_requested.emit)
        btn_next = QPushButton("➕  Nächste Runde (weiter bei 4)")
        btn_next.setToolTip("Neue Zeile – Soll/Ist und Eingrenzen werden übernommen")
        btn_next.clicked.connect(lambda: self.new_round())
        nr.addWidget(btn_back)
        nr.addWidget(btn_next)
        c6.body.addWidget(self._nein_row)
        self._three_card = _amber_label()
        self._three_card.setText(f"⚠ <b>{html.escape(guide.STEP6_NOTE)}</b>")
        c6.body.addWidget(self._three_card)

        done_row = QHBoxLayout()
        done_row.addStretch()
        self._btn_done = QPushButton("✓  Fertig")
        self._btn_done.setToolTip("Runde zuklappen – sie bleibt gespeichert und lässt sich in "
                                  "der Liste wieder öffnen")
        self._btn_done.clicked.connect(self.close_entry)
        done_row.addWidget(self._btn_done)
        cl.addLayout(done_row)
        cl.addStretch(1)

        scroll.setWidget(cards_w)
        split.addWidget(scroll)
        split.setSizes([190, 420])
        self.set_level(LEVEL_KL10)

    def _card(self, nr: int, layout: QVBoxLayout) -> _StepCard:
        c = _StepCard(nr)
        self._cards.append(c)
        layout.addWidget(c)
        return c

    def _apply_styles(self):
        dim = THEME["text_dim"]
        self._banner.setStyleSheet(
            f"background:{guide.RED}; color:#ffffff; border-radius:8px; padding:7px 10px;")
        self._file_lbl.setStyleSheet(f"color:{dim}; font-size:10px;")
        self._empty_hint.setStyleSheet(f"color:{dim}; padding:6px 2px;")
        self._weil_hint.setStyleSheet(f"color:{guide.RED}; font-size:11px;")
        self._facts.setStyleSheet(f"color:{dim}; font-size:11px;")
        chip = (f"QPushButton#caseChip {{ background:transparent; color:{THEME['text']}; "
                f"border:1px solid {THEME['border']}; border-radius:12px; padding:4px 6px; "
                f"font-size:11px; font-weight:normal; }}"
                f"QPushButton#caseChip:hover {{ border-color:{guide.NAVY}; }}"
                f"QPushButton#caseChip:checked {{ background:{guide.NAVY}; color:#ffffff; "
                f"border:1px solid {guide.NAVY}; }}")
        for b in self._chips.values():
            b.setStyleSheet(chip)
        self._chip_style = chip
        self._btn_ja.setStyleSheet(
            f"QPushButton:checked {{ background:{guide.GREEN}; color:#ffffff; }}")
        self._btn_nein.setStyleSheet(
            f"QPushButton:checked {{ background:{guide.RED}; color:#ffffff; }}")
        for c in self._cards:
            c.apply_theme()

    def refresh_theme(self):
        self._apply_styles()

    # ── Stufe ────────────────────────────────────────────────────────────
    def set_level(self, level: str):
        if level not in guide.LEVELS:
            level = LEVEL_KL10
        self._level = level
        self._loading = True
        idx = self._form_combo.findData(level)
        if idx >= 0 and idx != self._form_combo.currentIndex():
            self._form_combo.setCurrentIndex(idx)
        # Fall-Schaltflächen für diese Stufe
        while self._chip_grid.count():
            w = self._chip_grid.takeAt(0).widget()
            if w is not None:
                w.setParent(None)   # sofort ausblenden (deleteLater käme erst später)
                w.deleteLater()
        self._chips = {}
        cs = guide.cases(level)
        spalten = 2 if all(len(c.label) <= 22 for c in cs) else 1   # lange Namen: untereinander
        for i, c in enumerate(cs):
            b = QPushButton(c.label)
            b.setObjectName("caseChip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if c.zusatz:
                b.setToolTip(c.zusatz)
            b.setStyleSheet(getattr(self, "_chip_style", ""))
            b.toggled.connect(lambda on, key=c.key: self._on_chip(key, on))
            self._chips[c.key] = b
            self._chip_grid.addWidget(b, i // spalten, i % spalten)
        self._f_eingr.setPlaceholderText(
            "Was hast du gefunden? z. B. K3 und K2 kommen gleichzeitig; nach K3 fehlt „1 s warten“ aus dem PAP"
            if level == LEVEL_KL89 else
            "Was hast du gefunden? z. B. IBD P1; i2c.scan() → [119] = 0x77")
        self._loading = False
        self._on_select(self._list.currentRow())
        self._schedule_save()

    # ── Datei ────────────────────────────────────────────────────────────
    def set_program(self, program_path: str | None):
        """Protokoll zur Programmdatei laden (bzw. leeres anlegen)."""
        if program_path == self._program:
            return
        self.save()
        self._program = program_path
        self._runden = []
        if program_path:
            try:
                with open(protocol_path(program_path), encoding="utf-8") as f:
                    runden, level = from_markdown(f.read())
                self._runden = runden
                if level:
                    self.set_level(level)
            except OSError:
                pass
        name = os.path.basename(program_path) if program_path else "–"
        self._title.setText(f"📝  Fehlerprotokoll – {name}")
        self._file_lbl.setText(
            f"Wird gespeichert als {os.path.basename(protocol_path(program_path))} neben dem Programm."
            if program_path else "Speichere zuerst dein Programm, dann wird das Protokoll mitgespeichert.")
        self._rebuild_list()

    def save(self):
        self._save_timer.stop()
        if not self._program:
            return
        path = protocol_path(self._program)
        # Ohne Runden keine neue Datei anlegen – eine vorhandene aber leeren,
        # sonst tauchen gelöschte Runden beim nächsten Öffnen wieder auf.
        if not self._runden and not os.path.exists(path):
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_markdown(os.path.basename(self._program), self._runden, self._level))
        except OSError as exc:
            self._file_lbl.setText(f"⚠  Protokoll konnte nicht gespeichert werden: {exc}")

    def _schedule_save(self):
        if not self._loading:
            self._save_timer.start()

    # ── Runden ───────────────────────────────────────────────────────────
    def new_round(self, ist: str = "", copy_previous: bool = True) -> Runde:
        """Neue Zeile. War die letzte Runde ein „Nein“, geht es beim selben Fehler weiter
        (Soll/Ist und Eingrenzen werden übernommen, „zurück zu 4“). Mit ``ist`` (Meldung aus
        der Konsole) beginnt dagegen ein frischer Eintrag."""
        nr = max((r.nr for r in self._runden), default=0) + 1
        r = Runde(nr=nr)
        prev = self._runden[-1] if self._runden else None
        if ist:
            r.soll_ist = f"Ist: {ist}"
        elif copy_previous and prev is not None and prev.geklappt == "nein":
            r.soll_ist, r.fall, r.eingrenzen = prev.soll_ist, prev.fall, prev.eingrenzen
        self._runden.append(r)
        self._rebuild_list(select=len(self._runden) - 1)
        (self._f_verm if r.soll_ist else self._f_soll).setFocus()
        self._schedule_save()
        return r

    def close_entry(self):
        """Geöffnete Runde zuklappen (Felder ausblenden)."""
        self.save()
        self._list.setCurrentRow(-1)
        self._list.clearSelection()

    def current(self) -> Runde | None:
        row = self._list.currentRow()
        return self._runden[row] if 0 <= row < len(self._runden) else None

    def open_round(self) -> Runde | None:
        """Die Runde, an der gerade gearbeitet wird (geöffnet, noch kein Ja/Nein)."""
        r = self.current()
        return r if (r is not None and not r.geklappt) else None

    def failed_in_a_row(self) -> int:
        """Wie viele Runden hintereinander am Ende mit „Nein“ endeten."""
        n = 0
        for r in reversed(self._runden):
            if r.geklappt != "nein":
                break
            n += 1
        return n

    def record_run(self, ergebnis: str, aenderung: str, kp: int | None = None):
        """Fakt eintragen: ein Lauf bei der geöffneten, noch offenen Runde."""
        r = self.open_round()
        if r is None:
            return
        r.laeufe.append({"zeit": time.time(), "ergebnis": ergebnis,
                         "aenderung": aenderung, "kp": kp})
        self._show_facts(r)
        self._schedule_save()

    def add_eingrenzen_fact(self, text: str):
        """Fakt in „Eingrenzen“ übernehmen (z. B. Ergebnis von i2c.scan())."""
        r = self.current()
        if r is None:
            r = self.new_round()
        r.eingrenzen = (r.eingrenzen.rstrip() + "\n" if r.eingrenzen.strip() else "") + text
        self._on_select(self._list.currentRow())
        self._schedule_save()

    def focus_result(self):
        """Zu Schritt 6 springen (Link „Ergebnis eintragen“ in der Konsole)."""
        if self.current() is None and self._runden:
            self._list.setCurrentRow(len(self._runden) - 1)
        if self.current() is not None:
            self._form_scroll.ensureWidgetVisible(self._c6)
            self._f_erg.setFocus()

    def _delete(self):
        row = self._list.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "Fehlerprotokoll", "Diese Runde löschen?") \
                != QMessageBox.StandardButton.Yes:
            return
        del self._runden[row]
        self._rebuild_list()
        self._schedule_save()

    def _rebuild_list(self, select: int | None = None):
        """Liste neu aufbauen. Geöffnet wird nur die Runde ``select`` – sonst bleiben die
        Schrittkarten zu, bis eine Runde angeklickt wird."""
        self._loading = True
        self._list.clear()
        for r in self._runden:
            self._list.addItem(QListWidgetItem(self._item_text(r)))
        self._loading = False
        if select is not None and 0 <= select < len(self._runden):
            self._list.setCurrentRow(select)
        else:
            self._on_select(-1)
        self._update_enabled()

    @staticmethod
    def _item_text(r: Runde) -> str:
        first = (r.soll_ist.strip().splitlines() or ["(noch leer)"])[0]
        sym = {"ja": "   ✓", "nein": "   ✗"}.get(r.geklappt, "")
        return f"{r.nr}.  {first[:58]}{sym}"

    # ── Formular ↔ Runde ─────────────────────────────────────────────────
    def _on_select(self, row: int):
        r = self._runden[row] if 0 <= row < len(self._runden) else None
        self._loading = True
        self._f_soll.setPlainText(r.soll_ist if r else "")
        self._f_eingr.setPlainText(r.eingrenzen if r else "")
        self._f_verm.setPlainText(r.vermutung if r else "")
        self._f_aend.setPlainText(r.aenderung if r else "")
        self._f_erg.setPlainText(r.ergebnis if r else "")
        for key, b in self._chips.items():
            b.setChecked(bool(r and r.fall == key))
        self._btn_ja.setChecked(bool(r and r.geklappt == "ja"))
        self._btn_nein.setChecked(bool(r and r.geklappt == "nein"))
        self._loading = False
        self._show_facts(r)
        self._refresh_case_box()
        self._refresh_result_ui()
        self._refresh_weil()
        self._update_enabled()

    def _on_edit(self):
        if self._loading:
            return
        r = self.current()
        if r is None:
            return
        r.soll_ist = self._f_soll.toPlainText()
        r.eingrenzen = self._f_eingr.toPlainText()
        r.vermutung = self._f_verm.toPlainText()
        r.aenderung = self._f_aend.toPlainText()
        r.ergebnis = self._f_erg.toPlainText()
        item = self._list.currentItem()
        if item:
            item.setText(self._item_text(r))
        self._refresh_weil()
        self._schedule_save()

    def _on_chip(self, key: str, on: bool):
        if self._loading:
            return
        r = self.current()
        if r is None:
            return
        self._loading = True
        if on:
            for k, b in self._chips.items():
                if k != key:
                    b.setChecked(False)
            r.fall = key
        elif r.fall == key:
            r.fall = ""
        self._loading = False
        self._refresh_case_box()
        self._schedule_save()

    def _on_result_btn(self, which: str, on: bool):
        if self._loading:
            return
        r = self.current()
        if r is None:
            return
        self._loading = True
        other = self._btn_nein if which == "ja" else self._btn_ja
        if on:
            other.setChecked(False)
            r.geklappt = which
        elif r.geklappt == which:
            r.geklappt = ""
        self._loading = False
        item = self._list.currentItem()
        if item:
            item.setText(self._item_text(r))
        self._refresh_result_ui()
        self._schedule_save()

    def _refresh_case_box(self):
        r = self.current()
        c = guide.case(r.fall, self._level) if (r and r.fall) else None
        self._case_box.setVisible(c is not None)
        if c is not None:
            zusatz = f" <small>{html.escape(c.zusatz)}</small>" if c.zusatz else ""
            self._case_box.setText(f"<b>{html.escape(c.label)}</b>{zusatz}<br>"
                                   f"{guide.inline_html(c.text)}")

    def _refresh_result_ui(self):
        r = self.current()
        res = r.geklappt if r else ""
        if res == "ja":
            self._res_hint.setText(f"<span style='color:{guide.GREEN}'><b>Ja:</b></span> "
                                   f"{html.escape(guide.STEP6_JA)}")
        elif res == "nein":
            self._res_hint.setText(f"<span style='color:{guide.RED}'><b>Nein:</b></span> "
                                   f"{html.escape(guide.STEP6_NEIN)}")
        else:
            self._res_hint.setText(
                f"<span style='color:{THEME['text_dim']}'>Teste das ganze Programm und entscheide.</span>")
        self._nein_row.setVisible(res == "nein")
        self._three_card.setVisible(self.failed_in_a_row() >= 3 and res == "nein")
        self._three.setVisible(self.failed_in_a_row() >= 3)

    def _refresh_weil(self):
        text = self._f_verm.toPlainText().strip()
        show = bool(text) and "weil" not in text.lower()
        self._weil_hint.setText("Fehlt das „weil“? Es stützt sich auf das, was du in 2 und 3 gesehen hast."
                                if show else "")
        self._weil_hint.setVisible(show)

    def _show_facts(self, r: Runde | None):
        if r is not None and r.laeufe:
            self._facts.setText("Läufe (von NIT_Code): " + html.escape(laeufe_text(r)))
            self._facts.setVisible(True)
        else:
            self._facts.setText("")
            self._facts.setVisible(False)

    def _update_enabled(self):
        has = self.current() is not None
        self._btn_del.setEnabled(has)
        self._btn_export.setEnabled(bool(self._runden))
        # Schrittkarten nur bei geöffneter Runde zeigen
        was_hidden = self._form_scroll.isHidden()
        self._form_scroll.setVisible(has)
        if has and was_hidden:
            total = max(sum(self._split.sizes()), 460)
            self._split.setSizes([190, total - 190])
        self._empty_hint.setVisible(not has)
        if self._runden:
            self._empty_hint.setText("Klicke auf eine Runde, um sie anzusehen oder weiterzuschreiben – "
                                     "oder lege mit „Neue Runde“ eine neue an.")
        else:
            self._empty_hint.setText("Noch keine Runden. Wenn du einem Fehler auf der Spur bist, "
                                     "klicke auf „Neue Runde“ – eine Zeile pro Runde.")
        self._refresh_result_ui()

    # ── Export ───────────────────────────────────────────────────────────
    def _export_pdf(self):
        from PyQt6.QtGui import QPageLayout, QPageSize, QTextDocument
        from PyQt6.QtPrintSupport import QPrinter
        name = os.path.basename(self._program) if self._program else "programm.py"
        default = os.path.splitext(protocol_path(self._program))[0] + ".pdf" if self._program \
            else "fehlerprotokoll.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Fehlerprotokoll als PDF", default, "PDF (*.pdf)")
        if not path:
            return
        md = _DATA_RE.sub("", to_markdown(name, self._runden, self._level))
        doc = QTextDocument()
        doc.setMarkdown(md)
        doc.setDefaultStyleSheet("table { border-collapse: collapse; } td, th { padding: 3px; }")
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        doc.print(printer)
