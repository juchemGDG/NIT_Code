"""Python-Code zum aktuellen Diagramm der Datenauswertung erzeugen – ohne Qt.

Brücke vom Klick-Werkzeug zum Programmieren: Das erzeugte Programm liest die
CSV-Datei mit dem stdlib-Modul ``csv`` Zeile für Zeile ein und zeichnet das
gleiche Diagramm mit ``matplotlib``. Der Code ist bewusst einfach gehalten
(Listen, Dictionaries, for-Schleifen – kein pandas/numpy), damit Schülerinnen
und Schüler ihn lesen und verändern können.

Die Diagrammtypen sind dieselben Zeichenketten wie in ``csv_plot.CHART_TYPES``.
"""
import json

# Gleiche Farbreihenfolge wie im Fenster (csv_plot._CAT_COLORS).
COLORS = [
    "#3b82f6", "#ef4444", "#22c55e", "#f59e0b",
    "#a855f7", "#06b6d4", "#ec4899", "#84cc16",
    "#eab308", "#14b8a6", "#f43f5e", "#8b5cf6",
]

_AGG_CODE = {
    "Mittelwert": ("statistics.mean", True),
    "Summe": ("sum", False),
    "Median": ("statistics.median", True),
    "Minimum": ("min", False),
    "Maximum": ("max", False),
}


def _q(s: str) -> str:
    """Python-Stringliteral mit doppelten Anführungszeichen."""
    return json.dumps(s, ensure_ascii=False)


def _path_literal(path: str) -> str:
    if '"' not in path and not path.endswith("\\"):
        return f'r"{path}"'
    return repr(path)


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else repr(round(v, 10))


class _Code:
    """Kleiner Zeilen-Sammler mit Einrückung."""

    def __init__(self):
        self.lines: list[str] = []

    def __call__(self, text: str = "", indent: int = 0):
        self.lines.append(("    " * indent + text) if text else "")

    def text(self) -> str:
        return "\n".join(self.lines).rstrip() + "\n"


def generate_code(spec: dict) -> str:
    """Erzeugt das Programm. ``spec`` beschreibt die aktuelle Auswahl:

    path, delimiter, header (bool), headers, chart_type, x_col, y_col,
    value_col (None = Anzahl), cat_col, numeric_categories (bool), agg,
    bins (Klassengrenzen), relative, regression, outliers.
    """
    t = spec["chart_type"]
    h = spec["headers"]
    cat = spec.get("cat_col")
    val = spec.get("value_col")
    uses_xy = t in ("Streudiagramm", "Liniendiagramm")
    uses_groups = t in ("Säulendiagramm", "Balkendiagramm", "Kreisdiagramm")
    if t == "Histogramm":
        cat = None
    agg = "Summe" if t == "Kreisdiagramm" else spec.get("agg", "Mittelwert")
    need_stats = (uses_groups and val is not None and _AGG_CODE[agg][1]) or t == "Boxplot"
    need_colors = uses_groups or (t == "Boxplot")
    regression = t == "Streudiagramm" and spec.get("regression")
    file_name = spec["path"].replace("\\", "/").rsplit("/", 1)[-1]

    c = _Code()
    c('"""' + f"{t} zu „{file_name}“ – erzeugt von NIT_Code (Datenauswertung).")
    c()
    c("Das Programm liest die CSV-Datei Zeile für Zeile ein und zeichnet das")
    c("Diagramm mit matplotlib. Ändere ruhig Spalten, Farben oder Beschriftungen!")
    c('"""')
    c("import csv")
    if need_stats:
        c("import statistics")
    c()
    c("try:")
    c("import matplotlib.pyplot as plt", 1)
    c("except ImportError:")
    c('raise SystemExit("matplotlib fehlt – bitte über „Python → Pakete '
      'installieren (pip) …“ nachinstallieren.")', 1)
    c()
    c(f"DATEI = {_path_literal(spec['path'])}")
    c(f"# Liegt dieses Programm im selben Ordner wie die CSV-Datei, reicht: DATEI = {_q(file_name)}")
    c(f"TRENNZEICHEN = {_q(spec['delimiter'])}")

    # Spaltennummern (Zählung beginnt bei 0)
    cols = []
    if uses_xy:
        cols += [("SPALTE_X", spec["x_col"]), ("SPALTE_Y", spec["y_col"])]
    elif uses_groups:
        if val is not None:
            cols.append(("SPALTE_WERT", val))
    else:
        cols.append(("SPALTE_WERT", spec["y_col"]))
    if cat is not None:
        cols.append(("SPALTE_KATEGORIE", cat))
    for name, idx in cols:
        c(f"{name} = {idx}".ljust(24) + f"# „{h[idx]}“ (Spalten zählen ab 0)")
    if need_colors:
        c(f"FARBEN = {json.dumps(COLORS)}")
    c()
    c()
    c("def zahl(text):")
    c('"""Wandelt einen Zelleninhalt wie "152,5" oder "152.5" in eine Zahl um."""', 1)
    c("text = text.strip()", 1)
    c('if "," in text:                      # deutsches Format: 1.234,5', 1)
    c('text = text.replace(".", "").replace(",", ".")', 2)
    c("return float(text)", 1)
    c()
    if t == "Boxplot":
        c()
        c("def kennwerte(werte):")
        c('"""Fünf-Zahlen-Zusammenfassung wie im Schulbuch: Quartile = Median', 1)
        c('der unteren bzw. oberen Hälfte (bei ungeradem n ohne den Median)."""', 1)
        c("w = sorted(werte)", 1)
        c("n = len(w)", 1)
        c("if n == 1:", 1)
        c("q1 = median = q3 = w[0]", 2)
        c("else:", 1)
        c("haelfte = n // 2", 2)
        c("unten = w[:haelfte]", 2)
        c("oben = w[haelfte + 1:] if n % 2 else w[haelfte:]", 2)
        c("q1, median, q3 = (statistics.median(unten), statistics.median(w),", 2)
        c(" " * 26 + "statistics.median(oben))")
        if spec.get("outliers"):
            c("# Antennen höchstens 1,5 Quartilsabstände lang, weiter weg = Ausreißer", 1)
            c("grenze_unten = q1 - 1.5 * (q3 - q1)", 1)
            c("grenze_oben = q3 + 1.5 * (q3 - q1)", 1)
            c("drin = [x for x in w if grenze_unten <= x <= grenze_oben]", 1)
            c("ausreisser = [x for x in w if x < grenze_unten or x > grenze_oben]", 1)
            c('return {"whislo": min(drin), "q1": q1, "med": median, "q3": q3,', 1)
            c(" " * 12 + '"whishi": max(drin), "fliers": ausreisser}')
        else:
            c("# Antennen von Minimum bis Maximum", 1)
            c('return {"whislo": w[0], "q1": q1, "med": median, "q3": q3,', 1)
            c(" " * 12 + '"whishi": w[-1], "fliers": []}')
        c()
    if regression:
        c()
        c("def ausgleichsgerade(punkte):")
        c('"""Methode der kleinsten Quadrate → Steigung m, y-Achsenabschnitt b, R²."""', 1)
        c("n = len(punkte)", 1)
        c("mx = sum(x for x, y in punkte) / n", 1)
        c("my = sum(y for x, y in punkte) / n", 1)
        c("sxx = sum((x - mx) ** 2 for x, y in punkte)", 1)
        c("sxy = sum((x - mx) * (y - my) for x, y in punkte)", 1)
        c("syy = sum((y - my) ** 2 for x, y in punkte)", 1)
        c("m = sxy / sxx", 1)
        c("b = my - m * mx", 1)
        c("r2 = sxy ** 2 / (sxx * syy) if syy else 1.0", 1)
        c("return m, b, r2", 1)
        c()
    c()

    # ── Einlesen ──
    c("# ── Daten einlesen ─────────────────────────────────────────────")
    if uses_xy:
        c("gruppen = {}                            # Kategorie → Liste von (x, y)"
          if cat is not None else "punkte = []                             # Liste von (x, y)")
    elif uses_groups and val is None:
        c("anzahl = {}                             # Kategorie → Anzahl der Zeilen")
    elif cat is not None:
        c("gruppen = {}                            # Kategorie → Liste der Werte")
    else:
        c("werte = []")
    c('with open(DATEI, encoding="utf-8-sig", newline="") as datei:')
    c("leser = csv.reader(datei, delimiter=TRENNZEICHEN)", 1)
    if spec.get("header", True):
        c("next(leser)                         # Kopfzeile überspringen", 1)
    c("for zeile in leser:", 1)
    c("try:", 2)
    if uses_xy:
        c("x = zahl(zeile[SPALTE_X])", 3)
        c("y = zahl(zeile[SPALTE_Y])", 3)
    elif not (uses_groups and val is None):
        c("wert = zahl(zeile[SPALTE_WERT])", 3)
    if cat is not None:
        c("kategorie = zeile[SPALTE_KATEGORIE].strip()", 3)
    c("except (ValueError, IndexError):", 2)
    c("continue                    # leere oder ungültige Zeile überspringen", 3)
    if uses_xy:
        if cat is not None:
            c("gruppen.setdefault(kategorie, []).append((x, y))", 2)
        else:
            c("punkte.append((x, y))", 2)
    elif uses_groups and val is None:
        c("anzahl[kategorie] = anzahl.get(kategorie, 0) + 1", 2)
    elif cat is not None:
        c("gruppen.setdefault(kategorie, []).append(wert)", 2)
    else:
        c("werte.append(wert)", 2)
    c()

    # Reihenfolge der Kategorien wie im Fenster
    if cat is not None and not uses_xy:
        src = "anzahl" if (uses_groups and val is None) else "gruppen"
        if spec.get("numeric_categories"):
            c(f"namen = sorted({src}, key=zahl)            # Kategorien der Größe nach")
        else:
            c(f"namen = list({src})                        # Kategorien in Reihenfolge der Datei")

    # ── Zeichnen ──
    if cat is not None and not uses_xy:
        c()
    c("# ── Diagramm zeichnen ──────────────────────────────────────────")
    x_title = y_title = None
    grid = "both"
    if uses_xy:
        x_title, y_title = h[spec["x_col"]], h[spec["y_col"]]
        line = t == "Liniendiagramm"
        if cat is not None:
            c("for name, punkte in gruppen.items():")
            ind = 1
        else:
            ind = 0
        if line:
            c("punkte.sort()                       # Linie von links nach rechts", ind)
        c("xs = [x for x, y in punkte]", ind)
        c("ys = [y for x, y in punkte]", ind)
        label = ", label=name" if cat is not None else ""
        if line:
            c(f'linie, = plt.plot(xs, ys, marker="o"{label})', ind)
            color_expr = "linie.get_color()"
        else:
            c(f"marken = plt.scatter(xs, ys{label})", ind)
            color_expr = "marken.get_facecolor()[0]"
        if regression:
            c("if len(set(xs)) > 1:                # Gerade braucht mind. 2 verschiedene x", ind)
            c("m, b, r2 = ausgleichsgerade(punkte)", ind + 1)
            c("x_links, x_rechts = min(xs), max(xs)", ind + 1)
            c("plt.plot([x_links, x_rechts], [m * x_links + b, m * x_rechts + b], \"--\",", ind + 1)
            c(f'color={color_expr}, label=f"y = {{m:.4g}}·x + {{b:.4g}}  (R² = {{r2:.4f}})")',
              ind + 3)
        if cat is not None or regression:
            title = f", title={_q(h[cat])}" if cat is not None else ""
            c(f"plt.legend({title.lstrip(', ')})")
    elif uses_groups:
        if val is None:
            c("werte = [anzahl[n] for n in namen]")
            value_title = "Anzahl"
        else:
            func = _AGG_CODE[agg][0]
            c(f"werte = [{func}(gruppen[n]) for n in namen]   # {agg} je Kategorie")
            value_title = f"{agg} von {h[val]}"
        if t == "Säulendiagramm":
            c("saeulen = plt.bar(namen, werte, color=FARBEN)")
            c("plt.bar_label(saeulen)                  # Werte über die Säulen schreiben")
            x_title, y_title, grid = h[cat], value_title, "y"
        elif t == "Balkendiagramm":
            c("balken = plt.barh(namen, werte, color=FARBEN)")
            c("plt.bar_label(balken)")
            c("plt.gca().invert_yaxis()                # erste Kategorie oben")
            x_title, y_title, grid = value_title, None, "x"
        else:
            c('plt.pie(werte, labels=namen, colors=FARBEN, autopct="%1.1f %%",')
            c("startangle=90, counterclock=False)      # im Uhrzeigersinn ab 12 Uhr", 2)
            c('plt.axis("equal")                       # Kreis statt Ellipse')
            grid = None
    elif t == "Histogramm":
        bins = spec.get("bins") or []
        c(f"klassen = [{', '.join(_num(b) for b in bins)}]   # Klassengrenzen")
        if spec.get("relative"):
            c("gewichte = [100 / len(werte)] * len(werte)  # jeder Wert zählt 100/n %")
            c('plt.hist(werte, bins=klassen, weights=gewichte, edgecolor="white")')
            y_title = "relative Häufigkeit in %"
        else:
            c('plt.hist(werte, bins=klassen, edgecolor="white")')
            y_title = "absolute Häufigkeit"
        if len(bins) <= 13:
            c("plt.xticks(klassen)")
        x_title, grid = h[spec["y_col"]], "y"
    else:   # Boxplot
        # Eigene Kennwerte statt plt.boxplot(): matplotlib würde die Quartile
        # per Interpolation anders berechnen als das Schulbuch.
        if cat is not None:
            c("boxen = []")
            c("for name in namen:")
            c("k = kennwerte(gruppen[name])", 1)
            c('k["label"] = f"{name} (n={len(gruppen[name])})"', 1)
            c("boxen.append(k)", 1)
            x_title = h[cat]
        else:
            c("k = kennwerte(werte)")
            c(f'k["label"] = {_q(h[spec["y_col"]])}')
            c("boxen = [k]")
        c("kaesten = plt.gca().bxp(boxen, patch_artist=True)   # Boxplots aus den Kennwerten")
        c("for kasten, farbe in zip(kaesten[\"boxes\"], FARBEN * 10):")
        c("kasten.set_facecolor(farbe)", 1)
        c("kasten.set_alpha(0.5)", 1)
        y_title, grid = h[spec["y_col"]], "y"

    c()
    if x_title:
        c(f"plt.xlabel({_q(x_title)})")
    if y_title:
        c(f"plt.ylabel({_q(y_title)})")
    c(f"plt.title({_q(t)})")
    if grid == "both":
        c("plt.grid(True, alpha=0.3)")
    elif grid:
        c(f'plt.grid(axis="{grid}", alpha=0.3)')
    c("plt.tight_layout()")
    c("plt.show()")
    return c.text()
