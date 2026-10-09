# Messreihe I2C-Fehler (BME280, `nitbw_bme280`)

Stand: 2026-10-09 · Aufbau: ESP32-C3 (SDA = GPIO 3, SCL = GPIO 4), MicroPython v1.29.0, Hardware-I2C, Sensor-Adresse 0x76 (= 118)

Messprogramm (ein Fall pro Programmstart, damit sich die Fälle nicht beeinflussen):

```python
from machine import I2C, Pin
from nitbw_bme280 import BME280

SDA, SCL, ADRESSE = 3, 4, 0x76     # pro Fall nur diese Zeile ändern

i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL))
print("i2c.scan() liefert:", i2c.scan())
sensor = BME280(i2c, addr=ADRESSE)
print(sensor.read_all())
```

## Ergebnisse

| Nr. | Sabotage | Auslösung | `i2c.scan()` | Meldung | Ort im Traceback |
|---|---|---|---|---|---|
| 0 | richtig (Kontrolle) | SDA 3, SCL 4, 0x76 | `[118]` | läuft: `(21.31, 993.07, 43.68)` | – |
| 1 | Adresse im Code falsch | `ADRESSE = 0x77` | `[118]` | `OSError: [Errno 19] ENODEV` | `__init__` (Z. 103) → `_read_u8` (Z. 129) |
| 2 | SDA/SCL **im Code** vertauscht | `SDA, SCL = 4, 3` | `[]` | `OSError: [Errno 19] ENODEV` | wie Nr. 1 |
| 3 | SDA/SCL **am Kabel** vertauscht | Kabel umgesteckt (USB getrennt) | `[]` | `OSError: [Errno 19] ENODEV` | wie Nr. 1 |
| 4 | Wackelkontakt | nicht gezielt reproduzierbar (siehe Nr. 6) | – | – | – |
| 5 | Sensor ohne Versorgung | 3V3 abgezogen (USB getrennt) | nicht gemessen | `OSError: [Errno 19] ENODEV` | wie Nr. 1 |
| 6 | Verbindung **im Lauf** gelöst | Datenleitungen während der Messschleife abgezogen | – | `OSError: [Errno 19] ENODEV` nach 4 gelungenen Messungen | `read_all` (Z. 321) → `_read_raw_data` (Z. 216) → `_read_u8` (Z. 129) |

## Was die Messung zeigt

1. **Die Meldung allein trennt die Ursachen nicht.** Fünf verschiedene Ursachen (Nr. 1, 2, 3, 5 und 6) liefern dieselbe Meldung `ENODEV`. Das ist die Kernbotschaft des Moduls: *Die Meldung grenzt ein, die Karte lokalisiert.*
2. **`i2c.scan()` trennt zwei Gruppen:**
   - `[118]` (eine andere Adresse antwortet) → Adresse im Code (Nr. 1).
   - `[]` (niemand antwortet) → Pins im Code, Kabel, Versorgung (Nr. 2, 3, 5, 6).
3. **Innerhalb von `[]` hilft nur noch Hinsehen:** Nr. 2 (Code) und Nr. 3 (Kabel) sind in Meldung und Scan **identisch**. Unterscheiden lassen sie sich nur, indem man die Pin-Nummern im Code mit dem Aufbau vergleicht (IBD, P1). Das ist die Aufgabe „gleiches Symptom, zwei Ursachen“.
4. **Der Ort im Traceback trennt „von Anfang an“ und „später“:** Läuft der Fehler über `__init__`, war der Sensor nie erreichbar (Nr. 1, 2, 3, 5). Läuft er über `read_all`, hat der Sensor zuerst geantwortet und dann nicht mehr (Nr. 6, Wackler). NIT_Code zeigt dafür zwei verschiedene Hinweise.
5. **`ETIMEDOUT` ist bei Hardware-I2C auf diesem Aufbau in keinem Fall aufgetreten.** Die Lesart bleibt Arbeitshypothese.
6. Ein `ValueError: invalid pin`, der in einem Mehrfachlauf auftrat, war ein Artefakt (mehrere Fälle nacheinander auf demselben Bus). Im sauberen Einzellauf ergibt Nr. 2 `ENODEV`.

## Was NIT_Code daraus macht

- `ENODEV` ist **belegt** (alle genannten Verdächtigen erzeugen sie). Der erste Test lautet jetzt: `i2c.scan()` – leere Liste oder andere Zahl.
- Zwei Varianten je nach Ort im Traceback (siehe 4); ohne erkennbaren Ort gilt der allgemeine Text.
- `ETIMEDOUT` und `EIO` bleiben als Arbeitshypothese gekennzeichnet.

## ETIMEDOUT: nur mit SoftI2C und festgehaltener SCL (2026-10-09)

**Hardware-I2C (`I2C(0, …)`) liefert in allen weiteren Versuchen `ENODEV`:**

| Versuch | Meldung |
|---|---|
| alle Pins einzeln ausgesteckt | `ENODEV` |
| SCL gezielt auf GND | `ENODEV` |
| SDA gezielt auf GND | `ENODEV` |
| `freq` geändert | `ENODEV` |

**`ETIMEDOUT` tritt mit `SoftI2C` auf, wenn ein anderer Teilnehmer SCL auf LOW hält** (Clock Stretching ohne Ende). Aufbau: Ein freier GPIO (`TEST_PIN = 2`) ist extern mit SCL verbunden und als Open-Drain konfiguriert. Er kann die Leitung nur nach LOW ziehen oder loslassen und erzeugt daher keinen Kurzschluss.

| Zustand | Ausgabe |
|---|---|
| SCL festgehalten | `scan: []` und `OSError: [Errno 116] ETIMEDOUT` bei `writeto` |
| nach dem Loslassen | `scan: [118]` |

Das passt zur MicroPython-Dokumentation (für `SoftI2C` ist `ETIMEDOUT` das Zeichen, dass ein Gerät SCL zu lange festhält). Im Unterricht, mit `I2C(0, …)`, ist `ETIMEDOUT` daher **nicht zu erwarten**. Er bleibt als Arbeitshypothese in der Lesetabelle, weil nur die Ursache „SCL wird festgehalten“ gemessen ist.

**Hinweis zur Sicherheit:** Eine Datenleitung gezielt an GND zu legen gehört nicht in die Sabotageliste für SuS. Die Open-Drain-Variante oben ist für die Lehrkraft die harmlose Form.

## Testskript: ETIMEDOUT mit der Bibliothek

Ein Skript, mit dem sich Bus (SoftI2C oder Hardware) und Zeitpunkt (Start oder im Betrieb) umschalten lassen. Der Fehler bleibt **ungefangen**, damit NIT_Code seine Hinweise zeigt; `finally` gibt den Bus danach wieder frei.

```python
from machine import Pin, SoftI2C, I2C
import time
from nitbw_bme280 import BME280

SDA_PIN, SCL_PIN, TEST_PIN = 3, 4, 2   # TEST_PIN: freier GPIO, extern mit SCL verbinden
DEVICE_ADDR = 0x76
BUS = "soft"        # "soft" = SoftI2C, "hardware" = I2C(0, ...)
MODUS = "start"     # "start": SCL schon beim Erzeugen festhalten, "betrieb": erst nach 3 Messungen

if BUS == "soft":
    i2c = SoftI2C(sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100_000, timeout=20_000)
else:
    i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100_000)

blocker = Pin(TEST_PIN, Pin.OPEN_DRAIN, value=1)   # 1 = hochohmig, lässt SCL frei

try:
    if MODUS == "start":
        blocker.value(0)                           # SCL nach LOW ziehen
    sensor = BME280(i2c, addr=DEVICE_ADDR)
    for n in range(1, 6):
        if MODUS == "betrieb" and n == 4:
            blocker.value(0)
        print(n, sensor.read_all())
        time.sleep(0.5)
finally:
    blocker.value(1)                               # Bus wieder freigeben
```

Erwartung (noch zu bestätigen):

| BUS | MODUS | Erwartet |
|---|---|---|
| `soft` | `start` | `ETIMEDOUT` über `__init__` → `_read_u8` |
| `soft` | `betrieb` | 3 Messungen, dann `ETIMEDOUT` über `read_all` |
| `hardware` | `start` | `ENODEV` (wie bisher) |
| `hardware` | `betrieb` | offen |
