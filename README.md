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
| **Syntax-Highlighting** | Farbige Python-Syntax, Zeilennummern, Klammernagleich |
| **Fehler-Links** | Fehler in rot, klickbar → Sprung zur Fehlerstelle im Editor |
| **Shell** | Integriertes Terminal für Einzelbefehle |
| **Dateibaum** | Ordner/Dateien verwalten, neue Dateien erstellen |
| **Modernes Design** | Dunkles Theme, optimal für den Unterricht |
| **KI-Tutor „Infi"** | Lokaler, kostenloser KI-Tutor für Python-Anfängerinnen und -Anfänger (optional, via Ollama) |

---

## Voraussetzungen

- **Python 3.10+** muss installiert sein
- Für MicroPython-Funktionen: Controller per USB anschließen

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

## Starten

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
│   ├── main_window.py          # Hauptfenster
│   ├── editor_widget.py        # Code-Editor (QScintilla)
│   ├── file_panel.py           # Dateibaum
│   ├── console_panel.py        # Konsole + Shell
│   ├── micropython_dialogs.py  # Flash- & Bibliotheks-Dialog
│   ├── tutor_panel.py          # KI-Tutor „Infi" (Ollama-Chat)
│   └── config.py               # Konstanten & Theme
├── start.py                    # Bootstrap-Skript
├── run.sh                      # Linux/macOS Starter
├── run.bat                     # Windows Starter
└── requirements.txt
```
