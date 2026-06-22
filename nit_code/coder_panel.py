"""Code-Generator-Panel – Schüler spezifizieren, die KI setzt um."""
import json
import os
import re
import sys
from pathlib import Path

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QRect, QPoint, QUrl
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QFrame, QLayout, QSizePolicy,
)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _WEBENGINE_AVAILABLE = True
except ImportError:
    _WEBENGINE_AVAILABLE = False

from .config import THEME, TUTOR_DEFAULT_URL, TUTOR_DEFAULT_MODEL


# ── Offline-Asset-Pfad (mermaid.min.js) ──────────────────────────────────────
def _asset_path(name: str):
    """Findet eine Datei im assets-Ordner – im Dev- wie im PyInstaller-Bundle."""
    candidates = []
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "nit_code" / "assets" / name)
        candidates.append(Path(sys.executable).parent / "nit_code" / "assets" / name)
    candidates.append(Path(__file__).resolve().parent / "assets" / name)
    for p in candidates:
        if p.exists():
            return p
    return None


# ── FlowLayout: Buttons brechen automatisch in die nächste Zeile um ──────────
class FlowLayout(QLayout):
    """Anordnung, die Kinder zeilenweise umbricht (wie Wörter im Fließtext)."""

    def __init__(self, parent=None, margin=0, spacing=4):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        line_height = 0
        spacing = self.spacing()
        right = rect.right() - m.right()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > right and line_height > 0:
                x = rect.x() + m.left()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + m.bottom()


class _FlowWidget(QWidget):
    """Container, der eine FlowLayout korrekt in vertikale Layouts einbettet."""

    def __init__(self, parent=None, spacing=4):
        super().__init__(parent)
        self._flow = FlowLayout(self, margin=0, spacing=spacing)
        sp = self.sizePolicy()
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def add_widget(self, w):
        self._flow.addWidget(w)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._flow.heightForWidth(width)

# ── System-Prompt: Auftragnehmer-Modus ───────────────────────────────────────
CODER_SYSTEM_PROMPT = """\
Du bist ein Code-Generator für den Informatikunterricht. Du setzt \
Spezifikationen von Schülerinnen und Schülern in Python-Code um – \
aber NUR, wenn die Spezifikation vollständig ist.

Eine vollständige Spezifikation besteht aus vier Teilen:
1. EINGABE: Welche Sensoren oder Eingaben gibt es? (Datentyp, Wertebereich)
2. ABLAUF: Der Algorithmus als Freitext mit Signalwörtern (falls, solange, \
wiederhole, zähle) ODER als Mermaid-Flussdiagramm – inklusive aller \
Bedingungen und Schleifen mit konkreten Abbruchkriterien.
3. AUSGABE: Welche Aktoren oder Ausgaben gibt es? (Pins, Formate, Wertebereiche)
4. VARIABLEN: Name, Datentyp und Bedeutung jeder benötigten Variable.

WICHTIG – leere Teile sind ausdrücklich erlaubt: Markiert die Schülerin oder \
der Schüler einen Teil mit „-", „keine", „nicht vorhanden", „entfällt" oder \
einer ähnlichen eindeutigen Formulierung, dann ist dieser Teil BEWUSST LEER \
und gilt als VOLLSTÄNDIG geklärt. Du fragst dazu NICHT nach und behandelst \
ihn NICHT als fehlend. Nur der ABLAUF darf nie leer sein.

Eine Spezifikation ist VOLLSTÄNDIG, sobald ein ABLAUF vorhanden ist UND die \
Teile EINGABE, AUSGABE und VARIABLEN jeweils entweder ausgefüllt ODER als \
leer markiert sind. In diesem Fall generierst du SOFORT Code – ohne weitere \
Rückfragen.

Deine Regeln:
- Generiere Code, sobald die Spezifikation vollständig ist (siehe oben). Ein \
mit „-"/„keine" als leer markierter Teil ist KEIN fehlender Teil.
- Stelle eine Rückfrage NUR, wenn ein Teil tatsächlich völlig fehlt (gar nicht \
erwähnt) oder echt mehrdeutig ist. Stelle dieselbe Frage NIEMALS zweimal.
- Du siehst den gesamten bisherigen Gesprächsverlauf. Berücksichtige IMMER \
alle vorherigen Angaben und frage NIE erneut nach Punkten, die bereits \
beantwortet oder als leer markiert wurden.
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
- Verzichte VOLLSTÄNDIG auf eine "main()"-Funktion und auf die Konstruktion \
"if __name__ == \"__main__\":". Das Programm beginnt nach Importen und \
Initialisierung DIREKT mit dem ersten Befehl bzw. der (Haupt-)Schleife auf \
oberster Ebene. Das ist für Schülerinnen und Schüler leichter zu verstehen.
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
  oled.draw_rect(x,y,w,h) / oled.fill_rect(x,y,w,h,farbe)
  oled.draw_circle(x,y,r) / oled.fill_circle(x,y,r)
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
  from nitbw_niton import viertel, achtel, halbe, ganze, viertelpunkt, halbepunkt, vierteltriole
  ton = NITon(15, geschwindigkeit=80, legato=95)   # erstes Argument positional (Pin)
  ton.ton(c, viertel)
  ton.ton(0, viertel)        # Pause/Rest (Hoehe 0); ton.pause(ms) erwartet Millisekunden
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
  motor = StepperULN(IN1, IN2, IN3, IN4, geschwindigkeit=800)   # 4 Pins positional
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
  sensor.messen_roh()        # Werte der 6 Kanaele (450–680 nm)
  sensor.messen_kalibriert() / sensor.dominanter_kanal()

Kompass / Magnetometer (I2C):
  from nitbw_compass import Compass
  kompass = Compass(i2c)
  kompass.read_heading()   # Gradzahl 0–360 (NICHT heading())

Lage-/Bewegungssensor MPU6050 (I2C):
  from nitbw_mpu6050 import MPU6050
  mpu = MPU6050(i2c, addr=0x68)
  mpu.read_pitch() / mpu.read_roll() / mpu.read_tilt_angle()   # Grad
  ax, ay, az = mpu.read_accel()   # g    /    gx, gy, gz = mpu.read_gyro()   # deg/s
  mpu.read_temperature()
  mpu.is_level(threshold=5.0) / mpu.read_orientation_text()
  mpu.calibrate_gyro(samples=200)   # einmalig zu Beginn (Sensor ruhig halten)

Maschinelles Lernen (kNN / Entscheidungsbaum / Random Forest / Neuronales Netz):
  from nitbw_mlearn import MLearn
  model = MLearn(k=3)
  model.load_csv('daten.csv', separator=',', target=0)
  model.train_knn() / model.predict_knn(features)
  model.train_tree(max_depth=3) / model.predict_tree(features)
  model.train_forest(n_trees=5, max_depth=3) / model.predict_forest(features)
  model.train_netz(hidden=8, epochs=200, lr=0.01) / model.predict_netz(features)
  model.train_logreg() / model.predict_logreg(features)
  model.add_sample(features, label) / model.split_data(anteil_test=0.2, seed=42)
  model.save_model('modell.json', model_type='knn') / model.load_model('modell.json')

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
    "Berücksichtige ALLE bisherigen Angaben aus dem Verlauf und frage NICHT "
    "erneut nach Teilen, die bereits beantwortet oder mit '-'/'keine' als leer "
    "markiert wurden. Sind EINGABE, AUSGABE und VARIABLEN ausgefüllt oder als "
    "leer markiert und ein ABLAUF vorhanden, generiere SOFORT Code statt "
    "Rückfragen zu stellen. Stelle dieselbe Frage nie zweimal. "
    "Kein Kommentar im Code. Imports nur als 'from ... import ...'. "
    "KEINE 'main()'-Funktion und kein 'if __name__ == \"__main__\":' – das "
    "Programm startet direkt mit dem ersten Befehl bzw. der Schleife auf "
    "oberster Ebene. "
    "Antworte auf Deutsch.]"
)

# Erkennt einen Leer-Marker als Wert ("-", "keine", "nicht vorhanden", …).
# Greift nur bei NICHT-leerem Wert in derselben Zeile, damit die Vorlagen-Form
# ("## AUSGABE" mit Inhalt in der Folgezeile) nicht fälschlich als leer gilt.
_ABSENT_RE = re.compile(
    r'^[\-–—_.]+$|^(keine|kein|nichts?|nicht\s+vorhanden|entf[äa]llt|n/?a|none)\b',
    re.IGNORECASE,
)
# Zeile der Form  "EINGABE: …"  oder  "## EINGABE …"
_SPEC_LINE_RE = re.compile(
    r'^\s*#*\s*(EINGABE|AUSGABE|VARIABLEN?)\s*[:\-–]?\s*(.*)$',
    re.IGNORECASE,
)


def _normalize_spec(text: str) -> str:
    """Macht bewusst leere Teile (z. B. "EINGABE: -") für das Modell eindeutig.

    Schwache lokale Modelle interpretieren einen bloßen Bindestrich oft als
    "fehlt" und fragen endlos nach. Hier wird daraus ein klarer Satz.
    """
    out = []
    for line in text.splitlines():
        m = _SPEC_LINE_RE.match(line)
        if m:
            label, value = m.group(1).upper(), m.group(2).strip()
            if value and _ABSENT_RE.match(value):
                out.append(
                    f"{label}: keine (dieser Teil ist bewusst leer und gilt "
                    f"als vollständig geklärt – bitte NICHT nachfragen)"
                )
                continue
        out.append(line)
    return "\n".join(out)

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
    ("wiederhole fortlaufend", "wiederhole fortlaufend:\n    AKTION\n"),
    ("wiederhole … bis", "wiederhole:\n    AKTION\nbis BEDINGUNG\n"),
    ("zähle … bis",    "zähle i von 0 bis ZAHL:\n    AKTION\n"),
    ("warte bis",      "warte bis BEDINGUNG\n"),
]

# Mermaid-Bausteine: (Beschriftung, einzufügender Text)
_MERMAID_SNIPPETS = [
    ("▶ Start",        "flowchart TD\n    A([Start]) --> B[ ]\n"),
    ("▭ Aktion",       "    B[Aktion beschreiben]\n"),
    ("◇ Verzweigung",  "    C{Bedingung?}\n    C -- Ja --> D[ ]\n    C -- Nein --> E[ ]\n"),
    ("↻ Schleife",     "    F{Weiter?}\n    F -- Ja --> G[Aktion] --> F\n"),
    ("⏹ Ende",         "    Z([Ende])\n"),
    ("→ Pfeil",        "    X --> Y\n"),
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
    f"border:1px solid {THEME['border']}; border-radius:4px;"
    f"padding:4px 9px; font-size:11px;"
)


def _btn_signal_style() -> str:
    """Stil der Baustein-Buttons (aus aktuellem THEME)."""
    return (
        f"QPushButton {{ background:{THEME.get('bg_mid', THEME['bg_dark'])};"
        f" color:{THEME['info']}; border:1px solid {THEME['border']};"
        f" border-radius:4px; padding:4px 9px; font-size:11px; }}"
        f"QPushButton:hover {{ background:{THEME['selection']}; }}"
    )


# ── Mermaid-Live-Vorschau (offline via mermaid.min.js) ───────────────────────
_MERMAID_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html,body {{ margin:0; padding:6px; background:{bg}; color:{fg};
               font-family:system-ui,-apple-system,'Segoe UI',sans-serif; }}
  #diagram {{ display:flex; justify-content:center; align-items:flex-start; }}
  #diagram svg {{ max-width:100%; height:auto; }}
  pre.err {{ color:#cc0000; white-space:pre-wrap; font-size:12px; padding:6px; }}
  .hint {{ color:{dim}; font-size:12px; text-align:center; margin-top:24px; }}
</style>
<script src="mermaid.min.js"></script>
</head><body>
<div id="diagram"><div class="hint">Diagramm erscheint hier …</div></div>
<script>
  mermaid.initialize({{ startOnLoad:false, theme:'{theme}',
                        securityLevel:'loose', flowchart:{{useMaxWidth:true}} }});
  async function renderMermaid(code) {{
    const el = document.getElementById('diagram');
    code = (code || '').trim();
    if (!code) {{ el.innerHTML = '<div class="hint">Diagramm erscheint hier …</div>'; return; }}
    try {{
      const {{ svg }} = await mermaid.render('g' + Date.now(), code);
      el.innerHTML = svg;
    }} catch (e) {{
      el.innerHTML = '<pre class="err">⚠ ' + ((e && e.message) || e) + '</pre>';
    }}
  }}
</script>
</body></html>"""


class MermaidPreview(QWidget):
    """Rendert Mermaid-Diagramme live über mermaid.js in einer Webansicht."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready    = False
        self._pending  = None
        self._asset    = _asset_path("mermaid.min.js")
        self._available = _WEBENGINE_AVAILABLE and self._asset is not None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self._available:
            self._view = QWebEngineView(self)
            self._view.setMinimumHeight(160)
            self._view.loadFinished.connect(self._on_load)
            layout.addWidget(self._view)
            self._reload_shell()
        else:
            self._view = None
            self._fallback = QLabel(
                "Mermaid-Vorschau nicht verfügbar.\n"
                "(PyQt6-WebEngine oder mermaid.min.js fehlt.)"
            )
            self._fallback.setWordWrap(True)
            self._fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._fallback)

    def _reload_shell(self):
        if not self._available:
            return
        self._ready = False
        dark = self._is_dark()
        html = _MERMAID_HTML.format(
            bg=THEME["bg_editor"], fg=THEME["text"], dim=THEME["text_dim"],
            theme="dark" if dark else "default",
        )
        base = QUrl.fromLocalFile(str(self._asset.parent) + os.sep)
        self._view.setHtml(html, base)

    @staticmethod
    def _is_dark() -> bool:
        bg = THEME.get("bg_editor", "#ffffff").lstrip("#")
        try:
            r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
            return (r + g + b) / 3 < 128
        except Exception:
            return False

    def _on_load(self, _ok):
        self._ready = True
        if self._pending is not None:
            self.render(self._pending)
            self._pending = None

    def apply_theme(self):
        """Vorschau mit aktuellen Theme-Farben neu laden (behält Inhalt bei)."""
        if self._available:
            self._reload_shell()

    def render(self, code: str):
        if not self._available:
            return
        self._pending = code
        if not self._ready:
            return
        self._pending = None
        self._view.page().runJavaScript("renderMermaid(%s);" % json.dumps(code))


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
    open_as_blocks_requested = pyqtSignal(str) # Code-Block → Block-Editor (Coder→Blockly)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ollama_url       = TUTOR_DEFAULT_URL
        self._model            = TUTOR_DEFAULT_MODEL
        self._history: list    = [{"role": "system", "content": CODER_SYSTEM_PROMPT}]
        self._worker           = None
        self._retired_workers: list = []
        self._pending_response = ""
        self._last_code_block  = ""
        self._response_start   = 0
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
        self._header = QWidget()
        self._header.setFixedHeight(36)
        hlay = QHBoxLayout(self._header)
        hlay.setContentsMargins(10, 0, 10, 0)
        self._title_lbl = QLabel("⚙  Code-Generator")
        hlay.addWidget(self._title_lbl)
        hlay.addStretch()
        self._iter_lbl = QLabel("Iteration 0")
        hlay.addWidget(self._iter_lbl)
        self._status_lbl = QLabel("●")
        root.addWidget(self._header)

        # ── Spezifikations-Accordion ───────────────────────────────────────
        self._spec_wrapper = QWidget()
        self._spec_wrapper.setStyleSheet(f"background:{THEME['bg_panel']};")
        sw_layout = QVBoxLayout(self._spec_wrapper)
        sw_layout.setContentsMargins(8, 6, 8, 4)
        sw_layout.setSpacing(4)

        acc_row = QHBoxLayout()
        self._spec_lbl = QLabel("SPEZIFIKATION")
        acc_row.addWidget(self._spec_lbl)
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
        self._ablauf_lbl = QLabel("ABLAUF")
        ablauf_header.addWidget(self._ablauf_lbl)
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

        # Signalwort-Bausteine (Freitext-Modus) – umbrechende Leiste
        self._signal_row = _FlowWidget(spacing=4)
        self._signal_btns: list = []

        # Ein-/Ausrücken um 4 Leerzeichen
        self._indent_btn = QPushButton("→ einrücken")
        self._indent_btn.setToolTip("Markierte Zeilen um 4 Leerzeichen nach rechts")
        self._indent_btn.clicked.connect(lambda: self._shift_ablauf(outdent=False))
        self._signal_row.add_widget(self._indent_btn)
        self._signal_btns.append(self._indent_btn)

        self._outdent_btn = QPushButton("← ausrücken")
        self._outdent_btn.setToolTip("Markierte Zeilen um 4 Leerzeichen nach links")
        self._outdent_btn.clicked.connect(lambda: self._shift_ablauf(outdent=True))
        self._signal_row.add_widget(self._outdent_btn)
        self._signal_btns.append(self._outdent_btn)

        for label, snippet in _SIGNAL_SNIPPETS:
            btn = QPushButton(label)
            btn.setStyleSheet(_btn_signal_style())
            btn.setToolTip(f"Einfügen:\n{snippet}")
            btn.clicked.connect(
                lambda _checked=False, s=snippet: self._insert_signal_snippet(s)
            )
            self._signal_row.add_widget(btn)
            self._signal_btns.append(btn)
        ablauf_layout.addWidget(self._signal_row)

        # Mermaid-Bausteine (Mermaid-Modus) – umbrechende Leiste
        self._mermaid_row = _FlowWidget(spacing=4)
        self._mermaid_btns: list = []
        for label, snippet in _MERMAID_SNIPPETS:
            btn = QPushButton(label)
            btn.setStyleSheet(_btn_signal_style())
            btn.setToolTip(f"Einfügen:\n{snippet}")
            btn.clicked.connect(
                lambda _checked=False, s=snippet: self._insert_signal_snippet(s)
            )
            self._mermaid_row.add_widget(btn)
            self._mermaid_btns.append(btn)
        self._mermaid_row.setVisible(False)
        ablauf_layout.addWidget(self._mermaid_row)

        # Mermaid-Live-Vorschau (nur im Mermaid-Modus sichtbar)
        self._mermaid_preview = MermaidPreview()
        self._mermaid_preview.setVisible(False)
        ablauf_layout.addWidget(self._mermaid_preview)

        # Entprellte Aktualisierung der Vorschau beim Tippen
        self._mermaid_timer = QTimer(self)
        self._mermaid_timer.setSingleShot(True)
        self._mermaid_timer.setInterval(450)
        self._mermaid_timer.timeout.connect(self._render_mermaid_preview)
        self._ablauf_edit.textChanged.connect(self._on_ablauf_changed)

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

        self._sep1 = QFrame()
        self._sep1.setFrameShape(QFrame.Shape.HLine)
        self._sep1.setFixedHeight(1)
        root.addWidget(self._sep1)

        # ── Chat-Verlauf ─────────────────────────────────────────────────
        self._chat_view = QTextEdit()
        self._chat_view.setReadOnly(True)
        root.addWidget(self._chat_view, stretch=1)

        self._sep2 = QFrame()
        self._sep2.setFrameShape(QFrame.Shape.HLine)
        self._sep2.setFixedHeight(1)
        root.addWidget(self._sep2)

        # ── Eingabe & Buttons ────────────────────────────────────────────
        self._input_area = QWidget()
        ilay = QVBoxLayout(self._input_area)
        ilay.setContentsMargins(8, 6, 8, 8)
        ilay.setSpacing(6)

        self._input = QTextEdit()
        self._input.setPlaceholderText(
            "Rückfrage beantworten …  (Strg+Enter = Senden)"
        )
        self._input.setFixedHeight(60)
        self._input.installEventFilter(self)
        ilay.addWidget(self._input)

        btn_row = QHBoxLayout()

        self._clear_btn = QPushButton("Neu starten")
        self._clear_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(self._clear_btn)

        btn_row.addStretch()

        self._send_btn = QPushButton("Senden")
        self._send_btn.clicked.connect(self._send_message)
        btn_row.addWidget(self._send_btn)

        ilay.addLayout(btn_row)

        # Eigene, volle Zeile – der Text „Code in Editor schreiben“ passt sonst
        # bei schmalem Panel nicht zwischen die anderen Buttons und wird
        # abgeschnitten.
        self._insert_btn = QPushButton("→  Code in Editor schreiben")
        self._insert_btn.setToolTip("Generierten Code in einen neuen Editor-Tab übertragen")
        self._insert_btn.setEnabled(False)
        self._insert_btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Fixed)
        self._insert_btn.clicked.connect(self._on_insert_code)
        ilay.addWidget(self._insert_btn)

        self._blocks_btn = QPushButton("🧩  Als Blöcke öffnen")
        self._blocks_btn.setToolTip(
            "Den erzeugten Code im Block-Editor als Blöcke anzeigen "
            "(hilfreich für Einsteiger)")
        self._blocks_btn.setEnabled(False)
        self._blocks_btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Fixed)
        self._blocks_btn.clicked.connect(self._on_open_as_blocks)
        ilay.addWidget(self._blocks_btn)
        root.addWidget(self._input_area)
        self.refresh_theme()

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

    # ── Theme-Refresh ─────────────────────────────────────────────────────────
    def refresh_theme(self):
        self._header.setStyleSheet(
            f"background:{THEME['bg_panel']}; border-bottom:1px solid {THEME['border']};"
        )
        self._title_lbl.setStyleSheet(
            f"color:{THEME['text']}; font-weight:bold; font-size:13px;"
        )
        self._iter_lbl.setStyleSheet(f"color:{THEME['text_dim']}; font-size:10px;")
        self._status_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:10px; margin-left:6px;"
        )
        self._spec_wrapper.setStyleSheet(f"background:{THEME['bg_panel']};")
        self._spec_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        self._toggle_btn.setStyleSheet(
            f"background:transparent; color:{THEME['text_dim']}; border:none; font-size:10px; padding:0 2px;"
        )
        self._spec_edit.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f"border:1px solid {THEME['border']}; border-radius:4px; padding:4px;"
            f"font-family:'JetBrains Mono','Fira Code','Consolas',monospace; font-size:11px;"
        )
        self._ablauf_lbl.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        self._ablauf_edit.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f"border:1px solid {THEME['border']}; border-radius:4px; padding:4px;"
            f"font-family:'JetBrains Mono','Fira Code','Consolas',monospace; font-size:11px;"
        )
        self._send_spec_btn.setStyleSheet(
            f"background:{THEME['accent']}; color:#fff; font-weight:bold;"
            f"border:none; border-radius:4px; padding:5px 12px; font-size:12px;"
        )
        self._sep1.setStyleSheet(f"background:{THEME['border']}; margin:0;")
        self._chat_view.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f"border:none; padding:8px;"
            f"font-family:system-ui,-apple-system,'Segoe UI','Ubuntu',sans-serif; font-size:12px;"
        )
        self._sep2.setStyleSheet(f"background:{THEME['border']}; margin:0;")
        self._input_area.setStyleSheet(f"background:{THEME['bg_panel']};")
        self._input.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f"border:1px solid {THEME['border']}; border-radius:4px; padding:4px;"
            f"font-family:system-ui,-apple-system,'Segoe UI','Ubuntu',sans-serif; font-size:12px;"
        )
        self._clear_btn.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text_dim']};"
            f"border:1px solid {THEME['border']}; border-radius:4px; padding:4px 10px;"
        )
        _action_btn_style = (
            f"QPushButton {{ background:transparent; color:{THEME['accent']};"
            f" border:1px solid {THEME['accent']}; border-radius:4px;"
            f" font-weight:bold; padding:5px 22px; }}"
            f"QPushButton:hover {{ background:{THEME['accent']}; color:#fff; }}"
            f"QPushButton:disabled {{ background:transparent;"
            f" color:{THEME['text_dim']}; border:1px solid {THEME['border']}; }}"
        )
        self._insert_btn.setStyleSheet(_action_btn_style)
        self._blocks_btn.setStyleSheet(_action_btn_style)
        self._send_btn.setStyleSheet(
            f"background:{THEME['accent']}; color:#fff; font-weight:bold;"
            f"border:none; border-radius:4px; padding:5px 18px;"
        )
        btn_active = (
            f"background:{THEME['accent']}; color:#fff; font-weight:bold;"
            f"border:none; border-radius:4px; padding:3px 8px; font-size:11px;"
        )
        btn_inactive = (
            f"background:{THEME['bg_dark']}; color:{THEME['text_dim']};"
            f"border:1px solid {THEME['border']}; border-radius:4px;"
            f"padding:3px 8px; font-size:11px;"
        )
        btn_signal = _btn_signal_style()
        if self._ablauf_mode == "freitext":
            self._btn_freitext.setStyleSheet(btn_active)
            self._btn_mermaid.setStyleSheet(btn_inactive)
        else:
            self._btn_freitext.setStyleSheet(btn_inactive)
            self._btn_mermaid.setStyleSheet(btn_active)
        for btn in self._signal_btns + self._mermaid_btns:
            btn.setStyleSheet(btn_signal)
        self._mermaid_preview.apply_theme()

    # ── Ablauf-Modus umschalten ───────────────────────────────────────────────
    def _set_ablauf_mode(self, mode: str):
        self._ablauf_mode = mode
        if mode == "freitext":
            self._btn_freitext.setStyleSheet(_BTN_ACTIVE)
            self._btn_mermaid.setStyleSheet(_BTN_INACTIVE)
            self._ablauf_edit.setPlaceholderText(_ABLAUF_FREITEXT_PLACEHOLDER)
            self._signal_row.setVisible(True)
            self._mermaid_row.setVisible(False)
            self._mermaid_preview.setVisible(False)
        else:
            self._btn_freitext.setStyleSheet(_BTN_INACTIVE)
            self._btn_mermaid.setStyleSheet(_BTN_ACTIVE)
            self._ablauf_edit.setPlaceholderText(_ABLAUF_MERMAID_PLACEHOLDER)
            self._signal_row.setVisible(False)
            self._mermaid_row.setVisible(True)
            self._mermaid_preview.setVisible(True)
            self._render_mermaid_preview()

    # ── Signalwort-Baustein einfügen ──────────────────────────────────────────
    def _insert_signal_snippet(self, snippet: str):
        cursor = self._ablauf_edit.textCursor()
        cursor.insertText(snippet)
        self._ablauf_edit.setTextCursor(cursor)
        self._ablauf_edit.setFocus()

    # ── Zeilen ein-/ausrücken (4 Leerzeichen) ─────────────────────────────────
    def _shift_ablauf(self, outdent: bool):
        from PyQt6.QtGui import QTextCursor
        INDENT = "    "
        edit = self._ablauf_edit
        doc = edit.document()
        cursor = edit.textCursor()
        start_block = doc.findBlock(cursor.selectionStart())
        end_block = doc.findBlock(cursor.selectionEnd())

        cursor.beginEditBlock()
        block = start_block
        while block.isValid():
            bcur = QTextCursor(block)
            bcur.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            if outdent:
                text = block.text()
                removed = 0
                while removed < 4 and removed < len(text) and text[removed] == " ":
                    removed += 1
                if removed == 0 and text.startswith("\t"):
                    removed = 1
                if removed:
                    bcur.movePosition(
                        QTextCursor.MoveOperation.Right,
                        QTextCursor.MoveMode.KeepAnchor, removed,
                    )
                    bcur.removeSelectedText()
            else:
                bcur.insertText(INDENT)
            if block == end_block:
                break
            block = block.next()
        cursor.endEditBlock()
        edit.setFocus()

    # ── Mermaid-Live-Vorschau ──────────────────────────────────────────────────
    def _on_ablauf_changed(self):
        """Tippen im Ablauf-Feld → Vorschau entprellt neu rendern (nur Mermaid)."""
        if self._ablauf_mode == "mermaid":
            self._mermaid_timer.start()

    def _render_mermaid_preview(self):
        self._mermaid_preview.render(self._ablauf_edit.toPlainText())

    # ── Spezifikation zusammenbauen und senden ────────────────────────────────
    def _send_spec(self):
        static = _normalize_spec(self._spec_edit.toPlainText().strip())
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
        cursor = self._chat_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._response_start = cursor.position()

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
                self._blocks_btn.setEnabled(True)
            # Gestreamten Rohtext durch formatiertes HTML ersetzen
            # (Prosa + farbiger Python-Codeblock).
            cursor = self._chat_view.textCursor()
            cursor.setPosition(self._response_start)
            cursor.movePosition(
                cursor.MoveOperation.End, cursor.MoveMode.KeepAnchor
            )
            cursor.removeSelectedText()
            cursor.insertHtml(_format_response_html(self._pending_response))
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

    def _on_open_as_blocks(self):
        if self._last_code_block:
            self.open_as_blocks_requested.emit(self._last_code_block)

    # ── Verlauf zurücksetzen ──────────────────────────────────────────────────
    def _clear_history(self):
        self._history         = [{"role": "system", "content": CODER_SYSTEM_PROMPT}]
        self._last_code_block = ""
        self._iteration       = 0
        self._iter_lbl.setText("Iteration 0")
        self._insert_btn.setEnabled(False)
        self._blocks_btn.setEnabled(False)
        self._chat_view.clear()
        self._spec_edit.clear()
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


# ── Antwort als formatiertes HTML (Prosa + Python-Codeblock) ──────────────────
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_PY_KEYWORDS = frozenset(
    "False None True and as assert async await break class continue def del "
    "elif else except finally for from global if import in is lambda nonlocal "
    "not or pass raise return try while with yield".split()
)
_PY_BUILTINS = frozenset(
    "print range len int float str bool list dict tuple set input abs min max "
    "sum round sorted enumerate zip map filter open type isinstance".split()
)

# Reihenfolge wichtig: Kommentar/String vor Zahl/Name.
_PY_TOKEN_RE = re.compile(
    r"(?P<comment>#[^\n]*)"
    r"|(?P<string>'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\""
    r"|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\")"
    r"|(?P<number>\b\d+\.?\d*\b)"
    r"|(?P<name>\b[A-Za-z_]\w*\b)"
)


def _highlight_python_html(code: str) -> str:
    """Färbt Python-Code für die Chat-Ansicht ein (Farben aus dem Theme)."""
    out, pos = [], 0
    for m in _PY_TOKEN_RE.finditer(code):
        if m.start() > pos:
            out.append(_esc(code[pos:m.start()]))
        kind, tok = m.lastgroup, m.group()
        if kind == "comment":
            out.append(f"<span style='color:{THEME['text_dim']}'>{_esc(tok)}</span>")
        elif kind == "string":
            out.append(f"<span style='color:{THEME['success']}'>{_esc(tok)}</span>")
        elif kind == "number":
            out.append(f"<span style='color:{THEME['warning']}'>{_esc(tok)}</span>")
        elif tok in _PY_KEYWORDS:
            out.append(
                f"<span style='color:{THEME['accent_hover']}; font-weight:bold'>"
                f"{_esc(tok)}</span>"
            )
        elif tok in _PY_BUILTINS:
            out.append(f"<span style='color:{THEME['info']}'>{_esc(tok)}</span>")
        else:
            out.append(_esc(tok))
        pos = m.end()
    if pos < len(code):
        out.append(_esc(code[pos:]))
    body = "".join(out)
    return (
        f"<pre style=\"background:{THEME['bg_editor']}; color:{THEME['text']};"
        f" border:1px solid {THEME['border']}; border-radius:5px;"
        f" padding:8px; margin:6px 0;"
        f" font-family:'JetBrains Mono','Fira Code','Consolas',monospace;"
        f" font-size:11px; white-space:pre-wrap;\">{body}</pre>"
    )


def _format_response_html(text: str) -> str:
    """Wandelt eine Bot-Antwort in HTML: Prosa als Text, ```python``` als Codebox."""
    parts = re.split(r"```(?:python)?[ \t]*\n?([\s\S]*?)```", text)
    html_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            prose = part.strip("\n")
            if prose.strip():
                html_parts.append(_esc(prose).replace("\n", "<br>"))
        else:
            # Codeblock immer auf eigener Zeile beginnen lassen.
            html_parts.append("<br>" + _highlight_python_html(part.rstrip("\n")))
    return "".join(html_parts)
