"""Reiter „Statistik-Tests“ der Datenauswertung.

Binomialtest (Signifikanztest), t-Test für eine Stichprobe und t-Test für
zwei Stichproben (unabhängig/verbunden). Die Rechnungen stecken in
``stat_tests.py``; hier nur Eingabe (Spaltenauswahl aus der geladenen CSV)
und eine HTML-Ergebnistabelle mit Hypothesen, Kennzahlen und Entscheidung.
"""
from html import escape

from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QSpinBox, QStackedWidget,
    QTextBrowser, QVBoxLayout, QWidget,
)

from .mint_style import C
from .csv_stats import fmt_num
from .stat_tests import (
    ALTERNATIVES, binomial_test, one_sample_t, paired_t, two_sample_t,
)

BINOM, T1, T2 = ("Signifikanztest (Binomialtest)", "t-Test: eine Stichprobe",
                 "t-Test: zwei Stichproben")
_MANUAL = "— manuell —"
_INDEPENDENT_WELCH, _INDEPENDENT_POOLED, _PAIRED = (
    "unabhängig (Welch)", "unabhängig (gleiche Varianzen)", "verbunden (gepaart)")
_MAX_LEVELS = 50


def _p_text(p):
    return "< 0,0001" if p < 1e-4 else fmt_num(p, 4)


def _effect(d):
    a = abs(d)
    size = ("sehr klein" if a < 0.2 else "klein" if a < 0.5
            else "mittel" if a < 0.8 else "groß")
    return f"{fmt_num(d, 3)} ({size})"


class StatTestsPanel(QWidget):
    """Eingabe + Ergebnis eines Signifikanztests auf den Daten des Fensters."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._win = window
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        top = QHBoxLayout()
        self._test_combo = self._combo(top, "Test:", [BINOM, T1, T2])
        self._alt_combo = QComboBox()
        for key, label in (("two-sided", "zweiseitig (≠)"), ("less", "linksseitig (<)"),
                           ("greater", "rechtsseitig (>)")):
            self._alt_combo.addItem(label, key)
        self._add(top, "H₁:", self._alt_combo)
        self._alpha = self._dspin(0.001, 0.5, 3, 0.05, 0.01)
        self._alpha.setToolTip("Signifikanzniveau (Irrtumswahrscheinlichkeit 1. Art)")
        self._add(top, "α:", self._alpha)
        top.addStretch()
        root.addLayout(top)

        self._stack = QStackedWidget()
        # Binomialtest
        page, row = self._page()
        self._b_col = self._combo(row, "Spalte:")
        self._b_col.setMinimumWidth(140)
        self._b_hit = self._combo(row, "Treffer:")
        self._b_n = QSpinBox()
        self._b_n.setRange(1, 10_000_000)
        self._b_n.setValue(100)
        self._add(row, "n:", self._b_n)
        self._b_k = QSpinBox()
        self._b_k.setRange(0, 10_000_000)
        self._b_k.setValue(50)
        self._add(row, "k:", self._b_k)
        self._b_p0 = self._dspin(0.001, 0.999, 3, 0.5, 0.05)
        self._add(row, "p₀:", self._b_p0)
        row.addStretch()
        self._stack.addWidget(page)
        # t-Test, eine Stichprobe
        page, row = self._page()
        self._t1_col = self._combo(row, "Variable:")
        self._t1_mu0 = self._dspin(-1e9, 1e9, 4, 0, 1)
        self._add(row, "μ₀:", self._t1_mu0)
        row.addStretch()
        self._stack.addWidget(page)
        # t-Test, zwei Stichproben
        page, row = self._page()
        self._t2_kind = self._combo(row, "Art:", [_INDEPENDENT_WELCH, _INDEPENDENT_POOLED,
                                                 _PAIRED])
        self._t2_val, self._t2_val_box = self._combo(row, "Variable:", boxed=True)
        self._t2_grp, self._t2_grp_box = self._combo(row, "Gruppen:", boxed=True)
        self._t2_a, self._t2_a_box = self._combo(row, "A:", boxed=True)
        self._t2_b, self._t2_b_box = self._combo(row, "B:", boxed=True)
        row.addStretch()
        self._stack.addWidget(page)
        root.addWidget(self._stack)

        self._result = QTextBrowser()
        self._result.setOpenLinks(False)
        root.addWidget(self._result, 1)

        for w in (self._test_combo, self._alt_combo, self._b_hit, self._t1_col,
                  self._t2_val, self._t2_a, self._t2_b):
            w.currentIndexChanged.connect(self._on_changed)
        self._b_col.currentIndexChanged.connect(self._on_binom_col)
        # Art/Gruppenspalte ändern die Auswahllisten A/B – danach neu rechnen.
        self._t2_kind.currentIndexChanged.connect(self._on_group_col)
        self._t2_grp.currentIndexChanged.connect(self._on_group_col)
        for w in (self._alpha, self._b_p0, self._t1_mu0):
            w.valueChanged.connect(self._on_changed)
        for w in (self._b_n, self._b_k):
            w.valueChanged.connect(self._on_changed)
        self._on_changed()

    @staticmethod
    def _add(row, text, widget):
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(QLabel(text))
        lay.addWidget(widget)
        row.addWidget(box)
        return box

    def _combo(self, row, text, items=(), boxed=False):
        combo = QComboBox()
        combo.setMinimumWidth(100)
        combo.addItems(list(items))
        box = self._add(row, text, combo)
        return (combo, box) if boxed else combo

    @staticmethod
    def _dspin(lo, hi, decimals, value, step):
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setDecimals(decimals)
        sp.setSingleStep(step)
        sp.setValue(value)
        sp.setKeyboardTracking(False)
        return sp

    @staticmethod
    def _page():
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        return page, row

    # ── Spalten aus der CSV ───────────────────────────────────────────────────
    def refresh_columns(self):
        """Nach dem Laden einer CSV: Spaltenlisten neu füllen."""
        win = self._win
        num = win.numeric_column_indices()
        combos = (self._b_col, self._t1_col, self._t2_val, self._t2_grp,
                  self._t2_a, self._t2_b)
        for c in combos:
            c.blockSignals(True)
            c.clear()
        self._b_col.addItem(_MANUAL, None)
        for i, h in enumerate(win.headers):
            self._b_col.addItem(h, i)
            self._t2_grp.addItem(h, i)
        for i in num:
            self._t1_col.addItem(win.headers[i], i)
            self._t2_val.addItem(win.headers[i], i)
        # Vorauswahl: keine reine Nummerierung (1, 2, 3, …) als Messgröße
        measures = [i for i in num if not self._looks_like_id(i)] or num
        if measures:
            self._t1_col.setCurrentIndex(self._t1_col.findData(measures[0]))
            self._t2_val.setCurrentIndex(self._t2_val.findData(measures[0]))
        # Gruppenspalte: bevorzugt eine nicht-numerische Spalte
        text_cols = [i for i in range(len(win.headers)) if i not in num]
        if text_cols:
            self._t2_grp.setCurrentIndex(self._t2_grp.findData(text_cols[0]))
        for c in combos:
            c.blockSignals(False)
        self._on_binom_col()
        self._on_group_col()

    def _looks_like_id(self, col) -> bool:
        """True für eine fortlaufende Nummerierung wie 1, 2, 3, …"""
        vals = self._win.column_values(col)
        return len(vals) > 2 and all(b - a == 1 for a, b in zip(vals, vals[1:]))

    def _levels(self, col):
        seen, out = set(), []
        for r in self._win.rows:
            v = r[col].strip()
            if v and v not in seen:
                seen.add(v)
                out.append(v)
        return out[:_MAX_LEVELS]

    def _on_binom_col(self, *_):
        col = self._b_col.currentData()
        self._b_hit.blockSignals(True)
        self._b_hit.clear()
        if col is not None:
            self._b_hit.addItems(self._levels(col))
        self._b_hit.blockSignals(False)
        self._on_changed()

    def _on_group_col(self, *_):
        col = self._t2_grp.currentData()
        kind = self._t2_kind.currentText()
        for c in (self._t2_a, self._t2_b):
            c.blockSignals(True)
            c.clear()
        if kind == _PAIRED:
            num = self._win.numeric_column_indices()
            for i in num:
                self._t2_a.addItem(self._win.headers[i], i)
                self._t2_b.addItem(self._win.headers[i], i)
            measures = [i for i in num if not self._looks_like_id(i)]
            if len(measures) > 1:
                self._t2_a.setCurrentIndex(self._t2_a.findData(measures[0]))
                self._t2_b.setCurrentIndex(self._t2_b.findData(measures[1]))
            elif self._t2_b.count() > 1:
                self._t2_b.setCurrentIndex(1)
        elif col is not None:
            levels = self._levels(col)
            self._t2_a.addItems(levels)
            self._t2_b.addItems(levels)
            if len(levels) > 1:
                self._t2_b.setCurrentIndex(1)
        for c in (self._t2_a, self._t2_b):
            c.blockSignals(False)
        self._on_changed()

    # ── Rechnen + Anzeigen ────────────────────────────────────────────────────
    def _on_changed(self, *_):
        test = self._test_combo.currentText()
        self._stack.setCurrentIndex([BINOM, T1, T2].index(test))
        manual = self._b_col.currentData() is None
        self._b_hit.setEnabled(not manual)
        self._b_n.setEnabled(manual)
        self._b_k.setEnabled(manual)
        paired = self._t2_kind.currentText() == _PAIRED
        self._t2_val_box.setVisible(not paired)
        self._t2_grp_box.setVisible(not paired)
        a_label = self._t2_a_box.findChild(QLabel)
        b_label = self._t2_b_box.findChild(QLabel)
        a_label.setText("Spalte A:" if paired else "Gruppe A:")
        b_label.setText("Spalte B:" if paired else "Gruppe B:")
        try:
            html = {BINOM: self._run_binom, T1: self._run_t1, T2: self._run_t2}[test]()
        except ValueError as e:
            html = self._msg(escape(str(e)))
        self._result.setHtml(self._wrap(html))

    def _alt(self):
        return self._alt_combo.currentData(), self._alpha.value()

    def _run_binom(self):
        alt, alpha = self._alt()
        col = self._b_col.currentData()
        if col is None:
            n, k = self._b_n.value(), self._b_k.value()
            source = "manuelle Eingabe"
        else:
            hit = self._b_hit.currentText()
            cells = [r[col].strip() for r in self._win.rows if r[col].strip()]
            n, k = len(cells), sum(1 for c in cells if c == hit)
            source = escape(f"Spalte „{self._win.headers[col]}“, Treffer = „{hit}“")
            if not n:
                raise ValueError("Die Spalte enthält keine Werte.")
        if k > n:
            raise ValueError("Die Trefferzahl k darf nicht größer als n sein.")
        r = binomial_test(n, k, self._b_p0.value(), alt, alpha)
        p0 = fmt_num(r["p0"])
        regions = " ∪ ".join(f"{{{a}; …; {b}}}" if b > a else f"{{{a}}}"
                             for a, b in r["regions"]) or "leer (H₀ ist nie ablehnbar)"
        rows = [
            ("Daten", source),
            ("Stichprobenumfang n", str(n)),
            ("Anzahl Treffer k", str(k)),
            ("relative Häufigkeit k/n", fmt_num(r["h"], 4)),
            ("Erwartungswert μ = n·p₀", fmt_num(r["mu"], 4)),
            ("Standardabweichung σ = √(n·p₀·(1−p₀))", fmt_num(r["sigma"], 4)),
            ("Ablehnungsbereich", regions),
            ("tatsächliche Irrtumswahrscheinlichkeit", fmt_num(r["actual_alpha"], 4)),
            ("p-Wert", _p_text(r["p"])),
        ]
        hyp = f"H₀: p = {p0} &nbsp;·&nbsp; H₁: p {escape(ALTERNATIVES[alt])} {p0}"
        where = ("liegt im Ablehnungsbereich" if r["reject"]
                 else "liegt nicht im Ablehnungsbereich")
        note = ("X = Anzahl der Treffer ist unter H₀ binomialverteilt mit n und p₀. "
                + ("Zweiseitig: je Seite höchstens α/2." if alt == "two-sided" else ""))
        return self._report("Signifikanztest für eine Wahrscheinlichkeit (Binomialtest)",
                            hyp, rows, r, f"k = {k} {where}", note)

    def _run_t1(self):
        alt, alpha = self._alt()
        col = self._t1_col.currentData()
        if col is None:
            raise ValueError("Bitte eine numerische Variable wählen.")
        r = one_sample_t(self._win.column_values(col), self._t1_mu0.value(), alt, alpha)
        mu0 = fmt_num(r["mu0"])
        conf = fmt_num((1 - alpha) * 100, 1)
        rows = [
            ("Variable", escape(self._win.headers[col])),
            ("Stichprobenumfang n", str(r["n"])),
            ("Mittelwert x̄", fmt_num(r["mean"])),
            ("Standardabweichung s", fmt_num(r["s"])),
            ("Standardfehler s/√n", fmt_num(r["se"])),
            ("Teststatistik t = (x̄ − μ₀)/(s/√n)", fmt_num(r["t"])),
            ("Freiheitsgrade df", str(r["df"])),
            ("p-Wert", _p_text(r["p"])),
            (f"{conf}-%-Konfidenzintervall für μ",
             f"[{fmt_num(r['ci'][0])}; {fmt_num(r['ci'][1])}]"),
            ("Effektstärke Cohens d", _effect(r["d"])),
        ]
        hyp = f"H₀: μ = {mu0} &nbsp;·&nbsp; H₁: μ {escape(ALTERNATIVES[alt])} {mu0}"
        note = ("Voraussetzung: Die Werte sind annähernd normalverteilt "
                "(bei n ≥ 30 meist unkritisch).")
        return self._report("t-Test für eine Stichprobe", hyp, rows, r, None, note)

    def _run_t2(self):
        alt, alpha = self._alt()
        kind = self._t2_kind.currentText()
        win = self._win
        conf = fmt_num((1 - alpha) * 100, 1)
        if kind == _PAIRED:
            ca, cb = self._t2_a.currentData(), self._t2_b.currentData()
            if ca is None or cb is None:
                raise ValueError("Bitte zwei numerische Spalten wählen.")
            if ca == cb:
                raise ValueError("Bitte zwei verschiedene Spalten wählen.")
            pairs = []
            for row in win.rows:
                x, y = win.to_float(row[ca]), win.to_float(row[cb])
                if x is not None and y is not None:
                    pairs.append((x, y))
            name_a, name_b = escape(win.headers[ca]), escape(win.headers[cb])
            r = paired_t([x for x, _ in pairs], [y for _, y in pairs], alt, alpha)
            rows = [
                ("Anzahl Wertepaare n", str(r["n"])),
                (f"Mittelwert A ({name_a})", fmt_num(r["mean1"])),
                (f"Mittelwert B ({name_b})", fmt_num(r["mean2"])),
                ("mittlere Differenz d̄ = A − B", fmt_num(r["mean"])),
                ("Standardabweichung der Differenzen", fmt_num(r["s"])),
                ("Standardfehler", fmt_num(r["se"])),
                ("Teststatistik t", fmt_num(r["t"])),
                ("Freiheitsgrade df", str(r["df"])),
                ("p-Wert", _p_text(r["p"])),
                (f"{conf}-%-Konfidenzintervall für die Differenz",
                 f"[{fmt_num(r['ci'][0])}; {fmt_num(r['ci'][1])}]"),
                ("Effektstärke Cohens d (d̄/s)", _effect(r["d"])),
            ]
            title = "t-Test für verbundene Stichproben"
            note = ("Jede Zeile ist ein Wertepaar (z. B. vorher/nachher). Voraussetzung: "
                    "Die Differenzen sind annähernd normalverteilt.")
        else:
            val, grp = self._t2_val.currentData(), self._t2_grp.currentData()
            name_a, name_b = self._t2_a.currentText(), self._t2_b.currentText()
            if val is None or grp is None or not name_a or not name_b:
                raise ValueError("Bitte Variable, Gruppenspalte und zwei Gruppen wählen.")
            if name_a == name_b:
                raise ValueError("Bitte zwei verschiedene Gruppen wählen.")
            a, b = [], []
            for row in win.rows:
                x = win.to_float(row[val])
                g = row[grp].strip()
                if x is None:
                    continue
                if g == name_a:
                    a.append(x)
                elif g == name_b:
                    b.append(x)
            pooled = kind == _INDEPENDENT_POOLED
            r = two_sample_t(a, b, pooled, alt, alpha)
            rows = [
                ("Variable", escape(win.headers[val])),
                (f"Gruppe A „{escape(name_a)}“: n / x̄ / s",
                 f"{r['n1']} / {fmt_num(r['mean1'])} / {fmt_num(r['s1'])}"),
                (f"Gruppe B „{escape(name_b)}“: n / x̄ / s",
                 f"{r['n2']} / {fmt_num(r['mean2'])} / {fmt_num(r['s2'])}"),
                ("Differenz x̄<sub>A</sub> − x̄<sub>B</sub>", fmt_num(r["diff"])),
                ("Standardfehler der Differenz", fmt_num(r["se"])),
                ("Teststatistik t", fmt_num(r["t"])),
                ("Freiheitsgrade df", fmt_num(r["df"], 2)),
                ("p-Wert", _p_text(r["p"])),
                (f"{conf}-%-Konfidenzintervall für die Differenz",
                 f"[{fmt_num(r['ci'][0])}; {fmt_num(r['ci'][1])}]"),
                ("Effektstärke Cohens d (gepoolte s)", _effect(r["d"])),
            ]
            title = ("t-Test für unabhängige Stichproben"
                     + (" (gleiche Varianzen)" if pooled else " nach Welch"))
            note = ("Voraussetzung: Die Werte sind in beiden Gruppen annähernd "
                    "normalverteilt. Der Welch-Test braucht keine gleichen Varianzen "
                    "und ist darum meist die bessere Wahl.")
        hyp = (f"H₀: μ<sub>A</sub> = μ<sub>B</sub> &nbsp;·&nbsp; "
               f"H₁: μ<sub>A</sub> {escape(ALTERNATIVES[alt])} μ<sub>B</sub>")
        return self._report(title, hyp, rows, r, None, note)

    # ── HTML ──────────────────────────────────────────────────────────────────
    def _report(self, title, hyp, rows, r, reason, note):
        t = C
        alpha = fmt_num(r["alpha"])
        p = _p_text(r["p"])
        if r["reject"]:
            verdict = (f"p = {p} ≤ α = {alpha}"
                       + (f" ({reason})" if reason else "")
                       + " → <b>H₀ wird verworfen</b> – das Ergebnis ist signifikant.")
            color = C["ok"]
        else:
            verdict = (f"p = {p} &gt; α = {alpha}"
                       + (f" ({reason})" if reason else "")
                       + " → <b>H₀ kann nicht verworfen werden</b> – nicht signifikant.")
            color = C["warn"]
        cells = "".join(
            f"<tr><td style='padding:2px 14px 2px 0; color:{t['text_dim']}'>{k}</td>"
            f"<td style='padding:2px 0'>{v}</td></tr>" for k, v in rows)
        return (f"<p style='margin:0 0 4px 0'><b>{title}</b><br>{hyp}</p>"
                f"<table cellspacing='0'>{cells}</table>"
                f"<p style='margin:6px 0 2px 0; color:{color}'>{verdict}</p>"
                f"<p style='margin:2px 0; color:{t['text_dim']}'>{note}</p>")

    def _msg(self, text):
        return f"<p style='color:{C['text_dim']}'>{text}</p>"

    def _wrap(self, html):
        return f"<div style='color:{C['text']}'>{html}</div>"

    def refresh_theme(self):
        self._on_changed()
