'use strict';
// ════════════════════════════════════════════════════════════
// StatPlot – Rechenkern (ohne DOM)
//
// Portiert aus NIT_Code (csv_stats.py, stat_tests.py, csv_codegen.py und dem
// CSV-Einlesen aus csv_plot.py). Läuft im Browser (window.StatCore) und unter
// Node (require) – tests/test_stats.js prüft die Ergebnisse gegen die
// Python-Originale.
//
// Konventionen wie in der Schulmathematik (Bildungsplan BW, „Daten und Zufall“):
// * Quartile = Median der unteren/oberen Hälfte der sortierten Werte; bei
//   ungeradem n gehört der Median zu keiner Hälfte.
// * Standardabweichung σ teilt durch n, s (wie Taschenrechner „sx“) durch n − 1.
// * Histogrammklassen sind halboffen [a; b), die letzte Klasse schließt das
//   Maximum mit ein.
// ════════════════════════════════════════════════════════════
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.StatCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {

  // ── Zahlen ───────────────────────────────────────────────────
  /** Zelle → Zahl oder null. Erkennt auch deutsches Format „1.234,56“. */
  function toFloat(s) {
    s = String(s == null ? '' : s).trim();
    if (!s) return null;
    const v = pyFloat(s);
    if (v !== null) return v;
    if (s.includes(',')) return pyFloat(s.replace(/\./g, '').replace(/,/g, '.'));
    return null;
  }

  // Wie Pythons float(): ganze Zeichenkette muss eine Zahl sein.
  const FLOAT_RE = /^[+-]?(?:\d+(?:_\d+)*(?:\.(?:\d+(?:_\d+)*)?)?|\.\d+(?:_\d+)*)(?:[eE][+-]?\d+(?:_\d+)*)?$/;
  function pyFloat(s) {
    s = s.trim();
    if (FLOAT_RE.test(s)) return Number(s.replace(/_/g, ''));
    const low = s.toLowerCase().replace(/^[+-]/, '');
    if (low === 'inf' || low === 'infinity') return s[0] === '-' ? -Infinity : Infinity;
    if (low === 'nan') return NaN;
    return null;
  }

  /** Pythons round(x, n) – rundet über die exakte Dezimaldarstellung. */
  function roundTo(x, n) {
    if (!isFinite(x) || Math.abs(x) >= 1e21) return x;
    return Number(x.toFixed(n));
  }

  /** Pythons format(x, '.Ng') – inklusive Exponent mit mindestens 2 Ziffern. */
  function formatG(x, digits) {
    if (x === 0) return '0';
    if (!isFinite(x)) return isNaN(x) ? 'nan' : (x < 0 ? '-inf' : 'inf');
    const p = Math.max(1, digits);
    const [mant, expStr] = x.toExponential(p - 1).split('e');
    const exp = parseInt(expStr, 10);
    if (exp < -4 || exp >= p) {
      let m = mant.includes('.') ? mant.replace(/0+$/, '').replace(/\.$/, '') : mant;
      const sign = exp < 0 ? '-' : '+';
      const e = String(Math.abs(exp)).padStart(2, '0');
      return `${m}e${sign}${e}`;
    }
    let s = x.toFixed(Math.max(0, p - 1 - exp));
    if (s.includes('.')) s = s.replace(/0+$/, '').replace(/\.$/, '');
    return s;
  }

  /** Pythons repr(float) – kürzeste Darstellung, Exponent ab 1e16 bzw. unter 1e-4. */
  function pyRepr(x) {
    if (!isFinite(x)) return isNaN(x) ? 'nan' : (x < 0 ? '-inf' : 'inf');
    if (x === 0) return Object.is(x, -0) ? '-0.0' : '0.0';
    const abs = Math.abs(x);
    if (abs >= 1e16 || abs < 1e-4) {
      let [m, e] = x.toExponential().split('e');
      const exp = parseInt(e, 10);
      return `${m}e${exp < 0 ? '-' : '+'}${String(Math.abs(exp)).padStart(2, '0')}`;
    }
    const s = String(x);
    return /[.e]/.test(s) ? s : s + '.0';
  }

  /** Zahl für die Anzeige: deutsches Dezimalkomma, ohne überflüssige Nullen. */
  function fmtNum(v, digits) {
    if (digits === undefined) digits = 4;
    if (v === null || v === undefined) return '–';
    if (Number.isNaN(v)) return '–';
    if (Math.abs(v) < 1e12 && v === Math.trunc(v)) return String(Math.trunc(v) || 0);
    let s = (Math.abs(v) >= 1e6 || Math.abs(v) < 1e-3) ? formatG(v, digits) : v.toFixed(digits);
    if (!s.includes('e') && s.includes('.')) s = s.replace(/0+$/, '').replace(/\.$/, '');
    return s.replace(/\./g, ',');
  }

  // ── CSV ──────────────────────────────────────────────────────
  /** Zerlegt CSV-Text (Anführungszeichen mit "" als Escape) in Zeilen. */
  function splitCSV(text, delim) {
    const rows = [];
    let row = [], cell = '', i = 0, quoted = false;
    const n = text.length;
    while (i < n) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"') {
          if (text[i + 1] === '"') { cell += '"'; i += 2; continue; }
          quoted = false; i++; continue;
        }
        cell += ch; i++; continue;
      }
      if (ch === '"' && cell === '') { quoted = true; i++; continue; }
      if (ch === delim) { row.push(cell); cell = ''; i++; continue; }
      if (ch === '\r' || ch === '\n') {
        row.push(cell); rows.push(row); row = []; cell = '';
        if (ch === '\r' && text[i + 1] === '\n') i++;
        i++; continue;
      }
      cell += ch; i++;
    }
    if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
    return rows;
  }

  /** Häufigkeit eines Zeichens außerhalb von Anführungszeichen. */
  function countOutsideQuotes(line, ch) {
    let c = 0, q = false;
    for (const x of line) {
      if (x === '"') q = !q;
      else if (x === ch && !q) c++;
    }
    return c;
  }

  /** Trennzeichen erkennen: ; vor Tab vor , – je Zeile gleich oft und mindestens einmal. */
  function sniffDelimiter(sample) {
    const lines = sample.split(/\r\n|\r|\n/).filter(l => l.trim()).slice(0, 30);
    if (lines.length > 1 && !/[\r\n]$/.test(sample) && sample.length >= 8192) lines.pop();   // evtl. abgeschnitten
    for (const d of [';', '\t', ',']) {
      const counts = lines.map(l => countOutsideQuotes(l, d));
      if (counts.length && counts[0] > 0 && counts.every(c => c === counts[0])) return d;
    }
    const semi = (sample.match(/;/g) || []).length, comma = (sample.match(/,/g) || []).length;
    const tab = (sample.match(/\t/g) || []).length;
    if (tab > semi && tab > comma) return '\t';
    return semi >= comma ? ';' : ',';
  }

  /** CSV-Text → {headers, rows, info}. info = {delimiter, header} für den Code-Export. */
  function parseCSV(text) {
    text = String(text || '').replace(/^﻿/, '');
    const delimiter = sniffDelimiter(text.slice(0, 8192));
    const info = { delimiter, header: true };
    const all = splitCSV(text, delimiter).filter(r => r.some(c => c.trim()));
    if (!all.length) return { headers: [], rows: [], info };
    const first = all[0];
    let headers, data;
    // Kopfzeile annehmen, wenn die erste Zeile nicht rein numerisch ist.
    if (first.every(c => toFloat(c) !== null)) {
      headers = first.map((_, i) => `Spalte ${i + 1}`);
      data = all;
      info.header = false;
    } else {
      headers = first.map((h, i) => h.trim() || `Spalte ${i + 1}`);
      data = all.slice(1);
    }
    const width = headers.length;
    data = data.map(r => { const x = r.slice(0, width); while (x.length < width) x.push(''); return x; });
    return { headers, rows: data, info };
  }

  /** Indizes der Spalten, die überwiegend (≥ 60 %) numerisch sind. */
  function numericColumns(headers, rows) {
    const out = [];
    for (let c = 0; c < headers.length; c++) {
      const cells = rows.map(r => r[c]).filter(v => v.trim());
      if (!cells.length) continue;
      const num = cells.filter(v => toFloat(v) !== null).length;
      if (num >= 0.6 * cells.length) out.push(c);
    }
    return out;
  }

  // ── Beschreibende Statistik ──────────────────────────────────
  function sum(v) { let s = 0; for (const x of v) s += x; return s; }
  function numSort(v) { return v.slice().sort((a, b) => a - b); }

  function median(sorted) {
    const n = sorted.length;
    if (!n) return null;
    const m = Math.floor(n / 2);
    return n % 2 ? sorted[m] : (sorted[m - 1] + sorted[m]) / 2;
  }

  /** [q1, median, q3] nach Schulkonvention – oder [null, null, null]. */
  function quartiles(values) {
    const v = numSort(values), n = v.length;
    if (!n) return [null, null, null];
    if (n === 1) return [v[0], v[0], v[0]];
    const half = Math.floor(n / 2);
    const lower = v.slice(0, half);
    const upper = n % 2 ? v.slice(half + 1) : v.slice(half);
    return [median(lower), median(v), median(upper)];
  }

  // [Schlüssel, Beschriftung] in Anzeigereihenfolge.
  const STAT_LABELS = [
    ['n', 'Anzahl n'],
    ['min', 'Minimum'],
    ['q1', 'unteres Quartil q₁'],
    ['median', 'Median'],
    ['q3', 'oberes Quartil q₃'],
    ['max', 'Maximum'],
    ['range', 'Spannweite'],
    ['iqr', 'Quartilsabstand'],
    ['mean', 'arithmetisches Mittel x̄'],
    ['sigma', 'Standardabweichung σ (÷ n)'],
    ['s', 'Standardabweichung s (÷ (n−1))'],
  ];

  function describe(values) {
    const v = numSort(values), n = v.length;
    const res = {};
    STAT_LABELS.forEach(([k]) => { res[k] = null; });
    res.n = n;
    if (!n) return res;
    const [q1, med, q3] = quartiles(v);
    const mean = sum(v) / n;
    const ss = sum(v.map(x => (x - mean) ** 2));
    Object.assign(res, {
      min: v[0], max: v[n - 1], q1, median: med, q3,
      range: v[n - 1] - v[0], iqr: q3 - q1, mean,
      sigma: Math.sqrt(ss / n),
      s: n > 1 ? Math.sqrt(ss / (n - 1)) : null,
    });
    return res;
  }

  /** Antennen nach der 1,5·IQR-Regel → [unteres Ende, oberes Ende, Ausreißer]. */
  function tukeyWhiskers(values, q1, q3, k) {
    if (k === undefined) k = 1.5;
    const lo = q1 - k * (q3 - q1), hi = q3 + k * (q3 - q1);
    let inside = values.filter(v => lo <= v && v <= hi);
    if (!inside.length) inside = [q1, q3];
    return [Math.min(...inside), Math.max(...inside), values.filter(v => v < lo || v > hi)];
  }

  /** Ausgleichsgerade y = m·x + b → [m, b, r²] oder null. */
  function linearRegression(xs, ys) {
    const n = xs.length;
    if (n < 2) return null;
    const mx = sum(xs) / n, my = sum(ys) / n;
    let sxx = 0, sxy = 0, syy = 0;
    for (let i = 0; i < n; i++) {
      sxx += (xs[i] - mx) ** 2;
      sxy += (xs[i] - mx) * (ys[i] - my);
      syy += (ys[i] - my) ** 2;
    }
    if (sxx === 0) return null;
    const m = sxy / sxx;
    return [m, my - m * mx, syy ? sxy * sxy / (sxx * syy) : 1.0];
  }

  /** „y = 0,95·x − 102,3  (R² = 0,9310)“ */
  function regressionText(m, b, r2) {
    const sign = b < 0 ? '−' : '+';
    let text = `y = ${fmtNum(m)}·x ${sign} ${fmtNum(Math.abs(b))}`;
    if (r2 !== null && r2 !== undefined) text += `  (R² = ${r2.toFixed(4)})`.replace('.', ',');
    return text;
  }

  /** Rundet eine Schrittweite auf 1, 2 oder 5 · 10^k auf. */
  function niceStep(raw) {
    if (raw <= 0) return 1.0;
    const exp = Math.floor(Math.log10(raw));
    const base = 10 ** exp;
    for (const m of [1, 2, 5, 10]) if (raw <= m * base * (1 + 1e-9)) return m * base;
    return 10 * base;
  }

  /** Klassen für ein Histogramm → [[a, b, anzahl], …]; width ≤ 0 = automatisch (Sturges). */
  function histogramBins(values, width) {
    const v = values.filter(x => x !== null && x !== undefined);
    if (!v.length) return [];
    let lo = Infinity, hi = -Infinity;
    for (const x of v) { if (x < lo) lo = x; if (x > hi) hi = x; }
    if (!(width > 0)) {
      const k = Math.ceil(Math.log2(v.length) + 1);
      width = hi > lo ? niceStep((hi - lo) / k) : 1.0;
    }
    const start = Math.floor(lo / width) * width;
    let count = Math.max(1, Math.ceil((hi - start) / width - 1e-9));
    count = Math.min(count, 500);              // Schutz bei absurd kleiner Breite
    const bins = [];
    for (let i = 0; i < count; i++) bins.push([roundTo(start + i * width, 10), roundTo(start + (i + 1) * width, 10), 0]);
    for (const x of v) {
      let i = Math.floor((x - start) / width + 1e-9);
      i = Math.min(Math.max(i, 0), count - 1);
      bins[i][2] += 1;
    }
    return bins;
  }

  /** [[name, absolut]] → [[name, absolut, relativ, kumuliert_relativ]] */
  function cumulate(pairs) {
    const total = sum(pairs.map(p => p[1])) || 1;
    let acc = 0;
    return pairs.map(([name, c]) => { acc += c; return [name, c, c / total, acc / total]; });
  }

  const AGGREGATIONS = {
    'Mittelwert': v => sum(v) / v.length,
    'Summe': v => sum(v),
    'Median': v => median(numSort(v)),
    'Minimum': v => Math.min(...v),
    'Maximum': v => Math.max(...v),
  };
  function aggregate(values, how) { return values.length ? AGGREGATIONS[how](values) : null; }

  /** Achsenbereich auf „schöne“ Werte erweitern → [lo, hi, ticks]. */
  function niceTicks(lo, hi, count, pad) {
    if (count === undefined) count = 5;
    if (pad === undefined) pad = 0;
    if (lo === hi) { lo -= 1; hi += 1; }
    const span = hi - lo;
    lo -= span * pad; hi += span * pad;
    const step = niceStep((hi - lo) / count);
    const start = Math.floor(lo / step + 1e-9) * step;
    const end = Math.ceil(hi / step - 1e-9) * step;
    const n = Math.round((end - start) / step);
    const ticks = [];
    for (let i = 0; i <= n; i++) ticks.push(roundTo(start + i * step, 10));
    return [start, end, ticks];
  }

  // ── Verteilungen und Tests ───────────────────────────────────
  const ALTERNATIVES = { 'two-sided': '≠', 'less': '<', 'greater': '>' };

  // ln Γ(x) für x > 0 (Lanczos, g = 7) – genug für 15 Stellen.
  const LANCZOS = [0.99999999999980993, 676.5203681218851, -1259.1392167224028,
    771.32342877765313, -176.61502916214059, 12.507343278686905,
    -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  function lgamma(x) {
    if (x < 0.5) return Math.log(Math.PI / Math.abs(Math.sin(Math.PI * x))) - lgamma(1 - x);
    x -= 1;
    let a = LANCZOS[0];
    const t = x + 7.5;
    for (let i = 1; i < 9; i++) a += LANCZOS[i] / (x + i);
    return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
  }

  function betacf(a, b, x) {
    const tiny = 1e-300;
    const qab = a + b, qap = a + 1, qam = a - 1;
    let c = 1.0, d = 1 - qab * x / qap;
    d = 1 / (Math.abs(d) > tiny ? d : tiny);
    let h = d;
    for (let m = 1; m < 500; m++) {
      const m2 = 2 * m;
      let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
      d = 1 + aa * d; d = 1 / (Math.abs(d) > tiny ? d : tiny);
      c = 1 + aa / c; c = Math.abs(c) > tiny ? c : tiny;
      h *= d * c;
      aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
      d = 1 + aa * d; d = 1 / (Math.abs(d) > tiny ? d : tiny);
      c = 1 + aa / c; c = Math.abs(c) > tiny ? c : tiny;
      const delta = d * c;
      h *= delta;
      if (Math.abs(delta - 1) < 1e-15) break;
    }
    return h;
  }

  /** Regularisierte unvollständige Betafunktion I_x(a, b). */
  function betainc(a, b, x) {
    if (x <= 0) return 0.0;
    if (x >= 1) return 1.0;
    const lnFront = lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x);
    if (x < (a + 1) / (a + b + 2)) return Math.exp(lnFront) * betacf(a, b, x) / a;
    return 1 - Math.exp(lnFront) * betacf(b, a, 1 - x) / b;
  }

  function tCdf(t, df) {
    const tail = 0.5 * betainc(df / 2, 0.5, df / (df + t * t));
    return t > 0 ? 1 - tail : tail;
  }

  function tPpf(p, df) {
    let lo = -1.0, hi = 1.0;
    while (tCdf(lo, df) > p) lo *= 2;
    while (tCdf(hi, df) < p) hi *= 2;
    for (let i = 0; i < 200; i++) {
      const mid = (lo + hi) / 2;
      if (tCdf(mid, df) < p) lo = mid; else hi = mid;
      if (hi - lo < 1e-12) break;
    }
    return (lo + hi) / 2;
  }

  function tPValue(t, df, alternative) {
    if (alternative === 'less') return tCdf(t, df);
    if (alternative === 'greater') return 1 - tCdf(t, df);
    return Math.min(1.0, 2 * (1 - tCdf(Math.abs(t), df)));
  }

  function binomPmf(k, n, p) {
    if (p <= 0) return k === 0 ? 1.0 : 0.0;
    if (p >= 1) return k === n ? 1.0 : 0.0;
    return Math.exp(lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) + k * Math.log(p) + (n - k) * Math.log(1 - p));
  }

  function binomCdfTable(n, p) {
    const out = new Array(n + 1);
    let acc = 0.0;
    for (let k = 0; k <= n; k++) { acc += binomPmf(k, n, p); out[k] = Math.min(acc, 1.0); }
    return out;
  }

  class TestError extends Error {}

  function meanSd(values) {
    const n = values.length;
    const mean = sum(values) / n;
    const s = n > 1 ? Math.sqrt(sum(values.map(x => (x - mean) ** 2)) / (n - 1)) : 0.0;
    return [mean, s];
  }

  function ci(center, se, df, alpha) {
    const q = tPpf(1 - alpha / 2, df);
    return [center - q * se, center + q * se];
  }

  /** Signifikanztest für eine Wahrscheinlichkeit (H₀: p = p₀). */
  function binomialTest(n, k, p0, alternative, alpha) {
    alternative = alternative || 'two-sided';
    if (alpha === undefined) alpha = 0.05;
    if (!(n > 0) || !(k >= 0 && k <= n) || !(p0 > 0 && p0 < 1)) {
      throw new TestError('Es muss 0 ≤ k ≤ n, n > 0 und 0 < p₀ < 1 gelten.');
    }
    const F = binomCdfTable(n, p0);
    const upper = j => (j <= 0 ? 1.0 : Math.max(0.0, 1 - F[j - 1]));   // P(X ≥ j)
    const sideAlpha = alternative === 'two-sided' ? alpha / 2 : alpha;
    const regions = [];
    let actual = 0.0;
    if (alternative === 'less' || alternative === 'two-sided') {
      let g = null;
      for (let j = 0; j <= n; j++) if (F[j] <= sideAlpha) g = j;
      if (g !== null) { regions.push([0, g]); actual += F[g]; }
    }
    if (alternative === 'greater' || alternative === 'two-sided') {
      let g = null;
      for (let j = 0; j <= n; j++) if (upper(j) <= sideAlpha) { g = j; break; }
      if (g !== null) { regions.push([g, n]); actual += upper(g); }
    }
    let p;
    if (alternative === 'less') p = F[k];
    else if (alternative === 'greater') p = upper(k);
    else p = Math.min(1.0, 2 * Math.min(F[k], upper(k)));
    return {
      n, k, p0, h: k / n, mu: n * p0, sigma: Math.sqrt(n * p0 * (1 - p0)),
      p, regions, actual_alpha: actual, reject: p <= alpha, alpha, alternative,
    };
  }

  /** t-Test für eine Stichprobe (H₀: μ = μ₀). */
  function oneSampleT(values, mu0, alternative, alpha) {
    alternative = alternative || 'two-sided';
    if (alpha === undefined) alpha = 0.05;
    const n = values.length;
    if (n < 2) throw new TestError('Für einen t-Test sind mindestens 2 Werte nötig.');
    const [mean, s] = meanSd(values);
    if (s === 0) throw new TestError('Alle Werte sind gleich – die Standardabweichung ist 0.');
    const se = s / Math.sqrt(n);
    const t = (mean - mu0) / se;
    const df = n - 1;
    const p = tPValue(t, df, alternative);
    return {
      n, mean, s, se, t, df, p, ci: ci(mean, se, df, alpha), d: (mean - mu0) / s,
      reject: p <= alpha, alpha, alternative, mu0,
    };
  }

  /** t-Test für zwei unabhängige Stichproben; equalVar = false → Welch-Test. */
  function twoSampleT(a, b, equalVar, alternative, alpha) {
    alternative = alternative || 'two-sided';
    if (alpha === undefined) alpha = 0.05;
    const n1 = a.length, n2 = b.length;
    if (n1 < 2 || n2 < 2) throw new TestError('Jede Gruppe braucht mindestens 2 Werte.');
    const [m1, s1] = meanSd(a), [m2, s2] = meanSd(b);
    const v1 = s1 * s1, v2 = s2 * s2;
    const sp = Math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2));
    let se, df;
    if (equalVar) {
      se = sp * Math.sqrt(1 / n1 + 1 / n2);
      df = n1 + n2 - 2;
    } else {
      se = Math.sqrt(v1 / n1 + v2 / n2);
      df = se ? (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)) : 0;
    }
    if (se === 0) throw new TestError('Beide Gruppen haben keine Streuung – Test nicht möglich.');
    const diff = m1 - m2;
    const t = diff / se;
    const p = tPValue(t, df, alternative);
    return {
      n1, n2, mean1: m1, mean2: m2, s1, s2, diff, se, t, df, p,
      ci: ci(diff, se, df, alpha), d: sp ? diff / sp : NaN,
      reject: p <= alpha, alpha, alternative, equal_var: !!equalVar,
    };
  }

  /** t-Test für verbundene Stichproben: t-Test der Differenzen A − B gegen 0. */
  function pairedT(a, b, alternative, alpha) {
    if (a.length !== b.length) throw new TestError('Verbundene Stichproben brauchen gleich viele Werte.');
    const diffs = a.map((x, i) => x - b[i]);
    const res = oneSampleT(diffs, 0.0, alternative, alpha);
    Object.assign(res, { mean1: sum(a) / a.length, mean2: sum(b) / b.length, s1: meanSd(a)[1], s2: meanSd(b)[1] });
    return res;
  }

  // ── Python-Code zum Diagramm (csv + matplotlib) ──────────────
  // Gleiche Farbreihenfolge wie in den Diagrammen.
  const COLORS = [
    '#3b82f6', '#ef4444', '#22c55e', '#f59e0b',
    '#a855f7', '#06b6d4', '#ec4899', '#84cc16',
    '#eab308', '#14b8a6', '#f43f5e', '#8b5cf6',
  ];

  const AGG_CODE = {
    'Mittelwert': ['statistics.mean', true],
    'Summe': ['sum', false],
    'Median': ['statistics.median', true],
    'Minimum': ['min', false],
    'Maximum': ['max', false],
  };

  /** Python-Stringliteral mit doppelten Anführungszeichen (wie json.dumps). */
  function q(s) { return JSON.stringify(String(s)); }

  /** Pythons repr(str). */
  function pyStrRepr(s) {
    const quote = s.includes("'") && !s.includes('"') ? '"' : "'";
    let out = quote;
    for (const ch of s) {
      if (ch === '\\') out += '\\\\';
      else if (ch === quote) out += '\\' + ch;
      else if (ch === '\n') out += '\\n';
      else if (ch === '\r') out += '\\r';
      else if (ch === '\t') out += '\\t';
      else if (ch < ' ') out += '\\x' + ch.charCodeAt(0).toString(16).padStart(2, '0');
      else out += ch;
    }
    return out + quote;
  }

  function pathLiteral(path) {
    if (!path.includes('"') && !path.endsWith('\\')) return `r"${path}"`;
    return pyStrRepr(path);
  }

  function num(v) { return Number.isInteger(v) ? String(v) : pyRepr(roundTo(v, 10)); }

  function ljust(s, w) { return s.length >= w ? s : s + ' '.repeat(w - s.length); }

  /**
   * Erzeugt ein Python-Programm, das das aktuelle Diagramm mit matplotlib zeichnet.
   * spec: path, delimiter, header, headers, chart_type, x_col, y_col, value_col
   * (null = Anzahl), cat_col, numeric_categories, agg, bins, relative,
   * regression, outliers – wie in NIT_Code (csv_codegen.generate_code);
   * nit = true schreibt die Hinweise für NIT_Code.
   */
  function generateCode(spec) {
    const t = spec.chart_type, h = spec.headers;
    let cat = spec.cat_col === undefined ? null : spec.cat_col;
    const val = spec.value_col === undefined ? null : spec.value_col;
    const usesXY = t === 'Streudiagramm' || t === 'Liniendiagramm';
    const usesGroups = t === 'Säulendiagramm' || t === 'Balkendiagramm' || t === 'Kreisdiagramm';
    if (t === 'Histogramm') cat = null;
    const agg = t === 'Kreisdiagramm' ? 'Summe' : (spec.agg || 'Mittelwert');
    const needStats = (usesGroups && val !== null && AGG_CODE[agg][1]) || t === 'Boxplot';
    const needColors = usesGroups || t === 'Boxplot';
    const regression = t === 'Streudiagramm' && !!spec.regression;
    const fileName = spec.path.replace(/\\/g, '/').split('/').pop();

    const lines = [];
    const c = (text, indent) => { lines.push(text ? '    '.repeat(indent || 0) + text : ''); };

    // In NIT_Code (spec.nit) mit Verweis auf dessen Paket-Menü, sonst allgemein.
    const nit = !!spec.nit;
    c('"""' + `${t} zu „${fileName}“ – erzeugt ${nit ? 'von NIT_Code (Datenauswertung)' : 'mit StatPlot'}.`);
    c();
    c('Das Programm liest die CSV-Datei Zeile für Zeile ein und zeichnet das');
    c('Diagramm mit matplotlib. Ändere ruhig Spalten, Farben oder Beschriftungen!');
    c('"""');
    c('import csv');
    if (needStats) c('import statistics');
    c();
    c('try:');
    c('import matplotlib.pyplot as plt', 1);
    c('except ImportError:');
    c(nit ? 'raise SystemExit("matplotlib fehlt – bitte über „Python → Pakete installieren (pip) …“ nachinstallieren.")'
      : 'raise SystemExit("matplotlib fehlt – bitte nachinstallieren: pip install matplotlib")', 1);
    c();
    c(`DATEI = ${pathLiteral(spec.path)}`);
    c(`# Liegt dieses Programm im selben Ordner wie die CSV-Datei, reicht: DATEI = ${q(fileName)}`);
    c(`TRENNZEICHEN = ${q(spec.delimiter)}`);

    const cols = [];
    if (usesXY) cols.push(['SPALTE_X', spec.x_col], ['SPALTE_Y', spec.y_col]);
    else if (usesGroups) { if (val !== null) cols.push(['SPALTE_WERT', val]); }
    else cols.push(['SPALTE_WERT', spec.y_col]);
    if (cat !== null) cols.push(['SPALTE_KATEGORIE', cat]);
    for (const [name, idx] of cols) c(ljust(`${name} = ${idx}`, 24) + `# „${h[idx]}“ (Spalten zählen ab 0)`);
    if (needColors) c(`FARBEN = [${COLORS.map(q).join(', ')}]`);
    c();
    c();
    c('def zahl(text):');
    c('"""Wandelt einen Zelleninhalt wie "152,5" oder "152.5" in eine Zahl um."""', 1);
    c('text = text.strip()', 1);
    c('if "," in text:                      # deutsches Format: 1.234,5', 1);
    c('text = text.replace(".", "").replace(",", ".")', 2);
    c('return float(text)', 1);
    c();
    if (t === 'Boxplot') {
      c();
      c('def kennwerte(werte):');
      c('"""Fünf-Zahlen-Zusammenfassung wie im Schulbuch: Quartile = Median', 1);
      c('der unteren bzw. oberen Hälfte (bei ungeradem n ohne den Median)."""', 1);
      c('w = sorted(werte)', 1);
      c('n = len(w)', 1);
      c('if n == 1:', 1);
      c('q1 = median = q3 = w[0]', 2);
      c('else:', 1);
      c('haelfte = n // 2', 2);
      c('unten = w[:haelfte]', 2);
      c('oben = w[haelfte + 1:] if n % 2 else w[haelfte:]', 2);
      c('q1, median, q3 = (statistics.median(unten), statistics.median(w),', 2);
      c(' '.repeat(26) + 'statistics.median(oben))');
      if (spec.outliers) {
        c('# Antennen höchstens 1,5 Quartilsabstände lang, weiter weg = Ausreißer', 1);
        c('grenze_unten = q1 - 1.5 * (q3 - q1)', 1);
        c('grenze_oben = q3 + 1.5 * (q3 - q1)', 1);
        c('drin = [x for x in w if grenze_unten <= x <= grenze_oben]', 1);
        c('ausreisser = [x for x in w if x < grenze_unten or x > grenze_oben]', 1);
        c('return {"whislo": min(drin), "q1": q1, "med": median, "q3": q3,', 1);
        c(' '.repeat(12) + '"whishi": max(drin), "fliers": ausreisser}');
      } else {
        c('# Antennen von Minimum bis Maximum', 1);
        c('return {"whislo": w[0], "q1": q1, "med": median, "q3": q3,', 1);
        c(' '.repeat(12) + '"whishi": w[-1], "fliers": []}');
      }
      c();
    }
    if (regression) {
      c();
      c('def ausgleichsgerade(punkte):');
      c('"""Methode der kleinsten Quadrate → Steigung m, y-Achsenabschnitt b, R²."""', 1);
      c('n = len(punkte)', 1);
      c('mx = sum(x for x, y in punkte) / n', 1);
      c('my = sum(y for x, y in punkte) / n', 1);
      c('sxx = sum((x - mx) ** 2 for x, y in punkte)', 1);
      c('sxy = sum((x - mx) * (y - my) for x, y in punkte)', 1);
      c('syy = sum((y - my) ** 2 for x, y in punkte)', 1);
      c('m = sxy / sxx', 1);
      c('b = my - m * mx', 1);
      c('r2 = sxy ** 2 / (sxx * syy) if syy else 1.0', 1);
      c('return m, b, r2', 1);
      c();
    }
    c();

    // ── Einlesen ──
    c('# ── Daten einlesen ─────────────────────────────────────────────');
    if (usesXY) {
      c(cat !== null ? 'gruppen = {}                            # Kategorie → Liste von (x, y)'
        : 'punkte = []                             # Liste von (x, y)');
    } else if (usesGroups && val === null) {
      c('anzahl = {}                             # Kategorie → Anzahl der Zeilen');
    } else if (cat !== null) {
      c('gruppen = {}                            # Kategorie → Liste der Werte');
    } else {
      c('werte = []');
    }
    c('with open(DATEI, encoding="utf-8-sig", newline="") as datei:');
    c('leser = csv.reader(datei, delimiter=TRENNZEICHEN)', 1);
    if (spec.header !== false) c('next(leser)                         # Kopfzeile überspringen', 1);
    c('for zeile in leser:', 1);
    c('try:', 2);
    if (usesXY) {
      c('x = zahl(zeile[SPALTE_X])', 3);
      c('y = zahl(zeile[SPALTE_Y])', 3);
    } else if (!(usesGroups && val === null)) {
      c('wert = zahl(zeile[SPALTE_WERT])', 3);
    }
    if (cat !== null) c('kategorie = zeile[SPALTE_KATEGORIE].strip()', 3);
    c('except (ValueError, IndexError):', 2);
    c('continue                    # leere oder ungültige Zeile überspringen', 3);
    if (usesXY) {
      if (cat !== null) c('gruppen.setdefault(kategorie, []).append((x, y))', 2);
      else c('punkte.append((x, y))', 2);
    } else if (usesGroups && val === null) {
      c('anzahl[kategorie] = anzahl.get(kategorie, 0) + 1', 2);
    } else if (cat !== null) {
      c('gruppen.setdefault(kategorie, []).append(wert)', 2);
    } else {
      c('werte.append(wert)', 2);
    }
    c();

    if (cat !== null && !usesXY) {
      const src = usesGroups && val === null ? 'anzahl' : 'gruppen';
      if (spec.numeric_categories) c(`namen = sorted(${src}, key=zahl)            # Kategorien der Größe nach`);
      else c(`namen = list(${src})                        # Kategorien in Reihenfolge der Datei`);
    }

    // ── Zeichnen ──
    if (cat !== null && !usesXY) c();
    c('# ── Diagramm zeichnen ──────────────────────────────────────────');
    let xTitle = null, yTitle = null, grid = 'both';
    if (usesXY) {
      xTitle = h[spec.x_col]; yTitle = h[spec.y_col];
      const line = t === 'Liniendiagramm';
      let ind = 0;
      if (cat !== null) { c('for name, punkte in gruppen.items():'); ind = 1; }
      if (line) c('punkte.sort()                       # Linie von links nach rechts', ind);
      c('xs = [x for x, y in punkte]', ind);
      c('ys = [y for x, y in punkte]', ind);
      const label = cat !== null ? ', label=name' : '';
      let colorExpr;
      if (line) { c(`linie, = plt.plot(xs, ys, marker="o"${label})`, ind); colorExpr = 'linie.get_color()'; }
      else { c(`marken = plt.scatter(xs, ys${label})`, ind); colorExpr = 'marken.get_facecolor()[0]'; }
      if (regression) {
        c('if len(set(xs)) > 1:                # Gerade braucht mind. 2 verschiedene x', ind);
        c('m, b, r2 = ausgleichsgerade(punkte)', ind + 1);
        c('x_links, x_rechts = min(xs), max(xs)', ind + 1);
        c('plt.plot([x_links, x_rechts], [m * x_links + b, m * x_rechts + b], "--",', ind + 1);
        c(`color=${colorExpr}, label=f"y = {m:.4g}·x + {b:.4g}  (R² = {r2:.4f})")`, ind + 3);
      }
      if (cat !== null || regression) c(`plt.legend(${cat !== null ? 'title=' + q(h[cat]) : ''})`);
    } else if (usesGroups) {
      let valueTitle;
      if (val === null) { c('werte = [anzahl[n] for n in namen]'); valueTitle = 'Anzahl'; }
      else {
        c(`werte = [${AGG_CODE[agg][0]}(gruppen[n]) for n in namen]   # ${agg} je Kategorie`);
        valueTitle = `${agg} von ${h[val]}`;
      }
      if (t === 'Säulendiagramm') {
        c('saeulen = plt.bar(namen, werte, color=FARBEN)');
        c('plt.bar_label(saeulen)                  # Werte über die Säulen schreiben');
        xTitle = h[cat]; yTitle = valueTitle; grid = 'y';
      } else if (t === 'Balkendiagramm') {
        c('balken = plt.barh(namen, werte, color=FARBEN)');
        c('plt.bar_label(balken)');
        c('plt.gca().invert_yaxis()                # erste Kategorie oben');
        xTitle = valueTitle; yTitle = null; grid = 'x';
      } else {
        c('plt.pie(werte, labels=namen, colors=FARBEN, autopct="%1.1f %%",');
        c('startangle=90, counterclock=False)      # im Uhrzeigersinn ab 12 Uhr', 2);
        c('plt.axis("equal")                       # Kreis statt Ellipse');
        grid = null;
      }
    } else if (t === 'Histogramm') {
      const bins = spec.bins || [];
      c(`klassen = [${bins.map(num).join(', ')}]   # Klassengrenzen`);
      if (spec.relative) {
        c('gewichte = [100 / len(werte)] * len(werte)  # jeder Wert zählt 100/n %');
        c('plt.hist(werte, bins=klassen, weights=gewichte, edgecolor="white")');
        yTitle = 'relative Häufigkeit in %';
      } else {
        c('plt.hist(werte, bins=klassen, edgecolor="white")');
        yTitle = 'absolute Häufigkeit';
      }
      if (bins.length <= 13) c('plt.xticks(klassen)');
      xTitle = h[spec.y_col]; grid = 'y';
    } else {   // Boxplot – eigene Kennwerte, matplotlib würde die Quartile anders interpolieren
      if (cat !== null) {
        c('boxen = []');
        c('for name in namen:');
        c('k = kennwerte(gruppen[name])', 1);
        c('k["label"] = f"{name} (n={len(gruppen[name])})"', 1);
        c('boxen.append(k)', 1);
        xTitle = h[cat];
      } else {
        c('k = kennwerte(werte)');
        c(`k["label"] = ${q(h[spec.y_col])}`);
        c('boxen = [k]');
      }
      c('kaesten = plt.gca().bxp(boxen, patch_artist=True)   # Boxplots aus den Kennwerten');
      c('for kasten, farbe in zip(kaesten["boxes"], FARBEN * 10):');
      c('kasten.set_facecolor(farbe)', 1);
      c('kasten.set_alpha(0.5)', 1);
      yTitle = h[spec.y_col]; grid = 'y';
    }

    c();
    if (xTitle) c(`plt.xlabel(${q(xTitle)})`);
    if (yTitle) c(`plt.ylabel(${q(yTitle)})`);
    c(`plt.title(${q(t)})`);
    if (grid === 'both') c('plt.grid(True, alpha=0.3)');
    else if (grid) c(`plt.grid(axis="${grid}", alpha=0.3)`);
    c('plt.tight_layout()');
    c('plt.show()');
    return lines.join('\n').replace(/\s+$/, '') + '\n';
  }

  return {
    toFloat, roundTo, formatG, pyRepr, fmtNum,
    splitCSV, sniffDelimiter, parseCSV, numericColumns,
    median, quartiles, STAT_LABELS, describe, tukeyWhiskers, linearRegression,
    regressionText, niceStep, histogramBins, cumulate, AGGREGATIONS, aggregate, niceTicks,
    ALTERNATIVES, lgamma, betainc, tCdf, tPpf, binomPmf, binomialTest, oneSampleT,
    twoSampleT, pairedT, TestError, COLORS, generateCode,
  };
});
