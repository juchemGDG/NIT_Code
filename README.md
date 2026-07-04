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
| **Bibliotheks-Manager** | Bibliotheken aus [NIT_Bibliotheken](https://github.com/juchemGDG/NIT_Bibliotheken) direkt auf den Controller laden – online oder (in Schulnetzen ohne Internet) offline aus einem entpackten ZIP-Ordner |
| **Block-Editor** | Blockbasiert programmieren (wie Snap!/Scratch) und automatisch in lesbaren Python-/MicroPython-Code umwandeln – inkl. GPIO-, ADC-, DAC-, NeoPixel- und nitbw-Bibliotheks-Blöcken |
| **Serial Plotter** | Zahlenausgabe eines laufenden Programms live als Graph – ideal für Sensorwerte (Temperatur, Abstand, Helligkeit). Bei Bedarf über „Ausführen → 📈 Serial Plotter" einblendbar |
| **KI-Codegenerator** | Schülerinnen und Schüler spezifizieren Eingabe/Ablauf/Ausgabe/Variablen, die KI setzt es in Code um (lokal via Ollama) |
| **Git-Integration** | Repository klonen, Status, Commit, Push, Pull, Branch wechseln und Merge-Konflikte lösen – direkt aus dem Menü „Git" |
| **Syntax-Highlighting** | Farbige Python-Syntax, Zeilennummern, Klammernabgleich, Auto-Vervollständigung (Jedi) |
| **Fehler-Links** | Fehler in rot, klickbar → Sprung zur Fehlerstelle im Editor |
| **Fehler-Erklärung** | Verständliche deutsche Klartext-Hinweise zu Programmfehlern; auf Wunsch erklärt der KI-Tutor „Infi" den Fehler mit Bezug auf den eigenen Code |
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

### Linux: Zugriff auf den seriellen Port (MicroPython)

Unter Linux gehören serielle Ports (z. B. `/dev/ttyUSB0`, `/dev/ttyACM0`) der
Gruppe `dialout`. Ist der eigene Benutzer nicht in dieser Gruppe, scheitert die
Verbindung zum Controller mit:

```
Verbindungsfehler: [Errno 13] could not open port /dev/ttyUSB0:
[Errno 13] Permission denied: '/dev/ttyUSB0'
```

Den eigenen Benutzer **einmalig** zur Gruppe `dialout` hinzufügen:

```bash
sudo usermod -a -G dialout $USER
```

Anschließend **ab- und wieder anmelden** (oder neu starten), damit die
Gruppenzugehörigkeit wirksam wird. Prüfen lässt sie sich mit dem Befehl `groups`
(die Ausgabe muss `dialout` enthalten).

> Wird der USB-Seriell-Adapter (CH340 o. ä.) gar nicht erkannt, kann unter Ubuntu
> der Dienst `brltty` den Port belegen. Abhilfe: `sudo apt remove brltty`.

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

## Fehler verstehen

Stürzt ein Programm ab, zeigt NIT_Code unter der Fehlermeldung einen **verständlichen,
deutschen Hinweis** an: was der Fehler bedeutet und worauf zu achten ist (z. B. bei
`NameError`, `IndentationError`, `IndexError`, `TypeError` …). Das funktioniert
vollständig lokal, ganz ohne KI.

Ist zusätzlich der KI-Tutor **„Infi" aktiv**, erscheint der Knopf
**🤖 Infi erklärt diesen Fehler**. Ein Klick schickt die Fehlermeldung zusammen mit
dem eigenen Code an Infi, der den Fehler kindgerecht erklärt – mit Hinweisen statt
fertiger Lösung, damit das eigene Nachdenken im Vordergrund bleibt.

---

## Block-Editor (blockbasiert programmieren)

Über das Menü **Blöcke → Block-Editor öffnen** startet ein eigenes Fenster, in dem
Programme – ähnlich wie in **Snap!** oder **Scratch** – aus Blöcken zusammengesteckt
werden. Das ist besonders für Einsteigerinnen und Einsteiger (z. B. Klasse 7) geeignet,
weil der Algorithmus im Vordergrund steht und keine Syntaxfehler entstehen.

- Kategorien: Logik, Schleifen, Mathematik, Text, Listen, Tupel, Dictionary,
  Variablen, Funktionen, Zeit
- Mathematik enthält die **Typumwandlung** `int()`/`float()`/`str()` (z. B. für
  `int(input(...))`); Text bietet String-Methoden (Großschreibung, Teilstring,
  ersetzen, suchen …) und einen **Kommentar**-Block, Listen zusätzlich sortieren,
  umdrehen, Teilliste u. a.
- MicroPython-Blöcke: digitale Ein-/Ausgänge, ADC, DAC, PWM, NeoPixel
- **nitbw-Bibliotheken** als Blöcke (OLED, LCD, Töne, Servo, Ultraschall u. v. m.)
- Knopf **„In Python umwandeln"** erzeugt sauberen, lesbaren Code in einem Editor-Tab
  (Aufbau: Bibliotheken → Instanzen → Variablen → Funktionen → Hauptprogramm)
- Block-Programme lassen sich als `.nitblocks`-Datei speichern und laden

> Wird ein bereits umgewandeltes Block-Programm erneut umgewandelt, aktualisiert
> NIT_Code den bestehenden Tab, statt einen neuen zu öffnen.

---

## Serial Plotter (Werte live als Graph)

Über **Ausführen → 📈 Serial Plotter** (oder den gleichnamigen Knopf in der
Werkzeugleiste) lässt sich bei Bedarf ein Live-Graph einblenden. Er zeichnet die
Zahlen, die ein laufendes Programm zeilenweise ausgibt – besonders praktisch für
Sensorexperimente (Temperatur, Abstand, Helligkeit) am Controller.

- **Eine Zahl pro Zeile** → eine Kurve: `print(temp)`
- **Mehrere Zahlen pro Zeile** (Leerzeichen/Komma getrennt) → mehrere Kurven: `print(temp, feuchte)`
- **Benannte Kurven** mit `name:wert` oder `name=wert`: `print(f"temp:{t}")`
- Zeilen mit gemischtem Text werden ignoriert und erscheinen weiter im Ausgabe-Tab.

Der Plotter ist standardmäßig **ausgeblendet** und erzeugt erst dann Aufwand, wenn er
aktiviert wird. Bei jedem Programmstart beginnt er mit einem frischen Graph; mit
**Pause** lässt sich der aktuelle Verlauf einfrieren und in Ruhe betrachten.

**Achsen einstellen:** Die automatische Skalierung ist nicht immer erwünscht. Beide
Achsen lassen sich daher umstellen – direkt in der Plotter-Leiste (sofort wirksam) und
als gespeicherter Standard unter **Datei → Einstellungen → Serial Plotter**:

- **Hochachse (Y):** *Automatisch* (gleitend) oder *Feste Grenzen* mit Min/Max.
- **Rechtsachse (X):** *Gleitend* (zeigt die letzten Werte) oder *Sweep* – ein fester
  Indexbereich von Min bis Max, der sich einmal füllt und dann stehen bleibt (wie eine
  Einzelaufnahme).

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

NIT_Code nutzt dabei einen **Hybrid-Startmodus**:

- Wenn im Projektordner eine Runtime unter `python_runtime/` liegt, wird diese bevorzugt.
- Andernfalls wird der vorhandene System-Interpreter verwendet.
- Die eigentliche Laufumgebung wird als `.venv` angelegt (bei schreibgeschütztem Projektordner automatisch im Benutzerprofil unter `NIT_Code/.venv`).

Optional kann das Verhalten per Umgebungsvariable gesteuert werden:

- `NIT_PYTHON_MODE=auto` (Standard): bevorzugt `python_runtime/`, sonst System-Python
- `NIT_PYTHON_MODE=bundled`: erzwingt `python_runtime/` (Fehler, wenn nicht vorhanden)
- `NIT_PYTHON_MODE=system`: ignoriert `python_runtime/` und nutzt immer System-Python

Eine mitlieferbare Runtime kann ueber die Release-Skripte erzeugt werden:

- Linux/macOS: `bash release/scripts/create_embedded_runtime.sh --force`
- Windows: `pwsh -File release/scripts/create_embedded_runtime.ps1 -Force`

Fuer Release-Builds kann die Runtime direkt in die Pakete aufgenommen werden:

- Linux: `INCLUDE_RUNTIME=1 bash release/scripts/build_linux.sh`
- macOS: `INCLUDE_RUNTIME=1 bash release/scripts/build_macos.sh`
- Windows: `pwsh -File release/scripts/build_windows.ps1 -IncludeRuntime`

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

## Schulnetze mit Proxy

Viele Schulnetze leiten den Internetverkehr über einen Proxy, der eine
Anmeldung verlangt. Downloads (Bibliotheken, Firmware, pip) schlagen dann mit
`407 Proxy Authentication Required` fehl – der Browser meldet sich automatisch
mit der Windows-Anmeldung an, Programme können das nicht. NIT_Code zeigt in dem
Fall einen erklärenden Hinweis statt eines kryptischen Fehlers.

Zwei Lösungswege:

1. **Administrator gibt die benötigten Adressen am Proxy frei** (empfohlen):
   `raw.githubusercontent.com`, `api.github.com`, `micropython.org`,
   `pypi.org`, `files.pythonhosted.org`.
2. **Offline-Installation der Bibliotheken:** Das Repository
   [NIT_Bibliotheken](https://github.com/juchemGDG/NIT_Bibliotheken) einmal (z. B.
   zu Hause) über „Code → Download ZIP“ herunterladen und entpacken. Im
   Bibliotheks-Manager dann **„📁 Aus Ordner installieren …“** wählen und den
   entpackten Ordner angeben – das läuft komplett ohne Internet.

> Software-Rendering für den Block-Editor auf Terminal-/RDP-Servern lässt sich
> bei Grafikproblemen mit der Umgebungsvariable `NIT_SOFTWARE_RENDER=1`
> erzwingen (in RDP-Sitzungen erkennt NIT_Code das automatisch).

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
