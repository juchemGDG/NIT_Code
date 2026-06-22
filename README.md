# NIT_Code

**NIT_Code** ist ein moderner, plattformunabhängiger Code-Editor für Python und MicroPython – entwickelt für den Einsatz im Schulunterricht (Sekundarstufe I & II).

GitHub-Repository: https://github.com/juchemGDG/NIT_Code

---

## Features

| Funktion | Beschreibung |
|---|---|
| **Python (lokal)** | Code schreiben und mit lokaler Python-Installation (`.venv`) ausführen |
| **MicroPython** | Direktes Programmieren für ESP32, micro:bit v2, Raspberry Pi Pico 2 / Pico 2W |
| **Firmware flashen** | MicroPython-Firmware von lokaler Datei oder micropython.org flashen |
| **Bibliotheks-Manager** | Bibliotheken aus [NIT_Bibliotheken](https://github.com/juchemGDG/NIT_Bibliotheken) direkt auf den Controller laden |
| **Block-Editor** | Blockbasiert programmieren (wie Snap!/Scratch) und automatisch in lesbaren Python-/MicroPython-Code umwandeln – inkl. GPIO-, ADC-, DAC-, NeoPixel- und nitbw-Bibliotheks-Blöcken |
| **KI-Codegenerator** | Schülerinnen und Schüler spezifizieren Eingabe/Ablauf/Ausgabe/Variablen, die KI setzt es in Code um (lokal via Ollama) |
| **Git-Integration** | Repository klonen, Status, Commit, Push, Pull, Branch wechseln und Merge-Konflikte lösen – direkt aus dem Menü „Git" |
| **Syntax-Highlighting** | Farbige Python-Syntax, Zeilennummern, Klammernabgleich, Auto-Vervollständigung (Jedi) |
| **Fehler-Links** | Fehler in rot, klickbar → Sprung zur Fehlerstelle im Editor |
| **Shell** | Integriertes Terminal für Einzelbefehle |
| **Dateibaum** | Ordner/Dateien verwalten, neue Dateien erstellen |
| **Helles & dunkles Design** | Zwei Themes – klassisch-hell (Standard) und modern-dunkel, umschaltbar in den Einstellungen |
| **KI-Tutor „Infi"** | Lokaler, kostenloser KI-Tutor für Python-Anfängerinnen und -Anfänger (optional, via Ollama) |

---

## Voraussetzungen

- Für die **Download-Versionen**: keine Python-Installation erforderlich
- Für MicroPython-Funktionen: Controller per USB anschließen

---

## Download & Installation (empfohlen)

Aktuelle Versionen stehen auf der GitHub-Release-Seite bereit:

- Release-Übersicht: https://github.com/juchemGDG/NIT_Code/releases/latest
- **Windows (.exe):** https://github.com/juchemGDG/NIT_Code/releases/latest/download/NIT_Code.exe
- **macOS (.dmg):** https://github.com/juchemGDG/NIT_Code/releases/latest/download/NIT_Code-macos.dmg
- **Linux (.tar.gz):** https://github.com/juchemGDG/NIT_Code/releases/latest/download/NIT_Code-linux-x86_64.tar.gz

### Schnellstart

- **Windows:** `NIT_Code.exe` herunterladen und starten
- **macOS:** `NIT_Code-macos.dmg` öffnen, App in Programme ziehen, dann starten
- **Linux:** Archiv entpacken und die enthaltene Startdatei im Ordner `NIT_Code` ausführen

---

## KI-Tutor „Infi" (optional)

Infi ist ein eingebauter, ermutigender Lern-Assistent für Python- und Arduino-Anfängerinnen und -Anfänger. Er läuft **vollständig lokal und kostenlos** über [Ollama](https://ollama.com) – es wird keine Internetverbindung und kein API-Schlüssel benötigt.

Die Option erscheint in den Einstellungen nur, wenn Ollama auf dem Rechner installiert ist.

### Installation (einmalig pro Rechner)

#### Windows

1. Installer herunterladen: [ollama.com/download](https://ollama.com/download/windows)
2. Setup ausführen – Ollama startet danach automatisch im Hintergrund
3. Eingabeaufforderung öffnen (`Win + R` → `cmd`) und Modell herunterladen:
   ```cmd
   ollama pull llama3.2
   ```

#### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
```

#### macOS

```bash
brew install ollama
ollama pull llama3.2
```

> Alternativ: Installer unter [ollama.com/download](https://ollama.com/download/mac) herunterladen.

### Empfohlene Modelle

| Modell | Größe | Empfehlung |
|---|---|---|
| `llama3.2` | ~2 GB | Standard – gut und schnell |
| `llama3.1:8b` | ~4,7 GB | Bessere Qualität, mehr RAM nötig |
| `gemma2:2b` | ~1,6 GB | Für schwächere Schulrechner |

### Infi aktivieren

1. NIT_Code starten
2. **Datei → Einstellungen** öffnen (oder `Strg+,`)
3. Im Abschnitt **KI-TUTOR (INFI)** den Haken bei „Infi-Tutor aktivieren" setzen
4. **Übernehmen** klicken – das Chat-Panel öffnet sich rechts

> Das Modell kann im Einstellungs-Dialog jederzeit geändert werden (Feld „Modell").  
> Ollama muss laufen, bevor Infi gestartet wird. Beim Fehler „Keine Verbindung" bitte in einer Eingabeaufforderung `ollama serve` ausführen.

---

## Block-Editor (blockbasiert programmieren)

Über das Menü **Blöcke → Block-Editor öffnen** startet ein eigenes Fenster, in dem
Programme – ähnlich wie in **Snap!** oder **Scratch** – aus Blöcken zusammengesteckt
werden. Das ist besonders für Einsteigerinnen und Einsteiger (z. B. Klasse 7) geeignet,
weil der Algorithmus im Vordergrund steht und keine Syntaxfehler entstehen.

- Kategorien: Logik, Schleifen, Mathematik, Text, Listen, Variablen, Funktionen, Zeit
- MicroPython-Blöcke: digitale Ein-/Ausgänge, ADC, DAC, PWM, NeoPixel
- **nitbw-Bibliotheken** als Blöcke (OLED, LCD, Töne, Servo, Ultraschall u. v. m.)
- Knopf **„In Python umwandeln"** erzeugt sauberen, lesbaren Code in einem Editor-Tab
  (Aufbau: Bibliotheken → Instanzen → Variablen → Funktionen → Hauptprogramm)
- Block-Programme lassen sich als `.nitblocks`-Datei speichern und laden

> Wird ein bereits umgewandeltes Block-Programm erneut umgewandelt, aktualisiert
> NIT_Code den bestehenden Tab, statt einen neuen zu öffnen.

---

## KI-Codegenerator (optional)

Der Code-Generator arbeitet im **Auftragnehmer-Modus**: Die Schülerinnen und Schüler
geben eine vollständige Spezifikation an (EINGABE, ABLAUF, AUSGABE, VARIABLEN), und die
KI setzt **genau diesen** Algorithmus in Code um – ohne den Lösungsweg vorzugeben. Läuft
lokal über [Ollama](https://ollama.com). So bleibt das Algorithmen-Entwerfen Aufgabe der
Lernenden, während die reine Umsetzung in Syntax unterstützt wird.

> Mit **„🧩 Als Blöcke öffnen"** lässt sich der erzeugte Code zusätzlich im Block-Editor
> als Blöcke anzeigen – ideal für den Übergang vom Block- zum Textprogrammieren. Die
> Umwandlung ist deterministisch; nicht erkannte Zeilen bleiben als Roh-Python-Block erhalten.

---

## Git-Integration

Versionsverwaltung direkt aus dem Menü **„Git"** – ideal für Projektarbeit und das
Verteilen/Einsammeln von Aufgaben:

- Repository **klonen** und auswählen (HTTPS mit Zugangsdaten)
- **Status**, **Commit**, **Push**, **Pull**, **Fetch**
- **Branch** wechseln und **mergen**, inkl. geführter **Konfliktlösung**

> Zugangsdaten werden sicher im Schlüsselspeicher des Betriebssystems abgelegt
> (Windows Credential Manager / macOS Keychain / libsecret) – nicht im Klartext.

---

## Starten aus Quellcode (für Entwicklung)

Für diese Variante ist **Python 3.10+** erforderlich.

### Linux / macOS
```bash
chmod +x run.sh
./run.sh
```

### Windows
```
run.bat
```

Beim ersten Start wird automatisch eine virtuelle Umgebung (`.venv`) erstellt und alle Abhängigkeiten installiert.

---

## Manuell starten (nach erster Installation)

```bash
python start.py
```

oder direkt:

```bash
.venv/bin/python -m nit_code.main
```

---

## Abhängigkeiten

| Paket | Zweck |
|---|---|
| `PyQt6` | GUI-Framework |
| `PyQt6-QScintilla` | Code-Editor mit Syntax-Highlighting |
| `esptool` | ESP32 flashen |
| `mpremote` | MicroPython-Controller-Kommunikation |
| `pyserial` | Serielle Ports erkennen |
| `requests` | GitHub API / Firmware-Downloads |

---

## Unterstützte Controller

- **ESP32** (alle Varianten)
- **micro:bit v2**
- **Raspberry Pi Pico 2**
- **Raspberry Pi Pico 2W**

---

## Projektstruktur

```
NIT_Code/
├── nit_code/
│   ├── main.py                 # Einstiegspunkt
│   ├── main_window.py          # Hauptfenster (inkl. Git-Integration)
│   ├── editor_widget.py        # Code-Editor (QScintilla)
│   ├── completion.py           # Auto-Vervollständigung (Jedi)
│   ├── file_panel.py           # Dateibaum
│   ├── console_panel.py        # Konsole + Shell
│   ├── block_panel.py          # Block-Editor-Fenster (Blockly)
│   ├── coder_panel.py          # KI-Codegenerator
│   ├── ais_chat_panel.py       # AIS-Schulchat
│   ├── micropython_dialogs.py  # Flash- & Bibliotheks-Dialog
│   ├── tutor_panel.py          # KI-Tutor „Infi" (Ollama-Chat)
│   ├── settings_dialog.py      # Einstellungen
│   ├── config.py               # Konstanten & Themes (hell/dunkel)
│   └── assets/
│       └── blockly/            # Blockly offline + NIT-/nitbw-Blöcke
├── start.py                    # Bootstrap-Skript
├── run.sh                      # Linux/macOS Starter
├── run.bat                     # Windows Starter
└── requirements.txt
```
