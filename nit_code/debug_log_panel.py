"""Fehlerprotokoll als Seitenleiste (Debugging-Landkarte, Konzept Abschnitt 5).

Kurzform (Kl. 8/9): Soll/Ist, Vermutung, Test, Ergebnis.
Vollform (Kl. 10/KS): Soll/Ist, Ebene und Karte, Hypothese, Test, Ergebnis,
Zurück nötig?, Lösung und Lerneffekt.

Grundsatz: NIT_Code trägt nur Fakten ein (Zeit, Meldung, Läufe mit Änderungen).
Alles, was Denken zeigt – Ebene, Hypothese, Lerneffekt – schreiben die SuS.

Gespeichert wird als ``<programm>.fehlerprotokoll.md`` neben dem Programm
(Obsidian-Tabelle). Die Rohdaten stehen als HTML-Kommentar am Dateiende, damit
das Protokoll wieder geladen werden kann; in Obsidian sind sie unsichtbar.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from .config import THEME
from .error_hints import EBENEN, EBENEN_JE_STUFE, KARTEN_JE_STUFE, LEVEL_KL10, LEVEL_KL89

_DATA_RE = re.compile(r"<!--\s*nit-fehlerprotokoll\s*(\{.*\})\s*-->", re.S)

ERGEBNISSE = {
    LEVEL_KL10: ["", "bestätigt", "widerlegt", "verfeinert"],
    LEVEL_KL89: ["", "hat geholfen", "hat nicht geholfen"],
}


@dataclass
class Eintrag:
    nr: int
    zeit: float = field(default_factory=time.time)
    soll_ist: str = ""
    ebene: str = ""
    karte: str = ""
    hypothese: str = ""
    test: str = ""
    ergebnis: str = ""
    zurueck: bool = False
    loesung: str = ""
    laeufe: list = field(default_factory=list)   # [{zeit, ergebnis, aenderung}]


def protocol_path(program_path: str) -> str:
    base, _ = os.path.splitext(program_path)
    return base + ".fehlerprotokoll.md"


def _cell(text: str) -> str:
    return (text or "").strip().replace("|", "\\|").replace("\n", "<br>")


def laeufe_text(e: Eintrag) -> str:
    parts = []
    for lauf in e.laeufe:
        t = time.strftime("%H:%M", time.localtime(lauf.get("zeit", 0)))
        sym = {"ok": "✓", "error": "✗", "stopped": "■"}.get(lauf.get("ergebnis"), "…")
        aend = lauf.get("aenderung", "")
        parts.append(f"{t} {sym}" + (f" ({aend})" if aend else ""))
    return " · ".join(parts)


def to_markdown(name: str, eintraege: list[Eintrag], level: str) -> str:
    voll = level == LEVEL_KL10
    stufe = "Klasse 10/KS · Vollform" if voll else "Klasse 8/9 · Kurzform"
    out = [f"# Fehlerprotokoll – {name}", "",
           f"*{stufe} · Stand {time.strftime('%d.%m.%Y %H:%M')}*", ""]
    if voll:
        out += ["| Nr. | Soll/Ist | Ebene und Karte | Hypothese (mit Begründung) | "
                "Test (eine Änderung) | Ergebnis | Zurück nötig? | Lösung und Lerneffekt |",
                "|---|---|---|---|---|---|---|---|"]
    else:
        out += ["| Nr. | Soll/Ist | Vermutung | Test | Ergebnis |", "|---|---|---|---|---|"]
    for e in eintraege:
        test = _cell(e.test)
        if e.laeufe:
            test += ("<br>" if test else "") + "*Läufe: " + _cell(laeufe_text(e)) + "*"
        if voll:
            ek = " / ".join(x for x in (f"Ebene {e.ebene}" if e.ebene else "", e.karte) if x)
            out.append(f"| {e.nr} | {_cell(e.soll_ist)} | {_cell(ek)} | {_cell(e.hypothese)} | "
                       f"{test} | {_cell(e.ergebnis)} | {'ja' if e.zurueck else 'nein'} | "
                       f"{_cell(e.loesung)} |")
        else:
            out.append(f"| {e.nr} | {_cell(e.soll_ist)} | {_cell(e.hypothese)} | {test} | "
                       f"{_cell(e.ergebnis)} |")
    data = json.dumps({"level": level, "eintraege": [asdict(e) for e in eintraege]},
                      ensure_ascii=False)
    out += ["", f"<!-- nit-fehlerprotokoll {data} -->", ""]
    return "\n".join(out)


def from_markdown(text: str) -> tuple[list[Eintrag], str | None]:
    m = _DATA_RE.search(text or "")
    if not m:
        return [], None
    try:
        raw = json.loads(m.group(1))
        known = set(Eintrag.__dataclass_fields__)
        return ([Eintrag(**{k: v for k, v in e.items() if k in known})
                 for e in raw.get("eintraege", [])], raw.get("level"))
    except (ValueError, TypeError):
        return [], None


class DebugLogPanel(QWidget):
    """Seitliches Panel „📝 Fehlerprotokoll“."""

    close_requested = pyqtSignal()
    restore_requested = pyqtSignal()   # „⏪ Zurück zum letzten funktionierenden Stand“

    def __init__(self, parent=None):
        super().__init__(parent)
        self._program: str | None = None
        self._eintraege: list[Eintrag] = []
        self._level = LEVEL_KL10
        self._loading = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self.save)
        self._build_ui()
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
        self._form_combo.addItem("Kurzform (Kl. 8/9)", LEVEL_KL89)
        self._form_combo.addItem("Vollform (Kl. 10/KS)", LEVEL_KL10)
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

        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(8, 6, 8, 4)
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        tl.addWidget(self._list, 1)
        row = QHBoxLayout()
        self._btn_new = QPushButton("➕  Neuer Eintrag")
        self._btn_new.clicked.connect(lambda: self.new_entry())
        self._btn_del = QPushButton("Löschen")
        self._btn_del.setToolTip("Eintrag löschen")
        self._btn_del.clicked.connect(self._delete)
        self._btn_export = QPushButton("PDF …")
        self._btn_export.setToolTip("Protokoll als PDF speichern (zur Abgabe)")
        self._btn_export.clicked.connect(self._export_pdf)
        row.addWidget(self._btn_new)
        row.addWidget(self._btn_del)
        row.addStretch()
        row.addWidget(self._btn_export)
        tl.addLayout(row)
        self._file_lbl = QLabel("")
        self._file_lbl.setWordWrap(True)
        self._file_lbl.setStyleSheet(f"color:{THEME['text_dim']}; font-size:10px;")
        tl.addWidget(self._file_lbl)
        split.addWidget(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_w = QWidget()
        self._form = QFormLayout(form_w)
        self._form.setContentsMargins(8, 6, 8, 8)
        self._form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        def text_field(h=54):
            w = QPlainTextEdit()
            w.setFixedHeight(h)
            w.textChanged.connect(self._on_edit)
            return w

        self._f_soll = text_field()
        self._f_ebene = QComboBox()
        self._f_karte = QComboBox()
        self._f_ebene.currentIndexChanged.connect(lambda _i: self._on_edit())
        self._f_karte.currentIndexChanged.connect(lambda _i: self._on_edit())
        ek = QWidget()
        ekl = QHBoxLayout(ek)
        ekl.setContentsMargins(0, 0, 0, 0)
        ekl.addWidget(self._f_ebene, 1)
        ekl.addWidget(self._f_karte, 1)
        self._f_hyp = text_field(66)
        self._f_test = text_field()
        self._f_laeufe = QLabel("")
        self._f_laeufe.setWordWrap(True)
        self._f_laeufe.setStyleSheet(f"color:{THEME['text_dim']}; font-size:11px;")
        self._f_erg = QComboBox()
        self._f_erg.currentIndexChanged.connect(lambda _i: self._on_edit())
        zr = QWidget()
        zrl = QHBoxLayout(zr)
        zrl.setContentsMargins(0, 0, 0, 0)
        self._f_zurueck = QCheckBox("ja")
        self._f_zurueck.toggled.connect(lambda _b: self._on_edit())
        btn_restore = QPushButton("⏪  Zurück zum letzten funktionierenden Stand")
        btn_restore.clicked.connect(self.restore_requested.emit)
        zrl.addWidget(self._f_zurueck)
        zrl.addWidget(btn_restore, 1)
        self._f_loes = text_field(66)

        self._lbl_soll = QLabel("Soll/Ist")
        self._lbl_ek = QLabel("Ebene und Karte")
        self._lbl_hyp = QLabel("Hypothese (mit Begründung)")
        self._lbl_test = QLabel("Test (eine Änderung)")
        self._lbl_erg = QLabel("Ergebnis")
        self._lbl_zr = QLabel("Zurück nötig?")
        self._lbl_loes = QLabel("Lösung und Lerneffekt")
        self._form.addRow(self._lbl_soll, self._f_soll)
        self._form.addRow(self._lbl_ek, ek)
        self._form.addRow(self._lbl_hyp, self._f_hyp)
        self._form.addRow(self._lbl_test, self._f_test)
        self._form.addRow("", self._f_laeufe)
        self._form.addRow(self._lbl_erg, self._f_erg)
        self._form.addRow(self._lbl_zr, zr)
        self._form.addRow(self._lbl_loes, self._f_loes)
        self._voll_rows = [(self._lbl_ek, ek), (self._lbl_zr, zr), (self._lbl_loes, self._f_loes)]
        scroll.setWidget(form_w)
        split.addWidget(scroll)
        split.setSizes([160, 420])
        self.set_level(LEVEL_KL10)

    def refresh_theme(self):
        self._file_lbl.setStyleSheet(f"color:{THEME['text_dim']}; font-size:10px;")
        self._f_laeufe.setStyleSheet(f"color:{THEME['text_dim']}; font-size:11px;")

    # ── Stufe ────────────────────────────────────────────────────────────
    def set_level(self, level: str):
        if level not in (LEVEL_KL10, LEVEL_KL89):
            level = LEVEL_KL10
        self._level = level
        self._loading = True
        idx = self._form_combo.findData(level)
        if idx >= 0 and idx != self._form_combo.currentIndex():
            self._form_combo.setCurrentIndex(idx)
        voll = level == LEVEL_KL10
        for lbl, w in self._voll_rows:
            lbl.setVisible(voll)
            w.setVisible(voll)
        self._lbl_hyp.setText("Hypothese (mit Begründung)" if voll else "Vermutung (Ich vermute …, weil …)")
        self._lbl_test.setText("Test (eine Änderung)" if voll else "Test (genau EINE Änderung)")
        self._f_ebene.clear()
        self._f_ebene.addItem("Ebene …", "")
        for e in EBENEN_JE_STUFE[level]:
            self._f_ebene.addItem(f"{e} – {EBENEN[e][level]}", e)
        self._f_karte.clear()
        self._f_karte.addItem("Karte …", "")
        for k in KARTEN_JE_STUFE[level]:
            self._f_karte.addItem(k, k)
        self._f_erg.clear()
        for r in ERGEBNISSE[level]:
            self._f_erg.addItem(r or "Ergebnis …", r)
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
        self._eintraege = []
        if program_path:
            path = protocol_path(program_path)
            try:
                with open(path, encoding="utf-8") as f:
                    eintraege, level = from_markdown(f.read())
                self._eintraege = eintraege
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
        self._update_enabled()

    def save(self):
        self._save_timer.stop()
        if not self._program or not self._eintraege:
            return
        try:
            with open(protocol_path(self._program), "w", encoding="utf-8") as f:
                f.write(to_markdown(os.path.basename(self._program), self._eintraege, self._level))
        except OSError as exc:
            self._file_lbl.setText(f"⚠  Protokoll konnte nicht gespeichert werden: {exc}")

    def _schedule_save(self):
        if not self._loading:
            self._save_timer.start()

    # ── Einträge ─────────────────────────────────────────────────────────
    def new_entry(self, ist: str = "") -> Eintrag:
        nr = max((e.nr for e in self._eintraege), default=0) + 1
        e = Eintrag(nr=nr, soll_ist=(f"Ist: {ist}" if ist else ""))
        self._eintraege.append(e)
        self._rebuild_list()
        self._list.setCurrentRow(len(self._eintraege) - 1)
        self._f_soll.setFocus()
        self._schedule_save()
        return e

    def current(self) -> Eintrag | None:
        row = self._list.currentRow()
        return self._eintraege[row] if 0 <= row < len(self._eintraege) else None

    def record_run(self, ergebnis: str, aenderung: str):
        """Fakt eintragen: ein Lauf beim aktuellen, noch offenen Eintrag."""
        e = self.current()
        if e is None or e.ergebnis:
            return
        e.laeufe.append({"zeit": time.time(), "ergebnis": ergebnis, "aenderung": aenderung})
        self._f_laeufe.setText("Läufe (von NIT_Code): " + laeufe_text(e))
        self._schedule_save()

    def _delete(self):
        row = self._list.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "Fehlerprotokoll", "Diesen Eintrag löschen?") \
                != QMessageBox.StandardButton.Yes:
            return
        del self._eintraege[row]
        self._rebuild_list()
        self._schedule_save()

    def _rebuild_list(self):
        self._loading = True
        cur = self._list.currentRow()
        self._list.clear()
        for e in self._eintraege:
            self._list.addItem(QListWidgetItem(self._item_text(e)))
        self._loading = False
        if self._eintraege:
            self._list.setCurrentRow(min(max(cur, 0), len(self._eintraege) - 1)
                                     if cur >= 0 else len(self._eintraege) - 1)
        else:
            self._on_select(-1)
        self._update_enabled()

    @staticmethod
    def _item_text(e: Eintrag) -> str:
        first = (e.soll_ist.strip().splitlines() or ["(noch leer)"])[0]
        return f"{e.nr}.  {first[:60]}" + (f"   → {e.ergebnis}" if e.ergebnis else "")

    def _on_select(self, row: int):
        e = self._eintraege[row] if 0 <= row < len(self._eintraege) else None
        self._loading = True
        self._f_soll.setPlainText(e.soll_ist if e else "")
        self._f_hyp.setPlainText(e.hypothese if e else "")
        self._f_test.setPlainText(e.test if e else "")
        self._f_loes.setPlainText(e.loesung if e else "")
        self._f_zurueck.setChecked(bool(e and e.zurueck))
        self._f_ebene.setCurrentIndex(max(0, self._f_ebene.findData(e.ebene if e else "")))
        self._f_karte.setCurrentIndex(max(0, self._f_karte.findData(e.karte if e else "")))
        self._f_erg.setCurrentIndex(max(0, self._f_erg.findData(e.ergebnis if e else "")))
        self._f_laeufe.setText(("Läufe (von NIT_Code): " + laeufe_text(e)) if e and e.laeufe else "")
        self._loading = False
        self._update_enabled()

    def _on_edit(self):
        if self._loading:
            return
        e = self.current()
        if e is None:
            return
        e.soll_ist = self._f_soll.toPlainText()
        e.hypothese = self._f_hyp.toPlainText()
        e.test = self._f_test.toPlainText()
        e.loesung = self._f_loes.toPlainText()
        e.zurueck = self._f_zurueck.isChecked()
        e.ebene = self._f_ebene.currentData() or ""
        e.karte = self._f_karte.currentData() or ""
        e.ergebnis = self._f_erg.currentData() or ""
        item = self._list.currentItem()
        if item:
            item.setText(self._item_text(e))
        self._schedule_save()

    def _update_enabled(self):
        has = self.current() is not None
        for w in (self._f_soll, self._f_ebene, self._f_karte, self._f_hyp, self._f_test,
                  self._f_erg, self._f_zurueck, self._f_loes):
            w.setEnabled(has)
        self._btn_del.setEnabled(has)
        self._btn_export.setEnabled(bool(self._eintraege))

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
        md = to_markdown(name, self._eintraege, self._level)
        md = _DATA_RE.sub("", md)
        doc = QTextDocument()
        doc.setMarkdown(md)
        doc.setDefaultStyleSheet("table { border-collapse: collapse; } td, th { padding: 3px; }")
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        doc.print(printer)
