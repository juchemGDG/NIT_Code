# NIT ESP32 Blockly – Prototyp

Standalone-IDE auf dem ESP32: Board als eigener Accesspoint, Oberfläche wird
direkt vom Board ausgeliefert, kein Schulnetz/Internet nötig.

Die Web-Oberfläche zeigt drei Bereiche nebeneinander (auf dem iPad hochkant
untereinander): links die **Blöcke**, rechts oben den **Python-Code** (live aus
den Blöcken erzeugt, per „✏️ bearbeiten“ auch manuell editierbar) und rechts
unten eine **Konsole** mit den Ausgaben und Fehlermeldungen des Programms.

## Dateistruktur

```
boot.py                          Richtet WLAN-Accesspoint ein
main.py                          Webserver (uasyncio): liefert /www aus, führt Code im Thread aus, sammelt Ausgaben
www/index.html                   Oberfläche: Blöcke + Python-Editor + Konsole (Toolbox aus NIT_Code)
www/app.js                       Live-Codegen, Ausführen -> /api/run, Konsole pollt /api/output, Stopp -> /api/stop
www/blockly/*.js                 Blockly-Core + geteilte Blockdefinitionen (nit_blocks.js, nitbw_blocks.js)
www/blockly/msg/de.js            Deutsche Übersetzung
www/blockly/media/               Sprites/Sounds (offline)
sync_from_nit_code.py            Hält www/ mit nit_code/assets/blockly/ synchron
```

## Blöcke: eine gemeinsame Quelle

Der iPad-Modus nutzt **dieselben Blöcke wie der NIT_Code-Block-Editor** – exakt
die Dateien aus `nit_code/assets/blockly/` (`nit_blocks.js`, `nitbw_blocks.js`)
und dieselbe Toolbox aus `editor.html`. `www/blockly/` ist eine gespiegelte
Kopie davon; die Oberfläche ist damit komplett offline lauffähig.

Wenn du in NIT_Code Blöcke oder die Toolbox änderst, danach einmal ausführen:

```bash
python firmware/sync_from_nit_code.py
```

Das kopiert Binaries + Blockdefinitionen und übernimmt die Toolbox in
`index.html`. So ist jeder neue Block **automatisch auch im iPad-Modus** da –
keine Doppelpflege.

Das Sync-Skript **entfernt für den iPad-Modus die Kategorie „Funk (ESP-NOW /
MQTT)"** (Liste `EXCLUDE_CATEGORIES`): Das WLAN dient hier als Accesspoint fürs
iPad, deshalb funktionieren MQTT und ESP-NOW nicht. Der Desktop-Editor behält
diese Blöcke.

> **Sensor-Blöcke** (BME280, OLED, Servo, …) erzeugen `from nitbw_xxx import …`
> und laufen nur, wenn die passenden `nitbw_`-Bibliotheken in `/lib` auf dem
> Board liegen. Der Deploy (Weg A) kann sie auf Wunsch mitinstallieren.

## Speichern & Laden (im Browser)

Die Arbeit wird **automatisch im Browser gesichert** (localStorage) und beim
erneuten Öffnen wiederhergestellt – ein Reload verliert also nichts. Zusätzlich:

- **💾 Speichern** – legt das aktuelle Programm unter einem Namen ab.
- **📂 Projekte** – Liste der gespeicherten Programme zum Laden/Löschen; darin
  auch **„Als Datei sichern"** (lädt eine `.blocks`-Datei zum Mitnehmen herunter)
  und **„Datei laden"** (importiert eine solche Datei).

> Hinweis: localStorage hängt am jeweiligen Gerät/Browser. Für ein echtes,
> geräteübergreifendes Backup die `.blocks`-Datei exportieren.

## Deployment auf den ESP32

> **Wichtig:** Das braucht USB-Zugriff auf das Board und läuft deshalb **nur
> lokal** – nicht im Cloud-Codespace. Port-Namen: ESP32-C3 mit nativem USB
> meist `/dev/ttyACM0` (Linux) bzw. `/dev/cu.usbmodemXXXX` (macOS), mit
> USB-Serial-Chip `/dev/ttyUSB0`.

Zuerst muss **MicroPython** auf dem Board sein – am einfachsten über den
NIT_Code-Flash-Dialog (Board „ESP32-C3" wählen, neueste Firmware automatisch).
Manuell:

```bash
esptool --chip esp32c3 --port /dev/ttyACM0 --baud 460800 \
    write_flash -e -z 0x0 ESP32_GENERIC_C3-*.bin
```

### Weg A – direkt in NIT_Code (empfohlen)

Menü **MicroPython → 📲 iPad-Blockly aufs Board spielen**. Kopiert `boot.py`,
`main.py` und `www/` automatisch auf den angeschlossenen Controller und startet
ihn neu – kein Terminal nötig. Der Dialog fragt nach einer **Nummer/Name für das
Board** (→ WLAN-SSID, siehe unten) und kann per Häkchen zusätzlich die
**Sensor-Bibliotheken (`nitbw_`)** nach `/lib` installieren (nötig, damit die
Sensor-Blöcke laufen; dauert einige Minuten, braucht Internet).

### Weg B – manuell per mpremote

```bash
pip install mpremote
cd firmware
mpremote connect /dev/ttyACM0 cp boot.py main.py :
mpremote connect /dev/ttyACM0 cp -r www :
mpremote connect /dev/ttyACM0 reset
```

Danach mit Laptop/iPad ins jeweilige Board-WLAN (Passwort: `mint2026`) und
`http://192.168.4.1/` öffnen. Die SSID steht oben in der Oberfläche.

## Eindeutige SSIDs im Klassensatz

Damit sich bei 10+ Boards niemand ins falsche WLAN verbindet, hat jedes Board
eine eindeutige SSID:

- **Name gesetzt** (Deploy-Dialog, Weg A): SSID = `NIT-ESP32-<Name>`, z. B.
  `NIT-ESP32-01`. Board am besten gleich mit derselben Nummer bekleben.
- **Kein Name**: `boot.py` bildet automatisch `NIT-ESP32-<Chip-ID>` aus den
  letzten 4 Stellen der eindeutigen Chip-Kennung (z. B. `NIT-ESP32-A1B2`). So
  gibt es **nie zwei gleiche SSIDs**, auch ohne Konfiguration.

Der Deploy-Dialog zeigt die resultierende SSID an; zusätzlich steht sie in der
Web-Oberfläche und wird beim Boot seriell ausgegeben. Der Name liegt auf dem
Board in `ap_name.txt` – bei Weg B (manuell) kann man ihn selbst setzen:

```bash
echo -n "01" | mpremote connect /dev/ttyACM0 fs cp - :ap_name.txt   # oder Datei anlegen
```

## Bekannte Einschränkungen von V1

1. **Ausführung im Hintergrund-Thread**: `main.py` startet den Nutzercode per
   `_thread`, fängt `print`-Ausgaben und Fehler ab (Ringpuffer) und liefert sie
   über `/api/output`; der Webserver bleibt erreichbar. „Stopp" beendet das
   Programm per Board-Reset. Einschränkung des einzelnen C3-Kerns: Eine reine
   Endlosschleife **ohne** `time.sleep(_ms)` kann den Webserver ausbremsen –
   in Schülerprogrammen ist praktisch immer ein `sleep` enthalten.
2. **Ein Client pro Board**: AP-Client-Limit ist bei 1:1-Zuordnung
   (ein ESP32 pro Schüler:in) unkritisch.
3. **Kein Captive Portal** in V1 – man muss die IP manuell aufrufen.
   Lässt sich später per simplem DNS-Spoofing nachrüsten.
4. **Sensor-Blöcke brauchen Bibliotheken auf dem Board**: Die `nitbw_`-Blöcke
   (BME280, OLED, Servo, …) erzeugen `import nitbw_...`; die zugehörigen Module
   müssen in `/lib` liegen (Deploy-Häkchen oder „Bibliotheken installieren …“).
   Reine MicroPython-Blöcke (GPIO, PWM, ADC, NeoPixel) laufen ohne Zusatz.

## Troubleshooting: „Verbindung fehlgeschlagen" auf dem iPad

`boot.py` enthält seit Juli 2026 drei Stabilitäts-Fixes (dazu die Boards einmal
**neu bespielen**, Weg A oder B):

- **Kanalverteilung**: Jedes Board wählt anhand seiner Chip-ID fest Kanal 1, 6
  oder 11 (vorher: alle auf Kanal 6). Im Klassensatz stören sich die APs so
  deutlich weniger gegenseitig. Der Kanal wird beim Boot seriell ausgegeben.
- **Modem-Sleep aus** (`pm=PM_NONE`): Der Stromsparmodus ließ den AP
  Anmelde-Frames verpassen – häufigste Einzelursache für Verbindungsabbrüche.
- **`ap.config()`-Retry**: Direkt nach dem Aktivieren schlägt die
  AP-Konfiguration auf dem C3 gelegentlich intern fehl; ohne Retry lief der AP
  dann mit Default-SSID weiter.

Bleibt es instabil:

- **Nach „Stopp" 3–5 s warten**: Stopp = Board-Reset, das WLAN verschwindet
  kurz und das iPad muss sich neu verbinden.
- **Abstand zum Schul-WLAN-Accesspoint**: Ein starker AP direkt im Raum
  überdeckt die schwachen ESP32-Signale; notfalls Boards näher ans iPad.
- **iPad-Seite**: Netzwerk einmal „ignorieren" und neu verbinden, falls iOS
  einen alten Zustand gespeichert hat.

## Integration in NIT_Code (später)

Denkbarer Weg: NIT_Code bekommt einen "Firmware"-Modus, in dem die hier
gebaute www/-Struktur + main.py/boot.py als flashbares Firmware-Image
bereitgestellt wird (z. B. per esptool + vorgefertigtem Filesystem-Image).
Nutzer:in flasht einmalig, verbindet sich danach direkt mit dem ESP32-WLAN
und programmiert über dieselbe Blockly-Oberfläche wie in NIT_Code –
ohne Server, ohne Internet, auch vom iPad aus nutzbar.
