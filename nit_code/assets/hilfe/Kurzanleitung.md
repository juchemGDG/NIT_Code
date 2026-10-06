# NIT_Code – Kurzanleitung

Python und MicroPython in einer Oberfläche. Download: <https://github.com/juchemGDG/NIT_Code/releases/latest>

---

## 1. Python (lokal)

![Python-Modus mit Nummern](img/python_annotiert.png)

| Nr. | Element | Was es tut |
|---|---|---|
| 1 | **Starten** (`F5`) | Programm ausführen |
| 2 | **Stoppen** (`F6`) | Programm abbrechen |
| 3 | **Modus** | `Python (lokal)` einstellen |
| 4 | Editor | Code schreiben, `Strg+F` suchen, `Strg+H` ersetzen, `Strg+/` auskommentieren |
| 5 | **Ausgabe** | `print()`-Ausgaben, Eingaben mit `input()`, Fehler in Rot (Klick springt zur Zeile) |
| 6 | Menüleiste | Datei, Blöcke, Visualisieren, Python (pip), Git, Hilfe |

### Beispiel: Zahlenraten

```python
import random

zahl = random.randint(1, 10)
tipp = 0
while tipp != zahl:
    tipp = int(input("Rate (1-10): "))
print("Richtig!")
```

### Die wichtigsten Befehle

| Aufgabe | Code |
|---|---|
| Ausgabe | `print("Hallo", name)` |
| Eingabe (Text / Zahl) | `name = input("Name? ")` · `n = int(input("Zahl? "))` |
| Bedingung | `if x > 5:` … `elif x == 5:` … `else:` |
| Schleife mit Zähler | `for i in range(10):` |
| Schleife mit Bedingung | `while x < 10:` |
| Funktion | `def quadrat(x):` → `return x * x` |
| Liste | `werte = [3, 5, 7]` · `werte.append(9)` · `len(werte)` |
| Zufall / Pause | `random.randint(1, 6)` · `time.sleep(0.5)` |

> **Tipp:** Zeigt die Ausgabe einen Fehler, kann der KI-Tutor **Infi** ihn erklären (optional, lokal über Ollama).

---

## 2. MicroPython (ESP32, Pico, micro:bit)

![MicroPython-Modus mit Nummern](img/micropython_annotiert.png)

| Nr. | Element | Was es tut |
|---|---|---|
| 1 | **Starten** | Programm direkt auf dem Controller ausführen (ohne zu speichern) |
| 2 | **Modus** | auf `MicroPython` umschalten |
| 3 | **Gerät** | USB-Port des Controllers wählen (↻ sucht neu) |
| 4 | **Hochladen** (`F7`) | Programm als `main.py` auf den Controller speichern, läuft nach jedem Einschalten |
| 5 | **Neustart** | Controller zurücksetzen |
| 6 | Controller-Dateien | Dateien auf dem Board ansehen |

### Erste Schritte

1. Controller per USB anschließen → Modus **MicroPython** → Gerät wählen.
2. Neues Board? Menü **MicroPython → Firmware flashen …**
3. Sensor-Bibliotheken: Menü **MicroPython → Bibliotheken installieren …**

![Menü MicroPython](img/05_menu_micropython.png)

### Beispiel: LED blinken lassen

```python
from machine import Pin
import time

led = Pin(2, Pin.OUT)      # ESP32: eingebaute LED an Pin 2
while True:
    led.value(1)           # an
    time.sleep(0.5)
    led.value(0)           # aus
    time.sleep(0.5)
```

### Die wichtigsten Befehle

| Aufgabe | Code |
|---|---|
| Digitaler Ausgang (LED) | `led = Pin(2, Pin.OUT)` · `led.value(1)` / `led.on()` / `led.off()` |
| Digitaler Eingang (Taster) | `taster = Pin(4, Pin.IN, Pin.PULL_UP)` · `taster.value()` |
| Analog lesen (0–4095) | `adc = ADC(Pin(34))` · `adc.read()` |
| Analog lesen in Volt (ESP32) | `adc.atten(ADC.ATTN_11DB)` · `adc.read_uv() / 1_000_000` |
| PWM (Helligkeit, Servo) | `pwm = PWM(Pin(5), freq=1000)` · `pwm.duty(512)` |
| NeoPixel | `np = NeoPixel(Pin(15), 8)` · `np[0] = (255, 0, 0)` · `np.write()` |
| Pause | `time.sleep(1)` · `time.sleep_ms(200)` |
| Import | `from machine import Pin, ADC, PWM` · `from neopixel import NeoPixel` |

### Beispiel: Sensorwert als Graph (Serial Plotter)

```python
from machine import Pin, ADC
import time

sensor = ADC(Pin(34))
while True:
    print(sensor.read())   # nur Zahlen ausgeben
    time.sleep(0.1)
```

Dann in der Werkzeugleiste **Serial Plotter** einschalten: Die Zahlen erscheinen live als Kurve.

---

## 3. Block-Editor

Programmieren mit Blöcken – NIT_Code erzeugt daraus lesbaren Python- bzw. MicroPython-Code.
Öffnen: Menü **Blöcke → Block-Editor öffnen …**

![Block-Editor](img/blockeditor_annotiert.png)

| Nr. | Element | Was es tut |
|---|---|---|
| 1 | Kategorien | Blöcke auswählen (Kontrollstrukturen, Logik, Zeit, MicroPython, NeoPixel, nitbw-Bibliotheken …) |
| 2 | Arbeitsfläche | Blöcke hineinziehen und zusammenstecken (Beispiel: LED blinken) |
| 3 | **In Python umwandeln** | Code erzeugen und in den Editor einfügen |

Umgekehrt geht es auch: **Blöcke → Code → Blöcke (aktuelle Datei)** wandelt vorhandenen Code in Blöcke um (BETA).

---

## 4. KI-Codegenerator

Du beschreibst, die KI programmiert: erst **Eingabe / Ausgabe / Variablen** und den **Ablauf** festlegen, dann wird der Code erzeugt.
Einschalten: **Einstellungen** (`Strg+,`) → KI-Tutor → *Code-Generator*.

![Code-Generator](img/codegenerator_annotiert.png)

| Nr. | Element | Was es tut |
|---|---|---|
| 1 | **Spezifikation** | `## EINGABE`, `## AUSGABE`, `## VARIABLEN` ausfüllen |
| 2 | **Ablauf** | in eigenen Worten (Freitext) oder als Mermaid-Diagramm beschreiben |
| 3 | Signalwörter | `falls … dann`, `solange … tue`, `zähle … bis` per Klick einfügen |
| 4 | **Spezifikation senden** | KI prüft auf Vollständigkeit und fragt bei Lücken nach |
| 5 | Rückfrage | Antworten der KI beantworten, `Strg+Enter` sendet |
| 6 | **Code in Editor schreiben** / **Als Blöcke öffnen** | fertigen Code übernehmen |

> Die KI setzt den Ablauf **genau** um – auch Fehler. Das Programm testen und prüfen, ob es das tut, was du wolltest.

---

## 5. Weitere Hilfen

| Funktion | Wo |
|---|---|
| **Programmablaufplan** zeichnen | Knopf **PAP-Editor** rechts oben |
| **CSV-Daten** auswerten (Diagramme, Boxplot, Kennwerte, Signifikanz- und t-Tests) | *Visualisieren → Datenauswertung (CSV) …* |
| **pip-Pakete** installieren | Menü *Python → Pakete installieren (pip) …* |
| **Git** | Menü *Git* (klonen, commit, push, pull) |

### Tastenkürzel

| Taste | Aktion | Taste | Aktion |
|---|---|---|---|
| `F5` | Starten | `Strg+S` | Speichern |
| `F6` | Stoppen | `Strg+F` / `Strg+H` | Suchen / Ersetzen |
| `F7` | Hochladen (MicroPython) | `Strg+/` | Kommentar umschalten |
| `Strg+N` / `Strg+O` | Neu / Öffnen | `Strg+,` | Einstellungen |
| `F1` | Diese Kurzanleitung | | |

### Linux: „Permission denied" am USB-Port

```bash
sudo usermod -a -G dialout $USER   # danach ab- und wieder anmelden
```
