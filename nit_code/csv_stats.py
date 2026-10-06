"""Beschreibende Statistik für die Datenauswertung – bewusst ohne Qt.

Konventionen wie in der Schulmathematik (Bildungsplan BW, „Daten und Zufall“):

* Quartile = Median der unteren/oberen Hälfte der sortierten Werte; bei
  ungeradem n gehört der Median zu keiner Hälfte.
* Standardabweichung σ teilt durch n, s (wie Taschenrechner „sx“) durch n − 1.
* Histogrammklassen sind halboffen [a; b), die letzte Klasse schließt das
  Maximum mit ein.
"""
import math


def median(sorted_vals):
    n = len(sorted_vals)
    if n == 0:
        return None
    m = n // 2
    if n % 2:
        return sorted_vals[m]
    return (sorted_vals[m - 1] + sorted_vals[m]) / 2


def quartiles(values):
    """(q1, median, q3) nach Schulkonvention – oder (None, None, None)."""
    v = sorted(values)
    n = len(v)
    if n == 0:
        return None, None, None
    if n == 1:
        return v[0], v[0], v[0]
    half = n // 2
    lower = v[:half]
    upper = v[half + 1:] if n % 2 else v[half:]
    return median(lower), median(v), median(upper)


# (Schlüssel, Beschriftung) in Anzeigereihenfolge.
STAT_LABELS = [
    ("n", "Anzahl n"),
    ("min", "Minimum"),
    ("q1", "unteres Quartil q₁"),
    ("median", "Median"),
    ("q3", "oberes Quartil q₃"),
    ("max", "Maximum"),
    ("range", "Spannweite"),
    ("iqr", "Quartilsabstand"),
    ("mean", "arithmetisches Mittel x̄"),
    ("sigma", "Standardabweichung σ (÷ n)"),
    ("s", "Standardabweichung s (÷ (n−1))"),
]


def describe(values) -> dict:
    """Kennwerte einer Zahlenliste als dict (Schlüssel siehe STAT_LABELS)."""
    v = sorted(values)
    n = len(v)
    res = {key: None for key, _ in STAT_LABELS}
    res["n"] = n
    if n == 0:
        return res
    q1, med, q3 = quartiles(v)
    mean = sum(v) / n
    ss = sum((x - mean) ** 2 for x in v)
    res.update(
        min=v[0], max=v[-1], q1=q1, median=med, q3=q3,
        range=v[-1] - v[0], iqr=q3 - q1, mean=mean,
        sigma=math.sqrt(ss / n),
        s=math.sqrt(ss / (n - 1)) if n > 1 else None,
    )
    return res


def tukey_whiskers(values, q1, q3, k=1.5):
    """Antennen nach der 1,5·IQR-Regel → (unteres Ende, oberes Ende, Ausreißer)."""
    lo, hi = q1 - k * (q3 - q1), q3 + k * (q3 - q1)
    inside = [v for v in values if lo <= v <= hi] or [q1, q3]
    return min(inside), max(inside), [v for v in values if v < lo or v > hi]


def linear_regression(xs, ys):
    """Ausgleichsgerade y = m·x + b (kleinste Quadrate) → (m, b, r²) oder None."""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    syy = sum((y - my) ** 2 for y in ys)
    m = sxy / sxx
    return m, my - m * mx, (sxy * sxy / (sxx * syy) if syy else 1.0)


def regression_text(m, b, r2=None) -> str:
    """„y = 0,95·x − 102,3 (R² = 0,931)“ – für Legende und Kennwerte."""
    sign = "−" if b < 0 else "+"
    text = f"y = {fmt_num(m)}·x {sign} {fmt_num(abs(b))}"
    if r2 is not None:        # feste Stellen: 0,9997 soll nicht als „1“ erscheinen
        text += f"  (R² = {r2:.4f})".replace(".", ",")
    return text


def nice_step(raw: float) -> float:
    """Rundet eine Schrittweite auf 1, 2 oder 5 · 10^k auf."""
    if raw <= 0:
        return 1.0
    exp = math.floor(math.log10(raw))
    base = 10 ** exp
    for m in (1, 2, 5, 10):
        if raw <= m * base * (1 + 1e-9):
            return m * base
    return 10 * base


def histogram_bins(values, width: float = 0):
    """Klassen für ein Histogramm → Liste von (a, b, anzahl).

    ``width`` ≤ 0 wählt die Klassenbreite automatisch (Sturges-Regel, auf eine
    „schöne“ Breite gerundet). Die Klassengrenzen beginnen bei einem
    Vielfachen der Breite.
    """
    v = [x for x in values if x is not None]
    if not v:
        return []
    lo, hi = min(v), max(v)
    if width <= 0:
        k = math.ceil(math.log2(len(v)) + 1)
        width = nice_step((hi - lo) / k) if hi > lo else 1.0
    start = math.floor(lo / width) * width
    # Liegt das Maximum genau auf einer Grenze, gehört es zur letzten Klasse.
    count = max(1, math.ceil((hi - start) / width - 1e-9))
    count = min(count, 500)               # Schutz bei absurd kleiner Breite
    bins = [[round(start + i * width, 10), round(start + (i + 1) * width, 10), 0]
            for i in range(count)]
    for x in v:
        i = math.floor((x - start) / width + 1e-9)   # 1e-9: Rundungsfehler bei 0,1 …
        i = min(max(i, 0), count - 1)
        bins[i][2] += 1
    return [tuple(b) for b in bins]


def frequency_table(labels):
    """Häufigkeiten von Ausprägungen (Reihenfolge des ersten Auftretens).

    → Liste von (ausprägung, absolut, relativ, kumuliert_relativ).
    """
    counts = {}
    for lab in labels:
        counts[lab] = counts.get(lab, 0) + 1
    return cumulate(list(counts.items()))


def cumulate(pairs):
    """[(name, absolut)] → [(name, absolut, relativ, kumuliert_relativ)]."""
    total = sum(c for _, c in pairs) or 1
    out, acc = [], 0
    for name, c in pairs:
        acc += c
        out.append((name, c, c / total, acc / total))
    return out


AGGREGATIONS = {
    "Mittelwert": lambda v: sum(v) / len(v),
    "Summe": sum,
    "Median": lambda v: median(sorted(v)),
    "Minimum": min,
    "Maximum": max,
}


def aggregate(values, how: str):
    """Fasst eine Zahlenliste zusammen (siehe AGGREGATIONS) – None bei leer."""
    if not values:
        return None
    return AGGREGATIONS[how](values)


def fmt_num(v, digits: int = 4) -> str:
    """Zahl für die Anzeige: deutsches Dezimalkomma, ohne überflüssige Nullen."""
    if v is None:
        return "–"
    if isinstance(v, int) or (abs(v) < 1e12 and v == int(v)):
        return str(int(v))
    s = f"{v:.{digits}g}" if abs(v) >= 1e6 or abs(v) < 1e-3 else f"{v:.{digits}f}"
    if "e" not in s and "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")
