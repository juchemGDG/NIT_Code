"""I2C-Scan für „Fehler finden“ (Schritt 3, Fall „Meldung zur Hardware“: `i2c.scan()`).

Zeigt, welche Adressen am Bus antworten – so, wie `i2c.scan()` sie liefert (dezimal,
z. B. [119]) und dazu als Hex (0x77) –, und stellt sie neben die Adresse aus dem
eigenen Code, ohne Urteil. Den Schluss ziehen die SuS. „Als Skript einfügen“ öffnet
die Vorlage fürs Arbeitsblatt, „In Protokoll übernehmen“ trägt das Ergebnis als Fakt
bei „Eingrenzen“ ein.
"""
import re
import subprocess

from PyQt6.QtCore import QSettings, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QTextEdit, QVBoxLayout,
)

from .config import THEME, tool_command
from .error_hints import detect_busy, lesetabelle

SCAN_TIMEOUT = 12   # Sekunden – ohne Pull-ups kann der Bus hängen


def scan_script(bus: int, sda: int, scl: int) -> str:
    """Die Vorlage für das Arbeitsblatt (identisch mit dem, was der Dialog ausführt)."""
    return (
        "from machine import I2C, Pin\n"
        f"i2c = I2C({bus}, sda=Pin({sda}), scl=Pin({scl}))\n"
        "geraete = i2c.scan()\n"
        'print("i2c.scan() liefert:", geraete)\n'
        'print("als Hex:", [hex(a) for a in geraete])\n'
    )


def _chip_script(bus: int, sda: int, scl: int, addr: int) -> str:
    return (
        "from machine import I2C, Pin\n"
        f"i2c = I2C({bus}, sda=Pin({sda}), scl=Pin({scl}))\n"
        f'print("Chip-ID:", hex(i2c.readfrom_mem({addr}, 0xD0, 1)[0]))\n'
    )


def pins_from_code(code: str) -> tuple[int | None, int | None, int | None]:
    """(Bus, SDA, SCL) aus einer I2C(...)-Zeile im Code – soweit vorhanden."""
    code = code or ""
    sda = re.search(r"sda\s*=\s*Pin\s*\(\s*(\d+)", code)
    scl = re.search(r"scl\s*=\s*Pin\s*\(\s*(\d+)", code)
    bus = re.search(r"I2C\s*\(\s*(\d+)\s*,", code)
    return (int(bus.group(1)) if bus else None,
            int(sda.group(1)) if sda else None,
            int(scl.group(1)) if scl else None)


def addresses_from_code(code: str) -> list[str]:
    """I2C-taugliche Hex-Adressen (0x08–0x77) im Code, in Reihenfolge, ohne Doppelte."""
    seen: list[str] = []
    for m in re.finditer(r"\b0[xX]([0-9a-fA-F]{2})\b", code or ""):
        val = int(m.group(1), 16)
        txt = f"0x{val:02x}"
        if 0x08 <= val <= 0x77 and txt not in seen:
            seen.append(txt)
    return seen


def parse_addresses(output: str) -> list[str] | None:
    """Adressen (als Hex-Text) aus der Skriptausgabe oder None, wenn die Zeile fehlt."""
    m = re.search(r"i2c\.scan\(\) liefert:\s*\[(.*?)\]", output or "")
    if not m:
        return None
    return [f"0x{int(a):02x}" for a in re.findall(r"\d+", m.group(1))]


def fact_text(found: list[str]) -> str:
    """Kurzer Fakt fürs Protokoll, z. B. „i2c.scan() → [119] = 0x77“."""
    if not found:
        return "i2c.scan() → [] (kein Gerät antwortet)"
    dec = ", ".join(str(int(a, 16)) for a in found)
    return f"i2c.scan() → [{dec}] = {', '.join(found)}"


def describe_address(addr: str) -> str:
    return lesetabelle().get("adressen", {}).get(addr.lower(), "")


class _MpremoteWorker(QThread):
    done = pyqtSignal(int, str, str)   # (rc, stdout, stderr); rc -1 = Zeitüberschreitung

    def __init__(self, port: str, code: str):
        super().__init__()
        self._cmd = [*tool_command("mpremote"), "connect", port, "exec", code]

    def run(self):
        try:
            r = subprocess.run(self._cmd, capture_output=True, timeout=SCAN_TIMEOUT)
            self.done.emit(r.returncode, r.stdout.decode("utf-8", "replace"),
                           r.stderr.decode("utf-8", "replace"))
        except subprocess.TimeoutExpired:
            self.done.emit(-1, "", "")
        except OSError as exc:
            self.done.emit(1, "", str(exc))


class I2CScanDialog(QDialog):
    """Dialog „I2C-Scan“. ``acquire``/``release`` reservieren den seriellen Port."""

    insert_script = pyqtSignal(str)
    result_text = pyqtSignal(str)      # Zusammenfassung für die Konsole
    fact_text = pyqtSignal(str)        # Fakt fürs Fehlerprotokoll (Eingrenzen)

    def __init__(self, parent, port: str, code: str, acquire, release):
        super().__init__(parent)
        self.setWindowTitle("🔍  I2C-Scan")
        self.setMinimumWidth(480)
        self._port, self._code = port, code
        self._acquire, self._release = acquire, release
        self._worker: _MpremoteWorker | None = None
        self._found: list[str] = []
        self._settings = QSettings()

        lay = QVBoxLayout(self)
        intro = QLabel("Welche Geräte antworten am I2C-Bus? Der Scan ist ein Test im "
                       "Zyklus: Er zeigt, was am Bus ist – den Schluss ziehst du.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        bus_c, sda_c, scl_c = pins_from_code(code)
        form = QFormLayout()
        self._bus = self._spin(0, 1, bus_c, "debug/i2c_bus", 0)
        self._sda = self._spin(0, 48, sda_c, "debug/i2c_sda", 21)
        self._scl = self._spin(0, 48, scl_c, "debug/i2c_scl", 22)
        form.addRow("Bus:", self._bus)
        form.addRow("SDA-Pin:", self._sda)
        form.addRow("SCL-Pin:", self._scl)
        lay.addLayout(form)
        src = QLabel("Pins aus deinem Code übernommen." if (sda_c is not None or scl_c is not None)
                     else "Keine I2C-Zeile im Code gefunden – Pins bitte prüfen.")
        src.setStyleSheet(f"color:{THEME['text_dim']}; font-size:11px;")
        lay.addWidget(src)

        self._out = QTextEdit()
        self._out.setReadOnly(True)
        self._out.setMinimumHeight(150)
        lay.addWidget(self._out, 1)

        row = QHBoxLayout()
        self._btn_scan = QPushButton("🔍  Scannen")
        self._btn_chip = QPushButton("Chip-ID lesen")
        self._btn_chip.setToolTip("Liest Register 0xD0: 0x60 = BME280, 0x58 = BMP280")
        self._btn_chip.setEnabled(False)
        self._btn_fact = QPushButton("📝  In Protokoll übernehmen")
        self._btn_fact.setToolTip("Trägt das Scan-Ergebnis bei „Eingrenzen“ der offenen Runde ein")
        self._btn_fact.setEnabled(False)
        btn_insert = QPushButton("Als Skript einfügen")
        btn_insert.setToolTip("Öffnet die Scan-Vorlage vom Arbeitsblatt in einem neuen Tab")
        btn_close = QPushButton("Schließen")
        for b in (self._btn_scan, self._btn_chip, self._btn_fact, btn_insert):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(btn_close)
        lay.addLayout(row)

        self._btn_scan.clicked.connect(self._scan)
        self._btn_chip.clicked.connect(self._read_chip)
        self._btn_fact.clicked.connect(lambda: self.fact_text.emit(fact_text(self._found)))
        self._scanned = False
        btn_insert.clicked.connect(lambda: self.insert_script.emit(
            scan_script(self._bus.value(), self._sda.value(), self._scl.value())))
        btn_close.clicked.connect(self.reject)

    def _spin(self, lo, hi, from_code, key, default) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        if from_code is not None:
            s.setValue(from_code)
        else:
            try:
                s.setValue(int(self._settings.value(key, default)))
            except (TypeError, ValueError):
                s.setValue(default)
        s.setFixedWidth(80)
        return s

    # ── Ausführung ───────────────────────────────────────────────────────
    def _run(self, code: str, handler):
        if self._worker is not None or not self._acquire():
            return
        self._btn_scan.setEnabled(False)
        self._btn_chip.setEnabled(False)
        self._worker = _MpremoteWorker(self._port, code)
        self._worker.done.connect(handler)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self):
        self._worker = None
        self._release()
        self._btn_scan.setEnabled(True)
        self._btn_chip.setEnabled(any(a in ("0x76", "0x77") for a in self._found))
        self._btn_fact.setEnabled(self._scanned)

    def _log(self, html: str):
        self._out.append(html)

    def _scan(self):
        bus, sda, scl = self._bus.value(), self._sda.value(), self._scl.value()
        for key, val in (("debug/i2c_bus", bus), ("debug/i2c_sda", sda), ("debug/i2c_scl", scl)):
            self._settings.setValue(key, val)
        self._log(f"<b>🔍 I2C-Scan an SDA={sda}, SCL={scl} …</b>")
        self._run(scan_script(bus, sda, scl), self._on_scan_done)

    def _on_scan_done(self, rc: int, out: str, err: str):
        sda, scl = self._sda.value(), self._scl.value()
        lines = [f"🔍 I2C-Scan an SDA={sda}, SCL={scl}"]
        if rc == -1:
            lines.append("   Der Scan hat nicht rechtzeitig geantwortet – das ist selbst ein "
                         "Befund (Bus blockiert?). Startet der Controller neu: Schritt 0.")
        else:
            found = parse_addresses(out)
            if found is None:
                text = (err or out)
                last = text.strip().splitlines()[-1:] or ["keine Antwort vom Controller"]
                lines.append(f"   Scan nicht möglich: {last[0]}")
                if detect_busy(text):
                    lines.append("   Schritt 1 · Läuft schon was? Dann läuft ein altes Programm "
                                 "(main.py): Stopp-Knopf oder Strg+C in der Konsole; hilft das "
                                 "nicht, Reset-Taster am Board und sofort Strg+C.")
            else:
                self._found = found
                self._scanned = True
                dec = ", ".join(str(int(a, 16)) for a in found)
                lines.append(f"   i2c.scan() liefert: [{dec}]")
                if not found:
                    lines.append("   Kein Gerät antwortet. Verdächtige: Versorgung (3V3, GND), "
                                 "SDA/SCL-Leitung, Pins im Scan.")
                for a in found:
                    name = describe_address(a)
                    lines.append(f"   {int(a, 16)} = {a}" + (f"   (bekannt als: {name})" if name else ""))
        in_code = addresses_from_code(self._code)
        if in_code:
            lines.append("   In deinem Code steht die Adresse: "
                         + ", ".join(f"{a} (= {int(a, 16)})" for a in in_code))
        else:
            lines.append("   In deinem Code steht keine Adresse (die Bibliothek nimmt dann "
                         "ihre Standardadresse).")
        text = "\n".join(lines)
        self._log(f"<pre>{_esc(text)}</pre>")
        self.result_text.emit(text + "\n")

    def _read_chip(self):
        addr = next((a for a in self._found if a in ("0x76", "0x77")), None)
        if not addr:
            return
        self._log(f"<b>Chip-ID an {addr} …</b>")
        code = _chip_script(self._bus.value(), self._sda.value(), self._scl.value(), int(addr, 16))
        self._run(code, lambda rc, out, err: self._on_chip_done(addr, rc, out, err))

    def _on_chip_done(self, addr: str, rc: int, out: str, err: str):
        m = re.search(r"Chip-ID:\s*(0x[0-9a-fA-F]+)", out or "")
        if m:
            cid = f"0x{int(m.group(1), 16):02x}"
            name = lesetabelle().get("chip_ids", {}).get(cid, "unbekannter Chip")
            text = f"   Chip-ID an {addr}: {cid}   (bekannt als: {name})"
        elif rc == -1:
            text = "   Chip-ID: keine Antwort (Zeitüberschreitung)."
        else:
            last = (err or out).strip().splitlines()[-1:] or ["keine Antwort"]
            text = f"   Chip-ID nicht lesbar: {last[0]}"
        self._log(f"<pre>{_esc(text)}</pre>")
        self.result_text.emit(text + "\n")

    def reject(self):
        if self._worker is not None:
            return   # Scan läuft noch – Port erst nach Ende freigeben
        super().reject()


def _esc(text: str) -> str:
    import html
    return html.escape(text)
