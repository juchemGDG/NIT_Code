# NIT ESP32 Blockly – Prototyp

Standalone-IDE auf dem ESP32: Board als eigener Accesspoint, Blockly-Oberfläche
wird direkt vom Board ausgeliefert, kein Schulnetz/Internet nötig.

## Dateistruktur

```
boot.py                          Richtet WLAN-Accesspoint ein
main.py                          Webserver (uasyncio), liefert /www aus, nimmt Code entgegen
www/index.html                   Blockly-Oberfläche (Toolbox: Steuerung, GPIO, Logik, Mathe, Variablen)
www/blocks.js                    Eigene GPIO-Blöcke + Python-Codegenerator
www/app.js                       Verdrahtung: "Ausführen" -> POST /api/upload, "Stopp" -> POST /api/stop
www/blockly/*.js                 Blockly-Binaries (Core, Blocks, Python-Generator)
www/blockly/msg/de.js            Deutsche Übersetzung
www/blockly/media/               Sprites/Sounds (offline)
```

## Blockly-Binaries sind enthalten

Die Blockly-Dateien in `www/blockly/` wurden aus `nit_code/assets/blockly/`
übernommen (identische Version wie im NIT_Code-Block-Editor). Damit ist der
Ordner **komplett offline lauffähig** – nichts muss mehr nachgeladen werden.

> Hinweis: Aktuell liegen diese ~700 KB doppelt im Repo (einmal für NIT_Code,
> einmal hier). Eine gemeinsame `shared-blocks/`-Quelle ist als späterer
> Aufräumschritt vorgesehen, sobald der Prototyp auf Hardware bestätigt ist.

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
ihn neu – kein Terminal nötig.

### Weg B – manuell per mpremote

```bash
pip install mpremote
cd firmware
mpremote connect /dev/ttyACM0 cp boot.py main.py :
mpremote connect /dev/ttyACM0 cp -r www :
mpremote connect /dev/ttyACM0 reset
```

Danach mit Laptop/iPad ins WLAN "NIT-ESP32-Blockly" (Passwort: `mint2026`)
und `http://192.168.4.1/` öffnen.

## Bekannte Einschränkungen von V1

1. **Kein echtes Multitasking**: Nutzercode (z. B. Blink-Endlosschleife)
   blockiert den Webserver. Workflow ist "Hochladen → Reset → Läuft".
   Über den Stopp-Button bzw. die physische Reset-Taste kommt man zurück
   in den Programmiermodus. Ausbaustufe 2: `_thread` (zweiter Kern) für
   echtes Nebeneinander von Webserver und Nutzerprogramm.
2. **Ein Client pro Board**: AP-Client-Limit ist bei 1:1-Zuordnung
   (ein ESP32 pro Schüler:in) unkritisch.
3. **Kein Captive Portal** in V1 – man muss die IP manuell aufrufen.
   Lässt sich später per simplem DNS-Spoofing nachrüsten.
4. **Codegenerator ist bewusst minimal** (nur GPIO read/write, wait) –
   als Fundament für spätere `nitbw_`-Bausteine (Sensoren, MQTT, etc.).

## Integration in NIT_Code (später)

Denkbarer Weg: NIT_Code bekommt einen "Firmware"-Modus, in dem die hier
gebaute www/-Struktur + main.py/boot.py als flashbares Firmware-Image
bereitgestellt wird (z. B. per esptool + vorgefertigtem Filesystem-Image).
Nutzer:in flasht einmalig, verbindet sich danach direkt mit dem ESP32-WLAN
und programmiert über dieselbe Blockly-Oberfläche wie in NIT_Code –
ohne Server, ohne Internet, auch vom iPad aus nutzbar.
