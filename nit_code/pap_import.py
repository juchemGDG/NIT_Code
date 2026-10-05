"""Import von PAP-Editor-Diagrammen (pap.mint-checker.de) in den Code-Generator.

Der PAP-Editor liefert beim „In Projekt übernehmen“ neben dem Bild auch die
Diagrammdaten (JSON: ``nodes`` + ``arrows``). Daraus wird hier ein Mermaid-
Flussdiagramm erzeugt, das der Code-Generator (lokales Ollama-Modell) ohne
Bilderkennung lesen kann.

Bausteine des Editors (``templateLabel``): Start, Stop, Anweisung, Funktion,
Entscheidung, Verzweigung zu, Schleife, Schleife zu. „Funktion“-Bausteine
können ein eigenes Unterdiagramm (``subdiagram``) enthalten.
"""
from __future__ import annotations

import json

# MIME-Typ, unter dem der PAP-Editor die Diagrammdaten in die Zwischenablage legt.
PAP_MIME = "application/x-nit-pap+json"


def parse_pap(data) -> dict | None:
    """Gibt das Diagramm als dict zurück, wenn ``data`` (str/bytes/dict) eines ist."""
    if isinstance(data, (bytes, bytearray)):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(data, str):
        data = data.strip()
        if not data.startswith("{"):
            return None
        try:
            data = json.loads(data)
        except ValueError:
            return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("arrows"), list):
        return None
    return data


def _get(d: dict, *names, default=None):
    """Feld lesen, egal ob camelCase (Web) oder snake_case (Desktop-Format)."""
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default


def _label(text: str) -> str:
    text = (text or "").strip().replace('"', "'")
    return "<br/>".join(part.strip() for part in text.splitlines() if part.strip()) or " "


def _shape(kind: str, text: str) -> str:
    t = _label(text)
    if kind in ("Start", "Stop"):
        return f'(["{t}"])'
    if kind == "Entscheidung":
        return f'{{"{t}"}}'
    if kind == "Funktion":
        return f'[["{t}"]]'
    if kind == "Schleife":
        return f'{{{{"Schleife: {t}"}}}}'
    if kind == "Schleife zu":
        return '{{"Schleifenende"}}'
    return f'["{t}"]'


def _render(diagram: dict, prefix: str, lines: list[str], indent: str) -> None:
    nodes = {n["id"]: n for n in diagram["nodes"] if isinstance(n, dict) and "id" in n}
    arrows = [a for a in diagram["arrows"] if isinstance(a, dict)]

    def ends(a):
        return _get(a, "sourceId", "source_id"), _get(a, "targetId", "target_id")

    def kind(n):
        return _get(n, "templateLabel", "template_label", default="Anweisung")

    # „Verzweigung zu“ ist nur ein Zusammenführungspunkt: wegkürzen und die
    # Pfeile direkt zum Folgebaustein führen (spart dem Modell Rauschen).
    connectors = {i for i, n in nodes.items() if kind(n) == "Verzweigung zu"}
    follow = {}
    for a in arrows:
        s, t = ends(a)
        if s in connectors and s not in follow:
            follow[s] = t

    def resolve(i):
        seen = set()
        while i in connectors and i in follow and i not in seen:
            seen.add(i)
            i = follow[i]
        return i

    used = set()
    edges = []
    for a in arrows:
        s, t = ends(a)
        if s not in nodes or s in connectors:
            continue
        t = resolve(t)
        if t not in nodes:
            continue
        edges.append((s, t, (a.get("label") or "").strip()))
        used.update((s, t))
    isolated = {i for i in nodes if i not in connectors}

    def nid(i):
        return f"{prefix}n{i}"

    for i in sorted(isolated, key=lambda x: (str(type(x)), x)):
        n = nodes[i]
        lines.append(f"{indent}{nid(i)}{_shape(kind(n), n.get('label', ''))}")
    for s, t, lab in edges:
        arrow = f'-->|"{_label(lab)}"|' if lab else "-->"
        lines.append(f"{indent}{nid(s)} {arrow} {nid(t)}")

    # Unterdiagramme von Funktions-Bausteinen als eigene Gruppen
    for i, n in nodes.items():
        sub = parse_pap(n.get("subdiagram")) if n.get("subdiagram") else None
        if kind(n) == "Funktion" and sub:
            title = _label(n.get("label", "")) 
            lines.append(f'{indent}subgraph {prefix}f{i}["Funktion: {title}"]')
            _render(sub, f"{prefix}f{i}_", lines, indent + "    ")
            lines.append(f"{indent}end")


def pap_to_mermaid(diagram: dict) -> str:
    """Wandelt ein PAP-Diagramm in einen Mermaid-Flowchart-Text um."""
    lines = ["flowchart TD"]
    _render(diagram, "", lines, "    ")
    return "\n".join(lines) + "\n"
