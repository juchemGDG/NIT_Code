"""KI-Tutor-Panel – Infi, lokaler Lernassistent via Ollama."""
import json
import time

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QSizePolicy, QFrame,
)

from .config import THEME, TUTOR_DEFAULT_URL, TUTOR_DEFAULT_MODEL

# ── System-Prompt für Infi ────────────────────────────────────────────────────
INFI_SYSTEM_PROMPT = """\
Du bist Infi, ein optimistischer, ermutigender Tutor für den Schulunterricht. \
Dein Schwerpunkt liegt auf Programmieren mit Python und MicroPython für ESP32, \
micro:bit und Raspberry Pi Pico nach dem Lehrgang py.nitbw.de.

PERSONA UND TON
- Du bist ein freundlicher, junger Programmierer namens Infi: warm, humorvoll, \
respektvoll, klar und kurz in den Absätzen.
- Du nutzt sparsam Emojis und lobst echte Fortschritte.
- Du klingst selbstbewusst und motivierend, ohne zu überrollen.
- Du erklärst in einfacher, zugänglicher Sprache (Mittelstufen-Niveau).
- Du sprichst immer die Sprache, in der du angesprochen wirst, duzt dein Gegenüber \
und nutzt gendersensible Paarformen (z. B. Schülerinnen und Schüler).

ZIEL
Lernende befähigen, kleine Aufgaben selbst zu lösen, ihr Denken zu erklären \
und schrittweise zu testen, ohne fertige Komplettlösungen zu erhalten.

LEHRMATERIAL – REFERENZ py.nitbw.de
Der Unterricht folgt dem Lehrgang auf py.nitbw.de (Kapitel 01–15 + Referenz). \
Orientiere dich immer an diesem Curriculum. Die Kapitelfolge ist:
01 Erste Schritte (print, Variablen, Datentypen)
02 Eingaben und Rechnen (input, int(), float(), Operatoren)
03 Entscheidungen (if / elif / else, Vergleiche, ==, !=, >, <, >=, <=)
04 Schleifen (while, while True, for, range(), break, continue)
05 Listen ([…], append(), pop(), insert(), len(), index, Iteration)
06 Funktionen (def, Parameter, return, Scope)
07 Zufall (import random, randint(), choice())
08 Strings und f-Strings (Konkatenation, f"…{var}…", Methoden)
09 Dictionaries ({key: value}, Zugriff, .keys(), .values(), .items(), .get(), .pop())
10 MicroPython Grundlagen (from machine import Pin, Pin.OUT/IN/PULL_UP/PULL_DOWN, \
pin.on(), pin.off(), pin.value(), from time import sleep)
11 PWM und analoge Ausgaben (from machine import PWM, PWM(Pin(n), freq=500), duty())
12 NeoPixel / Addressierbare LEDs (from neopixel import NeoPixel, neo[i]=(r,g,b), \
neo.write(), Farb-Tupel)
13 Töne / Musik (from nitbw_toene import TOENE, .ton(('C4', 1/4)), .stop(), \
Pausen mit ('P', …))
14 OLED-Display (from nitbw_oled import OLED, OLED(scl=22, sda=21, chip='ssd1306'), \
.print(text, x, y), .show(), .fill(0))
15 LCD-Display (from nitbw_lcd import LCD, LCD(scl=22, sda=21, addr=0x27), \
.print(text, x, y))
Referenz: Empfohlene ESP32-GPIO-Pins: Ausgabe/PWM: 18,19,21-23,25-27,32,33 | \
Eingabe: 18,19,21-23,25-27,32,33 | nur Eingabe (kein Pull): 34,35,36,39 | \
meiden: 0,2,5,6-11,12,15

ARBEITSWEISE MIT LERNENDEN
- Frage zu Beginn nach: Ziel in 1–2 Sätzen, Vorwissen (Kapitel aus py.nitbw.de, \
welche Konzepte schon bekannt), Kontext (Aufgabe, Controller, IDE).
- Lass Lernende zuerst Pseudocode schreiben, dann Schritt für Schritt implementieren; \
nach jedem Mini-Schritt testen und Ergebnis beschreiben.
- Fordere Denkprozesse ein: „Warum diese Anweisung?" „Was erwartest du als Ausgabe?"
- Stelle nur eine Frage auf einmal; halte Antworten dialogfreundlich kurz.
- Prüfe regelmäßig Tempo und Schwierigkeit: „Passt das Tempo für dich?"
- Verweise bei Bedarf explizit auf das zugehörige Kapitel auf py.nitbw.de, \
z. B. „Schau dir nochmal Kapitel 04 auf py.nitbw.de an."

GRENZEN UND SICHERHEIT
- Keine Komplettlösungen; maximal 2–3 Zeilen Code, wenn nötig.
- Kein Code außerhalb des py.nitbw.de-Curriculums (keine Klassen/OOP, \
keine komplexen Bibliotheken, keine fortgeschrittenen Konzepte).
- Bei MicroPython: keine const int, keine Klassen, keine Pointer-Arithmetik.
- Datenschutz beachten; neutrale Beispiele verwenden.
- Wenn Lernende Code aus dem Chat kopieren: weise darauf hin, Schritt für Schritt \
zu testen und nicht blind zu übernehmen.

STRUKTUR EINER TYPISCHEN ANTWORT
1. Kurze, freundliche Anerkennung und Zusammenfassung des Ziels/Status.
2. Ein Mini-Schritt oder fokussierte Erklärung, ggf. Pseudocode (max. 2–3 Zeilen).
3. Gezielter Hinweis auf einen einzelnen Befehl/Struktur aus py.nitbw.de.
4. Aufforderung zum Testen (z. B. mit print oder LED) und Ergebnis beschreiben.
5. Genau eine offene, handlungsleitende Frage am Ende.
6. Kurze Sprach-/Strukturkorrektur der letzten Nutzereingabe (2–4 Punkte).

DEBUGGING-HILFE
- Bitte Lernende, Problemstelle zu benennen, Fehlermeldung zu zitieren, Vermutung \
zu äußern.
- Nutze print() zur Zwischenkontrolle (Werte, Typen, Zwischenergebnisse).
- Bei MicroPython: pin.value() und sleep() zur Zustandskontrolle nutzen.
- Reduziere bei Feststecken: Teilziel definieren, Mini-Test isolieren.
- Hinweis auf i2c.scan() wenn I2C-Geräte (OLED, LCD) nicht reagieren.
"""


# ── Ollama-Worker (läuft in eigenem Thread, streamt Antwort) ─────────────────
class OllamaWorker(QThread):
    token_ready   = pyqtSignal(str)      # einzelner Token-Chunk
    response_done = pyqtSignal()         # Antwort vollständig
    error_occurred = pyqtSignal(str)     # Fehlermeldung

    def __init__(self, url: str, model: str, messages: list, parent=None):
        super().__init__(parent)
        self._url     = url.rstrip("/")
        self._model   = model
        self._messages = messages

    def run(self):
        endpoint = f"{self._url}/api/chat"
        payload = {
            "model":    self._model,
            "messages": self._messages,
            "stream":   True,
        }
        try:
            with requests.post(
                endpoint,
                json=payload,
                stream=True,
                timeout=120,
            ) as resp:
                if resp.status_code != 200:
                    self.error_occurred.emit(
                        f"Ollama antwortet mit Status {resp.status_code}.\n"
                        f'Ist das Modell "{self._model}" geladen?'
                    )
                    return
                for raw_line in resp.iter_lines():
                    if not raw_line:
                        continue
                    try:
                        data = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    content = data.get("message", {}).get("content", "")
                    if content:
                        self.token_ready.emit(content)
                    if data.get("done"):
                        break
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(
                "Keine Verbindung zu Ollama.\n"
                "Bitte Ollama starten: ollama serve"
            )
        except Exception as exc:
            self.error_occurred.emit(f"Fehler: {exc}")
        finally:
            self.response_done.emit()


# ── Chat-UI ───────────────────────────────────────────────────────────────────
class TutorPanel(QWidget):
    """Seitliches Chat-Panel für Infi, den KI-Tutor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ollama_url   = TUTOR_DEFAULT_URL
        self._model        = TUTOR_DEFAULT_MODEL
        self._history: list[dict] = [
            {"role": "system", "content": INFI_SYSTEM_PROMPT}
        ]
        self._worker: OllamaWorker | None = None
        self._retired_workers: list = []   # hält OllamaWorker bis finished
        self._pending_response = ""
        self._build_ui()

    # ── UI aufbauen ──────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setMinimumWidth(260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(
            f"background:{THEME['bg_panel']};"
            f"border-bottom:1px solid {THEME['border']};"
        )
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(10, 0, 10, 0)
        title_lbl = QLabel("🤖  Infi – KI-Tutor")
        title_lbl.setStyleSheet(
            f"color:{THEME['text']}; font-weight:bold; font-size:13px;"
        )
        hlay.addWidget(title_lbl)
        hlay.addStretch()
        self._status_lbl = QLabel("●")
        self._status_lbl.setStyleSheet(f"color:{THEME['text_dim']}; font-size:10px;")
        self._status_lbl.setToolTip("Ollama-Status")
        hlay.addWidget(self._status_lbl)
        layout.addWidget(header)

        # Chat-Verlauf
        self._chat_view = QTextEdit()
        self._chat_view.setReadOnly(True)
        self._chat_view.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f"border:none; padding:8px;"
            f"font-family: system-ui, -apple-system, 'Segoe UI', 'Ubuntu', sans-serif;"
            f"font-size: 12px;"
        )
        layout.addWidget(self._chat_view, stretch=1)

        # Trennlinie
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{THEME['border']}; margin:0;")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # Eingabebereich
        input_area = QWidget()
        input_area.setStyleSheet(f"background:{THEME['bg_panel']};")
        ilay = QVBoxLayout(input_area)
        ilay.setContentsMargins(8, 6, 8, 8)
        ilay.setSpacing(6)

        self._input = QTextEdit()
        self._input.setPlaceholderText("Frag Infi …  (Strg+Enter = Senden)")
        self._input.setFixedHeight(72)
        self._input.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f"border:1px solid {THEME['border']}; border-radius:4px; padding:4px;"
            f"font-family: system-ui, -apple-system, 'Segoe UI', 'Ubuntu', sans-serif;"
            f"font-size: 12px;"
        )
        self._input.installEventFilter(self)
        ilay.addWidget(self._input)

        btn_row = QHBoxLayout()
        self._clear_btn = QPushButton("Verlauf löschen")
        self._clear_btn.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text_dim']};"
            f"border:1px solid {THEME['border']}; border-radius:4px; padding:4px 10px;"
        )
        self._clear_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(self._clear_btn)
        btn_row.addStretch()

        self._send_btn = QPushButton("Senden")
        self._send_btn.setStyleSheet(
            f"background:{THEME['accent']}; color:#fff; font-weight:bold;"
            f"border:none; border-radius:4px; padding:5px 18px;"
        )
        self._send_btn.clicked.connect(self._send_message)
        btn_row.addWidget(self._send_btn)
        ilay.addLayout(btn_row)

        layout.addWidget(input_area)

        # Begrüßung
        self._append_infi(
            "Hallo! Ich bin Infi, dein Tutor für Python und Arduino. 👋\n\n"
            "Erzähl mir kurz: Was möchtest du heute programmieren und "
            "was hast du schon ausprobiert?"
        )

    # ── Strg+Enter senden ───────────────────────────────────────────────────
    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if mods & Qt.KeyboardModifier.ControlModifier:
                    self._send_message()
                    return True
        return super().eventFilter(obj, event)

    # ── Nachricht senden ────────────────────────────────────────────────────
    def _send_message(self):
        text = self._input.toPlainText().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()
        self._append_user(text)
        self._history.append({"role": "user", "content": text})

        self._send_btn.setEnabled(False)
        self._status_lbl.setStyleSheet(
            f"color:{THEME['warning']}; font-size:10px;"
        )
        self._status_lbl.setToolTip("Infi denkt …")
        self._pending_response = ""

        self._worker = OllamaWorker(
            self._ollama_url, self._model, self._history, self
        )
        self._worker.token_ready.connect(self._on_token)
        self._worker.response_done.connect(self._on_done)
        self._worker.error_occurred.connect(self._on_error)
        # finished feuert NACH run() – erst dann ist es sicher, die Referenz freizugeben
        w = self._worker
        self._worker.finished.connect(
            lambda t=w: self._retired_workers.remove(t)
            if t in self._retired_workers else None
        )
        self._worker.start()

        # Platzhalter für die laufende Antwort einfügen
        self._chat_view.append("")
        self._chat_view.append("<b style='color:#7c6af7'>Infi:</b> ")
        self._infi_cursor_at_end = True

    def _on_token(self, token: str):
        self._pending_response += token
        cursor = self._chat_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self._chat_view.setTextCursor(cursor)
        self._chat_view.ensureCursorVisible()

    def _on_done(self):
        # Wenn _on_error den Worker bereits zurückgesetzt hat, Status nicht überschreiben.
        if self._worker is None:
            self._pending_response = ""
            return
        if self._pending_response:
            self._history.append(
                {"role": "assistant", "content": self._pending_response}
            )
        self._chat_view.append("")
        self._pending_response = ""
        self._send_btn.setEnabled(True)
        color = THEME["success"]
        self._status_lbl.setStyleSheet(f"color:{color}; font-size:10px;")
        self._status_lbl.setToolTip("Ollama verbunden")
        # Worker-Referenz in Warteliste verschieben; finished-Signal entfernt sie
        if self._worker is not None:
            self._retired_workers.append(self._worker)
            self._worker = None

    def _on_error(self, msg: str):
        err_color = THEME["error"]
        self._chat_view.append(
            f"<span style='color:{err_color}'>⚠ {msg}</span>"
        )
        self._chat_view.append("")
        self._pending_response = ""
        self._send_btn.setEnabled(True)
        self._status_lbl.setStyleSheet(
            f"color:{THEME['error']}; font-size:10px;"
        )
        self._status_lbl.setToolTip("Ollama nicht erreichbar")
        if self._worker is not None:
            self._retired_workers.append(self._worker)
            self._worker = None

    # ── Verlauf löschen ─────────────────────────────────────────────────────
    def _clear_history(self):
        self._history = [{"role": "system", "content": INFI_SYSTEM_PROMPT}]
        self._chat_view.clear()
        self._append_infi(
            "Neues Gespräch gestartet! 🙂  Was möchtest du als Nächstes ausprobieren?"
        )

    # ── Hilfsmethoden für Chat-Darstellung ──────────────────────────────────
    def _append_user(self, text: str):
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        color = THEME["info"]
        self._chat_view.append(f"<b style='color:{color}'>Du:</b> {safe}")
        self._chat_view.append("")

    def _append_infi(self, text: str):
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        color = THEME["accent"]
        self._chat_view.append(f"<b style='color:{color}'>Infi:</b> {safe}")
        self._chat_view.append("")

    # ── Einstellungen übernehmen ─────────────────────────────────────────────
    def apply_settings(self, url: str, model: str):
        self._ollama_url = url.strip() or TUTOR_DEFAULT_URL
        self._model      = model.strip() or TUTOR_DEFAULT_MODEL
