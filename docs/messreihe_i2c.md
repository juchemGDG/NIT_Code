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

## Offen: ETIMEDOUT finden

Vorschlag für weitere Einzelfälle (nur bei getrenntem USB umstecken, nie VCC und GND vertauschen, kein Kurzschluss):

| Nr. | Sabotage |
|---|---|
| 7 | nur **SDA** abgezogen, SCL steckt |
| 8 | nur **SCL** abgezogen, SDA steckt |
| 9 | **GND** des Sensors abgezogen |
| 10 | Wackler: Messschleife laufen lassen und eine Datenleitung ein paar Mal kurz lösen und wieder einstecken |
