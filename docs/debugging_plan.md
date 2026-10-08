# NIT_Code für die Debugging-Landkarte – Umsetzungskonzept

*Bezug: „Debugging-Landkarte – Konzept Version 2.1“, vor allem Abschnitt 7 (Anforderungen an NIT_Code)*
Stand: 2026-10-08 · A–H umgesetzt in `feature_sj/debugging` (1.11.0-beta.1), siehe Abschnitt 16
Branch für die Umsetzung: `feature_sj/debugging` · Release als Beta `1.11.0-beta.N`

---

## 0. Leitlinien

1. **Gleiche Begriffe wie im Material.** NIT_Code spricht von *Fehlerebenen* (0, 1a, 1b, 2, 3), von den *Karten* PAP und IBD, vom *Zyklus* und von *Verdächtigen*. Kein eigenes Vokabular.
2. **Die Meldung grenzt ein, die Karte lokalisiert.** NIT_Code liefert Hinweise und Verdächtigenlisten, **nie die fertige Lösung**. Das gilt für die festen Hinweise genauso wie für Infi.
3. **Das Material funktioniert ohne NIT_Code-Erweiterung.** Jede Funktion hat eine Entsprechung auf Papier (Rückfallebene aus Abschnitt 7). Wo es geht, ist das Werkzeug *dieselbe* Vorlage wie auf dem AB (z. B. der I2C-Scan als einfügbares Skript).
4. **Offline und deterministisch.** Alles außer Infi läuft ohne Netz und ohne KI.
5. **Belegstand ehrlich halten.** Die Lesarten für `ENODEV`/`ETIMEDOUT` sind Arbeitshypothesen. Sie stehen in einer austauschbaren Tabelle und werden nach der Messreihe (Konzept, Abschnitt 11.1) ersetzt.

---

## 1. Stand heute (geprüft am Code)

| Bereich | Vorhanden | Lücke für das Konzept |
|---|---|---|
| Fehlererklärung | [error_hints.py](../nit_code/error_hints.py): fester Hinweis je Fehlertyp, Infi-Knopf „Fehler erklären“ | Nur nach **Typ** unterschieden. `OSError` hat einen Sammeltext („Pin/Bus richtig verkabelt? … Beim Dateizugriff …“), keine Unterscheidung nach Fehlercode, keine Ebene, kein Bezug zum IBD. `RuntimeError` aus `nitbw_bme280` bekommt nur den allgemeinen Text. |
| Traceback | Fehlerzeile im Editor markiert, `<stdin>` wird auf die aktive Datei abgebildet | Kein Hinweis „Hier beginnt deine Suche“ (letzte Zeile der **eigenen** Datei) im Unterschied zur Zeile in der Bibliothek. |
| Klickbare Fehlerlinks | in `OutputConsole.append_error` angelegt, funktionieren | – (Korrektur: ein zunächst vermuteter Fehler beim Löschen der Links besteht nicht) |
| I2C-Scan | – | fehlt |
| Stand sichern / zurück | Editor-Undo, Autosave, Git-Menü | Kein „letzter funktionierender Stand“; Git ist für Kl. 10 zu schwer. |
| Live-Werte | Serial Plotter (auch X-Y) | ausreichend; kleine Ergänzung für Plausibilität möglich (6.4) |
| Ebene 0 | Meldung „Verbindung zum Controller verloren“ | Kein Hinweis auf Schritt 0 (USB trennen, Sichtprüfung). Brownout-/Neustart-Meldungen des ESP32 werden nicht erkannt. |

---

## 2. Überblick: Bausteine und Reihenfolge

| Nr. | Baustein | Bezug im Konzept | Aufwand | Beta |
|---|---|---|---|---|
| **A** | Fehlerhinweise nach Ebenen, Hardware-Lesehilfe, gestufte Hilfe | 3.4, 3.5, 6.2, Abschnitt 7 Z. 3–4 | mittel | beta.1 |
| **B** | „Hier beginnt deine Suche“ im Traceback | 3.5 „Zeile im Traceback“ | klein | beta.1 |
| **C** | I2C-Scan (mit Vorlage zum Einfügen) | Abschnitt 7 Z. 1 | klein–mittel | beta.1 |
| **D** | Stände sichern und „Zurück zum letzten funktionierenden Stand“ | 3.1 Schritt 6, Abschnitt 7 Z. 2 | mittel | beta.2 |
| **E** | Schritt-0-Hinweis bei Gefahrenanzeichen | 3.6 | klein | beta.2 |
| **F** | Kontrollpunkte (PAP-Karte) | 3.2 | klein–mittel | beta.3 |
| **G** | Fehlerprotokoll-Panel mit Export | Abschnitt 5 | groß | beta.3/4 |
| **H** | Debugging-Landkarte als Hilfeseite | 3.1–3.6 | klein | beta.1 |
| **I** | Chip-ID prüfen (Sensortyp) | 3.4, „falscher Sensortyp“ | klein | optional |
| **J** | Erprobungsdaten (lokal, opt-in) | Abschnitt 9 | mittel | optional, nach Rücksprache |

A, B, C und H decken Abschnitt 7 schon weitgehend ab und sind die erste Beta. D bis G sind die „Ideen darüber hinaus“.

---

## 3. Baustein A – Fehlerhinweise nach Fehlerebenen

### 3.1 Regeln statt nur Fehlertyp

`error_hints.py` bekommt eine zweite Stufe: Vor dem Nachschlagen nach Typ werden **Regeln** geprüft, die auf Typ **und** Meldungstext passen. Die erste passende Regel gewinnt, sonst greift der bisherige Hinweis nach Typ.

| Regel | Erkennung (Meldung) | Ebene |
|---|---|---|
| `OSError` ENODEV | `[Errno 19]` oder `ENODEV` | 1b |
| `OSError` ETIMEDOUT | `[Errno 116]` oder `ETIMEDOUT` | 1b |
| `OSError` EIO | `[Errno 5]` oder `EIO` | 1b |
| `OSError` ENOENT | `[Errno 2]` oder `ENOENT` (Datei) | 1a (kein Hardwarefehler!) |
| BME280 nicht gefunden | `RuntimeError` + „BME280 nicht gefunden“ (Chip-ID im Text) | 1a, Verweis auf IBD |
| übrige `nitbw_*`-Meldungen | je Bibliothek nachpflegbar | 1a |
| alle bisherigen Typen | wie heute | 1a |

Wichtig ist ENOENT: Heute bekommt ein fehlender Dateipfad denselben „Pin/Bus“-Text wie ein I2C-Fehler. Das widerspricht der Ebenen-Logik.

### 3.2 Die Lesetabelle als Daten

Die Hardware-Regeln stehen nicht im Code, sondern in einer Datei `nit_code/assets/debug/lesetabelle.json`. Je Eintrag:

```json
{
  "id": "enodev",
  "match": {"type": "OSError", "message": ["Errno 19", "ENODEV"]},
  "ebene": "1b",
  "karte": "IBD",
  "lesart": "Unter der angesprochenen Adresse hat kein Gerät geantwortet.",
  "verdaechtige": ["Adresse im Code", "SDA/SCL (Leitung, Vertauschung)", "Versorgung des Sensors", "Sensor nicht angeschlossen"],
  "erster_test": "I2C-Scan: Liste leer → Bus oder Versorgung; andere Adresse → Adresse im Code",
  "belegt": false
}
```

- `belegt: false` → im Hinweis steht „mögliche Verdächtige“ statt „Ursachen“. Nach der Messreihe wird `belegt` auf `true` gesetzt und der Text angepasst, ohne Code-Änderung.
- Dieselbe Datei kann zu einer **Druckversion** der Lesetabelle für das AB gerendert werden (Baustein H), damit Werkzeug und Papier identisch bleiben.
- Lehrkräfte können eine eigene Tabelle neben der eingebauten ablegen (Einstellungsordner), etwa für weitere Sensoren.

### 3.3 Gestufte Hilfe in der Konsole

Der Hinweis erscheint nicht als Textblock, sondern gestuft, entsprechend den Hilfekarten aus Konzept 6.2:

```
💡 Ebene 1b – Meldung der Hardware-Schicht (OSError ENODEV)
   [ Stufe 2: Welche Karte? ]  [ Stufe 3: Verdächtige & erster Test ]
```

- **Stufe 1** (sofort sichtbar): Ebene und Klartext-Lesart.
- **Stufe 2** (Klick): Karte (PAP oder IBD) und die Leitfrage der Karte.
- **Stufe 3** (Klick): Verdächtigenliste entlang der IBD-Kette und ein erster Test. Beim Test steht, falls vorhanden, ein Knopf „I2C-Scan starten“ (Baustein C).
- Einstellung (Datei → Einstellungen → Editor/Hilfen): **„Fehlerhilfe gestuft“** an/aus. Aus = alles sofort sichtbar wie heute. Voreinstellung: an.

Technisch: Die Konsole ist ein `QTextEdit`. Die Stufenknöpfe werden als Anker-Links umgesetzt (gleiches Prinzip wie die Traceback-Links); ein Klick hängt die nächste Stufe an.

### 3.4 Infi passt sich an

`build_infi_error_prompt` erhält die erkannte Ebene und die Verdächtigenliste und bittet Infi ausdrücklich, im Zyklus zu antworten:

> Nenne die Fehlerebene, welche Karte (PAP oder IBD) hilft, höchstens drei Verdächtige und **einen** Test, der sie unterscheidet. Gib keine fertige Lösung und keinen korrigierten Code.

Bei Ebene 1b wird zusätzlich die IBD-Kette aus Konzept 3.3 mitgeschickt.

---

## 4. Baustein B – „Hier beginnt deine Suche“

Nach einem Absturz wertet NIT_Code alle `File "…", line N`-Zeilen aus und unterscheidet:

- **eigene Datei** (aktive Datei bzw. `<stdin>` bei MicroPython),
- **Bibliothek** (`nitbw_*.py`, alles unter `lib/`, Standardbibliothek).

Ausgabe unter dem Traceback:

```
📍 Hier beginnt deine Suche: Zeile 8 in deiner Datei  sensor = BME280(i2c)
   Die Meldung entsteht in nitbw_bme280.py, Zeile 41 (Bibliothek – dort nichts ändern).
```

- Zeile 8 wird im Editor markiert (wie heute), die Bibliothekszeile nicht.
- Didaktischer Zweck: genau die kleine Übung aus DS 1 („Markiere die letzte Zeile der eigenen Datei“). Für diese Übung kann die Lehrkraft die Zeile über die Einstellung „Fehlerhilfe gestuft“ zunächst verbergen; sie erscheint dann erst als Stufe 2.

---

## 5. Baustein C – I2C-Scan

### 5.1 Bedienung

- Menü **MicroPython → 🔍 I2C-Scan …** (nur im MicroPython-Modus, wie die übrigen Einträge).
- Kleiner Dialog: Bus-Nummer, **SDA-Pin, SCL-Pin** (Voreinstellung 21/22 wie die Blockly-Vorlage; zuletzt genutzte Werte werden gemerkt), Knopf „Scannen“.
- Ergebnis in der Konsole und im Dialog:

```
🔍 I2C-Scan an SDA=21, SCL=22
   Gefunden: 0x76   (bekannt als: BME280 / BMP280)
   In deinem Code steht die Adresse: 0x77
```

- Bei leerer Liste: „Kein Gerät antwortet. Verdächtige: Versorgung, SDA/SCL-Leitung, Pins im Scan-Dialog.“
- Die Zeile **„In deinem Code steht …“** liest Adressen der Form `0x..` aus der aktiven Datei. Es wird **kein Urteil** ausgegeben („Adresse falsch!“), nur beide Werte nebeneinander. Den Schluss ziehen die SuS. So bleibt der Scan ein Test im Zyklus und keine Lösungsmaschine.
- Tabelle bekannter Adressen (aus den NIT-Bibliotheken): 0x76/0x77 BME280/BMP280, 0x23/0x5C BH1750, 0x40–0x45 INA219, 0x48–0x4B ADS1015, 0x3C/0x3D OLED, 0x68/0x69 MPU6050/RTC … (als Daten neben der Lesetabelle).

### 5.2 Rückfallebene = dieselbe Vorlage

Knopf **„Als Skript einfügen“** öffnet einen neuen Tab mit genau dem Skript, das auf dem AB steht:

```python
from machine import I2C, Pin
i2c = I2C(0, sda=Pin(21), scl=Pin(22))
geraete = i2c.scan()
print("Gefundene Adressen:", [hex(a) for a in geraete])
```

### 5.3 Technik

- Ausführung wie bei „Firmware-Version abfragen“: `mpremote connect <port> exec <code>` mit `_acquire_port()`/`_release_port()`.
- Zeitlimit (z. B. 8 s): Ohne Pull-ups kann der Bus blockieren. Dann Meldung „Der Scan hat nicht geantwortet – das ist selbst ein Befund (Bus blockiert?)“ und Hinweis auf Schritt 0 bei Neustarts.
- Fehler beim Erzeugen des Busses (falsche Pin-Nummer) werden als normale Meldung durchgereicht.

---

## 6. Baustein D – Stände sichern und zurückgehen

Ziel: Schritt 6 des Zyklus („zurück zum letzten funktionierenden Stand“) und das Bewertungskriterium „eine Änderung“ ohne Git unterstützen.

### 6.1 Automatische Lauf-Stände

- Bei **jedem Programmstart** legt NIT_Code einen Stand der Datei an, zusammen mit dem Ergebnis des Laufs: ✓ (Ende ohne Fehler), ✗ (mit Fehlermeldung, erste Zeile der Meldung wird gespeichert) oder ■ (vom Nutzer gestoppt).
- Gespeichert wird im Projekt in einem versteckten Ordner `.nit_staende/<dateiname>/` (Zeitstempel + kleine JSON-Datei). Höchstens 50 Stände je Datei, ältere werden gelöscht. Gleiche Inhalte werden nicht doppelt gespeichert.
- Gilt auch für Controller-Dateien, die direkt bearbeitet werden (📟), dann im lokalen Einstellungsordner.

### 6.2 Manuell: „Stand merken“

- **Bearbeiten → 📌 Stand merken …** mit kurzer Notiz („läuft, Temperatur plausibel“). Gemerkte Stände sind hervorgehoben. Das entspricht dem „Ausgangszustand dokumentieren“ vor der Sabotage.

### 6.3 Zurück

- **Bearbeiten → ⏪ Zurück zum letzten funktionierenden Stand** (letzter ✓- oder 📌-Stand).
- **Bearbeiten → 🕘 Stände anzeigen …**: Liste mit Zeit, Ergebnis, Notiz; rechts ein **Vergleich** (Diff) zum aktuellen Code. Wiederherstellen ersetzt den Editorinhalt (mit Strg+Z rückgängig zu machen).
- Für den Diff wird die vorhandene Vergleichsansicht aus dem Git-Menü wiederverwendet, falls sie sich lösen lässt; sonst `difflib` mit einfacher Einfärbung.

### 6.4 Hinweis „Eine Änderung, dann testen“

- Beim Programmstart zeigt die Konsole in einer Zeile, wie viel sich seit dem letzten Lauf geändert hat: `Seit dem letzten Lauf: 1 Stelle geändert (Zeile 12)`.
- Bei mehreren Stellen: `… 4 Stellen geändert – im Zyklus testest du eine Änderung nach der anderen.` Nur Hinweis, kein Blockieren.
- Einstellung an/aus. Sinnvoll schon ab Kl. 8/9 („Eine Änderung, dann testen“).

---

## 7. Baustein E – Schritt 0 bei Gefahrenanzeichen

NIT_Code kann einen Kurzschluss nicht erkennen. Es sieht aber **Folgen**, die zu den Anzeichen aus Konzept 3.6 passen:

| Beobachtung in NIT_Code | Erkennung |
|---|---|
| USB-Verbindung bricht während des Laufs ab | bestehende Meldung „Verbindung zum Controller verloren“ |
| Board startet neu | Boot-Text des ESP32 in der Ausgabe (`rst:0x…`, `ets …`, `boot:`) |
| Spannungseinbruch | ESP32-Meldung `Brownout detector was triggered` |
| Port verschwindet mehrfach in kurzer Zeit | Portliste |

Dann erscheint ein deutlich abgesetzter Kasten (kein Pop-up, das weggeklickt wird):

```
⚠ Schritt 0 – erst sichern, dann suchen
  1. USB-Kabel trennen.
  2. Nicht anfassen, wenn etwas heiß ist oder riecht. Lehrkraft rufen.
  3. Sichtprüfung: Berühren sich Leitungen? Sitzt der Sensor richtig? Polung?
  Das kann auch ein Wackelkontakt sein – geprüft wird trotzdem zuerst.
```

Bei „Brownout“ ist der Text deutlicher (Spannungseinbruch → Versorgung/Kurzschluss prüfen). Die Formulierung entspricht dem Poster.

---

## 8. Baustein F – Kontrollpunkte (PAP-Karte)

Unterstützt die Leitfrage „Bis zu welchem Kästchen läuft mein Programm wie geplant?“.

- **Rechtsklick im Editor → „Kontrollpunkt hier einfügen“** (oder Strg+K): fügt `print("KP 1:", )` mit fortlaufender Nummer und der Markierung `# KP` ein. Ist ein Name markiert, wird er mitausgegeben (`print("KP 2: temp =", temp)  # KP`).
- In der Konsole werden `KP n`-Ausgaben farbig hervorgehoben.
- Nach einem Absturz: `Letzter erreichter Kontrollpunkt: KP 2 (Zeile 14)`. Damit ist der Suchraum halbiert, ganz im Sinne der Karte.
- **„Alle Kontrollpunkte entfernen“** löscht alle Zeilen mit `# KP` wieder. So bleibt der Code sauber und die Änderung ist eindeutig rückgängig zu machen.
- Optional später: Nummern der Kontrollpunkte den Kästchen im PAP-Editor zuordnen (PAP läuft im iframe, das ist aufwändiger und gehört nicht in die erste Beta).

---

## 9. Baustein G – Fehlerprotokoll im Programm

Das Protokoll aus Konzept Abschnitt 5 als Seitenleiste (neben Infi und AIS-Chat im rechten Bereich).

### 9.1 Aufbau

- **Kurzform** (Kl. 8/9): Soll/Ist, Vermutung, Test, Ergebnis.
- **Vollform** (Kl. 10/KS): alle acht Spalten.
- Umschaltbar in den Einstellungen und im Panel.

### 9.2 Was NIT_Code einträgt – und was nicht

| Spalte | Von NIT_Code vorbelegt | Von SuS |
|---|---|---|
| Nr., Zeit | ✓ | |
| Ist | letzte Meldung (letzte Traceback-Zeile) als Vorschlag | präzisieren |
| Ebene und Karte | **nicht vorbelegt**, Auswahl 0/1a/1b/2/3 und PAP/IBD | ✓ (begründen) |
| Hypothese | | ✓ |
| Test (eine Änderung) | Verweis auf den Lauf-Stand mit Diff (Baustein D) | Beschreibung |
| Ergebnis | ✓/✗ des folgenden Laufs als Hinweis | bestätigt / widerlegt / verfeinert |
| Zurück nötig? | Knopf „Zurück zum letzten funktionierenden Stand“ | ✓ |
| Lösung und Lerneffekt | | ✓ |

Grundsatz: NIT_Code trägt nur **Fakten** ein (Zeit, Meldung, Änderung, Laufergebnis). Alles, was Denken zeigt und bewertet wird (Ebene, Hypothese, Lerneffekt), schreiben die SuS.

### 9.3 Sabotage-Runde

- Feld **„Verdeckte Notiz (Partner B)“**: Fehler und erwartetes Symptom, wird verborgen gespeichert und erst mit „Auflösen“ angezeigt. Unterstützt den Ablauf aus Konzept 4 (Vorhersage des Symptoms).

### 9.4 Speichern und Abgabe

- Gespeichert als `<datei>.fehlerprotokoll.md` neben dem Programm, im Obsidian-Stil (Tabelle oder Callouts), passend zu den Arbeitsblättern und mit der vorhandenen Arbeitsblatt-Vorschau darstellbar.
- Export als PDF/Druck für die Bewertung nach 5.1; die Bewertungsstufen sind **nicht** im Programm, sie bleiben bei der Lehrkraft.

---

## 10. Baustein H – Debugging-Landkarte als Hilfeseite

- **Hilfe → 🗺 Debugging-Landkarte** öffnet eine Seite in der Arbeitsblatt-Vorschau mit Zyklus (Schritt 0–6), Fehlerebenen-Tabelle, den beiden Karten, der IBD-Kette BME280 und der Lesetabelle (aus `lesetabelle.json` erzeugt).
- Gleicher Wortlaut wie Poster/Folie. Die Markdown-Quelle liegt unter `nit_code/assets/debug/landkarte.md` und kann für das Material wiederverwendet werden.

---

## 11. Optionale Bausteine

### I – Chip-ID prüfen

Im I2C-Scan-Dialog bei gefundener Adresse 0x76/0x77 der Knopf „Chip-ID lesen“ (Register 0xD0): `0x60` = BME280, `0x58` = BMP280. Passt zum Fall „falscher Sensortyp“ und zum `RuntimeError` der Bibliothek. Wieder nur Anzeige, kein Urteil.

### J – Erprobungsdaten (Konzept Abschnitt 9)

Nur nach Rücksprache, **Datenschutz zuerst**:
- strikt opt-in durch die Lehrkraft, nur lokal, keine Namen, kein Code, keine Übertragung;
- erfasst würden nur: Zeit vom ersten Fehler bis zum nächsten ✓-Lauf, Zahl der geänderten Stellen je Lauf;
- Export als CSV, Auswertung z. B. mit StatPlot.

Vorschlag: zunächst weglassen und die Messung wie im Konzept mit Stoppuhr und Beobachtung machen.

---

## 12. Nicht im Umfang

- Schrittweises Debuggen mit Haltepunkten (MicroPython über Raw-REPL bietet das nicht sinnvoll; widerspricht auch dem Konzept, das mit Kontrollpunkten arbeitet).
- Fehlerzuordnung zu Blockly-Blöcken (Zeilennummern beziehen sich auf den erzeugten Code).
- Automatische Fehlerdiagnose („Dein SDA ist vertauscht“).

---

## 13. Technische Einordnung (Dateien)

| Baustein | Dateien |
|---|---|
| A | `error_hints.py` (Regeln, Stufen, Infi-Prompt), neu `assets/debug/lesetabelle.json`, `console_panel.py` (Stufen-Links), `settings_dialog.py` |
| B | `main_window.py` (`_handle_program_error`, `_resolve_traceback_file`), `console_panel.py` |
| C | `main_window.py` (Menüeintrag, mpremote-Aufruf), neu `i2c_scan.py` (Dialog, Adresstabelle) |
| D | neu `snapshots.py` (Speichern, Aufräumen, Diff), `main_window.py` (Hooks bei Start/Ende, Menü) |
| E | `console_panel.py` (Erkennung im MicroPython-Runner), `error_hints.py` (Texte) |
| F | `editor_widget.py` (Kontextmenü, Einfügen/Entfernen), `console_panel.py` (Hervorhebung) |
| G | neu `debug_log_panel.py`, `main_window.py` (rechter Bereich) |
| H | neu `assets/debug/landkarte.md`, `main_window.py` (Hilfe-Menü), `worksheet_panel.py` |

Tests: Einheitstests für Regel-Erkennung (echte MicroPython-Tracebacks aus der Messreihe als Testdaten), „eigene Datei vs. Bibliothek“, Snapshot-Aufräumen, Kontrollpunkte einfügen/entfernen.

---

## 14. Branch, Versionen, Release

- Branch `feature_sj/debugging` von `main` (Stand 1.10.4).
- Version im Branch: `1.11.0-beta.1`, `-beta.2`, … (Tag `v1.11.0-beta.N`); der CI-Build lädt Tag-Builds bereits ans Entwurfs-Release, dort als **Pre-Release** markieren.
- Fehlerbehebungen für `main` können vorab einzeln nach `main` übernommen werden.
- Merge nach `main` und Release als `1.11.0`, wenn die Messreihe eingearbeitet und das Modul einmal erprobt ist.

### Vorschlag Beta-Folge

| Beta | Inhalt | sinnvoll bis |
|---|---|---|
| beta.1 | A, B, C, H | zur Messreihe – die Lesetabelle wird dabei direkt am Gerät geprüft |
| beta.2 | D, E | vor DS 1 |
| beta.3 | F, G (Kurz- und Vollform) | vor DS 1 / DS 2 |
| beta.4 | Lesetabelle mit Messreihe belegt, Feinschliff nach Erprobung | – |

---

## 15. Offene Fragen

1. **Pins für den Scan:** Sind SDA 21 / SCL 22 auf euren Boards (Steckbrett und Breakout) überall richtig?
2. **Gestufte Hilfe voreingestellt an?** Oder soll die Lehrkraft sie pro Rechner/Kurs einschalten?
3. **Ort der Stände:** im Projektordner (`.nit_staende/`, wandert mit dem Projekt auf den Schulserver) oder lokal im Benutzerprofil (Netzlaufwerk bleibt sauber)?
4. **Fehlerprotokoll im Programm oder auf Papier?** Baustein G ist der größte Aufwand. Er lohnt sich, wenn das Protokoll digital abgegeben werden soll.
5. **Messreihe:** Sobald sie vorliegt, liefert sie gleich die Testdaten für Baustein A. Ein Mitschnitt der Konsolenausgabe (kopierter Text) pro Sabotage reicht.

---

## 16. Umsetzungsstand und Entscheidungen (2026-10-08)

**Entscheidungen**
- A–G werden umgesetzt; die verdeckte Notiz von Partner B (9.3) entfällt.
- Die Landkarte (H) sind die beiden Poster als Bild (`assets/debug/landkarte_kl89.png`, `landkarte_kl10.png`) statt einer Markdown-Seite.
- Die Begriffe folgen den Postern: Kl. 8/9 kennt die Ebenen 0, 1a, 2, 3 und die Karten STOPP, PAP, Checkliste; Kl. 10/KS zusätzlich 1b, IBD und „PAP + IBD“. Kontrollpunkte heißen wie auf dem Poster `print("K3")`.
- Stände liegen im Benutzerprofil (`<Konfig>/nit_code/staende/`), nicht im Projektordner.
- Die Pins für den I2C-Scan werden aus dem eigenen Code übernommen (sonst zuletzt genutzte Werte, Voreinstellung 21/22).

**Umgesetzt in 1.11.0-beta.1**

| Baustein | Wo |
|---|---|
| A Fehlerhilfe nach Ebenen, gestuft, Lesetabelle, Infi im Zyklus | `error_hints.py`, `assets/debug/lesetabelle.json`, Links in `console_panel.py` |
| B „Hier beginnt deine Suche“ (eigene Datei vs. Bibliothek) | `main_window._show_search_start` |
| C I2C-Scan mit Adresse aus dem Code, Chip-ID (I), Vorlage einfügen | `i2c_scan.py`, Menü Debuggen und MicroPython |
| D Lauf-Stände ✓/✗/■, 📌 Stand merken, ⏪ Zurück, Stände-Dialog mit Vergleich, Änderungshinweis | `snapshots.py` |
| E Schritt-0-Kasten bei Brownout, Neustart, USB-Abbruch | `error_hints.detect_danger`, `main_window._debug_track_output` |
| F Kontrollpunkte einfügen/entfernen (Strg+K, Rechtsklick), letzter erreichter Kontrollpunkt | `checkpoints.py` |
| G Fehlerprotokoll-Panel Kurz-/Vollform, Läufe als Fakten, Markdown neben dem Programm, PDF | `debug_log_panel.py` |
| H Debugging-Landkarte (Hilfe und Debuggen) | `debug_map_dialog.py` |

Einstellungen → DEBUGGING: Stufe (Kl. 8/9 / Kl. 10/KS), Fehlerhilfe in Stufen, Änderungshinweis.

**Noch offen:** Messreihe am Gerät (Lesetabelle von „Arbeitshypothese“ auf „belegt“ umstellen), Test mit echtem ESP32 (I2C-Scan, Brownout-Erkennung), Erprobung im Unterricht.
