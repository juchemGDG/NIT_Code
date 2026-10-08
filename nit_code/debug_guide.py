"""Der Leitfaden „Fehler finden: Schritt für Schritt“ als Daten (Cheatsheet V2).

Eine Quelle für alles, was NIT_Code zum Debugging anzeigt – Konsole, Fehlerprotokoll
und die Anleitungsseite –, damit die Wörter überall dieselben sind wie auf dem
Cheatsheet: Schritte 0 bis 6, in Schritt 3 vier Fälle, ein Protokoll mit sechs
Spalten und einer Zeile pro Runde.

Zwei Stufen: Klasse 8/9 (``kl89``) und Klasse 10/KS (``kl10``). Sie unterscheiden sich
nur in Schritt 3 (Fälle, IBD).

Texte stehen mit `Backticks` für Code; :func:`plain` entfernt sie für die Konsole,
:func:`inline_html` macht daraus ``<code>``.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

LEVEL_KL89 = "kl89"
LEVEL_KL10 = "kl10"
LEVELS = (LEVEL_KL89, LEVEL_KL10)
LEVEL_LABEL = {LEVEL_KL89: "Klasse 8/9", LEVEL_KL10: "Klasse 10/KS"}

# Farben des Cheatsheets
NAVY = "#1d2a4a"
RED = "#b3261e"
BLUE = "#2f6db5"
YELLOW = "#f5b800"
GREEN = "#2e7d32"
CREAM = "#fff6d6"
CREAM_TEXT = "#3d3200"


@dataclass(frozen=True)
class Step:
    nr: int
    title: str
    lead: str          # fett
    detail: str        # normal, \n = Zeilenumbruch
    color: str


STEPS: tuple[Step, ...] = (
    Step(0, "Stopp?",
         "Wird etwas warm, riecht es, ist die Betriebs-LED aus?",
         "Sofort USB trennen, nichts anfassen, Lehrkraft rufen.", RED),
    Step(1, "Läuft schon was?",
         "Tut das Board etwas, bevor du startest? Reagiert die Konsole nicht oder meldet „busy“?",
         "Dann läuft ein altes Programm (`main.py`). Stopp-Knopf der Programmierumgebung "
         "oder **Strg+C** in der Konsole.\n"
         "Hilft nicht: Reset-Taster am Board, sofort Strg+C.", BLUE),
    Step(2, "Beobachten",
         "Was soll passieren? Was passiert?",
         "Gibt es eine Meldung? Dann schreib sie **wörtlich** ab, mit Zeilennummer.", NAVY),
    Step(3, "Eingrenzen", "Welcher Fall liegt vor?", "", NAVY),
    Step(4, "Vermuten",
         "Schreib einen Satz: „Ich vermute …, weil …“",
         "Das „weil“ stützt sich auf das, was du in 2 und 3 gesehen hast.", NAVY),
    Step(5, "Ändern und testen",
         "Ändere genau eine Sache.",
         "Vorher eine Kopie machen oder `#` vor die alte Zeile setzen.\n"
         "Dann starten und beobachten.", NAVY),
    Step(6, "Geklappt?", "", "", NAVY),
)
STEP = {s.nr: s for s in STEPS}

STEP6_JA = "Ganzes Programm noch einmal testen. Zeile ins Heft."
STEP6_NEIN = "Änderung rückgängig machen, zurück zu 4."
STEP6_NOTE = "Drei Runden ohne Erfolg? Partner oder Lehrkraft holen."

# Spalten des Protokolls („Ins Heft oder Laborbuch: eine Zeile pro Runde“)
PROTOCOL_COLUMNS = ("Nr.", "Soll / Ist", "Eingrenzen", "Vermutung", "Änderung", "Ergebnis")


@dataclass(frozen=True)
class Case:
    key: str
    label: str
    zusatz: str        # z. B. „(SyntaxError, NameError)“
    text: str          # Anleitung
    visible: bool = True


_KL9_NICHTS = ("Pin im Code = Pin am Kabel? LED richtig herum? GND? Wackler? "
               "Umstecken nur bei getrenntem USB.")

CASES: dict[str, tuple[Case, ...]] = {
    LEVEL_KL89: (
        Case("code", "Meldung", "",
             "Zeile ansehen, Fehler liegt dort oder knapp davor. "
             "Tippfehler? Doppelpunkt? Einrückung?"),
        Case("wert", "Keine Meldung, Ergebnis falsch", "",
             "An jeden Kontrollpunkt (K) im PAP ein `print(\"K1\")` usw. setzen. "
             "Vorher überlegen: Was erwarte ich dort? Wo es zum ersten Mal nicht stimmt: "
             "diesen Abschnitt **Kasten für Kasten** mit dem Code vergleichen."),
        Case("nichts", "Nichts reagiert", "", _KL9_NICHTS),
        # Hardware-Meldung (z. B. OSError) – in Klasse 8/9 kein eigener Fall, hier gilt die Checkliste.
        Case("hardware", "Meldung", "", _KL9_NICHTS, visible=False),
    ),
    LEVEL_KL10: (
        Case("code", "Meldung zum Code", "(SyntaxError, NameError)",
             "Zeile ansehen, Fehler dort oder knapp davor."),
        Case("hardware", "Meldung zur Hardware", "(OSError: ENODEV, ETIMEDOUT)",
             "IBD ab **P1** prüfen. `i2c.scan()`: Antwortet ein Gerät?"),
        Case("wert", "Wert falsch", "(z. B. 250 °C)",
             "`print()` an die Kontrollpunkte im PAP und an P2/P3 der IBD, mit Erwartung "
             "vergleichen. Wo es nicht stimmt: PAP und Code **Kasten für Kasten** vergleichen."),
        Case("nichts", "Nichts reagiert", "",
             "IBD **Glied für Glied**. Umstecken nur bei getrenntem USB."),
    ),
}

IBD_NOTE = "Wo stimmt die Erwartung zum ersten Mal nicht? Dort liegt der Fehler."
# Allgemeine Informationskette (ohne konkretes Beispiel)
IBD_CHAIN = ("Quelle (z. B. Sensor)", "P1", "Auslesen im Code", "P2", "Variable",
             "P3", "`print()`", "P4", "Konsole")


def cases(level: str, visible_only: bool = True) -> tuple[Case, ...]:
    cs = CASES.get(level, CASES[LEVEL_KL10])
    return tuple(c for c in cs if c.visible) if visible_only else cs


def case(key: str, level: str) -> Case | None:
    return next((c for c in cases(level, visible_only=False) if c.key == key), None)


def case_label(key: str, level: str) -> str:
    c = case(key, level)
    return c.label if c else ""


# ── Textwerkzeuge ─────────────────────────────────────────────────────────────
def plain(text: str) -> str:
    """Für die Konsole: Backticks und **fett**-Markierung entfernen."""
    return text.replace("`", "").replace("**", "")


def inline_html(text: str) -> str:
    """Für HTML: escapen, `code` → <code>, **fett** → <b>, \\n → <br>."""
    t = html.escape(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    return t.replace("\n", "<br>")


def step_header(nr: int) -> str:
    """„◆ Schritt 3 · Eingrenzen“ für die Konsole."""
    return f"◆ Schritt {nr} · {STEP[nr].title}"


# ── Konsolentexte zu den Schritten ────────────────────────────────────────────
def step0_text(grund: str = "") -> str:
    s = STEP[0]
    out = "\n⚠  SCHRITT 0 · STOPP\n"
    if grund:
        out += f"   {grund}\n"
    out += f"   {s.lead}\n   → {plain(s.detail)} Erst danach weiterdenken.\n"
    return out


def step1_text() -> str:
    s = STEP[1]
    lines = plain(s.detail).split("\n")
    return ("\n" + step_header(1) + "\n"
            f"   {s.lead}\n   " + "\n   ".join(lines) + "\n")


def steps45_text() -> str:
    """Abschluss der Fehlerhilfe: Schritt 4 und 5 als Erinnerung."""
    s4, s5 = STEP[4], STEP[5]
    return ("\n" + step_header(4) + f" – {s4.lead}\n"
            f"   {s4.detail}\n"
            + step_header(5) + f" – {s5.lead}\n"
            "   " + plain(s5.detail).replace("\n", " ")
            + " NIT_Code sichert bei jedem Start automatisch einen Stand (⏪ bringt dich zurück).\n")


def step6_text(ok: bool, drei_runden: bool = False) -> str:
    head = step_header(6) + "\n"
    if ok:
        body = f"   Ja: {STEP6_JA}\n"
    else:
        body = f"   Nein: {STEP6_NEIN}\n"
    if drei_runden:
        body += f"   {STEP6_NOTE}\n"
    return "\n" + head + body


# ── Die Anleitungsseite ───────────────────────────────────────────────────────
_CSS = f"""
body {{ font-family: -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; color:#16213a;
        background:#ffffff; margin:0; padding:18px 22px; font-size:13px; }}
h1 {{ font-size:22px; margin:0 0 2px 0; color:{NAVY}; }}
p.sub {{ color:#5b6478; margin:0 0 14px 0; }}
table.steps {{ width:100%; border-collapse:separate; border-spacing:0 7px; }}
td.badge {{ width:118px; vertical-align:top; padding:10px 12px; color:#ffffff;
            border-radius:8px 0 0 8px; }}
td.badge .nr {{ font-size:24px; font-weight:bold; color:{YELLOW}; line-height:1.1; }}
td.badge .ttl {{ font-weight:bold; font-size:13px; }}
td.body {{ vertical-align:top; padding:10px 14px; background:#ffffff; border:1px solid #c9cfdd;
           border-radius:0 8px 8px 0; }}
td.body .lead {{ font-weight:bold; }}
td.body code, code {{ background:#eef1f7; padding:0 3px; border-radius:3px;
           font-family:'JetBrains Mono', Consolas, Menlo, monospace; font-size:12px; }}
ul.cases {{ margin:6px 0 0 0; padding-left:0; list-style:none; }}
ul.cases li {{ margin:5px 0; }}
.chain {{ margin-top:8px; padding:6px 8px; background:#f3f5fa; border-radius:6px; }}
.chain .p {{ display:inline-block; background:{YELLOW}; color:#16213a; font-weight:bold;
             border-radius:10px; padding:0 6px; font-size:11px; }}
.note {{ color:#5b6478; font-size:12px; margin-top:4px; }}
.ja {{ color:{GREEN}; font-weight:bold; }}
.nein {{ color:{RED}; font-weight:bold; }}
h2 {{ font-size:11px; letter-spacing:1px; color:#5b6478; margin:18px 0 6px 0; }}
table.prot {{ width:100%; border-collapse:collapse; }}
table.prot th {{ background:#eef1f7; text-align:left; padding:6px 8px; border:1px solid #c9cfdd; }}
table.prot td {{ padding:14px 8px; border:1px solid #c9cfdd; }}
div.nitcode {{ margin-top:16px; padding:10px 14px; background:{CREAM}; color:{CREAM_TEXT};
               border:1px solid #e0c96a; border-radius:8px; }}
div.nitcode b.h {{ color:{CREAM_TEXT}; }}
"""


def _step_body_html(step: Step, level: str) -> str:
    if step.nr == 3:
        items = []
        for c in cases(level):
            zusatz = f" <span class='note'>{html.escape(c.zusatz)}</span>" if c.zusatz else ""
            items.append(f"<li>▸ <b>{html.escape(c.label)}</b>{zusatz}: {inline_html(c.text)}</li>")
        out = f"<div class='lead'>{html.escape(step.lead)}</div><ul class='cases'>{''.join(items)}</ul>"
        if level == LEVEL_KL10:
            chain = " ".join(
                f"<span class='p'>{html.escape(x)}</span>" if re.fullmatch(r"P\d", x)
                else inline_html(x) for x in IBD_CHAIN)
            out += f"<div class='chain'>{chain}</div><div class='note'>{html.escape(IBD_NOTE)}</div>"
        return out
    if step.nr == 6:
        return (f"<div><span class='ja'>Ja:</span> {html.escape(STEP6_JA)}<br>"
                f"<span class='nein'>Nein:</span> {html.escape(STEP6_NEIN)}</div>"
                f"<div class='note'>{html.escape(STEP6_NOTE)}</div>")
    lead = f"<div class='lead'>{inline_html(step.lead)}</div>" if step.lead else ""
    detail = f"<div>{inline_html(step.detail)}</div>" if step.detail else ""
    return lead + detail


def cheat_sheet_html(level: str) -> str:
    """Das Cheatsheet „Fehler finden: Schritt für Schritt“ ohne Beispiel als HTML-Seite."""
    rows = []
    for st in STEPS:
        rows.append(
            f"<tr><td class='badge' bgcolor='{st.color}' width='118' valign='top' "
            f"style='background-color:{st.color}; color:#ffffff; padding:10px;'>"
            f"<div class='nr'><font color='{YELLOW}' size='5'><b>{st.nr}</b></font></div>"
            f"<div class='ttl'><font color='#ffffff'><b>{html.escape(st.title)}</b></font></div></td>"
            f"<td class='body' valign='top' style='padding:10px;'>{_step_body_html(st, level)}</td></tr>")
    head = "".join(f"<th>{html.escape(c)}</th>" for c in PROTOCOL_COLUMNS)
    empty = "".join("<td>&nbsp;</td>" for _ in PROTOCOL_COLUMNS)
    nit = (
        "<div class='nitcode'><b class='h'>So hilft dir NIT_Code</b><br>"
        "• <b>Strg+K</b> setzt einen Kontrollpunkt <code>print(\"K1\")</code>, die Nummern "
        "folgen dem Programm. Nach einem Absturz zeigt die Konsole den letzten erreichten.<br>"
        "• <b>Konsole</b>: Nach einer Fehlermeldung begleitet sie dich durch Schritt 2 und 3 – "
        "Stufe für Stufe.<br>"
        "• <b>⏪ Zurück zum letzten funktionierenden Stand</b> und <b>📌 Stand merken</b> ersetzen "
        "die Kopie in Schritt 5 und 6.<br>"
        + ("• <b>I2C-Scan</b> (Debuggen-Menü) macht <code>i2c.scan()</code> auf Knopfdruck.<br>"
           if level == LEVEL_KL10 else "")
        + "• <b>Fehlerprotokoll</b> (Seitenleiste): eine Runde pro Zeile, in den Schritten 2 bis 6.</div>")
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{_CSS}</style></head><body>"
        f"<h1>Fehler finden: Schritt für Schritt</h1>"
        f"<p class='sub'>{LEVEL_LABEL[level]} · Gehe die Schritte von oben nach unten durch. "
        f"Überspringe keinen.</p>"
        f"<table class='steps' width='100%' cellspacing='6' cellpadding='0'>{''.join(rows)}</table>"
        f"<h2>INS HEFT ODER LABORBUCH: EINE ZEILE PRO RUNDE</h2>"
        f"<table class='prot' width='100%' border='1' cellspacing='0' cellpadding='6'>"
        f"<tr>{head}</tr><tr>{empty}</tr></table>{nit}</body></html>")
