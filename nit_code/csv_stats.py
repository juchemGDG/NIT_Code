"""Ausgleichsgerade für den Serial Plotter (X-Y-Modus) – bewusst ohne Qt.

Die übrige Statistik der früheren Datenauswertung (Kennwerte, Klassen, Tests)
steckt seit v1.10.1 in StatPlot (stats.js, mitgeliefert unter
nit_code/assets/statplot). Gleichungsformat und Zahlenformat sind dort gleich.
"""


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
