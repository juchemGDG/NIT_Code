"""Code-Generator-Panel – Schüler spezifizieren, die KI setzt um."""
import json
import re

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QFrame,
)

from .config import THEME, TUTOR_DEFAULT_URL, TUTOR_DEFAULT_MODEL

# ── System-Prompt: Auftragnehmer-Modus ───────────────────────────────────────
CODER_SYSTEM_PROMPT = """\
Du bist ein Code-Generator für den Informatikunterricht. Du setzt \
Spezifikationen von Schülerinnen und Schülern in Python-Code um – \
aber NUR, wenn die Spezifikation vollständig ist.

Eine vollständige Spezifikation enthält alle vier Teile:
1. EINGABE: Welche Sensoren oder Eingaben gibt es? (Datentyp, Wertebereich)
2. ABLAUF: Der Algorithmus als Freitext mit Signalwörtern (falls, solange, \
wiederhole, zähle) ODER als Mermaid-Flussdiagramm – inklusive aller \
Bedingungen und Schleifen mit konkreten Abbruchkriterien.
3. AUSGABE: Welche Aktoren oder Ausgaben gibt es? (Pins, Formate, Wertebereiche)
4. VARIABLEN: Name, Datentyp und Bedeutung jeder benötigten Variable.

Deine Regeln:
- Fehlt ein Teil oder ist etwas mehrdeutig, generierst du KEINEN Code. \
Stattdessen stellst du gezielte Rückfragen und benennst, welcher Teil fehlt.
- Du entwirfst NIEMALS selbst den Algorithmus. Auf "Wie löse ich das?" \
antwortest du: "Der Lösungsweg ist deine Aufgabe. Beschreibe mir deinen \
Ansatz, ich setze ihn um."
- Du verbesserst fehlerhafte Algorithmen NICHT stillschweigend. Einen \
logischen Fehler (z. B. Endlosschleife, unerreichbarer Zweig) setzt du \
TROTZDEM exakt so um. Am Ende weist du mit einer Frage darauf hin: \
"Mir ist aufgefallen, dass … Was passiert in deinem Diagramm, wenn …? \
Prüfe das."
- Kein Kommentar im generierten Code. Kommentieren ist ausschließlich \
Aufgabe der Schülerinnen und Schüler (Verifikation).
- Importe immer als "from ... import ..." schreiben, niemals "import modul".
- Warten: ausschließlich "from time import sleep" oder \
"from time import sleep_ms" verwenden.
- Analoge Eingänge (ADC): immer 10-Bit-Auflösung \
(adc.width(ADC.WIDTH_10BIT)) und volle Bandbreite \
(adc.atten(ADC.ATTN_11DB), 0–3,6 V) konfigurieren.
- Nach dem Code stellst du genau EINE Verstandnisfrage, die beantwortet \
werden soll, bevor der Code ausgefuhrt wird.
- Du antwortest auf Deutsch, freundlich und knapp.

NIT-BIBLIOTHEKEN – Verwende IMMER die passende Bibliothek, wenn die entsprechende \
Hardware in der Spezifikation vorkommt. Importiere niemals Funktionalität aus \
machine oder anderen Modulen, wenn eine NIT-Bibliothek existiert.

OLED-Display (SSD1306 / SH1106, I2C):
  from nitbw_oled import OLED
  from machine import I2C, Pin
  i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
  oled = OLED(i2c, chip='ssd1306')   # chip='sh1106' fuer SH1106
  oled.print("Text", x, y)           # font='sans' unterstuetzt Umlaute
  oled.hline(x,y,l) / oled.vline(x,y,l) / oled.line(x1,y1,x2,y2)
  oled.rect(x,y,w,h) / oled.fill_rect(x,y,w,h,farbe)
  oled.circle(x,y,r) / oled.fill_circle(x,y,r)
  oled.show()   # nach jeder Zeichenoperation aufrufen
  oled.clear()

LCD-Display (HD44780 + PCF8574, I2C):
  from nitbw_lcd import LCD
  lcd = LCD(i2c, addr=0x27)
  lcd.print("Text", spalte, zeile)
  lcd.clear() / lcd.clear_line(zeile)

Toene – einfach (passiver Piezo):
  from nitbw_toene import TOENE
  speaker = TOENE(Pin(15), geschwindigkeit=60)
  speaker.ton(("C4", 1/4))   # Note, Dauer als Bruch; "P" = Pause
  speaker.spiele_lied([("C4", 1/4), ("P", 1/4), ...])
  speaker.stop()

Toene – erweitert mit Notenkonstanten (NITon):
  from nitbw_niton import NITon, c, d, e, f, g, a, h, c2
  from nitbw_niton import viertel, halbe, vi, ha
  ton = NITon(pin=15, geschwindigkeit=80, legato=95)
  ton.ton(c, viertel)
  ton.pause(viertel)
  ton.setGeschw(140) / ton.setLegato(90)

Ultraschall HC-SR04:
  from nitbw_ultraschall import Ultraschall
  sensor = Ultraschall(trigger=5, echo=18)
  sensor.messen_cm() / sensor.messen_mm() / sensor.messen_laufzeit()

Servo:
  from nitbw_servo import Servo
  servo = Servo(pin=13)
  servo.winkel(grad)   # 0 bis 180
  servo.mitte() / servo.minimum() / servo.maximum()
  servo.lese_winkel() / servo.aus()

Schrittmotor NEMA17 mit A4988/DRV8825 (StepperDir):
  from nitbw_stepper import StepperDir, VOR, ZURUECK
  motor = StepperDir(step_pin=14, dir_pin=27, enable_pin=26,
                     schritte_pro_umdrehung=200, geschwindigkeit=400)
  motor.schritte(n, VOR) / motor.winkel(grad, VOR) / motor.umdrehungen(n, VOR)
  motor.geschwindigkeit(sps) / motor.lese_position()
  motor.aktivieren() / motor.deaktivieren() / motor.aus()

Schrittmotor 28BYJ-48 mit ULN2003 (StepperULN):
  from nitbw_stepper import StepperULN, VOR, ZURUECK
  motor = StepperULN(pins=[IN1, IN2, IN3, IN4], geschwindigkeit=800)
  motor.schritte(n, VOR) / motor.umdrehungen(n, VOR) / motor.aus()

Temperatur DS18B20 (OneWire):
  from machine import Pin
  from nitbw_ds18b20 import DS18B20
  sensor = DS18B20(Pin(4))
  sensor.messen()   # float Grad Celsius oder None

Temperatur + Luftdruck + Feuchte BME280 (I2C):
  from nitbw_bme280 import BME280
  sensor = BME280(i2c)
  temperatur, druck, feuchtigkeit = sensor.read_all()
  sensor.calculate_altitude()

Pulssensor (analoger ADC-Pin):
  from nitbw_puls import Pulssensor
  sensor = Pulssensor(adc_pin=34)
  sensor.lesen_roh()
  sensor.lesen_roh_mittelwert(samples=8, pause_ms=2)

Farbsensor TCS3200:
  from nitbw_tcs3200 import TCS3200
  sensor = TCS3200(out=27, s2=14, s3=12, s0=26, s1=25)
  sensor.messen_rohwerte(messungen=8)   # dict: 'rot','gruen','blau','klar'
  sensor.dominante_farbe(messungen=8)

TOF-Abstandssensor VL53L0X (I2C):
  from nitbw_tof import TOF
  sensor = TOF(i2c)
  sensor.messen_mm() / sensor.messen_cm()

Joystick KY-023:
  from nitbw_ky023 import KY023
  joystick = KY023(vrx_pin=34, vry_pin=35, sw_pin=32)
  d = joystick.daten()
  # d: {'x_raw':..., 'y_raw':..., 'x':-1..1, 'y':-1..1, 'sw':bool, 'richtung':str}
  joystick.kalibrieren_mitte(samples=100)

Echtzeituhr RTC DS3231/DS1307 (I2C):
  from nitbw_rtc import RTC
  rtc = RTC(chip='DS3231', i2c=i2c)
  rtc.toString("DD.MM.YYYY hh:mm:ss")

ESP-NOW (Funk zwischen zwei ESP32):
  from nitbw_espnow import ESPNow
  esp = ESPNow()
  esp.get_mac()
  esp.add_peer("AA:BB:CC:DD:EE:FF")
  esp.send("AA:BB:CC:DD:EE:FF", "Nachricht")
  msg, sender = esp.receive(timeout_ms=250)

MQTT (WiFi, Broker z.B. Raspberry Pi):
  import network
  from nitbw_mqtt import MQTTClient
  client = MQTTClient(client_id=b"esp32", server="192.168.x.x", keepalive=30)
  client.set_callback(lambda topic, msg: ...)
  client.connect()
  client.subscribe(b"nit/topic")
  client.publish(b"nit/topic", "wert")
  client.check_msg()   # regelmaessig in der Schleife aufrufen
  client.keepalive_step()

Spektralsensor AS7262 (I2C):
  from nitbw_as7262 import AS7262
  sensor = AS7262(i2c)
  sensor.messen_rohwerte()   # dict mit Wellenlaengen 450–680 nm

Kompass / Magnetometer (I2C):
  from nitbw_compass import Compass
  kompass = Compass(i2c)
  kompass.heading()   # Gradzahl 0–360

Maschinelles Lernen (kNN / Entscheidungsbaum / Random Forest / Neuronales Netz):
  from nitbw_mlearn import MLearn
  model = MLearn(k=3)
  model.load_csv('daten.csv', separator=',', target=0)
  model.train_knn() / model.predict_knn(features)
  model.train_tree(max_depth=3) / model.predict_tree(features)
  model.train_forest(n_trees=5, max_depth=3) / model.predict_forest(features)
  model.train_netz(hidden=8, epochs=200, lr=0.01) / model.predict_netz(features)

NeoPixel WS2812B (direkt MicroPython):
  from machine import Pin
  from neopixel import NeoPixel
  np = NeoPixel(Pin(DATA_PIN), ANZAHL_LEDS)
  np[0] = (255, 0, 0)   # (R, G, B) je 0–255
  np.write()
  np.fill((0, 0, 0))    # alle LEDs ausschalten
  np.write()

Temperatur + Feuchte DHT22 (direkt MicroPython):
  from machine import Pin
  from dht import DHT22
  sensor = DHT22(Pin(DATA_PIN))
  sensor.measure()
  temperatur = sensor.temperature()   # float Grad Celsius
  feuchte    = sensor.humidity()      # float Prozent\
"""

# Unsichtbar an jede Nutzernachricht angehängt – hält kleine Modelle auf Kurs
_RULE_REMINDER = (
    "\n\n[SYSTEMREGEL: Entwirf KEINEN Algorithmus selbst. "
    "Fehlt ein Spezifikationsteil, stelle Rückfragen. "
    "Kein Kommentar im Code. "
    "Imports nur als 'from ... import ...'. "
    "Antworte auf Deutsch.]"
)

# Vorlage: Eingabe / Ausgabe / Variablen
_SPEC_TEMPLATE = """\
## EINGABE
(Welche Sensoren oder Eingaben? Datentyp und Wertebereich angeben.)
z. B.: Keine externen Eingaben – Programmstart ist der Auslöser.

## AUSGABE
(Welche Aktoren oder Ausgaben? Pins, Formate, Wertebereiche.)
z. B.: 8 RGB-LEDs (WS2812B) an einem Datenpin; je LED Farbwert (R, G, B).

## VARIABLEN
(Name | Datentyp | Bedeutung)
z. B.:
position  | int | aktuelle LED-Position (0–7)
farbindex | int | aktueller Farbindex (0 = Rot, 1 = Grün, 2 = Blau)\
"""

# Ablauf-Vorlage: Freitext mit Signalwörtern
_ABLAUF_FREITEXT_PLACEHOLDER = """\
Beschreibe den Ablauf in eigenen Worten.
Nutze die Signalwörter aus der Leiste unten.

Beispiel:
position auf 0 setzen, farbindex auf 0 setzen
wiederhole für immer:
    position um 1 erhöhen
    falls position > 7:
        position auf 0 setzen
        farbindex um 1 erhöhen
        falls farbindex > 2:
            farbindex auf 0 setzen
    LED an position mit farbe[farbindex] leuchten lassen
    0,05 Sekunden warten\
"""

# Ablauf-Vorlage: Mermaid-Diagramm
_ABLAUF_MERMAID_PLACEHOLDER = """\
flowchart TD
    A([Start]) --> B[position = 0, farbindex = 0]
    B --> C[LED position leuchtet in farbe]
    C --> D[position + 1]
    D --> E{position > 7?}
    E -- Ja --> F[position = 0]
    F --> G[farbindex + 1]
    G --> H{farbindex > 2?}
    H -- Ja --> I[farbindex = 0]
    H -- Nein --> C
    I --> C
    E -- Nein --> C\
"""

# Signalwort-Bausteine: (Beschriftung, einzufügender Text)
_SIGNAL_SNIPPETS = [
    ("falls … dann",   "falls BEDINGUNG:\n    AKTION\n"),
    ("sonst",          "sonst:\n    AKTION\n"),
    ("solange … tue",  "solange BEDINGUNG:\n    AKTION\n"),
    ("wiederhole … bis", "wiederhole:\n    AKTION\nbis BEDINGUNG\n"),
    ("zähle … bis",    "zähle i von 0 bis ZAHL:\n    AKTION\n"),
    ("warte bis",      "warte bis BEDINGUNG\n"),
]

_BTN_ACTIVE = (
    f"background:{THEME['accent']}; color:#fff; font-weight:bold;"
    f"border:none; border-radius:4px; padding:3px 8px; font-size:11px;"
)
_BTN_INACTIVE = (
    f"background:{THEME['bg_dark']}; color:{THEME['text_dim']};"
    f"border:1px solid {THEME['border']}; border-radius:4px;"
    f"padding:3px 8px; font-size:11px;"
)
_BTN_SIGNAL = (
    f"background:{THEME['bg_mid'] if 'bg_mid' in THEME else THEME['bg_dark']};"
    f"color:{THEME['info']};"
    f"border:1px solid {THEME['border']}; border-radius:3px;"
    f"padding:2px 6px; font-size:10px;"
)


# ── Ollama-Worker ─────────────────────────────────────────────────────────────
class _OllamaWorker(QThread):
    token_ready    = pyqtSignal(str)
    response_done  = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, url: str, model: str, messages: list,
                 temperature: float, parent=None):
        super().__init__(parent)
        self._url         = url.rstrip("/")
        self._model       = model
        self._messages    = messages
        self._temperature = temperature

    def run(self):
        endpoint = f"{self._url}/api/chat"
        payload = {
            "model":    self._model,
            "messages": self._messages,
            "stream":   True,
            "options":  {"temperature": self._temperature},
        }
        try:
            with requests.post(
                endpoint, json=payload, stream=True, timeout=120,
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


# ── CoderPanel ────────────────────────────────────────────────────────────────
class CoderPanel(QWidget):
    """Seitliches Panel: Schüler spezifizieren vollständig – Bot generiert Code."""

    insert_code_requested = pyqtSignal(str)   # Code-Block → neuer Editor-Tab

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ollama_url       = TUTOR_DEFAULT_URL
        self._model            = TUTOR_DEFAULT_MODEL
        self._history: list    = [{"role": "system", "content": CODER_SYSTEM_PROMPT}]
        self._worker           = None
        self._retired_workers: list = []
        self._pending_response = ""
        self._last_code_block  = ""
        self._iteration        = 0
        self._ablauf_mode      = "freitext"   # "freitext" | "mermaid"
        self._build_ui()

    # ── UI aufbauen ──────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setMinimumWidth(260)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(
            f"background:{THEME['bg_panel']};"
            f"border-bottom:1px solid {THEME['border']};"
        )
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(10, 0, 10, 0)
        title_lbl = QLabel("⚙  Code-Generator")
        title_lbl.setStyleSheet(
            f"color:{THEME['text']}; font-weight:bold; font-size:13px;"
        )
        hlay.addWidget(title_lbl)
        hlay.addStretch()
        self._iter_lbl = QLabel("Iteration 0")
        self._iter_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:10px;"
        )
        hlay.addWidget(self._iter_lbl)
        self._status_lbl = QLabel("●")
        self._status_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:10px; margin-left:6px;"
        )
        root.addWidget(header)

        # ── Spezifikations-Accordion ───────────────────────────────────────
        self._spec_wrapper = QWidget()
        self._spec_wrapper.setStyleSheet(f"background:{THEME['bg_panel']};")
        sw_layout = QVBoxLayout(self._spec_wrapper)
        sw_layout.setContentsMargins(8, 6, 8, 4)
        sw_layout.setSpacing(4)

        acc_row = QHBoxLayout()
        spec_lbl = QLabel("SPEZIFIKATION")
        spec_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:10px;"
            f"font-weight:bold; letter-spacing:1px;"
        )
        acc_row.addWidget(spec_lbl)
        acc_row.addStretch()
        self._toggle_btn = QPushButton("▲ einklappen")
        self._toggle_btn.setStyleSheet(
            f"background:transparent; color:{THEME['text_dim']};"
            f"border:none; font-size:10px; padding:0 2px;"
        )
        self._toggle_btn.clicked.connect(self._toggle_spec)
        acc_row.addWidget(self._toggle_btn)
        sw_layout.addLayout(acc_row)

        # ── Kollabierter Inhalt ────────────────────────────────────────────
        self._spec_body = QWidget()
        sb_layout = QVBoxLayout(self._spec_body)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(4)

        # Eingabe / Ausgabe / Variablen
        self._spec_edit = QTextEdit()
        self._spec_edit.setPlaceholderText(_SPEC_TEMPLATE)
        self._spec_edit.setMinimumHeight(110)
        self._spec_edit.setMaximumHeight(180)
        self._spec_edit.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f"border:1px solid {THEME['border']}; border-radius:4px; padding:4px;"
            f"font-family:'JetBrains Mono','Fira Code','Consolas',monospace;"
            f"font-size:11px;"
        )
        sb_layout.addWidget(self._spec_edit)

        # ── Ablauf-Unterbereich ────────────────────────────────────────────
        ablauf_section = QWidget()
        ablauf_layout = QVBoxLayout(ablauf_section)
        ablauf_layout.setContentsMargins(0, 2, 0, 0)
        ablauf_layout.setSpacing(3)

        # Kopfzeile mit Modus-Toggle
        ablauf_header = QHBoxLayout()
        ablauf_lbl = QLabel("ABLAUF")
        ablauf_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:10px;"
            f"font-weight:bold; letter-spacing:1px;"
        )
        ablauf_header.addWidget(ablauf_lbl)
        ablauf_header.addStretch()

        self._btn_freitext = QPushButton("📝 Freitext")
        self._btn_freitext.setStyleSheet(_BTN_ACTIVE)
        self._btn_freitext.clicked.connect(lambda: self._set_ablauf_mode("freitext"))
        ablauf_header.addWidget(self._btn_freitext)

        self._btn_mermaid = QPushButton("📊 Mermaid")
        self._btn_mermaid.setStyleSheet(_BTN_INACTIVE)
        self._btn_mermaid.clicked.connect(lambda: self._set_ablauf_mode("mermaid"))
        ablauf_header.addWidget(self._btn_mermaid)

        ablauf_layout.addLayout(ablauf_header)

        # Ablauf-Textfeld
        self._ablauf_edit = QTextEdit()
        self._ablauf_edit.setPlaceholderText(_ABLAUF_FREITEXT_PLACEHOLDER)
        self._ablauf_edit.setMinimumHeight(120)
        self._ablauf_edit.setMaximumHeight(200)
        self._ablauf_edit.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f"border:1px solid {THEME['border']}; border-radius:4px; padding:4px;"
            f"font-family:'JetBrains Mono','Fira Code','Consolas',monospace;"
            f"font-size:11px;"
        )
        ablauf_layout.addWidget(self._ablauf_edit)

        # Signalwort-Bausteine (nur im Freitext-Modus sichtbar)
        self._signal_row = QWidget()
        signal_layout = QHBoxLayout(self._signal_row)
        signal_layout.setContentsMargins(0, 0, 0, 0)
        signal_layout.setSpacing(3)
        for label, snippet in _SIGNAL_SNIPPETS:
            btn = QPushButton(label)
            btn.setStyleSheet(_BTN_SIGNAL)
            btn.setToolTip(f"Einfügen:\n{snippet}")
            btn.clicked.connect(
                lambda _checked=False, s=snippet: self._insert_signal_snippet(s)
            )
            signal_layout.addWidget(btn)
        signal_layout.addStretch()
        ablauf_layout.addWidget(self._signal_row)

        sb_layout.addWidget(ablauf_section)

        # Senden-Button
        self._send_spec_btn = QPushButton("📤  Spezifikation senden")
        self._send_spec_btn.setStyleSheet(
            f"background:{THEME['accent']}; color:#fff; font-weight:bold;"
            f"border:none; border-radius:4px; padding:5px 12px; font-size:12px;"
        )
        self._send_spec_btn.clicked.connect(self._send_spec)
        sb_layout.addWidget(self._send_spec_btn)

        sw_layout.addWidget(self._spec_body)
        root.addWidget(self._spec_wrapper)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(f"background:{THEME['border']}; margin:0;")
        sep1.setFixedHeight(1)
        root.addWidget(sep1)

        # ── Chat-Verlauf ─────────────────────────────────────────────────
        self._chat_view = QTextEdit()
        self._chat_view.setReadOnly(True)
        self._chat_view.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f"border:none; padding:8px;"
            f"font-family:system-ui,-apple-system,'Segoe UI','Ubuntu',sans-serif;"
            f"font-size:12px;"
        )
        root.addWidget(self._chat_view, stretch=1)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background:{THEME['border']}; margin:0;")
        sep2.setFixedHeight(1)
        root.addWidget(sep2)

        # ── Eingabe & Buttons ────────────────────────────────────────────
        input_area = QWidget()
        input_area.setStyleSheet(f"background:{THEME['bg_panel']};")
        ilay = QVBoxLayout(input_area)
        ilay.setContentsMargins(8, 6, 8, 8)
        ilay.setSpacing(6)

        self._input = QTextEdit()
        self._input.setPlaceholderText(
            "Rückfrage beantworten …  (Strg+Enter = Senden)"
        )
        self._input.setFixedHeight(60)
        self._input.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f"border:1px solid {THEME['border']}; border-radius:4px; padding:4px;"
            f"font-family:system-ui,-apple-system,'Segoe UI','Ubuntu',sans-serif;"
            f"font-size:12px;"
        )
        self._input.installEventFilter(self)
        ilay.addWidget(self._input)

        btn_row = QHBoxLayout()

        self._clear_btn = QPushButton("Neu starten")
        self._clear_btn.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text_dim']};"
            f"border:1px solid {THEME['border']}; border-radius:4px; padding:4px 10px;"
        )
        self._clear_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(self._clear_btn)

        self._insert_btn = QPushButton("→ Editor")
        self._insert_btn.setToolTip("Letzten Code-Block in neuen Tab einfügen")
        self._insert_btn.setEnabled(False)
        self._insert_btn.setStyleSheet(
            f"background:{THEME['success']}; color:#1e1e2e; font-weight:bold;"
            f"border:none; border-radius:4px; padding:4px 10px;"
        )
        self._insert_btn.clicked.connect(self._on_insert_code)
        btn_row.addWidget(self._insert_btn)

        btn_row.addStretch()

        self._send_btn = QPushButton("Senden")
        self._send_btn.setStyleSheet(
            f"background:{THEME['accent']}; color:#fff; font-weight:bold;"
            f"border:none; border-radius:4px; padding:5px 18px;"
        )
        self._send_btn.clicked.connect(self._send_message)
        btn_row.addWidget(self._send_btn)

        ilay.addLayout(btn_row)
        root.addWidget(input_area)

        # Begrüßung
        self._append_bot(
            "Hallo! Ich bin dein Code-Generator. 🛠\n\n"
            "Füll die Spezifikation oben aus – alle vier Teile "
            "(Eingabe, Ablauf, Ausgabe, Variablen) – und klicke "
            'auf "Spezifikation senden".\n\n'
            "Erst wenn die Spezifikation vollständig ist, generiere ich Code."
        )

    # ── Accordion ────────────────────────────────────────────────────────────
    def _toggle_spec(self):
        visible = self._spec_body.isVisible()
        self._spec_body.setVisible(not visible)
        self._toggle_btn.setText("▼ ausklappen" if visible else "▲ einklappen")

    # ── Ablauf-Modus umschalten ───────────────────────────────────────────────
    def _set_ablauf_mode(self, mode: str):
        self._ablauf_mode = mode
        if mode == "freitext":
            self._btn_freitext.setStyleSheet(_BTN_ACTIVE)
            self._btn_mermaid.setStyleSheet(_BTN_INACTIVE)
            self._ablauf_edit.setPlaceholderText(_ABLAUF_FREITEXT_PLACEHOLDER)
            self._signal_row.setVisible(True)
        else:
            self._btn_freitext.setStyleSheet(_BTN_INACTIVE)
            self._btn_mermaid.setStyleSheet(_BTN_ACTIVE)
            self._ablauf_edit.setPlaceholderText(_ABLAUF_MERMAID_PLACEHOLDER)
            self._signal_row.setVisible(False)

    # ── Signalwort-Baustein einfügen ──────────────────────────────────────────
    def _insert_signal_snippet(self, snippet: str):
        cursor = self._ablauf_edit.textCursor()
        cursor.insertText(snippet)
        self._ablauf_edit.setTextCursor(cursor)
        self._ablauf_edit.setFocus()

    # ── Spezifikation zusammenbauen und senden ────────────────────────────────
    def _send_spec(self):
        static = self._spec_edit.toPlainText().strip()
        ablauf = self._ablauf_edit.toPlainText().strip()

        missing = []
        if not static:
            missing.append("Eingabe, Ausgabe und Variablen")
        if not ablauf:
            missing.append("Ablauf")
        if missing:
            self._append_bot(
                f"Bitte füll noch aus: {', '.join(missing)}."
            )
            return

        ablauf_label = (
            "## ABLAUF (Mermaid-Diagramm)" if self._ablauf_mode == "mermaid"
            else "## ABLAUF (Freitext)"
        )
        full_spec = f"{static}\n\n{ablauf_label}\n{ablauf}"
        self._send_text(full_spec)

    # ── Freie Nachricht (Rückfragen-Iteration) ────────────────────────────────
    def _send_message(self):
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self._send_text(text)

    # ── Gemeinsame Sende-Logik ────────────────────────────────────────────────
    def _send_text(self, text: str):
        if self._worker is not None:
            return

        self._iteration += 1
        self._iter_lbl.setText(f"Iteration {self._iteration}")
        self._append_user(text)

        self._history.append(
            {"role": "user", "content": text + _RULE_REMINDER}
        )

        self._send_btn.setEnabled(False)
        self._send_spec_btn.setEnabled(False)
        self._status_lbl.setStyleSheet(
            f"color:{THEME['warning']}; font-size:10px; margin-left:6px;"
        )
        self._pending_response = ""

        self._worker = _OllamaWorker(
            self._ollama_url, self._model, self._history,
            temperature=0.25, parent=self,
        )
        self._worker.token_ready.connect(self._on_token)
        self._worker.response_done.connect(self._on_done)
        self._worker.error_occurred.connect(self._on_error)
        w = self._worker
        self._worker.finished.connect(
            lambda t=w: self._retired_workers.remove(t)
            if t in self._retired_workers else None
        )
        self._worker.start()

        self._chat_view.append("")
        self._chat_view.append(
            f"<b style='color:{THEME['accent']}'>Generator:</b> "
        )

    # ── Streaming-Callbacks ───────────────────────────────────────────────────
    def _on_token(self, token: str):
        self._pending_response += token
        cursor = self._chat_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self._chat_view.setTextCursor(cursor)
        self._chat_view.ensureCursorVisible()

    def _on_done(self):
        if self._worker is None:
            self._pending_response = ""
            return
        if self._pending_response:
            self._history.append(
                {"role": "assistant", "content": self._pending_response}
            )
            code = _extract_code_block(self._pending_response)
            if code:
                self._last_code_block = code
                self._insert_btn.setEnabled(True)
        self._chat_view.append("")
        self._pending_response = ""
        self._send_btn.setEnabled(True)
        self._send_spec_btn.setEnabled(True)
        self._status_lbl.setStyleSheet(
            f"color:{THEME['success']}; font-size:10px; margin-left:6px;"
        )
        if self._worker is not None:
            self._retired_workers.append(self._worker)
            self._worker = None

    def _on_error(self, msg: str):
        self._chat_view.append(
            f"<span style='color:{THEME['error']}'>⚠ {msg}</span>"
        )
        self._chat_view.append("")
        self._pending_response = ""
        self._send_btn.setEnabled(True)
        self._send_spec_btn.setEnabled(True)
        self._status_lbl.setStyleSheet(
            f"color:{THEME['error']}; font-size:10px; margin-left:6px;"
        )
        if self._worker is not None:
            self._retired_workers.append(self._worker)
            self._worker = None

    # ── Code einfügen ────────────────────────────────────────────────────────
    def _on_insert_code(self):
        if self._last_code_block:
            self.insert_code_requested.emit(self._last_code_block)

    # ── Verlauf zurücksetzen ──────────────────────────────────────────────────
    def _clear_history(self):
        self._history         = [{"role": "system", "content": CODER_SYSTEM_PROMPT}]
        self._last_code_block = ""
        self._iteration       = 0
        self._iter_lbl.setText("Iteration 0")
        self._insert_btn.setEnabled(False)
        self._chat_view.clear()
        self._ablauf_edit.clear()
        self._spec_body.setVisible(True)
        self._toggle_btn.setText("▲ einklappen")
        self._set_ablauf_mode("freitext")
        self._append_bot(
            "Neues Projekt gestartet. "
            "Füll die Spezifikation aus und sende sie ab."
        )

    # ── Darstellung ──────────────────────────────────────────────────────────
    def _append_user(self, text: str):
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._chat_view.append(
            f"<b style='color:{THEME['info']}'>Du:</b> {safe}"
        )
        self._chat_view.append("")

    def _append_bot(self, text: str):
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._chat_view.append(
            f"<b style='color:{THEME['accent']}'>Generator:</b> {safe}"
        )
        self._chat_view.append("")

    # ── Strg+Enter im Eingabefeld ─────────────────────────────────────────────
    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key  = event.key()
            mods = event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if mods & Qt.KeyboardModifier.ControlModifier:
                    self._send_message()
                    return True
        return super().eventFilter(obj, event)

    # ── Einstellungen übernehmen ──────────────────────────────────────────────
    def apply_settings(self, url: str, model: str):
        self._ollama_url = url.strip()   or TUTOR_DEFAULT_URL
        self._model      = model.strip() or TUTOR_DEFAULT_MODEL


# ── Hilfsfunktion ─────────────────────────────────────────────────────────────
def _extract_code_block(text: str) -> str:
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return match.group(1).rstrip() if match else ""
