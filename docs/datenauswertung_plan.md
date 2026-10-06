# Plan: Datenauswertung (CSV) – Erweiterung des CSV-Streudiagramms

Stand: 2026-10-06 · Ausgangsversion 1.10.0-beta.8, Stufe 1 in 1.10.0-beta.9, als 1.10.1 released; seit 1.10.2 ausgelagert nach StatPlot (siehe unten)

## Ziel

Das bisherige Fenster „CSV-Streudiagramm“ (`nit_code/csv_plot.py`) wird zu einer
kleinen **Datenauswertung** ausgebaut. Orientierung an numiqo.de, aber bewusst
beschränkt auf **beschreibende Statistik** (Bildungsplan BW Mathe, Leitidee
„Daten und Zufall“, Kl. 5–10) plus Kennlinien für Physik/NwT.

Damit entsteht die Kette *Messen (ESP32/Sensor-Blöcke) → Serial Plotter → CSV →
Auswerten* in einem Werkzeug.

**Nicht** geplant: Hypothesentests (t-Test, ANOVA, Chi² …), Faktorenanalyse –
das ist Oberstufe/Uni und überfrachtet das Tool.

## Technische Leitlinien

- **Keine neuen Abhängigkeiten** (kein pandas/matplotlib im IDE-Bundle).
  Einlesen mit stdlib `csv`, Zeichnen mit eigenem `QPainter`-Canvas wie bisher.
- Reine Rechenfunktionen (Kennwerte, Quartile, Klassen, Häufigkeiten) in ein
  eigenes Qt-freies Modul `nit_code/csv_stats.py` → leicht testbar.
- Klassenname `CsvPlotWindow` und Modul `csv_plot.py` bleiben (Import in
  `main_window.py`), Fenstertitel/Menüeintrag werden „Datenauswertung“.
- Theme-Farben aus `config.THEME`, Kategorienfarben aus `_CAT_COLORS`.
- Bezeichnungen nach **Bildungsplan-Begriffen** (arithmetisches Mittel,
  Spannweite, Quartilsabstand …).

### Statistische Konventionen (Schulmathematik)

- **Quartile:** unteres/oberes Quartil = Median der unteren/oberen Hälfte der
  sortierten Werte; bei ungeradem n gehört der Median zu keiner Hälfte.
- **Boxplot-Antennen:** von Minimum bis Maximum (keine Ausreißer-Regel).
- **Standardabweichung:** beide anzeigen – σ (Division durch n, Schulbuch) und
  s (Division durch n−1, wie Taschenrechner „sx“).
- **Histogramm:** Klassen halboffen `[a; b)`, letzte Klasse schließt das
  Maximum ein. Klassenbreite einstellbar, 0 = automatisch (Sturges-Regel,
  auf „schöne“ Breite 1/2/5·10^k gerundet).

## Stufe 1 (Kern, Sek I) – erledigt (1.10.0-beta.9)

- [x] Auswahl **Diagrammtyp**: Streudiagramm, Liniendiagramm,
      Säulendiagramm, Balkendiagramm, Histogramm, Boxplot.
  - Streu/Linie: X, Y (numerisch), optional Kategorie (Farbe/Linie je Gruppe).
  - Säule/Balken: Kategorie-Spalte (Gruppen) + Wert = „Anzahl“ oder eine
    numerische Spalte mit Aggregation (Mittelwert, Summe, Median, Min, Max).
  - Histogramm: numerische Variable + Klassenbreite (Spinbox, 0 = auto),
    absolute oder relative Häufigkeit.
  - Boxplot: numerische Variable, optional gruppiert nach Kategorie
    (ein Boxplot je Gruppe nebeneinander).
  - Steuerelemente, die für den Typ irrelevant sind, werden ausgeblendet.
- [x] **Kennwerte**-Reiter: n, Minimum, unteres Quartil, Median, oberes
      Quartil, Maximum, Spannweite, Quartilsabstand, arithmetisches Mittel,
      Standardabweichung σ und s – für die gewählte Variable, bei Gruppierung
      eine Spalte je Gruppe. Werte kopierbar.
- [x] **Häufigkeiten**-Reiter: Häufigkeitstabelle (Wert bzw. Klasse,
      absolute H., relative H. in %, kumulierte relative H.). Beim Histogramm
      die Klassen, sonst die Ausprägungen der Kategorie-/Variablenspalte.
- [x] **Export** des Diagramms als PNG (Toolbar-Knopf).
- [x] Menü „Visualisieren → 📊 Datenauswertung (CSV) …“, README und
      `assets/hilfe/Kurzanleitung.md` anpassen; Version hochzählen.

Getestet offscreen mit einer Beispiel-CSV (alle sechs Typen, Gruppierung,
relative Häufigkeit, leere Datei, Datei ohne Kopfzeile). Noch offen: Test
auf Windows/macOS im echten Fenster.

## Stufe 2 – erledigt (1.10.0-beta.9)

- [x] Ausgleichsgerade (lineare Regression, kleinste Quadrate) + Gleichung +
      R² im Streudiagramm (Checkbox „Ausgleichsgerade“), bei gewählter
      Kategorie je Gruppe; Gleichungen in Legende und Kennwerte-Überschrift.
- [x] Dasselbe im X-Y-Modus des Serial Plotters (Checkbox, je Kurve).
- [x] Kreisdiagramm (Anzahl oder Summe einer Spalte je Kategorie).
- [x] Boxplot-Option „Ausreißer (1,5·IQR)“.
- R² wird immer mit 4 Nachkommastellen angezeigt (0,9997 soll nicht als „1“
  erscheinen).

## Stufe 3 – erledigt (1.10.0-beta.9)

- [x] Toolbar-Knopf „🐍 Als Python-Code …“: Dialog mit Vorschau, „Kopieren“
      und „In neuen Editor-Tab“ (`MainWindow._open_code_in_new_tab`).
- [x] Generator `nit_code/csv_codegen.py` (Qt-frei): `csv`-Modul + Listen/
      Dictionaries + matplotlib, kein pandas/numpy. Spaltennummern als
      Konstanten mit Spaltennamen im Kommentar, absoluter Pfad plus Hinweis
      auf den Dateinamen, freundliche Meldung, falls matplotlib fehlt.
- [x] Boxplot-Code rechnet die Quartile selbst nach Schulbuch-Methode und
      zeichnet mit `Axes.bxp` – `plt.boxplot` würde interpolieren und
      andere Kästen als das Fenster liefern.
- Getestet: 732 erzeugte Varianten (alle Typen × Kategorie × Optionen ×
  Aggregationen, mit/ohne Kopfzeile) laufen fehlerfrei mit matplotlib 3.11.
- [x] matplotlib wird seit 1.10.0-beta.9 in der Schüler-Runtime mitgeliefert
      (`release/requirements-runtime.txt`), weil pip in Schulnetzen oft am
      Proxy scheitert. Fehlt es trotzdem, bricht der erzeugte Code mit einem
      Hinweis auf den Pip-Manager ab.

## Stufe 4 – Statistik-Tests (1.10.0-beta.9)

- [x] Boxplot-Option „Werte beschriften“: Min, q₁, Median, q₃, Max neben dem
      Kasten, Mittelwert x̄ als Raute. (Median, Quartilsabstand, σ und s
      standen schon im Reiter Kennwerte.)
- [x] Reiter „Statistik-Tests“ (`nit_code/stat_tests_panel.py`), Rechnungen
      Qt- und scipy-frei in `nit_code/stat_tests.py`:
  - Signifikanztest (Binomialtest, Kursstufe BW): Daten aus einer Spalte
    (Treffer = Ausprägung) oder manuell n, k; p₀, ein-/zweiseitig, α.
    Ausgabe: h, μ, σ, Ablehnungsbereich, tatsächliche Irrtumswahrscheinlichkeit,
    p-Wert, Entscheidung. Zweiseitig mit α/2 je Seite.
  - t-Test eine Stichprobe: n, x̄, s, SE, t, df, p, Konfidenzintervall,
    Cohens d (mit Einordnung klein/mittel/groß).
  - t-Test zwei Stichproben: unabhängig (Welch oder gleiche Varianzen; Gruppen
    aus einer Kategorie-Spalte) oder verbunden (zwei Spalten, zeilenweise
    Paare). Ausgabe wie oben plus Gruppenkennwerte.
  - Vorauswahl überspringt reine Nummerierungsspalten (1, 2, 3, …).
- Validiert gegen scipy: t-Verteilung, alle t-Tests (Statistik, p-Wert, KI)
  und Binomialtests auf ≤ 1e-8 genau; Schulbuchbeispiel n = 100, p₀ = 0,5,
  rechtsseitig, α = 5 % → Ablehnungsbereich {59; …; 100}.
- Ideen für später: Chi²-Test (Vierfeldertafel), Korrelationstest für r,
  Code-Export der Tests.

## Layout im PAP-/IBD-Stil (1.10.0-beta.10)

- [x] Knopf „Datenauswertung“ in der Seitenleiste der IDE; das Fenster öffnet
      ohne Dateidialog, „CSV öffnen …“ startet im Sketchbook-Ordner.
- [x] Fenster im Look von pap.mint-checker.de / ibd.mint-checker.de:
      dunkle Seitenleiste (Titel, DATEI, DIAGRAMM als Karten-Raster mit
      Symbolen, EINSTELLUNGEN, „Hilfe & Bedienung“), heller Arbeitsbereich mit
      Kopfleiste (Diagrammname, Status, Knöpfe, „Als Python-Code“ blau),
      Diagramm oben, Reiter darunter.
- Farben/Stylesheets zentral in `nit_code/mint_style.py` (feste Palette,
  unabhängig vom IDE-Theme – wie die eingebetteten Web-Editoren).
- Klapp-Pfeile werden aus `icons.py` („chevron“) als PNG ins Temp-Verzeichnis
  gerendert, weil Qt-Stylesheets eine Bilddatei brauchen.

## Umzug nach StatPlot (1.10.2)

Die Datenauswertung ist jetzt eine eigene Web-App:
[StatPlot](https://github.com/juchemGDG/StatPlot) – Web-Version (z. B. auf dem
iPad), Desktop-Version (pywebview) und eingebettet in NIT_Code, wie PAP-/IBD-Editor.

- Rechenkern `stats.js` ist eine 1:1-Portierung von `csv_stats.py`,
  `stat_tests.py`, `csv_codegen.py` und dem CSV-Einlesen (Stand v1.10.1).
  StatPlots `tests/test_stats.js` prüft ihn gegen die Python-Ergebnisse
  (331 Fälle, Python-Code zeichengenau). Beim CSV-Einlesen ist StatPlot in zwei
  Fällen besser als `csv.Sniffer` (Dezimalkomma ohne Kopfzeile, Tab-Dateien).
- Seit 1.10.3 lädt NIT_Code zuerst die Online-Version von
  statplot.mint-checker.de (Änderungen dort sind sofort sichtbar). Meldet sie
  sich nicht binnen 8 s, zeigt es die mitgelieferte Kopie unter
  `nit_code/assets/statplot` über einen lokalen Server auf 127.0.0.1
  (`nit_code/statplot_window.py`, Unterklasse von `PapEditorWindow`).
  Die Kopie gleicht jeder Release-Build automatisch mit StatPlot `main` ab;
  von Hand: `bash release/scripts/sync_statplot.sh ../StatPlot`, Stand steht in
  `nit_code/assets/statplot/VERSION`.
- Embed-Protokoll wie PAP/IBD (`source/target: 'statplot'`) plus Schalter in
  `load`: `open` (Dateidialog im Sketchbook), `code` (neuer Editor-Tab),
  `clipboard` (Kopieren über Qt), `nit` (Hinweise im Python-Code),
  `save:false` (kein „In Projekt übernehmen“).
  Die gemeinsame Host-Seite in `pap_editor.py` kennt dafür `_LOAD`, `_send()`
  und `_on_embed_event()`.
- Entfallen: `csv_plot.py`, `stat_tests.py`, `stat_tests_panel.py`,
  `csv_codegen.py`, `mint_style.py`, die Diagramm-Symbole in `icons.py`.
  `csv_stats.py` enthält nur noch die Ausgleichsgerade für den Serial Plotter.
- Neu gegenüber der Qt-Version: SVG-Export, Beispieldaten, Datei per
  Drag & Drop, Excel-CSV (Windows-1252), Vorauswahl ohne Nummerierungsspalten
  auch bei X/Y.

## Dateien

| Datei | Rolle |
|---|---|
| `nit_code/statplot_window.py` | Fenster, lokaler Server, Dateidialog, Code → Editor-Tab |
| `nit_code/pap_editor.py` | gemeinsame Host-Seite (iframe, postMessage, PNG-Rasterung) |
| `nit_code/assets/statplot/` | mitgelieferte StatPlot-Web-App (nicht von Hand ändern) |
| `release/scripts/sync_statplot.sh` | übernimmt StatPlot aus dessen Repository |
| `nit_code/csv_stats.py` | Ausgleichsgerade für den Serial Plotter (X-Y-Modus) |
| `release/requirements-runtime.txt` | matplotlib für die Schüler-Runtime |
| `nit_code/main_window.py` | `_open_csv_plot` |
| `README.md`, `nit_code/assets/hilfe/Kurzanleitung.md` | Doku |
| `nit_code/config.py` | `APP_VERSION` |
