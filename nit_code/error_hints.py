"""Verständliche, deutsche Klartext-Hinweise zu Python-/MicroPython-Fehlern.

Rein lokal und deterministisch (keine KI): Aus einem Traceback wird der
Exception-Typ herausgelesen und – falls bekannt – eine kurze, schülergerechte
Erklärung samt Prüf-Tipps zurückgegeben. Ergänzt wird das durch einen optionalen
KI-Prompt für den Tutor "Infi" (siehe :func:`build_infi_error_prompt`).
"""
import re

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


def build_infi_error_prompt(code: str, traceback_text: str) -> str:
    """Baut einen schülergerechten Prompt, mit dem Infi den Fehler erklären soll."""
    tb_tail = "\n".join(traceback_text.strip().splitlines()[-15:])
    code = (code or "").strip()
    if len(code) > 4000:
        code = code[:4000] + "\n# … (gekürzt)"
    return (
        "Ich lerne gerade Python und mein Programm stürzt ab. Bitte erkläre mir "
        "kurz und einfach auf Deutsch, was dieser Fehler bedeutet und wie ich ihn "
        "finden und beheben kann. Gib mir Hinweise, aber NICHT die komplette "
        "Lösung – ich möchte selbst draufkommen.\n\n"
        f"--- Mein Code ---\n{code}\n\n"
        f"--- Fehlermeldung ---\n{tb_tail}\n"
    )
