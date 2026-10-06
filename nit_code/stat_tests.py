"""Signifikanztests für die Datenauswertung – bewusst ohne Qt und ohne scipy.

* Binomialtest (Signifikanztest für eine Wahrscheinlichkeit, wie in der
  Kursstufe BW): exakte Binomialverteilung, Ablehnungsbereich und p-Wert;
  zweiseitig mit α/2 je Seite.
* t-Test für eine Stichprobe (μ = μ₀).
* t-Test für zwei Stichproben: unabhängig (Welch oder gleiche Varianzen)
  oder verbunden (gepaarte Werte, z. B. vorher/nachher).

Die t-Verteilung wird über die regularisierte unvollständige Betafunktion
berechnet (Kettenbruch nach Lentz), Quantile per Bisektion.

``alternative`` ist überall "two-sided" (≠), "less" (<) oder "greater" (>).
"""
import math

ALTERNATIVES = {"two-sided": "≠", "less": "<", "greater": ">"}


# ── Verteilungen ──────────────────────────────────────────────────────────────
def _betacf(a, b, x):
    """Kettenbruch der unvollständigen Betafunktion (modifizierter Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return h


def betainc(a, b, x):
    """Regularisierte unvollständige Betafunktion I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ln_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return math.exp(ln_front) * _betacf(a, b, x) / a
    return 1 - math.exp(ln_front) * _betacf(b, a, 1 - x) / b


def t_cdf(t, df):
    """P(T ≤ t) für die t-Verteilung mit df Freiheitsgraden."""
    tail = 0.5 * betainc(df / 2, 0.5, df / (df + t * t))
    return 1 - tail if t > 0 else tail


def t_ppf(p, df):
    """Quantil der t-Verteilung: das t mit P(T ≤ t) = p."""
    lo, hi = -1.0, 1.0
    while t_cdf(lo, df) > p:
        lo *= 2
    while t_cdf(hi, df) < p:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return (lo + hi) / 2


def _t_p_value(t, df, alternative):
    if alternative == "less":
        return t_cdf(t, df)
    if alternative == "greater":
        return 1 - t_cdf(t, df)
    return min(1.0, 2 * (1 - t_cdf(abs(t), df)))


def binom_pmf(k, n, p):
    if p <= 0:
        return 1.0 if k == 0 else 0.0
    if p >= 1:
        return 1.0 if k == n else 0.0
    return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                    + k * math.log(p) + (n - k) * math.log(1 - p))


def binom_cdf_table(n, p):
    """Liste F[k] = P(X ≤ k) für k = 0 … n."""
    acc, out = 0.0, []
    for k in range(n + 1):
        acc += binom_pmf(k, n, p)
        out.append(min(acc, 1.0))
    return out


# ── Hilfen ────────────────────────────────────────────────────────────────────
def _mean_sd(values):
    n = len(values)
    mean = sum(values) / n
    s = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1)) if n > 1 else 0.0
    return mean, s


def _ci(center, se, df, alpha):
    q = t_ppf(1 - alpha / 2, df)
    return center - q * se, center + q * se


# ── Tests ─────────────────────────────────────────────────────────────────────
def binomial_test(n, k, p0, alternative="two-sided", alpha=0.05):
    """Signifikanztest für eine Wahrscheinlichkeit (H₀: p = p₀).

    Liefert p-Wert, Ablehnungsbereich (als Liste von (von, bis)), tatsächliche
    Irrtumswahrscheinlichkeit, Erwartungswert und Standardabweichung.
    """
    if n <= 0 or not 0 <= k <= n or not 0 < p0 < 1:
        raise ValueError("Es muss 0 ≤ k ≤ n, n > 0 und 0 < p₀ < 1 gelten.")
    F = binom_cdf_table(n, p0)

    def upper(j):               # P(X ≥ j)
        return 1.0 if j <= 0 else max(0.0, 1 - F[j - 1])

    side_alpha = alpha / 2 if alternative == "two-sided" else alpha
    regions, actual = [], 0.0
    if alternative in ("less", "two-sided"):
        g = max((j for j in range(n + 1) if F[j] <= side_alpha), default=None)
        if g is not None:
            regions.append((0, g))
            actual += F[g]
    if alternative in ("greater", "two-sided"):
        g = min((j for j in range(n + 1) if upper(j) <= side_alpha), default=None)
        if g is not None:
            regions.append((g, n))
            actual += upper(g)

    if alternative == "less":
        p_value = F[k]
    elif alternative == "greater":
        p_value = upper(k)
    else:
        p_value = min(1.0, 2 * min(F[k], upper(k)))
    return {
        "n": n, "k": k, "p0": p0, "h": k / n,
        "mu": n * p0, "sigma": math.sqrt(n * p0 * (1 - p0)),
        "p": p_value, "regions": regions, "actual_alpha": actual,
        "reject": p_value <= alpha, "alpha": alpha, "alternative": alternative,
    }


def one_sample_t(values, mu0, alternative="two-sided", alpha=0.05):
    """t-Test für eine Stichprobe (H₀: μ = μ₀)."""
    n = len(values)
    if n < 2:
        raise ValueError("Für einen t-Test sind mindestens 2 Werte nötig.")
    mean, s = _mean_sd(values)
    if s == 0:
        raise ValueError("Alle Werte sind gleich – die Standardabweichung ist 0.")
    se = s / math.sqrt(n)
    t = (mean - mu0) / se
    df = n - 1
    p = _t_p_value(t, df, alternative)
    return {
        "n": n, "mean": mean, "s": s, "se": se, "t": t, "df": df, "p": p,
        "ci": _ci(mean, se, df, alpha), "d": (mean - mu0) / s,
        "reject": p <= alpha, "alpha": alpha, "alternative": alternative, "mu0": mu0,
    }


def two_sample_t(a, b, equal_var=False, alternative="two-sided", alpha=0.05):
    """t-Test für zwei unabhängige Stichproben (H₀: μ_A = μ_B).

    ``equal_var=False`` = Welch-Test (Standard, robuster bei ungleichen
    Varianzen), sonst klassischer Student-t-Test mit gepoolter Varianz.
    """
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        raise ValueError("Jede Gruppe braucht mindestens 2 Werte.")
    m1, s1 = _mean_sd(a)
    m2, s2 = _mean_sd(b)
    v1, v2 = s1 * s1, s2 * s2
    sp = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    if equal_var:
        se = sp * math.sqrt(1 / n1 + 1 / n2)
        df = n1 + n2 - 2
    else:
        se = math.sqrt(v1 / n1 + v2 / n2)
        df = (v1 / n1 + v2 / n2) ** 2 / (
            (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)) if se else 0
    if se == 0:
        raise ValueError("Beide Gruppen haben keine Streuung – Test nicht möglich.")
    diff = m1 - m2
    t = diff / se
    p = _t_p_value(t, df, alternative)
    return {
        "n1": n1, "n2": n2, "mean1": m1, "mean2": m2, "s1": s1, "s2": s2,
        "diff": diff, "se": se, "t": t, "df": df, "p": p,
        "ci": _ci(diff, se, df, alpha), "d": diff / sp if sp else float("nan"),
        "reject": p <= alpha, "alpha": alpha, "alternative": alternative,
        "equal_var": equal_var,
    }


def paired_t(a, b, alternative="two-sided", alpha=0.05):
    """t-Test für verbundene Stichproben: t-Test der Differenzen A − B gegen 0."""
    if len(a) != len(b):
        raise ValueError("Verbundene Stichproben brauchen gleich viele Werte.")
    diffs = [x - y for x, y in zip(a, b)]
    res = one_sample_t(diffs, 0.0, alternative, alpha)
    res.update(mean1=sum(a) / len(a), mean2=sum(b) / len(b),
               s1=_mean_sd(a)[1], s2=_mean_sd(b)[1])
    return res
