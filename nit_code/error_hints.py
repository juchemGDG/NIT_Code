"""Verständliche, deutsche Klartext-Hinweise zu Python-/MicroPython-Fehlern.

Rein lokal und deterministisch (keine KI): Aus einem Traceback wird der
Exception-Typ herausgelesen und – falls bekannt – eine kurze, schülergerechte
Erklärung samt Prüf-Tipps zurückgegeben. Ergänzt wird das durch einen optionalen
KI-Prompt für den Tutor "Infi" (siehe :func:`build_infi_error_prompt`).

Debugging-Landkarte: :func:`analyze` ordnet einen Fehler einer Fehlerebene
(0, 1a, 1b, 2, 3) und einer Karte (PAP, IBD, Checkliste) zu und liefert eine
Verdächtigenliste – nie die fertige Lösung. Hardware-Meldungen (ENODEV,
ETIMEDOUT …) stehen als austauschbare Daten in ``assets/debug/lesetabelle.json``.
Die Begriffe folgen den Postern für Klasse 8/9 (``kl89``) und 10/KS (``kl10``).
"""
import json
import re
from dataclasses import dataclass, field

_EXC_RE = re.compile(r"^([A-Za-z_][\w.]*)\s*(?::\s*(.*))?$")

LEVEL_KL89 = "kl89"
LEVEL_KL10 = "kl10"

# Exception-Typ → mehrzeilige Erklärung (1. Zeile: was es bedeutet, dann Prüf-Tipps).
_HINTS: dict[str, str] = {
    "SyntaxError": """Python kann den Code nicht lesen – irgendwo stimmt die Schreibweise nicht.
Prüfe die Zeile davor/darüber: fehlt ein Doppelpunkt (:) am Ende von if/for/def?
Sind alle Klammern ( ) [ ] { } und Anführungszeichen paarweise geschlossen?""",

    "IndentationError": """Die Einrückung passt nicht. Python erkennt Blöcke an gleicher Einrückung.
Nutze überall gleich viele Leerzeichen (am besten 4) und mische keine Tabs und Leerzeichen.
Nach einem Doppelpunkt (if/for/def …) muss die nächste Zeile eingerückt sein.""",

    "TabError": """Tabs und Leerzeichen sind in der Einrückung gemischt.
Stelle den Editor auf Leerzeichen um und rücke alle Zeilen einheitlich (4 Leerzeichen) ein.""",

    "NameError": """Du benutzt einen Namen (Variable/Funktion), den Python hier noch nicht kennt.
Tippfehler? Groß-/Kleinschreibung beachten (Alter ≠ alter).
Wird die Variable erst NACH dieser Stelle zugewiesen oder fehlt ein import?""",

    "TypeError": """Du verknüpfst Datentypen, die nicht zusammenpassen (z. B. Text + Zahl).
Wandle bei Bedarf um: int("5"), str(5), float(...).
Stimmt die Anzahl der Argumente beim Funktionsaufruf?""",

    "ValueError": """Der Wert hat den richtigen Typ, aber einen unpassenden Inhalt.
Beispiel: int("abc") geht nicht, weil "abc" keine Zahl ist.
Prüfe, was der Nutzer eingegeben hat bzw. was in der Variablen steht.""",

    "IndexError": """Du greifst auf einen Listen-/String-Index zu, den es nicht gibt.
Denke daran: das erste Element hat Index 0, das letzte len(x)-1.
Prüfe die Schleifengrenzen (range) und ob die Liste überhaupt Einträge hat.""",

    "KeyError": """Du suchst in einem Dictionary nach einem Schlüssel, der nicht existiert.
Prüfe die Schreibweise des Schlüssels oder nutze dict.get(schlüssel), um Fehler zu vermeiden.""",

    "AttributeError": """Das Objekt hat die aufgerufene Methode/Eigenschaft nicht.
Tippfehler im Methodennamen? Hat die Variable wirklich den erwarteten Typ?
Häufig steckt dahinter ein None (eine Funktion ohne return liefert None zurück).""",

    "ZeroDivisionError": """Es wurde durch 0 geteilt – das ist mathematisch nicht erlaubt.
Fange den Fall ab (if teiler != 0:) oder prüfe, warum der Teiler 0 geworden ist.""",

    "ModuleNotFoundError": """Das angegebene Modul/die Bibliothek wurde nicht gefunden.
Schreibweise des import prüfen. Eigene Datei korrekt benannt?
Fehlende Pakete über "Python → Pakete installieren (pip)" bzw. den Bibliotheks-Manager nachinstallieren.""",

    "ImportError": """Ein import hat nicht geklappt – Modul oder Name darin existiert nicht.
Schreibweise prüfen. Auf dem Controller: ist die Bibliothek wirklich hochgeladen?""",

    "FileNotFoundError": """Die Datei wurde nicht gefunden.
Stimmt der Dateiname und der Pfad? Liegt die Datei im selben Ordner wie dein Programm?""",

    "RecursionError": """Eine Funktion ruft sich endlos selbst auf.
Fehlt der Abbruchfall (die Bedingung, bei der die Funktion NICHT mehr sich selbst aufruft)?""",

    "UnboundLocalError": """Eine lokale Variable wird benutzt, bevor sie in der Funktion einen Wert bekommt.
Soll eine Variable von außerhalb verändert werden, brauchst du evtl. 'global'.""",

    "AssertionError": """Eine assert-Prüfung ist fehlgeschlagen – eine erwartete Bedingung war nicht erfüllt.
Schau, welche Bedingung geprüft wurde und warum sie hier nicht zutrifft.""",

    "OverflowError": """Eine Zahl ist zu groß geworden (typisch bei float-Berechnungen).
Prüfe die Berechnung – wächst hier etwas unkontrolliert (z. B. in einer Schleife)?""",

    "KeyboardInterrupt": """Das Programm wurde abgebrochen (Strg+C). Das ist meist kein Programmfehler.""",

    "MemoryError": """Der Speicher ist voll – auf Mikrocontrollern passiert das schnell.
Vermeide sehr große Listen/Strings; gib nicht mehr Benötigtes frei; halte Schleifen schlank.""",

    "OSError": """Ein System-/Hardwarezugriff ist fehlgeschlagen.
Auf dem Controller: Pin/Bus richtig verkabelt und initialisiert? Adresse des Sensors korrekt?
Beim Dateizugriff: existiert der Pfad und ist er beschreibbar?""",

    "PermissionError": """Keine Berechtigung für diese Datei/diesen Ordner.
Ist die Datei evtl. in einem anderen Programm geöffnet oder schreibgeschützt?""",

    "RuntimeError": """Ein allgemeiner Laufzeitfehler. Lies die Meldung dahinter – sie nennt meist die Ursache.""",

    "StopIteration": """Ein Iterator hat keine weiteren Elemente. Tritt selten direkt im Schülercode auf –
prüfe Aufrufe von next() bzw. die Schleifenlogik.""",

    "UnicodeDecodeError": """Text/Bytes konnten nicht als UTF-8 gelesen werden.
Beim Öffnen von Dateien encoding="utf-8" angeben oder Sonderzeichen prüfen.""",

    "TimeoutError": """Eine Aktion hat zu lange gedauert und wurde abgebrochen.
Antwortet das Gerät/der Server? Ist die Verkabelung/Verbindung in Ordnung?""",
}


def _extract_exception(traceback_text: str):
    """Liest (Exception-Typ, Meldung) aus der letzten Traceback-Zeile."""
    lines = [ln for ln in traceback_text.strip().splitlines() if ln.strip()]
    if not lines:
        return None, None
    m = _EXC_RE.match(lines[-1].strip())
    if not m:
        return None, None
    full_type = m.group(1)
    message = (m.group(2) or "").strip()
    short_type = full_type.split(".")[-1]   # z. B. JSONDecodeError aus json.decoder.JSONDecodeError
    return short_type, message


def explain(traceback_text: str) -> str | None:
    """Liefert einen formatierten deutschen Hinweis – oder None bei unbekanntem Fehler."""
    etype, _ = _extract_exception(traceback_text)
    if not etype:
        return None
    body = _HINTS.get(etype)
    if body is None:
        return None
    out = [f'💡  Was bedeutet "{etype}"?']
    out += ["   " + ln.strip() for ln in body.strip().splitlines()]
    return "\n".join(out) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# Debugging-Landkarte: Fehlerebenen, Karten, Lesetabelle
# ──────────────────────────────────────────────────────────────────────────────
EBENEN: dict[str, dict[str, str]] = {
    "0":  {LEVEL_KL10: "Gefahr", LEVEL_KL89: "Gefahr"},
    "1a": {LEVEL_KL10: "Meldung des Interpreters", LEVEL_KL89: "Meldung"},
    "1b": {LEVEL_KL10: "Meldung der Hardware", LEVEL_KL89: "Meldung"},
    "2":  {LEVEL_KL10: "Läuft, aber falsch", LEVEL_KL89: "Läuft, aber falsch"},
    "3":  {LEVEL_KL10: "Hardware ohne Meldung", LEVEL_KL89: "Hardware ohne Meldung"},
}

# Welche Ebenen und Karten die jeweilige Stufe kennt (für Auswahllisten).
EBENEN_JE_STUFE = {
    LEVEL_KL89: ["0", "1a", "2", "3"],
    LEVEL_KL10: ["0", "1a", "1b", "2", "3"],
}
KARTEN_JE_STUFE = {
    LEVEL_KL89: ["STOPP", "PAP", "Checkliste"],
    LEVEL_KL10: ["STOPP", "PAP", "IBD", "PAP + IBD"],
}

_KARTEN_HINWEIS: dict[tuple[str, str], str] = {
    ("PAP", LEVEL_KL10): "Bis zu welchem Kästchen läuft dein Programm wie geplant? "
                         "Traceback von UNTEN lesen, Zeile prüfen. Sonst Kontrollpunkte "
                         "K1, K2 … mit print(\"K3\") setzen und den Suchraum halbieren.",
    ("PAP", LEVEL_KL89): "Meldung von UNTEN lesen, Zeile prüfen, Tippfehler? "
                         "Sonst print(\"K3\") an Kontrollpunkte setzen: "
                         "Erscheint K3, liegt der Fehler dahinter.",
    ("IBD", LEVEL_KL10): "An welchem Übergang (P1, P2 …) der Informationskette stimmt "
                         "die Erwartung zum ersten Mal NICHT? Glied für Glied von einem "
                         "Ende her prüfen.",
    ("Checkliste", LEVEL_KL89): "① Pin  ② Richtung  ③ GND  ④ Wackler – eins nach dem anderen.",
}


def karten_hinweis(karte: str, level: str) -> str:
    """Leitfrage der Karte in der Sprache der Stufe."""
    return (_KARTEN_HINWEIS.get((karte, level))
            or _KARTEN_HINWEIS.get((karte, LEVEL_KL10))
            or _KARTEN_HINWEIS.get((karte, LEVEL_KL89), ""))


@dataclass
class ErrorHint:
    """Strukturierter Hinweis zu einem Fehler (siehe :func:`analyze`)."""
    etype: str
    message: str
    ebene: str
    karte: str
    lesart: str
    verdaechtige: list[str] = field(default_factory=list)
    erster_test: str = ""
    aktion: str | None = None          # z. B. "i2c_scan"
    belegt: bool = True                # False = Arbeitshypothese (Messreihe fehlt)
    level: str = LEVEL_KL10

    @property
    def ebene_name(self) -> str:
        return EBENEN.get(self.ebene, {}).get(self.level, "")

    def render(self, stage: int) -> str:
        """Text einer Hilfestufe: 1 = Ebene + Lesart, 2 = Karte, 3 = Verdächtige + Test."""
        if stage == 1:
            head = f"💡  Ebene {self.ebene} – {self.ebene_name}  ({self.etype}"
            head += f" {self._kurzmeldung()})" if self._kurzmeldung() else ")"
            return f"{head}\n   {self.lesart}\n"
        if stage == 2:
            out = f"🗺   Karte: {self.karte}\n"
            hinweis = karten_hinweis(self.karte, self.level)
            if hinweis:
                out += f"   {hinweis}\n"
            return out
        if stage == 3:
            if self.belegt or self.level == LEVEL_KL89:
                titel = "🔎  Prüfe nacheinander:"
            else:
                titel = ("🔎  Mögliche Verdächtige (Arbeitshypothese – eine Meldung nennt "
                         "Verdächtige, keinen Schuldigen):")
            out = titel + "\n" + "".join(f"   • {v}\n" for v in self.verdaechtige)
            if self.erster_test:
                out += f"🧪  Erster Test: {self.erster_test}\n"
            return out
        return ""

    def _kurzmeldung(self) -> str:
        m = re.search(r"\b(E[A-Z]{2,})\b", self.message)
        return m.group(1) if m else ""


_LESETABELLE: dict | None = None


def lesetabelle() -> dict:
    """Lädt ``assets/debug/lesetabelle.json`` (einmalig, bei Fehler leer)."""
    global _LESETABELLE
    if _LESETABELLE is None:
        try:
            from .config import asset_path
            p = asset_path("debug/lesetabelle.json")
            _LESETABELLE = json.loads(p.read_text(encoding="utf-8")) if p else {}
        except (OSError, ValueError):
            _LESETABELLE = {}
    return _LESETABELLE


def _find_rule(etype: str, message: str) -> dict | None:
    for regel in lesetabelle().get("regeln", []):
        if regel.get("typ") != etype:
            continue
        muster = regel.get("meldung") or []
        if not muster or any(re.search(m, message) for m in muster):
            return regel
    return None


def _pick(regel: dict, key: str, level: str):
    if level == LEVEL_KL89 and f"{key}_kl89" in regel:
        return regel[f"{key}_kl89"]
    return regel.get(key)


def analyze(traceback_text: str, level: str = LEVEL_KL10) -> ErrorHint | None:
    """Ordnet einen Traceback Ebene und Karte zu – oder None ohne erkennbare Meldung."""
    etype, message = _extract_exception(traceback_text)
    if not etype or etype == "KeyboardInterrupt":
        return None
    message = message or ""
    regel = _find_rule(etype, message)
    if regel:
        return ErrorHint(
            etype=etype, message=message, level=level,
            ebene=_pick(regel, "ebene", level) or "1a",
            karte=_pick(regel, "karte", level) or "PAP",
            lesart=regel.get("lesart", ""),
            verdaechtige=list(_pick(regel, "verdaechtige", level) or []),
            erster_test=_pick(regel, "erster_test", level) or "",
            aktion=regel.get("aktion"),
            belegt=bool(regel.get("belegt", True)),
        )
    body = _HINTS.get(etype)
    if body:
        lines = [ln.strip() for ln in body.strip().splitlines() if ln.strip()]
        lesart, tipps = lines[0], lines[1:]
    else:
        lesart = "Lies die letzte Zeile der Meldung genau – sie nennt Fehlerart und Ursache."
        tipps = ["Welche Zeile deiner Datei nennt der Traceback?",
                 "Was steht in dieser Zeile, was in der Zeile davor?"]
    return ErrorHint(etype=etype, message=message, level=level, ebene="1a",
                     karte="PAP", lesart=lesart, verdaechtige=tipps)


# ──────────────────────────────────────────────────────────────────────────────
# Traceback: eigene Datei vs. Bibliothek
# ──────────────────────────────────────────────────────────────────────────────
_FRAME_RE = re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+)')


def traceback_frames(traceback_text: str) -> list[tuple[str, int]]:
    """Alle (Datei, Zeile)-Angaben eines Tracebacks in Reihenfolge."""
    return [(m.group("file"), int(m.group("line")))
            for m in _FRAME_RE.finditer(traceback_text or "")]


def search_start(frames: list[tuple[str, int]], is_own) -> tuple[tuple | None, tuple | None]:
    """(letzte Zeile in der eigenen Datei, Entstehungsort in einer Bibliothek oder None)."""
    own = [f for f in frames if is_own(f[0])]
    if not own:
        return None, None
    origin = frames[-1] if not is_own(frames[-1][0]) else None
    return own[-1], origin


# ──────────────────────────────────────────────────────────────────────────────
# Ebene 0: Anzeichen, die zu Kurzschluss/Spannungseinbruch passen
# ──────────────────────────────────────────────────────────────────────────────
_DANGER_PATTERNS = [
    ("brownout", re.compile(r"Brownout detector was triggered", re.I)),
    ("reset",    re.compile(r"rst:0x[0-9a-fA-F]+\s*\(")),
    ("usb",      re.compile(r"Verbindung zum Controller (verloren|unterbrochen)")),
]


def detect_danger(text: str) -> str | None:
    """'brownout' | 'reset' | 'usb' | None."""
    for kind, rx in _DANGER_PATTERNS:
        if rx.search(text or ""):
            return kind
    return None


def danger_text(kind: str) -> str:
    """Schritt-0-Kasten (gleicher Wortlaut wie das Poster)."""
    grund = {
        "brownout": "Der Controller meldet einen Spannungseinbruch (Brownout). "
                    "Das passt zu einem Kurzschluss oder einer überlasteten Versorgung.",
        "reset":    "Der Controller ist während des Programms neu gestartet.",
        "usb":      "Die USB-Verbindung zum Controller ist abgebrochen.",
    }.get(kind, "")
    return (
        "\n⚠  SCHRITT 0 · STOPP – erst sichern, dann suchen\n"
        f"   {grund}\n"
        "   1. USB-Kabel trennen.\n"
        "   2. Nicht anfassen, wenn etwas warm oder heiß ist oder riecht. Lehrkraft rufen.\n"
        "   3. Sichtprüfung: Berühren sich Leitungen? Sitzt der Sensor richtig? Polung?\n"
        "   Es kann auch ein Wackelkontakt sein – geprüft wird trotzdem zuerst.\n"
    )


def build_infi_error_prompt(code: str, traceback_text: str,
                            hint: ErrorHint | None = None) -> str:
    """Baut einen schülergerechten Prompt, mit dem Infi den Fehler erklären soll."""
    tb_tail = "\n".join(traceback_text.strip().splitlines()[-15:])
    code = (code or "").strip()
    if len(code) > 4000:
        code = code[:4000] + "\n# … (gekürzt)"
    zyklus = (
        "Antworte im Debugging-Zyklus: Nenne die Fehlerebene (1a = Meldung des "
        "Interpreters, 1b = Meldung der Hardware), welche Karte hilft (PAP für den "
        "Ablauf, IBD für die Informationskette Sensor → Bus → Pin → Variable → Ausgabe), "
        "höchstens drei Verdächtige und EINEN Test, der sie unterscheidet. "
        "Gib keine fertige Lösung und keinen korrigierten Code.\n\n"
    )
    kontext = ""
    if hint is not None:
        kontext = f"--- Einordnung von NIT_Code ---\nEbene {hint.ebene}, Karte {hint.karte}\n"
        if hint.verdaechtige:
            kontext += "Verdächtige: " + "; ".join(hint.verdaechtige) + "\n"
        kontext += "\n"
    return (
        "Ich lerne gerade Python und mein Programm stürzt ab. Bitte erkläre mir "
        "kurz und einfach auf Deutsch, was dieser Fehler bedeutet und wie ich ihn "
        "finden kann. Gib mir Hinweise, aber NICHT die komplette "
        "Lösung – ich möchte selbst draufkommen.\n"
        + zyklus + kontext +
        f"--- Mein Code ---\n{code}\n\n"
        f"--- Fehlermeldung ---\n{tb_tail}\n"
    )
