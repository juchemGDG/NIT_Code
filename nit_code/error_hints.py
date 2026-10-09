"""Verständliche, deutsche Klartext-Hinweise zu Python-/MicroPython-Fehlern.

Rein lokal und deterministisch (keine KI): Aus einem Traceback wird der
Exception-Typ herausgelesen und – falls bekannt – eine kurze, schülergerechte
Erklärung samt Prüf-Tipps zurückgegeben. Ergänzt wird das durch einen optionalen
KI-Prompt für den Tutor "Infi" (siehe :func:`build_infi_error_prompt`).

Fehler finden (Cheatsheet V2): :func:`analyze` ordnet einen Fehler einem Fall aus
Schritt 3 zu (Meldung zum Code, Meldung zur Hardware, …) und liefert eine
Verdächtigenliste – nie die fertige Lösung. Hardware-Meldungen (ENODEV,
ETIMEDOUT …) stehen als austauschbare Daten in ``assets/debug/lesetabelle.json``.
Die Wörter kommen aus :mod:`debug_guide`, damit sie zum Cheatsheet passen.
"""
import json
import re
from dataclasses import dataclass, field

from . import debug_guide as guide
from .debug_guide import LEVEL_KL10, LEVEL_KL89  # noqa: F401  (von anderen Modulen mitgenutzt)

_EXC_RE = re.compile(r"^([A-Za-z_][\w.]*)\s*(?::\s*(.*))?$")

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
# Fehler finden: Fälle (Schritt 3), Lesetabelle
# ──────────────────────────────────────────────────────────────────────────────
# Fehler, die Python schon beim Einlesen der Datei findet – vor der ersten Zeile.
# Kontrollpunkte können hier nichts zeigen, weil keine Zeile ausgeführt wird.
COMPILE_ERRORS = {"SyntaxError", "IndentationError", "TabError"}

VOR_START_HINWEIS = ("Bei diesem Fehler läuft das Programm gar nicht erst los – Python liest "
                     "zuerst die ganze Datei und stolpert dabei. Kontrollpunkte helfen hier "
                     "nicht. Prüfe auch die Zeile darüber.")


def is_compile_error(traceback_text: str) -> bool:
    """True bei SyntaxError & Co. (Fehler beim Einlesen, nicht beim Ausführen)."""
    etype, _ = _extract_exception(traceback_text)
    return etype in COMPILE_ERRORS


@dataclass
class ErrorHint:
    """Strukturierter Hinweis zu einem Fehler (siehe :func:`analyze`)."""
    etype: str
    message: str
    fall: str                          # Fall aus Schritt 3: code | hardware
    lesart: str
    verdaechtige: list[str] = field(default_factory=list)
    erster_test: str = ""
    aktion: str | None = None          # z. B. "i2c_scan"
    belegt: bool = True                # False = Arbeitshypothese (Messreihe fehlt)
    level: str = LEVEL_KL10

    @property
    def vor_start(self) -> bool:
        """Fehler beim Einlesen: das Programm ist gar nicht losgelaufen."""
        return self.etype in COMPILE_ERRORS

    @property
    def fall_name(self) -> str:
        return guide.case_label(self.fall, self.level)

    def render(self, stage: int) -> str:
        """Text einer Hilfestufe: 1 = Fall + Lesart, 2 = Wo suche ich?, 3 = Verdächtige + Test."""
        if stage == 1:
            kurz = self._kurzmeldung()
            tail = f"   ({self.etype}" + (f" · {kurz})" if kurz else ")")
            return (f"{guide.step_header(3)} – Fall: {self.fall_name}{tail}\n"
                    f"   {self.lesart}\n")
        if stage == 2:
            c = guide.case(self.fall, self.level)
            text = guide.plain(c.text) if c else ""
            if self.vor_start:
                text = (text + " " if text else "") + VOR_START_HINWEIS
            return "🧭  Wo suche ich?\n   " + text + "\n"
        if stage == 3:
            if self.belegt or self.level == LEVEL_KL89:
                titel = "🔎  Prüfe nacheinander:"
            else:
                titel = ("🔎  Mögliche Verdächtige (Arbeitshypothese – eine Meldung nennt "
                         "Verdächtige, keinen Schuldigen):")
            out = titel + "\n" + "".join(f"   • {v}\n" for v in self.verdaechtige)
            if self.erster_test:
                out += f"🧪  Erster Test: {self.erster_test}\n"
            return out + guide.steps45_text()
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


def _find_rule(etype: str, message: str, traceback_text: str = "") -> dict | None:
    """Erste passende Regel. Neben Typ und Meldung kann eine Regel den Traceback prüfen:
    ``traceback`` (mindestens ein Muster kommt vor) und ``traceback_nicht`` (keines kommt
    vor). So unterscheidet NIT_Code z. B. ENODEV beim Start (``__init__``) von ENODEV
    mitten im Betrieb."""
    for regel in lesetabelle().get("regeln", []):
        if regel.get("typ") != etype:
            continue
        muster = regel.get("meldung") or []
        if muster and not any(re.search(m, message) for m in muster):
            continue
        if regel.get("traceback") and not any(re.search(m, traceback_text) for m in regel["traceback"]):
            continue
        if any(re.search(m, traceback_text) for m in regel.get("traceback_nicht", [])):
            continue
        return regel
    return None


def _pick(regel: dict, key: str, level: str):
    if level == LEVEL_KL89 and f"{key}_kl89" in regel:
        return regel[f"{key}_kl89"]
    return regel.get(key)


def analyze(traceback_text: str, level: str = LEVEL_KL10) -> ErrorHint | None:
    """Ordnet einen Traceback einem Fall zu – oder None ohne erkennbare Meldung."""
    etype, message = _extract_exception(traceback_text)
    if not etype or etype == "KeyboardInterrupt":
        return None
    message = message or ""
    regel = _find_rule(etype, message, traceback_text)
    if regel:
        return ErrorHint(
            etype=etype, message=message, level=level,
            fall=regel.get("fall", "code"),
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
    return ErrorHint(etype=etype, message=message, level=level, fall="code",
                     lesart=lesart, verdaechtige=tipps)


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
# Schritt 0 und 1: Anzeichen aus der Ausgabe
# ──────────────────────────────────────────────────────────────────────────────
_DANGER_PATTERNS = [
    ("brownout", re.compile(r"Brownout detector was triggered", re.I)),
    ("reset",    re.compile(r"rst:0x[0-9a-fA-F]+\s*\(")),
    ("usb",      re.compile(r"Verbindung zum Controller (verloren|unterbrochen)")),
]

# Das Board antwortet nicht auf den Programmstart: meist läuft noch ein altes Programm.
_BUSY_PATTERNS = re.compile(
    r"nicht best[aä]tigt|could not enter raw repl|device or resource busy|"
    r"resource busy|\bbusy\b|Port wird gerade verwendet", re.I)


def detect_danger(text: str) -> str | None:
    """Schritt 0: 'brownout' | 'reset' | 'usb' | None."""
    for kind, rx in _DANGER_PATTERNS:
        if rx.search(text or ""):
            return kind
    return None


def detect_busy(text: str) -> bool:
    """Schritt 1: Hinweise darauf, dass auf dem Board noch ein altes Programm läuft."""
    return bool(_BUSY_PATTERNS.search(text or ""))


def danger_text(kind: str) -> str:
    """Schritt-0-Kasten (Wortlaut wie auf dem Cheatsheet)."""
    grund = {
        "brownout": "Der Controller meldet einen Spannungseinbruch (Brownout) – das passt zu "
                    "einem Kurzschluss oder einer überlasteten Versorgung.",
        "reset":    "Der Controller ist während des Programms neu gestartet.",
        "usb":      "Die USB-Verbindung zum Controller ist abgebrochen.",
    }.get(kind, "")
    return guide.step0_text(grund)


def build_infi_error_prompt(code: str, traceback_text: str,
                            hint: ErrorHint | None = None) -> str:
    """Baut einen schülergerechten Prompt, mit dem Infi den Fehler erklären soll."""
    tb_tail = "\n".join(traceback_text.strip().splitlines()[-15:])
    code = (code or "").strip()
    if len(code) > 4000:
        code = code[:4000] + "\n# … (gekürzt)"
    zyklus = (
        "Wir arbeiten nach dem Cheatsheet „Fehler finden: Schritt für Schritt“. Hilf bei "
        "Schritt 3 (Eingrenzen): Nenne den Fall (Meldung zum Code oder zur Hardware), wo "
        "ich suchen soll (PAP, Kontrollpunkte, bei Hardware die IBD von P1 an), höchstens "
        "drei Verdächtige und EINEN Test, der sie unterscheidet. Die Vermutung (Schritt 4: "
        "„Ich vermute …, weil …“) formuliere ich selbst. Gib keine fertige Lösung und "
        "keinen korrigierten Code.\n\n"
    )
    kontext = ""
    if hint is not None:
        kontext = f"--- Einordnung von NIT_Code ---\nFall: {hint.fall_name}\n"
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
