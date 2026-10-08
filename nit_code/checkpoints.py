"""Kontrollpunkte für die PAP-Karte (Debugging-Landkarte).

Ein Kontrollpunkt ist eine Zeile ``print("K3")  # Kontrollpunkt`` – genau wie auf
dem Poster. Erscheint „K3“ in der Ausgabe, läuft der Ablauf bis dorthin; der
Fehler liegt dahinter. Die Nummern werden immer in Dateireihenfolge vergeben
(K1 oben, K2 darunter …), damit sie zu den Kästchen im PAP passen.
"""
import re

MARK = "# Kontrollpunkt"
_LINE_RE = re.compile(r'^(?P<indent>[ \t]*)print\("K(?P<num>\d+)(?P<rest>.*)' + re.escape(MARK) + r"\s*$")
_OUTPUT_RE = re.compile(r"^K(\d+)\b", re.M)
_NAME_RE = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$")


def is_checkpoint(line: str) -> bool:
    return bool(_LINE_RE.match(line))


def _indent_for(lines: list[str], idx: int) -> str:
    """Einrückung für eine neue Zeile VOR lines[idx] (gleicher Block wie diese Zeile)."""
    def ind(s: str) -> str:
        return s[: len(s) - len(s.lstrip())]
    if idx < len(lines) and lines[idx].strip():
        return ind(lines[idx])
    # Leerzeile: nächste nicht-leere Zeile darunter, sonst darüber (+4 nach „:“)
    for j in range(idx + 1, len(lines)):
        if lines[j].strip():
            return ind(lines[j])
    for j in range(min(idx, len(lines)) - 1, -1, -1):
        if lines[j].strip():
            base = ind(lines[j])
            return base + "    " if lines[j].rstrip().endswith(":") else base
    return ""


def renumber(text: str) -> str:
    """Kontrollpunkte in Dateireihenfolge neu nummerieren (K1, K2, …)."""
    out, n = [], 0
    for line in text.split("\n"):
        m = _LINE_RE.match(line)
        if m:
            n += 1
            line = f'{m.group("indent")}print("K{n}{m.group("rest")}{MARK}'
        out.append(line)
    return "\n".join(out)


def insert(text: str, line_no: int, name: str = "") -> tuple[str, int]:
    """Fügt vor Zeile ``line_no`` (1-basiert) einen Kontrollpunkt ein.
    Ist ``name`` ein Variablenname, wird sein Wert mit ausgegeben.
    Gibt (neuer Text, Zeile des Kontrollpunkts) zurück."""
    lines = text.split("\n")
    idx = max(0, min(line_no - 1, len(lines)))
    indent = _indent_for(lines, idx)
    name = name.strip()
    if name and _NAME_RE.match(name):
        stmt = f'print("K0: {name} =", {name})  {MARK}'
    else:
        stmt = f'print("K0")  {MARK}'
    lines.insert(idx, indent + stmt)
    return renumber("\n".join(lines)), idx + 1


def remove_all(text: str) -> tuple[str, int]:
    """Entfernt alle Kontrollpunkt-Zeilen. Gibt (neuer Text, Anzahl) zurück."""
    kept, n = [], 0
    for line in text.split("\n"):
        if _LINE_RE.match(line):
            n += 1
        else:
            kept.append(line)
    return "\n".join(kept), n


def reached_in_output(output: str) -> list[int]:
    """Nummern der Kontrollpunkte, die in der Ausgabe erschienen sind (in Reihenfolge)."""
    return [int(m) for m in _OUTPUT_RE.findall(output or "")]


def line_of(text: str, num: int) -> int | None:
    """Zeile (1-basiert) des Kontrollpunkts K<num> im Code."""
    for i, line in enumerate(text.split("\n"), 1):
        m = _LINE_RE.match(line)
        if m and int(m.group("num")) == num:
            return i
    return None
