# NIT PyEd

**NIT PyEd** ist ein moderner, plattformunabhängiger Code-Editor für Python und MicroPython – entwickelt für den Einsatz im Schulunterricht (Sekundarstufe I & II).

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

---

## Voraussetzungen

- **Python 3.10+** muss installiert sein
- Für MicroPython-Funktionen: Controller per USB anschließen

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
.venv/bin/python -m nit_pyed.main
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
NIT_PyEd/
├── nit_pyed/
│   ├── main.py                 # Einstiegspunkt
│   ├── main_window.py          # Hauptfenster
│   ├── editor_widget.py        # Code-Editor (QScintilla)
│   ├── file_panel.py           # Dateibaum
│   ├── console_panel.py        # Konsole + Shell
│   ├── micropython_dialogs.py  # Flash- & Bibliotheks-Dialog
│   └── config.py               # Konstanten & Theme
├── start.py                    # Bootstrap-Skript
├── run.sh                      # Linux/macOS Starter
├── run.bat                     # Windows Starter
└── requirements.txt
```
