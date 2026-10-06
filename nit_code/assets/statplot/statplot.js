'use strict';
// ════════════════════════════════════════════════════════════
// StatPlot – CSV-Daten darstellen, beschreiben und testen
//
// Schwesterprojekt zu PAP Editor und IBD Editor (gleiche Bedienung, gleiches
// Aussehen). Ursprünglich die „Datenauswertung“ in NIT_Code; NIT_Code bettet
// diese Seite inzwischen per iframe (?embed=1) ein.
//
// Rechnen: stats.js (ohne DOM, mit Node getestet). Hier: Oberfläche,
// Diagramme als SVG (Anzeige und SVG/PNG-Export sind dieselbe Zeichenroutine),
// Tabellen, Statistik-Tests, Einbettung und Desktop-Anbindung.
// ════════════════════════════════════════════════════════════

const APP_VERSION = '1.0.0';
const GITHUB_REPO = 'juchemGDG/StatPlot';   // Quelle der Desktop-Pakete (leer = nur downloads/)
const S = window.StatCore;

// ── Farben (wie PAP/IBD) ─────────────────────────────────────
const C = {
  plotBg: '#ffffff', grid: '#e2e8f0', text: '#0f172a', textDim: '#64748b',
  accent: '#2563eb', ok: '#16a34a', warn: '#d97706',
};
const FONT = 'Helvetica, Arial, sans-serif';
const AXIS_SIZE = 11, TITLE_SIZE = 12;
const CAT_COLORS = S.COLORS;

const MAX_POINTS = 20000;      // Schutz vor zu vielen Punkten
const MAX_GROUPS = 60;         // höchstens so viele Säulen/Boxplots
const MAX_FREQ_ROWS = 100;     // Häufigkeitstabelle nur für überschaubare Werte
const MAX_TABLE_ROWS = 2000;   // Rohdatentabelle nicht endlos befüllen

const SCATTER = 'Streudiagramm', LINE = 'Liniendiagramm', COLUMN = 'Säulendiagramm',
  BAR = 'Balkendiagramm', PIE = 'Kreisdiagramm', HIST = 'Histogramm', BOX = 'Boxplot';
const CHART_TYPES = [SCATTER, LINE, COLUMN, BAR, PIE, HIST, BOX];
const GROUP_CHARTS = [COLUMN, BAR, PIE];

// Symbole (24×24, Strich) – dieselben wie in NIT_Code
const ICONS = {
  open: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  [SCATTER]: '<path d="M4 4v16h16"/><circle cx="8.5" cy="15" r="1.4"/><circle cx="11.5" cy="10.5" r="1.4"/><circle cx="15" cy="13" r="1.4"/><circle cx="18" cy="7" r="1.4"/>',
  [LINE]: '<path d="M4 4v16h16"/><path d="M7 16l4-5 3 2.5 5-6.5"/>',
  [COLUMN]: '<path d="M4 4v16h16"/><rect x="7" y="11" width="3" height="6" rx=".5"/><rect x="12" y="7" width="3" height="10" rx=".5"/><rect x="17" y="13" width="3" height="4" rx=".5"/>',
  [BAR]: '<path d="M4 4v16h16"/><rect x="7" y="6" width="8" height="3" rx=".5"/><rect x="7" y="11" width="12" height="3" rx=".5"/><rect x="7" y="16" width="5" height="1" rx=".5"/>',
  [PIE]: '<path d="M11 4a8 8 0 1 0 8 8h-8z"/><path d="M14 2.5a8 8 0 0 1 7 7h-7z"/>',
  [HIST]: '<path d="M3 20h18"/><path d="M5 20v-5h4v5M9 20V8h4v12M13 20v-9h4v9M17 20v-3h3v3"/>',
  [BOX]: '<path d="M12 3v4M12 17v4M9 3h6M9 21h6"/><rect x="7" y="7" width="10" height="10" rx="1"/><path d="M7 12h10"/>',
};
const TYPE_HINTS = {
  [SCATTER]: 'Zusammenhang zweier Größen',
  [LINE]: 'Verlauf, z. B. über die Zeit',
  [COLUMN]: 'Anzahl oder Wert je Kategorie',
  [BAR]: 'wie Säulen – gut bei langen Namen',
  [PIE]: 'Anteile am Ganzen',
  [HIST]: 'Verteilung in Klassen',
  [BOX]: 'Median, Quartile, Streuung',
};
const CAT_LABELS = {
  [SCATTER]: 'Kategorie (färbt die Punkte)', [LINE]: 'Kategorie (eine Linie je Wert)',
  [COLUMN]: 'Kategorie (eine Säule je Wert)', [BAR]: 'Kategorie (ein Balken je Wert)',
  [PIE]: 'Kategorie (ein Kreisstück je Wert)', [BOX]: 'Gruppierung (optional)', [HIST]: 'Kategorie',
};

// ── Zustand ──────────────────────────────────────────────────
const state = {
  headers: [], rows: [], numCols: [],
  fileName: '', path: '', csvText: '',
  info: { delimiter: ';', header: true },
  chartType: SCATTER, xCol: null, yCol: null, valueCol: null, catCol: null,
  agg: 'Mittelwert', binWidth: 0, histRelative: false, regression: false,
  outliers: false, boxLabels: false,
};
let activeTab = 'table';

// ── Hilfen ───────────────────────────────────────────────────
const byId = id => document.getElementById(id);
const on = (id, ev, fn) => { const el = byId(id); if (el) el.addEventListener(ev, fn); };
function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
const r1 = v => Math.round(v * 100) / 100;
const fmt = (v, d) => S.fmtNum(v, d);
const catName = name => (name ? name : '(leer)');

function setStatus(msg, kind) {
  const el = byId('status');
  if (!el) return;
  el.textContent = msg;
  el.title = msg;
  el.className = kind || '';
}

let measCtx = null;
function textW(text, size, bold) {
  if (!measCtx) measCtx = document.createElement('canvas').getContext('2d');
  measCtx.font = `${bold ? 'bold ' : ''}${size}px ${FONT}`;
  return measCtx.measureText(String(text)).width;
}
/** Text mit „…“ kürzen, bis er in maxW passt (wie Qt elidedText). */
function elide(text, size, maxW, bold) {
  text = String(text);
  if (maxW <= 0) return '';
  if (textW(text, size, bold) <= maxW) return text;
  let lo = 0, hi = text.length;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (textW(text.slice(0, mid) + '…', size, bold) <= maxW) lo = mid; else hi = mid - 1;
  }
  return lo ? text.slice(0, lo) + '…' : '';
}
/** Farbe abdunkeln wie QColor.darker(factor). */
function darker(hex, factor) {
  const n = parseInt(hex.slice(1), 16);
  const f = 100 / factor;
  const ch = s => Math.round(((n >> s) & 255) * f);
  return `rgb(${ch(16)},${ch(8)},${ch(0)})`;
}

// ── Daten für die Diagramme ──────────────────────────────────
function columnValues(col) {
  const out = [];
  for (const r of state.rows) { const v = S.toFloat(r[col]); if (v !== null) out.push(v); }
  return out;
}

/** Vorkommende Kategorien – numerisch sortiert, falls alle Zahlen sind. */
function categoryOrder() {
  if (state.catCol === null) return [];
  const seen = new Set(), order = [];
  for (const r of state.rows) {
    const v = r[state.catCol].trim();
    if (!seen.has(v)) { seen.add(v); order.push(v); }
  }
  if (order.length && order.every(v => S.toFloat(v) !== null)) order.sort((a, b) => S.toFloat(a) - S.toFloat(b));
  return order;
}

function categoryColorMap() {
  const m = new Map();
  categoryOrder().forEach((name, i) => m.set(name, CAT_COLORS[i % CAT_COLORS.length]));
  return m;
}

/** Zahlenwerte einer Spalte je Kategorie → [[name, werte], …] */
function groupedValues(col) {
  const groups = new Map(categoryOrder().map(n => [n, []]));
  for (const r of state.rows) {
    const v = S.toFloat(r[col]);
    if (v !== null) groups.get(r[state.catCol].trim()).push(v);
  }
  return [...groups.entries()];
}

function xyPoints() {
  const pts = [];
  for (const r of state.rows) {
    const x = S.toFloat(r[state.xCol]), y = S.toFloat(r[state.yCol]);
    if (x === null || y === null) continue;
    pts.push([x, y, state.catCol !== null ? r[state.catCol].trim() : null]);
    if (pts.length >= MAX_POINTS) break;
  }
  return pts;
}

/** [Kategorie, Höhe] – Anzahl der Zeilen oder zusammengefasste Werte. */
function barData() {
  if (state.valueCol === null) {
    const counts = new Map(categoryOrder().map(n => [n, 0]));
    for (const r of state.rows) { const k = r[state.catCol].trim(); counts.set(k, counts.get(k) + 1); }
    return [...counts.entries()];
  }
  const how = state.chartType === PIE ? 'Summe' : state.agg;
  const out = [];
  for (const [name, vals] of groupedValues(state.valueCol)) {
    const v = S.aggregate(vals, how);
    if (v !== null) out.push([name, v]);
  }
  return out;
}

function valueTitle() {
  if (state.valueCol === null) return 'Anzahl';
  const how = state.chartType === PIE ? 'Summe' : state.agg;
  return `${how} von ${state.headers[state.valueCol]}`;
}

/** [[kategorie, [m, b, r²], xMin, xMax], …] – je Kategorie oder gesamt. */
function regressionLines() {
  const groups = new Map();
  for (const [x, y, cat] of xyPoints()) {
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push([x, y]);
  }
  const out = [];
  for (const [cat, pts] of groups) {
    const xs = pts.map(p => p[0]);
    const reg = S.linearRegression(xs, pts.map(p => p[1]));
    if (reg) out.push([cat, reg, Math.min(...xs), Math.max(...xs)]);
  }
  return out;
}

const histBins = () => S.histogramBins(columnValues(state.yCol), state.binWidth);

function boxGroups() {
  if (state.catCol === null) return [[state.headers[state.yCol], columnValues(state.yCol)]];
  return groupedValues(state.yCol);
}

// ════════════════════════════════════════════════════════════
// Diagramme (SVG)
// ════════════════════════════════════════════════════════════
class Svg {
  constructor(w, h) { this.w = w; this.h = h; this.out = []; this.clipN = 0; }
  add(s) { this.out.push(s); }
  line(x1, y1, x2, y2, stroke, sw, extra) {
    this.add(`<line x1="${r1(x1)}" y1="${r1(y1)}" x2="${r1(x2)}" y2="${r1(y2)}" stroke="${stroke}" stroke-width="${sw || 1}"${extra || ''}/>`);
  }
  rect(x, y, w, h, fill, extra, tip) {
    if (w < 0) { x += w; w = -w; }
    if (h < 0) { y += h; h = -h; }
    const head = `<rect x="${r1(x)}" y="${r1(y)}" width="${r1(w)}" height="${r1(h)}" fill="${fill}"${extra || ''}`;
    this.add(tip ? `${head}><title>${esc(tip)}</title></rect>` : head + '/>');
  }
  circle(cx, cy, r, fill, stroke, sw) {
    this.add(`<circle cx="${r1(cx)}" cy="${r1(cy)}" r="${r}" fill="${fill}"${stroke ? ` stroke="${stroke}" stroke-width="${sw || 1}"` : ''}/>`);
  }
  /** Text, vertikal um y zentriert. anchor: start | middle | end */
  text(x, y, str, opt) {
    opt = opt || {};
    const size = opt.size || AXIS_SIZE;
    const tr = opt.rotate ? ` transform="rotate(${opt.rotate} ${r1(x)} ${r1(y)})"` : '';
    this.add(`<text x="${r1(x)}" y="${r1(y + size * 0.35)}" font-size="${size}"${opt.bold ? ' font-weight="bold"' : ''}`
      + ` text-anchor="${opt.anchor || 'start'}" fill="${opt.color || C.text}"${tr}>${esc(str)}</text>`);
  }
  clipStart(x, y, w, h) {
    const id = 'clip' + (++this.clipN);
    this.add(`<clipPath id="${id}"><rect x="${r1(x)}" y="${r1(y)}" width="${r1(w)}" height="${r1(h)}"/></clipPath><g clip-path="url(#${id})">`);
  }
  clipEnd() { this.add('</g>'); }
  toString() {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${this.w}" height="${this.h}" viewBox="0 0 ${this.w} ${this.h}"`
      + ` font-family="${FONT}"><rect width="100%" height="100%" fill="${C.plotBg}"/>${this.out.join('')}</svg>`;
  }
}

/** Zeichenbereich [left, top, pw, ph] – links Platz für die Y-Beschriftung. */
function plotArea(g, yLabels, bottom) {
  if (bottom === undefined) bottom = 34;
  const lw = yLabels.length ? Math.max(...yLabels.map(s => textW(s, AXIS_SIZE))) : 20;
  const left = lw + 28, right = 14, top = 14;
  const pw = g.w - left - right, ph = g.h - top - bottom;
  if (pw <= 20 || ph <= 20) return null;
  return [left, top, pw, ph];
}

function gridY(g, area, lo, hi, ticks, labels) {
  const [left, top, pw, ph] = area;
  ticks.forEach((t, i) => {
    const y = top + ph - (t - lo) / (hi - lo) * ph;
    g.line(left, y, left + pw, y, C.grid, 1);
    g.text(left - 6, y, labels ? labels[i] : fmt(t), { anchor: 'end', color: C.textDim });
  });
}

function gridX(g, area, lo, hi, ticks) {
  const [left, top, pw, ph] = area;
  for (const t of ticks) {
    const x = left + (t - lo) / (hi - lo) * pw;
    g.line(x, top, x, top + ph, C.grid, 1);
    g.text(x, top + ph + 10, fmt(t), { anchor: 'middle', color: C.textDim });
  }
}

function titles(g, area, xTitle, yTitle) {
  const [left, top, pw, ph] = area;
  if (xTitle) g.text(left + pw / 2, g.h - 9, elide(xTitle, TITLE_SIZE, pw, true), { anchor: 'middle', size: TITLE_SIZE, bold: true });
  if (yTitle) g.text(11, top + ph / 2, elide(yTitle, TITLE_SIZE, ph, true), { anchor: 'middle', size: TITLE_SIZE, bold: true, rotate: -90 });
}

function legend(g, area, items) {
  const [left, top] = area;
  const lx = left + 8, ly0 = top + 6;
  const shown = items.slice(0, 15);
  const width = Math.max(...shown.map(([name]) => textW(catName(name), TITLE_SIZE))) + 24;
  g.rect(lx - 4, ly0 - 3, width, shown.length * 16 + 4, C.plotBg, ' fill-opacity="0.78"');
  shown.forEach(([name, color], i) => {
    const ly = ly0 + i * 16;
    g.rect(lx, ly, 10, 10, color);
    g.text(lx + 16, ly + 5, catName(name), { size: TITLE_SIZE });
  });
}

function note(g, text) { g.text(g.w - 16, 9, text, { anchor: 'end', color: C.textDim }); }

function centerText(g, msg) {
  const lines = msg.split('\n');
  const lh = TITLE_SIZE * 1.4;
  const y0 = g.h / 2 - (lines.length - 1) * lh / 2;
  lines.forEach((l, i) => g.text(g.w / 2, y0 + i * lh, l, { anchor: 'middle', size: TITLE_SIZE, color: C.textDim }));
}

// ── Streu- / Liniendiagramm ──────────────────────────────────
function drawXY(g) {
  if (state.xCol === null || state.yCol === null) return 'Bitte zwei numerische Spalten für X und Y wählen.';
  const pts = xyPoints();
  if (!pts.length) return 'Keine gültigen Zahlenpaare in den gewählten Spalten.';
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  for (const [x, y] of pts) {
    if (x < xmin) xmin = x; if (x > xmax) xmax = x;
    if (y < ymin) ymin = y; if (y > ymax) ymax = y;
  }
  const [xlo, xhi, xt] = S.niceTicks(xmin, xmax, 5, 0.03);
  const [ylo, yhi, yt] = S.niceTicks(ymin, ymax, 5, 0.03);
  const area = plotArea(g, yt.map(t => fmt(t)));
  if (!area) return null;
  const [left, top, pw, ph] = area;
  gridY(g, area, ylo, yhi, yt);
  gridX(g, area, xlo, xhi, xt);
  titles(g, area, state.headers[state.xCol], state.headers[state.yCol]);
  const ax = x => left + (x - xlo) / (xhi - xlo) * pw;
  const ay = y => top + ph - (y - ylo) / (yhi - ylo) * ph;

  const catColor = categoryColorMap();
  const colorOf = cat => catColor.get(cat) || C.accent;
  g.clipStart(left, top, pw, ph);
  if (state.chartType === LINE) {
    const series = new Map();
    for (const [x, y, cat] of pts) { if (!series.has(cat)) series.set(cat, []); series.get(cat).push([x, y]); }
    for (const [cat, sp] of series) {
      sp.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
      g.add(`<polyline points="${sp.map(([x, y]) => r1(ax(x)) + ',' + r1(ay(y))).join(' ')}" fill="none" stroke="${colorOf(cat)}" stroke-width="2" stroke-linejoin="round"/>`);
    }
  }
  const r = state.chartType === LINE ? 2.5 : 3;
  for (const [x, y, cat] of pts) {
    const color = colorOf(cat);
    g.circle(ax(x), ay(y), r, color, darker(color, 120), 1);
  }
  let items = [...catColor.entries()];
  if (state.chartType === SCATTER && state.regression) {
    items = [];
    for (const [cat, [m, b, r2], x0, x1] of regressionLines()) {
      const color = colorOf(cat);
      g.line(ax(x0), ay(m * x0 + b), ax(x1), ay(m * x1 + b), color, 2, ' stroke-dasharray="8 4"');
      const eq = S.regressionText(m, b, r2);
      items.push([cat !== null ? `${catName(cat)}: ${eq}` : eq, color]);
    }
  }
  g.clipEnd();
  if (items.length) legend(g, area, items);
  return null;
}

// ── Säulen- / Balkendiagramm ─────────────────────────────────
function drawBars(g) {
  if (state.catCol === null) return 'Bitte eine Kategorie-Spalte wählen – je Kategorie entsteht eine Säule.';
  let data = barData();
  if (!data.length) return 'Keine gültigen Werte für die gewählten Spalten.';
  if (data.length > MAX_GROUPS) { data = data.slice(0, MAX_GROUPS); note(g, `nur die ersten ${MAX_GROUPS} Kategorien`); }
  const vals = data.map(d => d[1]);
  const [lo, hi, ticks] = S.niceTicks(Math.min(0, ...vals), Math.max(0, ...vals));
  const catColor = categoryColorMap();
  const colorOf = name => catColor.get(name) || C.accent;
  const n = data.length;

  if (state.chartType === COLUMN) {
    const area = plotArea(g, ticks.map(t => fmt(t)));
    if (!area) return null;
    const [left, top, pw, ph] = area;
    gridY(g, area, lo, hi, ticks);
    titles(g, area, state.headers[state.catCol], valueTitle());
    const ay = v => top + ph - (v - lo) / (hi - lo) * ph;
    const slot = pw / n;
    data.forEach(([name, v], i) => {
      const x0 = left + i * slot, bw = slot * 0.7;
      const y0 = Math.min(ay(0), ay(v)), y1 = Math.max(ay(0), ay(v));
      g.rect(x0 + (slot - bw) / 2, y0, bw, y1 - y0, colorOf(name), '', `${catName(name)}: ${fmt(v)}`);
      g.text(x0 + slot / 2, top + ph + 10, elide(catName(name), AXIS_SIZE, slot - 2), { anchor: 'middle', color: C.textDim });
      if (slot >= 28) g.text(x0 + slot / 2, v >= 0 ? y0 - 7 : y1 + 7, fmt(v, 2), { anchor: 'middle' });
    });
    return null;
  }

  // Balkendiagramm (waagrecht): Kategorien links, Werte unten
  const lw = Math.min(160, Math.max(...data.map(([name]) => textW(catName(name), AXIS_SIZE))));
  const left = lw + 14, right = 40, top = 14, bottom = 34;
  const pw = g.w - left - right, ph = g.h - top - bottom;
  if (pw <= 20 || ph <= 20) return null;
  const area = [left, top, pw, ph];
  gridX(g, area, lo, hi, ticks);
  titles(g, area, valueTitle(), null);
  const ax = v => left + (v - lo) / (hi - lo) * pw;
  const slot = ph / n;
  data.forEach(([name, v], i) => {
    const y0 = top + i * slot, bh = slot * 0.7;
    const x0 = Math.min(ax(0), ax(v)), x1 = Math.max(ax(0), ax(v));
    g.rect(x0, y0 + (slot - bh) / 2, x1 - x0, bh, colorOf(name), '', `${catName(name)}: ${fmt(v)}`);
    g.text(left - 6, y0 + slot / 2, elide(catName(name), AXIS_SIZE, lw), { anchor: 'end', color: C.textDim });
    if (slot >= 14) g.text(x1 + 4, y0 + slot / 2, fmt(v, 2));
  });
  return null;
}

// ── Kreisdiagramm ────────────────────────────────────────────
function drawPie(g) {
  if (state.catCol === null) return 'Bitte eine Kategorie-Spalte wählen – je Kategorie entsteht ein Kreisausschnitt.';
  let data = barData().filter(d => d[1]);
  if (!data.length) return 'Keine gültigen Werte für die gewählten Spalten.';
  if (data.some(d => d[1] < 0)) return 'Ein Kreisdiagramm geht nur mit Werten ≥ 0.';
  if (data.length > MAX_GROUPS) { data = data.slice(0, MAX_GROUPS); note(g, `nur die ersten ${MAX_GROUPS} Kategorien`); }
  const total = data.reduce((a, d) => a + d[1], 0);
  const catColor = categoryColorMap();
  const colorOf = name => catColor.get(name) || C.accent;

  // Kreis links, Legende (Name, Wert, Anteil) rechts daneben
  const texts = data.map(([name, v]) => `${catName(name)}: ${fmt(v, 2)} (${fmt(v / total * 100, 1)} %)`);
  const lw = Math.min(260, Math.max(...texts.map(s => textW(s, TITLE_SIZE))) + 30);
  const d = Math.min(g.w - lw - 40, g.h - 40);
  if (d < 40) return null;
  const cx0 = 20, cy0 = (g.h - d) / 2, rad = d / 2, cx = cx0 + rad, cy = cy0 + rad;
  const pt = (deg, rr) => [cx + Math.cos(deg * Math.PI / 180) * rr, cy - Math.sin(deg * Math.PI / 180) * rr];
  let start = 90;                         // 12 Uhr, dann im Uhrzeigersinn
  const labels = [];
  data.forEach(([name, v]) => {
    const span = -v / total * 360;
    const color = colorOf(name);
    const tip = `<title>${esc(catName(name))}: ${esc(fmt(v))}</title>`;
    if (Math.abs(span) >= 359.999) {
      g.add(`<circle cx="${r1(cx)}" cy="${r1(cy)}" r="${r1(rad)}" fill="${color}" stroke="${C.plotBg}" stroke-width="1.5">${tip}</circle>`);
    } else {
      const [x1, y1] = pt(start, rad), [x2, y2] = pt(start + span, rad);
      const large = Math.abs(span) > 180 ? 1 : 0;
      g.add(`<path d="M${r1(cx)} ${r1(cy)}L${r1(x1)} ${r1(y1)}A${r1(rad)} ${r1(rad)} 0 ${large} 1 ${r1(x2)} ${r1(y2)}Z" fill="${color}" stroke="${C.plotBg}" stroke-width="1.5" stroke-linejoin="round">${tip}</path>`);
    }
    const share = v / total;
    if (share >= 0.05) {                  // Prozentangabe nur bei genug Platz
      const [tx, ty] = pt(start + span / 2, d * 0.33);
      labels.push([tx, ty, `${fmt(share * 100, 1)} %`]);
    }
    start += span;
  });
  for (const [tx, ty, s] of labels) g.text(tx, ty, s, { anchor: 'middle', size: TITLE_SIZE, bold: true, color: '#ffffff' });

  const lx = cx0 + d + 24;
  const shown = data.slice(0, 20);
  let ly = Math.max(10, (g.h - shown.length * 18) / 2);
  shown.forEach(([name], i) => {
    g.rect(lx, ly + 2, 10, 10, colorOf(name));
    g.text(lx + 16, ly + 8, elide(texts[i], TITLE_SIZE, Math.min(lw, g.w - lx - 20)), { size: TITLE_SIZE });
    ly += 18;
  });
  g.text(lx, 12, elide(valueTitle(), TITLE_SIZE, g.w - lx - 8), { size: TITLE_SIZE, color: C.textDim });
  return null;
}

// ── Histogramm ───────────────────────────────────────────────
function drawHist(g) {
  if (state.yCol === null) return 'Bitte eine numerische Variable wählen.';
  const bins = histBins();
  if (!bins.length) return 'Keine Zahlenwerte in der gewählten Spalte.';
  const total = bins.reduce((a, b) => a + b[2], 0);
  const heights = bins.map(b => (state.histRelative ? b[2] / total : b[2]));
  const [ylo, yhi, yt] = S.niceTicks(0, Math.max(...heights));
  const yLabels = yt.map(t => (state.histRelative ? fmt(t * 100, 1) + ' %' : fmt(t)));
  const area = plotArea(g, yLabels);
  if (!area) return null;
  const [left, top, pw, ph] = area;
  const xlo = bins[0][0], xhi = bins[bins.length - 1][1];
  let xt;
  if (bins.length <= 12) xt = bins.map(b => b[0]).concat([xhi]);
  else xt = S.niceTicks(xlo, xhi, 8)[2].filter(t => xlo - 1e-9 <= t && t <= xhi + 1e-9);
  gridY(g, area, ylo, yhi, yt, yLabels);
  for (const t of xt) g.text(left + (t - xlo) / (xhi - xlo) * pw, top + ph + 10, fmt(t), { anchor: 'middle', color: C.textDim });
  titles(g, area, state.headers[state.yCol], state.histRelative ? 'relative Häufigkeit' : 'absolute Häufigkeit');
  bins.forEach(([a, b, c], i) => {
    const x0 = left + (a - xlo) / (xhi - xlo) * pw;
    const x1 = left + (b - xlo) / (xhi - xlo) * pw;
    const y = top + ph - (heights[i] - ylo) / (yhi - ylo) * ph;
    const last = i === bins.length - 1 ? ']' : '[';
    g.rect(x0, y, x1 - x0, top + ph - y, C.accent, ` stroke="${C.plotBg}" stroke-width="1"`, `[${fmt(a)}; ${fmt(b)}${last}: ${c}`);
  });
  return null;
}

// ── Boxplot ──────────────────────────────────────────────────
/** [Wert, Text] für die Boxplot-Beschriftung, von oben nach unten. */
function boxLabelItems(s) {
  const out = s.outliers.length > 0;
  return [
    [s.w_hi, out ? fmt(s.w_hi) : `Max ${fmt(s.w_hi)}`],
    [s.q3, `q₃ ${fmt(s.q3)}`],
    [s.median, `Median ${fmt(s.median)}`],
    [s.q1, `q₁ ${fmt(s.q1)}`],
    [s.w_lo, out ? fmt(s.w_lo) : `Min ${fmt(s.w_lo)}`],
  ];
}

function labelBox(g, cx, bw, slot, s, ay) {
  const x = cx + bw / 2 + 6;
  const width = Math.max(20, slot / 2 - bw / 2 - 8);
  let lastY = null;
  for (const [v, text] of boxLabelItems(s)) {
    const y = ay(v);
    if (lastY !== null && y - lastY < 12) continue;   // nicht überlappen
    g.text(x, y, elide(text, AXIS_SIZE, width));
    lastY = y;
  }
  // Mittelwert als Raute + Beschriftung links
  const ym = ay(s.mean);
  g.add(`<polygon points="${r1(cx)},${r1(ym - 5)} ${r1(cx + 5)},${r1(ym)} ${r1(cx)},${r1(ym + 5)} ${r1(cx - 5)},${r1(ym)}" fill="${C.text}"/>`);
  g.text(cx - bw / 2 - 6, ym, elide(`x̄ ${fmt(s.mean)}`, AXIS_SIZE, Math.max(0, slot / 2 - bw / 2 - 6)), { anchor: 'end' });
}

function drawBox(g) {
  if (state.yCol === null) return 'Bitte eine numerische Variable wählen.';
  let groups = [];
  for (const [name, vals] of boxGroups()) {
    if (!vals.length) continue;
    const s = S.describe(vals);
    if (state.outliers) [s.w_lo, s.w_hi, s.outliers] = S.tukeyWhiskers(vals, s.q1, s.q3);
    else [s.w_lo, s.w_hi, s.outliers] = [s.min, s.max, []];
    groups.push([name, s]);
  }
  if (!groups.length) return 'Keine Zahlenwerte in der gewählten Spalte.';
  if (groups.length > MAX_GROUPS) { groups = groups.slice(0, MAX_GROUPS); note(g, `nur die ersten ${MAX_GROUPS} Gruppen`); }
  const [lo, hi, ticks] = S.niceTicks(Math.min(...groups.map(x => x[1].min)), Math.max(...groups.map(x => x[1].max)), 5, 0.03);
  const area = plotArea(g, ticks.map(t => fmt(t)));
  if (!area) return null;
  const [left, top, pw, ph] = area;
  gridY(g, area, lo, hi, ticks);
  titles(g, area, state.catCol !== null ? state.headers[state.catCol] : null, state.headers[state.yCol]);
  const ay = v => top + ph - (v - lo) / (hi - lo) * ph;
  const catColor = categoryColorMap();
  const slot = pw / groups.length;
  const bw = Math.min(slot * 0.5, 90);
  groups.forEach(([name, s], i) => {
    const cx = left + (i + 0.5) * slot;
    const color = catColor.get(name) || C.accent;
    // Antennen + Endstriche (bis Min/Max oder nach 1,5·IQR-Regel)
    g.line(cx, ay(s.w_lo), cx, ay(s.q1), color, 2);
    g.line(cx, ay(s.q3), cx, ay(s.w_hi), color, 2);
    for (const v of s.outliers) g.circle(cx, ay(v), 3.5, 'none', color, 2);
    for (const k of ['w_lo', 'w_hi']) g.line(cx - bw / 4, ay(s[k]), cx + bw / 4, ay(s[k]), color, 2);
    // Kasten q1..q3 mit Median
    const y3 = ay(s.q3), y1 = ay(s.q1);
    g.rect(cx - bw / 2, y3, bw, y1 - y3, color, ` fill-opacity="0.27" stroke="${color}" stroke-width="2"`);
    g.line(cx - bw / 2, ay(s.median), cx + bw / 2, ay(s.median), C.text, 2.5);
    if (state.boxLabels) labelBox(g, cx, bw, slot, s, ay);
    g.text(cx, top + ph + 10, elide(`${catName(name)} (n=${s.n})`, AXIS_SIZE, slot - 2), { anchor: 'middle', color: C.textDim });
  });
  return null;
}

/** Komplettes Diagramm als SVG-Text in der Größe w × h. */
function buildChartSVG(w, h) {
  const g = new Svg(Math.max(1, Math.round(w)), Math.max(1, Math.round(h)));
  if (!state.headers.length) {
    centerText(g, 'Noch keine Daten geladen.\n\nLinks auf „CSV öffnen …“ tippen, eine CSV-Datei\nhierher ziehen oder „Beispieldaten“ wählen.');
    return g.toString();
  }
  const draw = {
    [SCATTER]: drawXY, [LINE]: drawXY, [COLUMN]: drawBars, [BAR]: drawBars,
    [PIE]: drawPie, [HIST]: drawHist, [BOX]: drawBox,
  }[state.chartType];
  const msg = draw(g);
  if (msg) centerText(g, msg);
  return g.toString();
}

function chartSize() {
  const box = byId('chart-box');
  return [box.clientWidth || 800, box.clientHeight || 500];
}

let renderQueued = false;
function renderChart() {
  if (renderQueued) return;
  renderQueued = true;
  requestAnimationFrame(() => {
    renderQueued = false;
    const [w, h] = chartSize();
    byId('chart-box').innerHTML = buildChartSVG(w, h).replace('<svg ', '<svg id="chart" ');
  });
}

// ════════════════════════════════════════════════════════════
// Tabellen
// ════════════════════════════════════════════════════════════
function fillDataTable() {
  const t = byId('tbl-data');
  if (!state.headers.length) { t.innerHTML = ''; return; }
  const shown = state.rows.slice(0, MAX_TABLE_ROWS);
  let h = '<thead><tr><th></th>' + state.headers.map(x => `<th>${esc(x)}</th>`).join('') + '</tr></thead><tbody>';
  const num = new Set(state.numCols);
  shown.forEach((row, i) => {
    h += `<tr><th>${i + 1}</th>` + row.map((v, c) => `<td${num.has(c) ? ' class="num"' : ''}>${esc(v)}</td>`).join('') + '</tr>';
  });
  h += '</tbody>';
  t.innerHTML = h;
  const wrap = t.parentElement;
  const old = wrap.querySelector('.table-note');
  if (old) old.remove();
  if (state.rows.length > MAX_TABLE_ROWS) {
    wrap.insertAdjacentHTML('beforeend', `<div class="table-note">Angezeigt: die ersten ${MAX_TABLE_ROWS} von ${state.rows.length} Zeilen – Diagramme und Kennwerte nutzen alle.</div>`);
  }
}

function fillStats() {
  const t = state.chartType;
  let columns = [], caption = '';
  if (!state.headers.length) {
    // nichts
  } else if (t === SCATTER || t === LINE) {
    columns = [state.xCol, state.yCol].filter(c => c !== null).map(c => [state.headers[c], columnValues(c)]);
    caption = 'Kennwerte der X- und Y-Spalte';
    if (t === SCATTER && state.regression) {
      const lines = regressionLines().map(([cat, reg]) => (cat !== null ? `${catName(cat)}: ` : '') + S.regressionText(...reg));
      caption += ' · Ausgleichsgerade ' + (lines.length ? lines.join('; ') : '–');
    }
  } else if (GROUP_CHARTS.includes(t) && state.valueCol === null) {
    caption = 'Bei „Anzahl“ gibt es keine Kennwerte – siehe Reiter Häufigkeiten.';
  } else {
    const col = GROUP_CHARTS.includes(t) ? state.valueCol : state.yCol;
    if (col !== null) {
      caption = `Kennwerte für „${state.headers[col]}“`;
      columns = [['Gesamt', columnValues(col)]];
      if (state.catCol !== null && t !== HIST) {
        caption += `, gruppiert nach „${state.headers[state.catCol]}“`;
        columns = columns.concat(groupedValues(col).slice(0, MAX_GROUPS).map(([name, v]) => [catName(name), v]));
      }
    }
  }
  byId('cap-stats').textContent = caption;
  const tbl = byId('tbl-stats');
  if (!columns.length) { tbl.innerHTML = ''; return; }
  const stats = columns.map(([, v]) => S.describe(v));
  let h = '<thead><tr><th></th>' + columns.map(([name]) => `<th>${esc(name)}</th>`).join('') + '</tr></thead><tbody>';
  for (const [key, label] of S.STAT_LABELS) {
    h += `<tr><th>${esc(label)}</th>` + stats.map(s => `<td class="num">${esc(fmt(s[key]))}</td>`).join('') + '</tr>';
  }
  tbl.innerHTML = h + '</tbody>';
}

function fillFreq() {
  const t = state.chartType;
  let rows = [], first = '', caption = '';
  if (!state.headers.length) {
    // nichts
  } else if (t === HIST && state.yCol !== null) {
    const bins = histBins();
    rows = S.cumulate(bins.map(([a, b, c], i) => [`[${fmt(a)}; ${fmt(b)}${i === bins.length - 1 ? ']' : '['}`, c]));
    first = 'Klasse';
    if (bins.length) caption = `Klassen von „${state.headers[state.yCol]}“, Klassenbreite ${fmt(bins[0][1] - bins[0][0])}`;
  } else if (state.catCol !== null) {
    const counts = new Map(categoryOrder().map(n => [n, 0]));
    for (const r of state.rows) { const k = r[state.catCol].trim(); counts.set(k, counts.get(k) + 1); }
    rows = S.cumulate([...counts.entries()].map(([k, v]) => [catName(k), v]));
    first = state.headers[state.catCol];
    caption = `Häufigkeiten der Kategorie „${first}“`;
  } else {
    const col = GROUP_CHARTS.includes(t) ? state.valueCol : state.yCol;
    if (col !== null) {
      const counts = new Map();
      for (const v of columnValues(col)) counts.set(v, (counts.get(v) || 0) + 1);
      first = state.headers[col];
      if (counts.size > MAX_FREQ_ROWS) {
        caption = `„${first}“ hat ${counts.size} verschiedene Werte – für eine Übersicht das Histogramm verwenden.`;
      } else {
        rows = S.cumulate([...counts.entries()].sort((a, b) => a[0] - b[0]).map(([k, c]) => [fmt(k), c]));
        caption = `Häufigkeiten der Werte von „${first}“`;
      }
    }
  }
  if (rows.length > MAX_FREQ_ROWS) { caption += ` (nur die ersten ${MAX_FREQ_ROWS})`; rows = rows.slice(0, MAX_FREQ_ROWS); }
  byId('cap-freq').textContent = caption;
  const tbl = byId('tbl-freq');
  if (!rows.length) { tbl.innerHTML = ''; return; }
  let h = `<thead><tr><th>${esc(first || 'Wert')}</th><th>absolute H.</th><th>relative H.</th><th>kumuliert (rel.)</th></tr></thead><tbody>`;
  for (const [name, a, rel, cum] of rows) {
    h += `<tr><td>${esc(name)}</td><td class="num">${a}</td><td class="num">${esc(fmt(rel * 100, 1))} %</td><td class="num">${esc(fmt(cum * 100, 1))} %</td></tr>`;
  }
  tbl.innerHTML = h + '</tbody>';
}

/** Sichtbare Tabelle als tabulatorgetrennter Text. */
function tableTSV(tbl) {
  return [...tbl.rows].map(tr => [...tr.cells].map(c => c.textContent.replace(/\s+/g, ' ').trim()).join('\t')).join('\n');
}

function copyCurrentTable() {
  const id = { table: 'tbl-data', stats: 'tbl-stats', freq: 'tbl-freq' }[activeTab];
  if (!id) { setStatus('Im Reiter Statistik-Tests gibt es keine Tabelle zum Kopieren.'); return; }
  const tbl = byId(id);
  if (!tbl.rows.length) { setStatus('Die Tabelle ist leer.'); return; }
  copyText(tableTSV(tbl), 'Tabelle kopiert – z. B. in eine Tabellenkalkulation einfügen.');
}

function copyText(text, okMsg) {
  if (EMBED && hostCaps.clipboard) {        // Zwischenablage über die einbettende App
    embedSend({ event: 'copy', text }, embedOrigin);
    setStatus(okMsg, 'ok');
    return;
  }
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    ta.remove();
    setStatus(ok ? okMsg : 'Kopieren nicht möglich – bitte manuell markieren.', ok ? 'ok' : 'error');
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => setStatus(okMsg, 'ok'), fallback);
  } else fallback();
}

// ════════════════════════════════════════════════════════════
// Statistik-Tests
// ════════════════════════════════════════════════════════════
const BINOM = 'Signifikanztest (Binomialtest)', T1 = 't-Test: eine Stichprobe', T2 = 't-Test: zwei Stichproben';
const T2_WELCH = 'unabhängig (Welch)', T2_POOLED = 'unabhängig (gleiche Varianzen)', T2_PAIRED = 'verbunden (gepaart)';
const MAX_LEVELS = 50;

function fillSelect(sel, items, keep) {
  // items: [[value, text], …] oder Texte
  const old = keep ? sel.value : null;
  sel.innerHTML = items.map(it => {
    const [v, t] = Array.isArray(it) ? it : [it, it];
    return `<option value="${esc(v)}">${esc(t)}</option>`;
  }).join('');
  if (old !== null && [...sel.options].some(o => o.value === old)) sel.value = old;
}
const selVal = sel => (sel.value === '' ? null : Number(sel.value));

function looksLikeId(col) {
  const v = columnValues(col);
  return v.length > 2 && v.every((x, i) => i === 0 || x - v[i - 1] === 1);
}

function levels(col) {
  const seen = new Set(), out = [];
  for (const r of state.rows) {
    const v = r[col].trim();
    if (v && !seen.has(v)) { seen.add(v); out.push(v); }
  }
  return out.slice(0, MAX_LEVELS);
}

function initTests() {
  fillSelect(byId('t-test'), [BINOM, T1, T2]);
  fillSelect(byId('t-alt'), [['two-sided', 'zweiseitig (≠)'], ['less', 'linksseitig (<)'], ['greater', 'rechtsseitig (>)']]);
  fillSelect(byId('t2-kind'), [T2_WELCH, T2_POOLED, T2_PAIRED]);
  ['t-test', 't-alt', 'b-hit', 't1-col', 't2-val', 't2-a', 't2-b'].forEach(id => on(id, 'change', runTest));
  ['t-alpha', 'b-p0', 't1-mu0', 'b-n', 'b-k'].forEach(id => { on(id, 'change', runTest); on(id, 'input', runTestSoon); });
  on('b-col', 'change', onBinomCol);
  on('t2-kind', 'change', onGroupCol);
  on('t2-grp', 'change', onGroupCol);
  refreshTestColumns();
}

let testTimer = null;
function runTestSoon() { clearTimeout(testTimer); testTimer = setTimeout(runTest, 300); }

/** Nach dem Laden einer CSV: Spaltenlisten neu füllen. */
function refreshTestColumns() {
  const num = state.numCols, hd = state.headers;
  fillSelect(byId('b-col'), [['', '— manuell —']].concat(hd.map((h, i) => [i, h])));
  fillSelect(byId('t2-grp'), hd.map((h, i) => [i, h]));
  fillSelect(byId('t1-col'), num.map(i => [i, hd[i]]));
  fillSelect(byId('t2-val'), num.map(i => [i, hd[i]]));
  // Vorauswahl: keine reine Nummerierung (1, 2, 3, …) als Messgröße
  const measures = num.filter(i => !looksLikeId(i));
  const m0 = measures.length ? measures[0] : num[0];
  if (m0 !== undefined) { byId('t1-col').value = m0; byId('t2-val').value = m0; }
  // Gruppenspalte: bevorzugt eine nicht-numerische Spalte
  const textCols = hd.map((_, i) => i).filter(i => !num.includes(i));
  if (textCols.length) byId('t2-grp').value = textCols[0];
  onBinomCol(true);
  onGroupCol();
}

function onBinomCol(silent) {
  const col = selVal(byId('b-col'));
  fillSelect(byId('b-hit'), col === null ? [] : levels(col));
  if (silent !== true) runTest();
}

function onGroupCol() {
  const col = selVal(byId('t2-grp'));
  const kind = byId('t2-kind').value;
  const a = byId('t2-a'), b = byId('t2-b');
  if (kind === T2_PAIRED) {
    const num = state.numCols;
    fillSelect(a, num.map(i => [i, state.headers[i]]));
    fillSelect(b, num.map(i => [i, state.headers[i]]));
    const measures = num.filter(i => !looksLikeId(i));
    if (measures.length > 1) { a.value = measures[0]; b.value = measures[1]; }
    else if (b.options.length > 1) b.selectedIndex = 1;
  } else if (col !== null) {
    const lv = levels(col);
    fillSelect(a, lv); fillSelect(b, lv);
    if (lv.length > 1) b.selectedIndex = 1;
  } else { fillSelect(a, []); fillSelect(b, []); }
  runTest();
}

const pText = p => (p < 1e-4 ? '< 0,0001' : fmt(p, 4));
function effect(d) {
  const a = Math.abs(d);
  const size = a < 0.2 ? 'sehr klein' : a < 0.5 ? 'klein' : a < 0.8 ? 'mittel' : 'groß';
  return `${fmt(d, 3)} (${size})`;
}
function inputNum(id, fallback) {
  const v = S.toFloat(byId(id).value);
  return v === null || Number.isNaN(v) ? fallback : v;
}

function runTest() {
  const test = byId('t-test').value;
  byId('t-page-binom').style.display = test === BINOM ? '' : 'none';
  byId('t-page-t1').style.display = test === T1 ? '' : 'none';
  byId('t-page-t2').style.display = test === T2 ? '' : 'none';
  const manual = selVal(byId('b-col')) === null;
  byId('b-hit').disabled = manual;
  byId('b-n').disabled = !manual;
  byId('b-k').disabled = !manual;
  const paired = byId('t2-kind').value === T2_PAIRED;
  byId('t2-val-box').style.display = paired ? 'none' : '';
  byId('t2-grp-box').style.display = paired ? 'none' : '';
  byId('t2-a-lbl').textContent = paired ? 'Spalte A:' : 'Gruppe A:';
  byId('t2-b-lbl').textContent = paired ? 'Spalte B:' : 'Gruppe B:';
  let html;
  try {
    html = { [BINOM]: runBinom, [T1]: runT1, [T2]: runT2 }[test]();
  } catch (e) {
    if (!(e instanceof S.TestError)) throw e;
    html = `<p class="note">${esc(e.message)}</p>`;
  }
  byId('t-result').innerHTML = html;
}

function alt() {
  let alpha = inputNum('t-alpha', 0.05);
  alpha = Math.min(0.5, Math.max(0.001, alpha));
  return [byId('t-alt').value, alpha];
}

function runBinom() {
  const [a, alpha] = alt();
  const col = selVal(byId('b-col'));
  let n, k, source;
  if (col === null) {
    n = Math.round(inputNum('b-n', 0)); k = Math.round(inputNum('b-k', 0));
    source = 'manuelle Eingabe';
  } else {
    const hit = byId('b-hit').value;
    const cells = state.rows.map(r => r[col].trim()).filter(Boolean);
    n = cells.length; k = cells.filter(c => c === hit).length;
    source = esc(`Spalte „${state.headers[col]}“, Treffer = „${hit}“`);
    if (!n) throw new S.TestError('Die Spalte enthält keine Werte.');
  }
  if (k > n) throw new S.TestError('Die Trefferzahl k darf nicht größer als n sein.');
  if (n > 10000000) throw new S.TestError('n ist zu groß (höchstens 10 000 000).');
  const r = S.binomialTest(n, k, inputNum('b-p0', 0.5), a, alpha);
  const p0 = fmt(r.p0);
  const regions = r.regions.map(([x, y]) => (y > x ? `{${x}; …; ${y}}` : `{${x}}`)).join(' ∪ ') || 'leer (H₀ ist nie ablehnbar)';
  const rows = [
    ['Daten', source],
    ['Stichprobenumfang n', String(n)],
    ['Anzahl Treffer k', String(k)],
    ['relative Häufigkeit k/n', fmt(r.h, 4)],
    ['Erwartungswert μ = n·p₀', fmt(r.mu, 4)],
    ['Standardabweichung σ = √(n·p₀·(1−p₀))', fmt(r.sigma, 4)],
    ['Ablehnungsbereich', regions],
    ['tatsächliche Irrtumswahrscheinlichkeit', fmt(r.actual_alpha, 4)],
    ['p-Wert', pText(r.p)],
  ];
  const hyp = `H₀: p = ${p0} &nbsp;·&nbsp; H₁: p ${esc(S.ALTERNATIVES[a])} ${p0}`;
  const where = r.reject ? 'liegt im Ablehnungsbereich' : 'liegt nicht im Ablehnungsbereich';
  const nt = 'X = Anzahl der Treffer ist unter H₀ binomialverteilt mit n und p₀. ' + (a === 'two-sided' ? 'Zweiseitig: je Seite höchstens α/2.' : '');
  return report('Signifikanztest für eine Wahrscheinlichkeit (Binomialtest)', hyp, rows, r, `k = ${k} ${where}`, nt);
}

function runT1() {
  const [a, alpha] = alt();
  const col = selVal(byId('t1-col'));
  if (col === null) throw new S.TestError('Bitte eine numerische Variable wählen.');
  const r = S.oneSampleT(columnValues(col), inputNum('t1-mu0', 0), a, alpha);
  const mu0 = fmt(r.mu0), conf = fmt((1 - alpha) * 100, 1);
  const rows = [
    ['Variable', esc(state.headers[col])],
    ['Stichprobenumfang n', String(r.n)],
    ['Mittelwert x̄', fmt(r.mean)],
    ['Standardabweichung s', fmt(r.s)],
    ['Standardfehler s/√n', fmt(r.se)],
    ['Teststatistik t = (x̄ − μ₀)/(s/√n)', fmt(r.t)],
    ['Freiheitsgrade df', String(r.df)],
    ['p-Wert', pText(r.p)],
    [`${conf}-%-Konfidenzintervall für μ`, `[${fmt(r.ci[0])}; ${fmt(r.ci[1])}]`],
    ['Effektstärke Cohens d', effect(r.d)],
  ];
  const hyp = `H₀: μ = ${mu0} &nbsp;·&nbsp; H₁: μ ${esc(S.ALTERNATIVES[a])} ${mu0}`;
  return report('t-Test für eine Stichprobe', hyp, rows, r, null,
    'Voraussetzung: Die Werte sind annähernd normalverteilt (bei n ≥ 30 meist unkritisch).');
}

function runT2() {
  const [a, alpha] = alt();
  const kind = byId('t2-kind').value;
  const conf = fmt((1 - alpha) * 100, 1);
  let r, rows, title, nt;
  if (kind === T2_PAIRED) {
    const ca = selVal(byId('t2-a')), cb = selVal(byId('t2-b'));
    if (ca === null || cb === null) throw new S.TestError('Bitte zwei numerische Spalten wählen.');
    if (ca === cb) throw new S.TestError('Bitte zwei verschiedene Spalten wählen.');
    const xs = [], ys = [];
    for (const row of state.rows) {
      const x = S.toFloat(row[ca]), y = S.toFloat(row[cb]);
      if (x !== null && y !== null) { xs.push(x); ys.push(y); }
    }
    const nameA = esc(state.headers[ca]), nameB = esc(state.headers[cb]);
    r = S.pairedT(xs, ys, a, alpha);
    rows = [
      ['Anzahl Wertepaare n', String(r.n)],
      [`Mittelwert A (${nameA})`, fmt(r.mean1)],
      [`Mittelwert B (${nameB})`, fmt(r.mean2)],
      ['mittlere Differenz d̄ = A − B', fmt(r.mean)],
      ['Standardabweichung der Differenzen', fmt(r.s)],
      ['Standardfehler', fmt(r.se)],
      ['Teststatistik t', fmt(r.t)],
      ['Freiheitsgrade df', String(r.df)],
      ['p-Wert', pText(r.p)],
      [`${conf}-%-Konfidenzintervall für die Differenz`, `[${fmt(r.ci[0])}; ${fmt(r.ci[1])}]`],
      ['Effektstärke Cohens d (d̄/s)', effect(r.d)],
    ];
    title = 't-Test für verbundene Stichproben';
    nt = 'Jede Zeile ist ein Wertepaar (z. B. vorher/nachher). Voraussetzung: Die Differenzen sind annähernd normalverteilt.';
  } else {
    const val = selVal(byId('t2-val')), grp = selVal(byId('t2-grp'));
    const nameA = byId('t2-a').value, nameB = byId('t2-b').value;
    if (val === null || grp === null || !nameA || !nameB) throw new S.TestError('Bitte Variable, Gruppenspalte und zwei Gruppen wählen.');
    if (nameA === nameB) throw new S.TestError('Bitte zwei verschiedene Gruppen wählen.');
    const xa = [], xb = [];
    for (const row of state.rows) {
      const x = S.toFloat(row[val]), g = row[grp].trim();
      if (x === null) continue;
      if (g === nameA) xa.push(x); else if (g === nameB) xb.push(x);
    }
    const pooled = kind === T2_POOLED;
    r = S.twoSampleT(xa, xb, pooled, a, alpha);
    rows = [
      ['Variable', esc(state.headers[val])],
      [`Gruppe A „${esc(nameA)}“: n / x̄ / s`, `${r.n1} / ${fmt(r.mean1)} / ${fmt(r.s1)}`],
      [`Gruppe B „${esc(nameB)}“: n / x̄ / s`, `${r.n2} / ${fmt(r.mean2)} / ${fmt(r.s2)}`],
      ['Differenz x̄<sub>A</sub> − x̄<sub>B</sub>', fmt(r.diff)],
      ['Standardfehler der Differenz', fmt(r.se)],
      ['Teststatistik t', fmt(r.t)],
      ['Freiheitsgrade df', fmt(r.df, 2)],
      ['p-Wert', pText(r.p)],
      [`${conf}-%-Konfidenzintervall für die Differenz`, `[${fmt(r.ci[0])}; ${fmt(r.ci[1])}]`],
      ['Effektstärke Cohens d (gepoolte s)', effect(r.d)],
    ];
    title = 't-Test für unabhängige Stichproben' + (pooled ? ' (gleiche Varianzen)' : ' nach Welch');
    nt = 'Voraussetzung: Die Werte sind in beiden Gruppen annähernd normalverteilt. Der Welch-Test braucht keine gleichen Varianzen und ist darum meist die bessere Wahl.';
  }
  const hyp = `H₀: μ<sub>A</sub> = μ<sub>B</sub> &nbsp;·&nbsp; H₁: μ<sub>A</sub> ${esc(S.ALTERNATIVES[a])} μ<sub>B</sub>`;
  return report(title, hyp, rows, r, null, nt);
}

function report(title, hyp, rows, r, reason, nt) {
  const alpha = fmt(r.alpha), p = pText(r.p);
  const why = reason ? ` (${reason})` : '';
  const verdict = r.reject
    ? `p = ${p} ≤ α = ${alpha}${why} → <b>H₀ wird verworfen</b> – das Ergebnis ist signifikant.`
    : `p = ${p} &gt; α = ${alpha}${why} → <b>H₀ kann nicht verworfen werden</b> – nicht signifikant.`;
  const cells = rows.map(([k, v]) => `<tr><td class="k">${k}</td><td>${v}</td></tr>`).join('');
  return `<p><b>${title}</b><br>${hyp}</p><table>${cells}</table>`
    + `<p class="verdict ${r.reject ? 'ok' : 'warn'}">${verdict}</p><p class="note">${nt}</p>`;
}

// ════════════════════════════════════════════════════════════
// Auswahl und Aktualisierung
// ════════════════════════════════════════════════════════════
function buildTypeCards() {
  byId('chart-types').innerHTML = CHART_TYPES.map(t => {
    const label = t.length > 12 ? t.replace('diagramm', '&shy;diagramm') : t;
    return `<button class="palette-card" type="button" data-type="${esc(t)}" title="${esc(TYPE_HINTS[t])}">`
      + `<svg class="card-icon" viewBox="0 0 24 24">${ICONS[t]}</svg>`
      + `<span class="palette-text"><span class="palette-name">${label}</span></span></button>`;
  }).join('');
  byId('chart-types').addEventListener('click', e => {
    const b = e.target.closest('[data-type]');
    if (!b) return;
    state.chartType = b.dataset.type;
    if (window.matchMedia('(max-width: 860px)').matches) byId('sidebar').classList.remove('open');
    refresh();
  });
  document.querySelectorAll('svg[data-icon]').forEach(s => { s.innerHTML = ICONS[s.dataset.icon]; });
}

function fillCombos() {
  const num = state.numCols = S.numericColumns(state.headers, state.rows);
  const hd = state.headers;
  fillSelect(byId('sel-x'), num.map(i => [i, hd[i]]));
  fillSelect(byId('sel-y'), num.map(i => [i, hd[i]]));
  fillSelect(byId('sel-value'), [['', '— Anzahl —']].concat(num.map(i => [i, hd[i]])));
  fillSelect(byId('sel-cat'), [['', '— keine —']].concat(hd.map((h, i) => [i, h])));
  // Sinnvolle Vorauswahl: erste zwei numerischen Spalten, die keine reine
  // Nummerierung (1, 2, 3, …) sind
  const measures = num.filter(i => !looksLikeId(i));
  const pick = measures.length >= 2 ? measures : num;
  if (pick.length) {
    byId('sel-x').value = pick[0];
    byId('sel-y').value = pick.length > 1 ? pick[1] : pick[0];
  }
  syncSelection();
}

function syncSelection() {
  state.xCol = selVal(byId('sel-x'));
  state.yCol = selVal(byId('sel-y'));
  state.valueCol = selVal(byId('sel-value'));
  state.catCol = selVal(byId('sel-cat'));
  state.agg = byId('sel-agg').value;
  const w = S.toFloat(byId('inp-width').value);
  state.binWidth = w && w > 0 ? w : 0;
  state.histRelative = byId('chk-rel').checked;
  state.regression = byId('chk-reg').checked;
  state.outliers = byId('chk-out').checked;
  state.boxLabels = byId('chk-boxlabel').checked;
}

function updateFieldVisibility() {
  const t = state.chartType;
  const show = (id, v) => { byId(id).style.display = v ? '' : 'none'; };
  show('f-x', t === SCATTER || t === LINE);
  show('f-y', [SCATTER, LINE, HIST, BOX].includes(t));
  byId('lbl-y').textContent = t === SCATTER || t === LINE ? 'Y-Achse' : 'Variable';
  byId('lbl-cat').textContent = CAT_LABELS[t];
  show('f-value', GROUP_CHARTS.includes(t));
  // Beim Kreisdiagramm sind nur Anteile an einer Summe sinnvoll.
  show('f-agg', (t === COLUMN || t === BAR) && state.valueCol !== null);
  show('f-cat', t !== HIST);
  show('f-width', t === HIST);
  show('f-rel', t === HIST);
  show('f-reg', t === SCATTER);
  show('f-out', t === BOX);
  show('f-boxlabel', t === BOX);
  document.querySelectorAll('#chart-types [data-type]').forEach(b => b.classList.toggle('active', b.dataset.type === t));
  byId('type-hint').textContent = TYPE_HINTS[t];
}

function refresh() {
  syncSelection();
  byId('breadcrumb').textContent = state.chartType + (state.fileName ? ' · ' + state.fileName : '');
  updateFieldVisibility();
  fillStats();
  fillFreq();
  renderChart();
  saveSession();
}

// ════════════════════════════════════════════════════════════
// Laden
// ════════════════════════════════════════════════════════════
/** CSV-Text übernehmen. path = voller Pfad (Desktop/NIT_Code) für den Code-Export. */
function loadText(text, name, path, keepSettings) {
  let parsed;
  try { parsed = S.parseCSV(text); } catch (e) { setStatus('Fehler beim Lesen: ' + e.message, 'error'); return false; }
  Object.assign(state, {
    headers: parsed.headers, rows: parsed.rows, info: parsed.info,
    fileName: name || 'daten.csv', path: path || '', csvText: text,
  });
  if (!keepSettings) {
    byId('inp-width').value = '';
  }
  fillDataTable();
  fillCombos();
  refreshTestColumns();
  if (!state.headers.length) {
    byId('file-label').textContent = 'Leere oder unlesbare CSV-Datei.';
    setStatus('Leere oder unlesbare CSV-Datei.', 'error');
  } else {
    const info = `${state.rows.length} Zeilen · ${state.headers.length} Spalten`;
    byId('file-label').textContent = `${state.fileName}\n${info}`;
    setStatus(info);
    document.title = `StatPlot – ${state.fileName}`;
  }
  refresh();
  return true;
}

/** Datei lesen – UTF-8, sonst Windows-1252 (Excel speichert CSV oft so). */
function readFile(file) {
  if (!file) return;
  file.arrayBuffer().then(buf => {
    let text;
    try { text = new TextDecoder('utf-8', { fatal: true }).decode(buf); }
    catch (e) { text = new TextDecoder('windows-1252').decode(buf); }
    loadText(text, file.name, '');
  }).catch(e => setStatus('Datei konnte nicht gelesen werden: ' + e.message, 'error'));
}

function openFile() {
  if (EMBED && hostCaps.open) { embedSend({ event: 'open' }, embedOrigin); return; }
  const api = window.pywebview && window.pywebview.api;
  if (api && api.open_file) {
    api.open_file().then(res => {
      if (res && typeof res.text === 'string') loadText(res.text, res.name, res.path);
    });
    return;
  }
  byId('file-input').click();
}

function loadExample() {
  fetch('beispiele/klassenumfrage.csv')
    .then(r => { if (!r.ok) throw new Error(String(r.status)); return r.text(); })
    .then(t => {
      loadText(t, 'klassenumfrage.csv', '');
      // Mit Kategorie startet das Beispiel anschaulicher
      const g = state.headers.indexOf('Geschlecht');
      if (g >= 0) { byId('sel-cat').value = g; refresh(); }
    })
    .catch(() => setStatus('Die Beispieldaten konnten nicht geladen werden.', 'error'));
}

// ── Sitzung im Browser merken (nur Komfort) ──────────────────
const SESSION_KEY = 'statplot.session';
function saveSession() {
  if (EMBED) return;
  try {
    if (!state.csvText || state.csvText.length > 1500000) { localStorage.removeItem(SESSION_KEY); return; }
    localStorage.setItem(SESSION_KEY, JSON.stringify({
      csv: state.csvText, name: state.fileName, path: state.path, chartType: state.chartType,
      sel: ['sel-x', 'sel-y', 'sel-value', 'sel-cat', 'sel-agg', 'inp-width'].map(id => byId(id).value),
      chk: ['chk-rel', 'chk-reg', 'chk-out', 'chk-boxlabel'].map(id => byId(id).checked),
    }));
  } catch (e) { /* Speicher voll oder gesperrt – egal */ }
}
function restoreSession() {
  let s = null;
  try { s = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch (e) { s = null; }
  if (!s || typeof s.csv !== 'string') return;
  if (!loadText(s.csv, s.name, s.path, true)) return;
  if (CHART_TYPES.includes(s.chartType)) state.chartType = s.chartType;
  ['sel-x', 'sel-y', 'sel-value', 'sel-cat', 'sel-agg', 'inp-width'].forEach((id, i) => {
    const el = byId(id), v = (s.sel || [])[i];
    if (v === undefined) return;
    if (el.tagName === 'SELECT' && ![...el.options].some(o => o.value === v)) return;
    el.value = v;
  });
  ['chk-rel', 'chk-reg', 'chk-out', 'chk-boxlabel'].forEach((id, i) => { byId(id).checked = !!(s.chk || [])[i]; });
  refresh();
  setStatus('Letzte Daten wiederhergestellt');
}

// ════════════════════════════════════════════════════════════
// Export: PNG, SVG, Python-Code
// ════════════════════════════════════════════════════════════
function baseName() {
  const stem = (state.fileName || 'diagramm').replace(/\.[^.]+$/, '');
  return `${stem}_${state.chartType}`.replace(/[\\/:*?"<>|]+/g, '_');
}

function needData() {
  if (state.headers.length) return false;
  setStatus('Erst eine CSV-Datei öffnen.', 'error');
  return true;
}

/** SVG-Text → PNG-Blob (2-fach aufgelöst, weißer Grund). */
function svgToPng(svg, w, h, scale) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = Math.round(w * scale); c.height = Math.round(h * scale);
      const g = c.getContext('2d');
      g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
      g.drawImage(img, 0, 0, c.width, c.height);
      c.toBlob(b => (b ? resolve(b) : reject(new Error('toBlob'))), 'image/png');
    };
    img.onerror = () => reject(new Error('SVG'));
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  });
}

function exportPNG() {
  if (needData()) return;
  const [w, h] = chartSize();
  svgToPng(buildChartSVG(w, h), w, h, 2)
    .then(b => downloadBlob(b, baseName() + '.png'))
    .catch(() => setStatus('Export fehlgeschlagen', 'error'));
}

function exportSVG() {
  if (needData()) return;
  const [w, h] = chartSize();
  downloadBlob(new Blob([buildChartSVG(w, h)], { type: 'image/svg+xml' }), baseName() + '.svg');
}

function downloadBlob(blob, name) {
  // Eingebettet speichert auf Wunsch die einbettende Seite
  if (EMBED && hostCaps.downloads) {
    embedSend({ event: 'download', name, mime: blob.type || 'application/octet-stream', blob }, embedOrigin);
    setStatus(`${name} an die einbettende Seite übergeben`);
    return;
  }
  // Desktop-Version: nativer Speichern-Dialog
  const api = window.pywebview && window.pywebview.api;
  if (api && api.save_file) {
    const rd = new FileReader();
    rd.onload = () => {
      api.save_file(name, String(rd.result).split(',')[1]).then(path => {
        if (path) setStatus('Gespeichert: ' + path, 'ok'); else setStatus('Speichern abgebrochen');
      });
    };
    rd.readAsDataURL(blob);
    return;
  }
  const url = URL.createObjectURL(new Blob([blob], { type: 'application/octet-stream' }));
  const a = document.createElement('a');
  a.href = url; a.download = name; a.rel = 'noopener'; a.style.display = 'none';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  setStatus(name + ' gespeichert', 'ok');
}

function codeProblem() {
  const t = state.chartType;
  if (!state.headers.length) return 'Erst eine CSV-Datei öffnen.';
  if ((t === SCATTER || t === LINE) && (state.xCol === null || state.yCol === null)) return 'Bitte zwei numerische Spalten für X und Y wählen.';
  if (GROUP_CHARTS.includes(t) && state.catCol === null) return 'Bitte eine Kategorie-Spalte wählen.';
  if ((t === HIST || t === BOX) && state.yCol === null) return 'Bitte eine numerische Variable wählen.';
  return null;
}

function codeSpec() {
  const order = categoryOrder();
  const bins = state.chartType === HIST && state.yCol !== null ? histBins() : [];
  return {
    path: state.path || state.fileName || 'daten.csv', headers: state.headers,
    delimiter: state.info.delimiter, header: state.info.header,
    chart_type: state.chartType, x_col: state.xCol, y_col: state.yCol,
    value_col: state.valueCol, cat_col: state.catCol, agg: state.agg,
    numeric_categories: order.length > 0 && order.every(v => S.toFloat(v) !== null),
    bins: bins.length ? bins.map(b => b[0]).concat([bins[bins.length - 1][1]]) : [],
    relative: state.histRelative, regression: state.regression, outliers: state.outliers,
    nit: !!hostCaps.nit,
  };
}

let lastCode = '';
function showCode() {
  const problem = codeProblem();
  if (problem) { setStatus(problem, 'error'); return; }
  lastCode = S.generateCode(codeSpec());
  byId('code-title').textContent = 'Python-Code: ' + state.chartType;
  byId('code-view').textContent = lastCode;
  byId('code-copy').textContent = 'Kopieren';
  byId('code-modal').classList.add('open');
}

// ════════════════════════════════════════════════════════════
// Dialoge
// ════════════════════════════════════════════════════════════
function showModal(title, body) {
  byId('modal-title').textContent = title;
  byId('modal-body').textContent = body;
  byId('modal').classList.add('open');
}
function closeOverlays() { document.querySelectorAll('.overlay.open').forEach(o => o.classList.remove('open')); }

// Desktop-Pakete: neuestes Release bei GitHub, sonst der Ordner downloads/
const DOWNLOADS = [
  ['macOS', 'StatPlot.dmg', 'Apple Silicon & Intel · .dmg'],
  ['Windows', 'StatPlot-Setup.exe', 'Installer · .exe'],
  ['Linux', 'StatPlot-linux-x86_64.tar.gz', 'entpacken & starten · .tar.gz'],
];
function showDownloads() {
  const list = byId('download-list'), ver = byId('download-version');
  const row = (os, href, meta, missing) => `<a class="download-item${missing ? ' missing' : ''}" ${href ? `href="${esc(href)}"` : ''} download><span class="download-os">${esc(os)}</span><span class="download-meta">${esc(meta)}</span></a>`;
  list.innerHTML = DOWNLOADS.map(d => row(d[0], 'downloads/' + d[1], d[2], false)).join('');
  ver.textContent = '';
  byId('download-modal').classList.add('open');
  if (!GITHUB_REPO) return;
  ver.textContent = 'Suche das neueste Release …';
  fetch(`https://api.github.com/repos/${GITHUB_REPO}/releases/latest`, { headers: { Accept: 'application/vnd.github+json' } })
    .then(r => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
    .then(rel => {
      ver.textContent = 'Version ' + (rel.tag_name || '');
      list.innerHTML = DOWNLOADS.map(d => {
        const as = (rel.assets || []).find(x => x.name === d[1]);
        return as ? row(d[0], as.browser_download_url, d[2] + ' · ' + (as.size / 1048576).toFixed(1) + ' MB', false) : row(d[0], '', 'noch nicht verfügbar', true);
      }).join('');
    })
    .catch(() => { ver.textContent = ''; });
}

// ════════════════════════════════════════════════════════════
// Einbettung in andere Apps (?embed=1) – wie PAP/IBD Editor
//
// Protokoll (window.postMessage, alle Nachrichten sind Objekte):
//   App -> Host:  {source:'statplot', event:'ready'}
//   Host -> App:  {target:'statplot', action:'load', csv?:<Text>, name?, path?,
//                  downloads?:true, open?:true, code?:true, clipboard?:true, nit?:true,
//                  save?:false}
//   App -> Host:  {source:'statplot', event:'save', svg:<SVG-Text>, name, width, height}
//                 (Knopf „In Projekt übernehmen“; save:false blendet ihn aus)
//   App -> Host:  {source:'statplot', event:'exit'}
//   App -> Host:  {source:'statplot', event:'download', name, mime, blob:<Blob>}
//   App -> Host:  {source:'statplot', event:'open'}             (nur mit open:true)
//   App -> Host:  {source:'statplot', event:'code', code, title} (nur mit code:true)
//   App -> Host:  {source:'statplot', event:'copy', text}        (nur mit clipboard:true)
// Schalter in „load“ sind Fähigkeiten des Hosts; jede weitere load-Nachricht mit
// csv lädt neue Daten. Die App nimmt nur Nachrichten ihres Eltern-Fensters an
// und antwortet ausschließlich an dessen Origin (aus der load-Nachricht).
// ════════════════════════════════════════════════════════════
const PARAMS = new URLSearchParams(location.search);
const EMBED = PARAMS.get('embed') === '1' && window.parent !== window;
const DESKTOP = PARAMS.get('desktop') === '1';
let embedOrigin = null;
const hostCaps = { downloads: false, open: false, code: false, clipboard: false, nit: false, save: true };

function embedSend(msg, origin) { window.parent.postMessage(Object.assign({ source: 'statplot' }, msg), origin); }

function embedSave() {
  if (!embedOrigin) { alert('Keine Verbindung zur einbettenden Seite.'); return; }
  if (needData()) return;
  const [w, h] = chartSize();
  embedSend({ event: 'save', svg: buildChartSVG(w, h), name: baseName() + '.png', width: w, height: h }, embedOrigin);
  setStatus('An das Projekt übergeben …');
}

function initEmbed() {
  if (!EMBED) return;
  document.body.classList.add('embed');
  const menubar = byId('menubar');
  const close = document.createElement('button');
  close.id = 'btn-embed-exit'; close.className = 'btn-menu'; close.type = 'button'; close.textContent = 'Schließen';
  close.addEventListener('click', () => { if (embedOrigin) embedSend({ event: 'exit' }, embedOrigin); });
  const save = document.createElement('button');
  save.id = 'btn-embed-save'; save.className = 'btn-menu btn-accent'; save.type = 'button'; save.textContent = 'In Projekt übernehmen';
  save.title = 'Diagramm als Bild an die einbettende App übergeben';
  save.addEventListener('click', embedSave);
  menubar.prepend(close); menubar.prepend(save);
  window.addEventListener('message', e => {
    if (e.source !== window.parent) return;
    const m = e.data;
    if (!m || typeof m !== 'object' || m.target !== 'statplot') return;
    if (m.action !== 'load') return;
    embedOrigin = e.origin;
    for (const k of Object.keys(hostCaps)) if (k in m) hostCaps[k] = m[k] === true;
    document.body.classList.toggle('host-code', hostCaps.code);
    save.hidden = !hostCaps.save;
    if (typeof m.csv === 'string') loadText(m.csv, typeof m.name === 'string' ? m.name : '', typeof m.path === 'string' ? m.path : '');
  });
  embedSend({ event: 'ready' }, '*');   // enthält keine Daten
}

// ════════════════════════════════════════════════════════════
// Aufteilung Diagramm / Reiter
// ════════════════════════════════════════════════════════════
const SPLIT_KEY = 'statplot.tabsHeight';
function setTabsHeight(h, remember) {
  const work = byId('work');
  const max = Math.max(90, work.clientHeight - 170);
  h = Math.max(90, Math.min(max, h));
  byId('tabs-pane').style.height = h + 'px';
  if (remember) { try { localStorage.setItem(SPLIT_KEY, String(Math.round(h))); } catch (e) { /* egal */ } }
  renderChart();
}
function initSplit() {
  const handle = byId('split-handle');
  let drag = null;
  handle.addEventListener('pointerdown', e => {
    drag = { y: e.clientY, h: byId('tabs-pane').offsetHeight };
    handle.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  handle.addEventListener('pointermove', e => { if (drag) setTabsHeight(drag.h - (e.clientY - drag.y), false); });
  const end = () => { if (drag) { drag = null; setTabsHeight(byId('tabs-pane').offsetHeight, true); } };
  handle.addEventListener('pointerup', end);
  handle.addEventListener('pointercancel', end);
  let saved = null;
  try { saved = parseInt(localStorage.getItem(SPLIT_KEY) || '', 10); } catch (e) { saved = null; }
  const work = byId('work');
  setTabsHeight(saved > 0 ? saved : Math.round(Math.min(300, work.clientHeight * 0.38)), false);
}

function selectTab(name) {
  activeTab = name;
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-page').forEach(p => p.classList.toggle('active', p.id === 'page-' + name));
  byId('btn-copy-table').style.visibility = name === 'tests' ? 'hidden' : 'visible';
  // Statistik-Tests brauchen mehr Platz für das Ergebnis als die Tabellen
  if (name === 'tests') {
    const pane = byId('tabs-pane'), work = byId('work');
    if (pane.offsetHeight < 420 && work.clientHeight > 640) setTabsHeight(420, false);
  }
}

// ════════════════════════════════════════════════════════════
// Start
// ════════════════════════════════════════════════════════════

// ── Daten von Hand eingeben ──────────────────────────────────
const entry = { headers: [], rows: [] };

function entryResize(cols, rows) {
  cols = Math.min(30, Math.max(1, cols | 0));
  rows = Math.min(1000, Math.max(1, rows | 0));
  entry.headers.length = cols;
  for (let c = 0; c < cols; c++) if (entry.headers[c] === undefined) entry.headers[c] = `Spalte ${c + 1}`;
  while (entry.rows.length > rows) entry.rows.pop();
  while (entry.rows.length < rows) entry.rows.push([]);
  entry.rows.forEach(r => { r.length = cols; for (let c = 0; c < cols; c++) if (r[c] === undefined) r[c] = ''; });
  byId('entry-cols').value = cols;
  byId('entry-rows').value = rows;
}

function entryRender() {
  const t = byId('entry-table');
  const head = entry.headers.map((h, c) => `<th><input data-r="-1" data-c="${c}" value="${escAttr(h)}" aria-label="Spaltenname ${c + 1}"></th>`).join('');
  const body = entry.rows.map((row, r) =>
    `<tr><th class="rn">${r + 1}</th>` +
    row.map((v, c) => `<td><input data-r="${r}" data-c="${c}" value="${escAttr(v)}" inputmode="decimal" autocomplete="off"></td>`).join('') + '</tr>').join('');
  t.innerHTML = `<thead><tr><th class="rn"></th>${head}</tr></thead><tbody>${body}</tbody>`;
}

function escAttr(v) { return String(v).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'); }

function openEntry() {
  entry.headers = state.headers.slice();
  entry.rows = state.rows.map(r => state.headers.map((_, c) => (r[c] === undefined || r[c] === null ? '' : String(r[c]))));
  if (!entry.headers.length) { entry.headers = ['x', 'y']; entry.rows = []; }
  entryResize(entry.headers.length, entry.rows.length || 10);
  byId('entry-error').textContent = '';
  entryRender();
  byId('entry-modal').classList.add('open');
  const first = byId('entry-table').querySelector('tbody input');
  if (first) first.focus();
}

function entryResizeFromInputs() {
  const cols = parseInt(byId('entry-cols').value, 10), rows = parseInt(byId('entry-rows').value, 10);
  if (!(cols >= 1) || !(rows >= 1)) return;
  entryResize(cols, rows);
  entryRender();
}

function entryApply() {
  const err = byId('entry-error');
  const heads = entry.headers.map((h, c) => (h.trim() || `Spalte ${c + 1}`));
  if (new Set(heads).size !== heads.length) { err.textContent = 'Spaltennamen müssen verschieden sein.'; return; }
  if (heads.every(h => S.toFloat(h) !== null)) { err.textContent = 'Mindestens ein Spaltenname darf keine reine Zahl sein.'; return; }
  const rows = entry.rows.filter(r => r.some(v => v.trim() !== ''));
  if (!rows.length) { err.textContent = 'Bitte mindestens einen Wert eintragen.'; return; }
  const q = v => (/[;"\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v);
  const text = [heads, ...rows].map(r => r.map(v => q(v.trim())).join(';')).join('\n') + '\n';
  closeOverlays();
  loadText(text, 'eingabe.csv', '');
}

function initEntry() {
  on('btn-entry', 'click', openEntry);
  on('entry-cancel', 'click', closeOverlays);
  on('entry-apply', 'click', entryApply);
  on('entry-cols', 'change', entryResizeFromInputs);
  on('entry-rows', 'change', entryResizeFromInputs);
  on('entry-clear', 'click', () => { entry.rows.forEach(r => r.fill('')); entryRender(); });
  const table = byId('entry-table');
  table.addEventListener('input', e => {
    const i = e.target, r = +i.dataset.r, c = +i.dataset.c;
    if (r < 0) entry.headers[c] = i.value; else entry.rows[r][c] = i.value;
  });
  table.addEventListener('keydown', e => {
    if (e.key !== 'Enter' && e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const i = e.target, r = +i.dataset.r, c = +i.dataset.c;
    const nr = r + (e.key === 'ArrowUp' || (e.key === 'Enter' && e.shiftKey) ? -1 : 1);
    if (nr >= entry.rows.length) {
      if (e.key !== 'Enter' || entry.rows.length >= 1000) return;
      entryResize(entry.headers.length, entry.rows.length + 1);
      entryRender();
    }
    const next = table.querySelector(`input[data-r="${nr}"][data-c="${c}"]`);
    if (next) { next.focus(); next.select(); }
  });
  table.addEventListener('paste', e => {
    const txt = (e.clipboardData || window.clipboardData).getData('text');
    if (!/[\t\n]/.test(txt.replace(/\r?\n$/, ''))) return;
    e.preventDefault();
    const i = e.target, r0 = Math.max(0, +i.dataset.r), c0 = +i.dataset.c;
    const grid = txt.replace(/\r?\n$/, '').split(/\r?\n/).map(l => l.split('\t'));
    entryResize(Math.max(entry.headers.length, c0 + Math.max(...grid.map(g => g.length))), Math.max(entry.rows.length, r0 + grid.length));
    grid.forEach((g, dr) => g.forEach((v, dc) => { entry.rows[r0 + dr][c0 + dc] = v.trim(); }));
    entryRender();
  });
}

function init() {
  buildTypeCards();
  initEntry();
  fillSelect(byId('sel-agg'), Object.keys(S.AGGREGATIONS));
  initTests();

  ['sel-x', 'sel-y', 'sel-value', 'sel-agg', 'sel-cat', 'chk-rel', 'chk-reg', 'chk-out', 'chk-boxlabel']
    .forEach(id => on(id, 'change', refresh));
  on('inp-width', 'change', refresh);
  let widthTimer = null;
  on('inp-width', 'input', () => { clearTimeout(widthTimer); widthTimer = setTimeout(refresh, 400); });

  on('card-open', 'click', openFile);
  on('btn-open', 'click', openFile);
  on('btn-example', 'click', loadExample);
  on('btn-png', 'click', exportPNG);
  on('btn-svg', 'click', exportSVG);
  on('btn-code', 'click', showCode);
  on('btn-desktop', 'click', showDownloads);
  on('btn-help-side', 'click', () => byId('help-modal').classList.add('open'));
  on('help-close', 'click', closeOverlays);
  on('modal-close', 'click', closeOverlays);
  on('download-close', 'click', closeOverlays);
  on('code-close', 'click', closeOverlays);
  on('code-copy', 'click', () => { copyText(lastCode, 'Python-Code kopiert'); byId('code-copy').textContent = 'Kopiert ✓'; });
  on('code-save', 'click', () => {
    const stem = (state.fileName || 'diagramm').replace(/\.[^.]+$/, '').replace(/[^\wäöüÄÖÜß-]+/g, '_');
    downloadBlob(new Blob([lastCode], { type: 'text/x-python' }), `${stem}_diagramm.py`);
  });
  on('code-to-tab', 'click', () => {
    if (EMBED && hostCaps.code) {
      embedSend({ event: 'code', code: lastCode, title: state.chartType }, embedOrigin);
      closeOverlays();
      setStatus('Code an den Editor übergeben', 'ok');
    }
  });
  document.querySelectorAll('.overlay').forEach(o => o.addEventListener('click', e => { if (e.target === o) closeOverlays(); }));
  on('file-input', 'change', e => { readFile(e.target.files[0]); e.target.value = ''; });
  on('btn-copy-table', 'click', copyCurrentTable);
  byId('tabbar').addEventListener('click', e => { const b = e.target.closest('.tab'); if (b) selectTab(b.dataset.tab); });

  on('sidebar-toggle', 'click', () => byId('sidebar').classList.toggle('open'));
  on('sidebar-overlay', 'click', () => byId('sidebar').classList.remove('open'));
  on('menu-toggle', 'click', () => byId('menubar').classList.toggle('open'));
  on('menu-overlay', 'click', () => byId('menubar').classList.remove('open'));
  on('menubar', 'click', () => byId('menubar').classList.remove('open'));

  // CSV-Datei auf das Fenster ziehen
  let dragDepth = 0;
  window.addEventListener('dragenter', e => { if ([...(e.dataTransfer.types || [])].includes('Files')) { dragDepth++; document.body.classList.add('dragging'); } });
  window.addEventListener('dragleave', () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) document.body.classList.remove('dragging'); });
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => {
    e.preventDefault(); dragDepth = 0; document.body.classList.remove('dragging');
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) readFile(f);
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeOverlays(); byId('sidebar').classList.remove('open'); byId('menubar').classList.remove('open'); return; }
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === 'o') { e.preventDefault(); openFile(); }
  });

  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(renderChart).observe(byId('chart-box'));
  window.addEventListener('resize', () => setTabsHeight(byId('tabs-pane').offsetHeight, false));

  if (DESKTOP) document.body.classList.add('desktop');
  window.addEventListener('pywebviewready', () => document.body.classList.add('desktop'));
  initSplit();
  selectTab('table');
  initEmbed();
  if (!EMBED) restoreSession();
  refresh();
  if (!state.headers.length) setStatus('Bereit');
}

window.addEventListener('DOMContentLoaded', init);
