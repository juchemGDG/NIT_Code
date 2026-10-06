# Plan: Datenauswertung (CSV) – Erweiterung des CSV-Streudiagramms

Stand: 2026-10-06 · Branch: `feature_sj/layout` · Ausgangsversion 1.10.0-beta.8, Stufe 1 in 1.10.0-beta.9

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

## Dateien

| Datei | Rolle |
|---|---|
| `nit_code/csv_stats.py` | Qt-freie Statistik: Kennwerte, Quartile, Klassen, Häufigkeiten, Aggregation |
| `nit_code/csv_plot.py` | Fenster, CSV-Einlesen, Canvas je Diagrammtyp, Code-Dialog |
| `nit_code/csv_codegen.py` | Qt-freier Generator für den Python-Code (csv + matplotlib) |
| `nit_code/serial_plot.py` | Ausgleichsgerade im X-Y-Modus |
| `nit_code/stat_tests.py` | Qt-freie Tests: Binomialtest, t-Tests, t-Verteilung |
| `nit_code/stat_tests_panel.py` | Reiter „Statistik-Tests“ |
| `nit_code/mint_style.py` | Palette + Stylesheets im PAP-/IBD-Look |
| `nit_code/icons.py` | Symbole der Diagrammtypen, Chevron |
| `release/requirements-runtime.txt` | matplotlib für die Schüler-Runtime |
| `nit_code/main_window.py` | Menüeintrag `_open_csv_plot` |
| `README.md`, `nit_code/assets/hilfe/Kurzanleitung.md` | Doku |
| `nit_code/config.py` | `APP_VERSION` |
