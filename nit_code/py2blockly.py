"""Wandelt Python-Quelltext in einen Blockly-Serialisierungs-State (dict) um.

Wird genutzt, um aus dem vom KI-Codegenerator erzeugten Python-Code Blöcke im
Block-Editor zu erzeugen ("Coder → Blockly"). Erkannt werden:

- Kontrollstrukturen: if/elif/else, while, for/range, for-each, break/continue
- Funktionen: ``def`` → echte Funktions-Blöcke (procedures_def*) mit Parametern
  und Rückgabe; Aufrufe eigener Funktionen → procedures_call*
- Typumwandlung int()/float()/str() → nit_cast
- Variablen (=, +=), Vergleiche, Arithmetik, Logik, print,
  sleep/sleep_ms (auch ``time.sleep``/``time.sleep_ms``)
- Hardware-BEFEHLE werden auf die echten Blöcke abgebildet (nicht Roh-Text):
  digitale Aus-/Eingänge (Pin, inkl. ``.on()``/``.off()``), ADC, DAC, PWM,
  NeoPixel. Dafür wird vorab eine kleine Symboltabelle aufgebaut (welche
  Variable ist welcher Pin/ADC/…), die Instanz-Zeilen (z. B.
  ``led = Pin(2, Pin.OUT)``) entfallen dann, weil die Operations-Blöcke sie
  selbst erzeugen – inklusive der nötigen Importe.
- Bibliotheks-Variablen mit dem KANONISCHEN Instanznamen der Blöcke (z. B.
  ``oled``, ``servo``, ``np`` – siehe nitbw_blocks.js) dürfen auch TEILWEISE
  abgebildet werden: bekannte Methoden werden Blöcke, unbekannte bleiben
  Roh-Zeilen und verweisen auf dieselbe Instanz, die der Init-Block erzeugt.
  Bei anderen Variablennamen gilt weiterhin alles-oder-nichts, damit nie
  ein Roh-Aufruf auf eine entfernte Instanz zeigt.

Alles übrige fällt auf einen Roh-Python-Block (``nit_raw``/``nit_raw_expr``)
zurück, der den Quelltext unverändert enthält – so bleibt das Programm immer
vollständig und ausführbar. Original-Importe werden nur übernommen, wenn ein
Roh-Block einen der importierten Namen wirklich benutzt (die Blöcke erzeugen
ihre Importe selbst). Bewusst deterministisch (Python ``ast``).
"""
import ast
import re

_DROP = object()      # Signal: diese Zeile bewusst weglassen (Block erzeugt sie selbst)
_MISSING = object()   # Signal: Argument nicht angegeben → Block-Standardwert verwenden

_BINOP = {ast.Add: "ADD", ast.Sub: "MINUS", ast.Mult: "MULTIPLY",
          ast.Div: "DIVIDE", ast.Pow: "POWER", ast.Mod: "MODULO"}
_CMP = {ast.Eq: "EQ", ast.NotEq: "NEQ", ast.Lt: "LT",
        ast.LtE: "LTE", ast.Gt: "GT", ast.GtE: "GTE"}


def python_to_block_state(code: str) -> dict:
    """Python-Quelltext → Blockly-Serialisierungs-State."""
    try:
        tree = ast.parse(code)
        st = _build_symtab(tree)
        if not isinstance(st, dict):
            st = {}
        # Hilfsdaten unter Nicht-Identifier-Schlüsseln (kollidieren nie mit
        # ``name in st``-Prüfungen, die immer gültige Python-Namen verwenden):
        #   " funcs" – eigene Funktionen für die Aufruf-Abbildung
        #   " vars"  – Parameter-Variablen (Name → id) für das variables-Array
        st[" funcs"], st[" vars"] = {}, {}
        for n in tree.body:
            if isinstance(n, ast.FunctionDef):
                info = _analyze_func(n)
                if info is not None:
                    st[" funcs"][n.name] = {"params": info[0], "returns": info[2] is not None}

        # Funktions-Definitionen werden zu eigenständigen Top-Level-Blöcken
        # (procedures_def* haben keine vorherige/nächste Verbindung), der Rest
        # bleibt eine verbundene Anweisungs-Kette (Hauptprogramm).
        func_blocks, main_nodes = [], []
        for n in tree.body:
            if isinstance(n, ast.FunctionDef):
                fb = _func_def_block(n, st)
                if fb is not None:
                    func_blocks.append(fb)
                    continue   # abbildbar → eigener Block; sonst unten als Roh-Anweisung
            main_nodes.append(n)
        main_blocks = [b for b in _suite(main_nodes, st) if b]

        # Original-Importe nur übernehmen, wenn ein Roh-Block einen der
        # importierten Namen wirklich benutzt (z. B. ``oled.fill(0)`` braucht
        # keinen Import mehr – den erzeugt der oled_init-Block selbst; eine
        # rohe ``math.sqrt``-Zeile braucht dagegen ``import math``).
        # Vollständig abgebildete Programme bleiben sauber.
        main_blocks = _needed_imports(tree, func_blocks + main_blocks) + main_blocks
        chain = _chain(main_blocks)

        tops = list(func_blocks)
        if chain:
            tops.append(chain)
        # Mehrere Top-Level-Blöcke positionieren: Funktionen untereinander, das
        # Hauptprogramm darunter. Streng wachsendes y sichert die Code-Reihenfolge
        # (Definitionen vor dem Hauptprogramm), da Blockly nach Position erzeugt.
        if len(tops) > 1:
            for i, fb in enumerate(func_blocks):
                fb["x"], fb["y"] = 20, 20 + i * 260
            if chain:
                chain["x"], chain["y"] = 20, 20 + len(func_blocks) * 260
        state = {"blocks": {"languageVersion": 0, "blocks": tops}}
        if st[" vars"]:
            state["variables"] = [{"name": n, "id": i} for n, i in st[" vars"].items()]
        return state
    except Exception:
        head = _raw_stmt(code or "")
        return {"blocks": {"languageVersion": 0, "blocks": [head]}}


def _raw_code_tokens(blocks) -> set:
    """Alle Bezeichner, die in Roh-Blöcken (nit_raw/nit_raw_expr) vorkommen."""
    tokens: set = set()

    def walk(b):
        if isinstance(b, dict):
            if b.get("type") in ("nit_raw", "nit_raw_expr"):
                code = b.get("fields", {}).get("CODE", "")
                tokens.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", code))
            for v in b.values():
                walk(v)
        elif isinstance(b, list):
            for v in b:
                walk(v)

    walk(blocks)
    return tokens


def _needed_imports(tree, blocks):
    """Original-Importe, deren gebundene Namen in Roh-Blöcken benutzt werden.

    Die abgebildeten Blöcke erzeugen ihre Importe selbst (from machine import
    Pin, from time import sleep, from nitbw_… import …); hier kommen nur die
    Importe zurück, die verbleibender Roh-Code tatsächlich noch braucht."""
    tokens = _raw_code_tokens(blocks)
    if not tokens:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            bound = [a.asname or a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            bound = [a.asname or a.name for a in node.names]
        else:
            continue
        if any(n == "*" or n in tokens for n in bound):
            out.append(_raw_stmt(_src(node)))
    return out


# ── Block-Bau-Hilfen ──────────────────────────────────────────────────────────
def _blk(type_, fields=None, inputs=None, extra_state=None):
    d = {"type": type_}
    if fields:
        d["fields"] = fields
    if inputs:
        d["inputs"] = inputs
    if extra_state is not None:
        d["extraState"] = extra_state
    return d


def _src(node) -> str:
    try:
        return ast.unparse(node).strip()
    except Exception:
        return ""


def _raw_stmt(text):
    return _blk("nit_raw", fields={"CODE": text if isinstance(text, str) else _src(text)})


def _raw_expr(node):
    return _blk("nit_raw_expr", fields={"CODE": _src(node)})


def _val(block):
    return {"block": block}


def _arith(op, a, b):
    return _blk("math_arithmetic", fields={"OP": op}, inputs={"A": _val(a), "B": _val(b)})


def _is_stringish(node) -> bool:
    """Ausdruck, dessen Block-Output sicher "String" ist (Text-Literal/f-String)
    und damit nicht in einen Number-Eingang passt."""
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)) \
        or isinstance(node, ast.JoinedStr)


def _text_join2(a, b):
    """Zwei Teile zu einem 'verbinde'-Block (text_join) zusammensetzen."""
    return _blk("text_join", extra_state={"itemCount": 2},
                inputs={"ADD0": _val(a), "ADD1": _val(b)})


def _chain(blocks):
    blocks = [b for b in blocks if b]
    if not blocks:
        return None
    head = cur = blocks[0]
    for b in blocks[1:]:
        cur["next"] = {"block": b}
        cur = b
    return head


def _suite(stmts, st):
    return [_stmt(s, st) for s in stmts]


# ── Hardware-Erkennung (Symboltabelle) ────────────────────────────────────────
def _attr_name(node) -> str:
    """ast.Attribute(Name('Pin'),'OUT') -> 'Pin.OUT'."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return ""


def _pin_num(node):
    """Pin-Nummer aus ``Pin(N, ...)`` (oder blankem Int)."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Pin" \
            and node.args and isinstance(node.args[0], ast.Constant) \
            and isinstance(node.args[0].value, int):
        return node.args[0].value
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


def _classify(value):
    """RHS einer Zuweisung → Hardware-Art (Tuple) oder None."""
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
        return None
    fn = value.func.id
    if fn == "Pin" and len(value.args) >= 2 and isinstance(value.args[0], ast.Constant):
        n = value.args[0].value
        mode = _attr_name(value.args[1])
        if mode == "Pin.OUT":
            return ("pin_out", n)
        if mode == "Pin.IN":
            pull = None
            if len(value.args) >= 3:
                pm = _attr_name(value.args[2])
                pull = "up" if pm == "Pin.PULL_UP" else "down" if pm == "Pin.PULL_DOWN" else None
            return ("pin_in", n, pull)
    if fn in ("ADC", "DAC") and value.args:
        p = _pin_num(value.args[0])
        if p is not None:
            return (fn.lower(), p)
    if fn == "PWM" and value.args:
        p = _pin_num(value.args[0])
        freq = next((kw.value.value for kw in value.keywords
                     if kw.arg == "freq" and isinstance(kw.value, ast.Constant)), 1000)
        if p is not None:
            return ("pwm", p, freq)
    if fn == "NeoPixel" and len(value.args) >= 2:
        p = _pin_num(value.args[0])
        num = value.args[1].value if isinstance(value.args[1], ast.Constant) else None
        if p is not None and num is not None:
            return ("neopixel", p, num)
    if fn == "I2C":
        return ("i2c",)
    if fn == "UART":
        tx = _pin_num(next((kw.value for kw in value.keywords if kw.arg == "tx"), None))
        rx = _pin_num(next((kw.value for kw in value.keywords if kw.arg == "rx"), None))
        return ("uart", tx, rx)
    if fn in _LIB_KIND:
        return ("lib", _LIB_KIND[fn])
    return None


def _lit_bit(node):
    """Liefert '1'/'0' für literal 1/0/True/False, sonst None."""
    if isinstance(node, ast.Constant):
        if node.value in (1, True):
            return "1"
        if node.value in (0, False):
            return "0"
    return None


# ── nitbw-Bibliotheken: Registry für das Rück-Mapping ─────────────────────────
_LIB_KIND = {
    "OLED": "oled", "LCD": "lcd", "TOENE": "toene", "NITon": "niton",
    "Ultraschall": "us", "Servo": "servo", "StepperDir": "stepperdir",
    "StepperULN": "stepperuln", "DS18B20": "ds18b20", "DHT22": "dht",
    "BME280": "bme280", "Pulssensor": "puls", "TCS3200": "tcs", "TOF": "tof",
    "KY023": "joy", "RTC": "rtc", "Compass": "compass", "AS7262": "as7262",
    "MPU6050": "mpu", "ESPNow": "espnow", "MQTTClient": "mqtt", "MLearn": "mlearn",
    "MP3TF16P": "mp3",
}

# Benannte Equalizer-Konstanten der MP3-Bibliothek → Dropdown-Wert des Blocks
_MP3_EQ = {
    "MP3TF16P.EQ_NORMAL": "0", "MP3TF16P.EQ_POP": "1", "MP3TF16P.EQ_ROCK": "2",
    "MP3TF16P.EQ_JAZZ": "3", "MP3TF16P.EQ_CLASSIC": "4", "MP3TF16P.EQ_BASS": "5",
}


def _kw(call, name):
    return next((k.value for k in call.keywords if k.arg == name), None)


def _conv(node, conv):
    if node is None:
        return None
    if conv == "int":
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, int) else None
    if conv == "str":
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None
    if conv == "bstr":
        if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
            return node.value.decode("utf-8", "replace")
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None
    if conv == "raw":
        return _src(node)
    if conv == "richt":
        s = _src(node)
        return s if s in ("VOR", "ZURUECK") else None
    if conv == "bool":
        s = _src(node)
        return s if s in ("True", "False") else None
    if conv == "eq":
        s = _src(node)
        if s in _MP3_EQ:
            return _MP3_EQ[s]
        return s if s in ("0", "1", "2", "3", "4", "5") else None
    return None


def _arg_node(call, pos, kwname):
    """Holt ein Argument positional ODER per Schlüsselwort."""
    if pos is not None and pos < len(call.args):
        return call.args[pos]
    if kwname:
        return _kw(call, kwname)
    return None


def _extract(src, call):
    """Feld-Wert aus dem Aufruf holen.

    Rückgabe: Wert, ``_MISSING`` (Argument nicht angegeben → Feld weglassen,
    der Block nutzt seinen Standardwert) oder ``None`` (Argument vorhanden,
    aber nicht als Feld darstellbar → Aufruf bleibt Roh-Code)."""
    tag = src[0]
    if tag == "const":
        return src[1]
    if tag == "pos":
        i, conv = src[1], src[2]
        return _conv(call.args[i], conv) if i < len(call.args) else _MISSING
    if tag == "kw":
        node = _kw(call, src[1])
        return _conv(node, src[2]) if node is not None else _MISSING
    if tag == "arg":            # positional ODER Schlüsselwort: ('arg', pos, kwname, conv)
        node = _arg_node(call, src[1], src[2])
        return _conv(node, src[3]) if node is not None else _MISSING
    if tag == "pin":            # Pin-Nummer aus Pin(N) an Position i
        i = src[1]
        return _pin_num(call.args[i]) if i < len(call.args) else _MISSING
    return None


# Init: kind -> (block_type, [(field, source)])
_LIB_INIT = {
    "oled": ("oled_init", [("CHIP", ("kw", "chip", "str"))]),
    "lcd": ("lcd_init", [("ADDR", ("kw", "addr", "raw"))]),
    "toene": ("toene_init", [("PIN", ("pin", 0)), ("GESCHW", ("kw", "geschwindigkeit", "int"))]),
    "niton": ("niton_init", [("PIN", ("pos", 0, "int")), ("GESCHW", ("kw", "geschwindigkeit", "int")),
                             ("LEGATO", ("kw", "legato", "int"))]),
    "us": ("us_init", [("TRIG", ("kw", "trigger", "int")), ("ECHO", ("kw", "echo", "int"))]),
    "servo": ("servo_init", [("PIN", ("kw", "pin", "int"))]),
    "stepperdir": ("stepperdir_init", [("STEP", ("kw", "step_pin", "int")),
                                       ("DIR", ("kw", "dir_pin", "int")), ("EN", ("kw", "enable_pin", "int"))]),
    "stepperuln": ("stepperuln_init", [("I1", ("arg", 0, "in1", "int")), ("I2", ("arg", 1, "in2", "int")),
                                       ("I3", ("arg", 2, "in3", "int")), ("I4", ("arg", 3, "in4", "int"))]),
    "ds18b20": ("ds18b20_init", [("PIN", ("pin", 0))]),
    "dht": ("dht_init", [("PIN", ("pin", 0))]),
    "bme280": ("bme280_init", []),
    "puls": ("puls_init", [("PIN", ("kw", "adc_pin", "int"))]),
    "tcs": ("tcs_init", [("OUT", ("kw", "out", "int")), ("S2", ("kw", "s2", "int")), ("S3", ("kw", "s3", "int")),
                         ("S0", ("kw", "s0", "int")), ("S1", ("kw", "s1", "int"))]),
    "tof": ("tof_init", [("TYP", ("kw", "sensor_typ", "str"))]),
    "joy": ("joy_init", [("VRX", ("kw", "vrx_pin", "int")), ("VRY", ("kw", "vry_pin", "int")),
                         ("SW", ("kw", "sw_pin", "int"))]),
    "rtc": ("rtc_init", [("CHIP", ("kw", "chip", "str"))]),
    "compass": ("compass_init", []),
    "as7262": ("as7262_init", []),
    "mpu": ("mpu_init", []),
    "espnow": ("espnow_init", []),
    "mqtt": ("mqtt_init", [("SERVER", ("kw", "server", "str")), ("ID", ("kw", "client_id", "bstr"))]),
    "mlearn": ("mlearn_init", [("K", ("kw", "k", "int"))]),
}

# Methoden: kind -> { methode: (block_type, is_value, [(field, source)], [(input, pos_idx)]) }
_LIB_METHODS = {
    "oled": {
        "clear": ("oled_clear", False, [], []),
        "show": ("oled_show", False, [], []),
        "print": ("oled_print", False, [("X", ("arg", 1, "x", "int")), ("Y", ("arg", 2, "y", "int"))],
                  [("TEXT", 0, "string")]),
        "line": ("oled_line", False, [("X1", ("pos", 0, "int")), ("Y1", ("pos", 1, "int")),
                                      ("X2", ("pos", 2, "int")), ("Y2", ("pos", 3, "int"))], []),
        "draw_rect": ("oled_rect", False, [("X", ("pos", 0, "int")), ("Y", ("pos", 1, "int")),
                                           ("W", ("pos", 2, "int")), ("H", ("pos", 3, "int"))], []),
        "draw_circle": ("oled_circle", False, [("X", ("pos", 0, "int")), ("Y", ("pos", 1, "int")),
                                               ("R", ("pos", 2, "int"))], []),
        "show_svg": ("oled_svg", False, [("DATEI", ("pos", 0, "str"))], []),
        "show_bmp": ("oled_bmp", False, [("DATEI", ("pos", 0, "str"))], []),
    },
    "lcd": {
        "print": ("lcd_print", False, [("SP", ("arg", 1, "spalte", "int")), ("ZE", ("arg", 2, "zeile", "int"))],
                  [("TEXT", 0, "text")]),
        "clear": ("lcd_clear", False, [], []),
    },
    "toene": {"stop": ("toene_stop", False, [], [])},
    "niton": {"setGeschw": ("niton_tempo", False, [("BPM", ("pos", 0, "int"))], [])},
    "us": {"messen_cm": ("us_cm", True, [], []), "messen_mm": ("us_mm", True, [], [])},
    "servo": {
        "winkel": ("servo_winkel", False, [], [("GRAD", 0)]),
        "mitte": ("servo_mitte", False, [], []),
        "lese_winkel": ("servo_lese", True, [], []),
        "aus": ("servo_aus", False, [], []),
    },
    "stepperdir": {
        "schritte": ("stepperdir_schritte", False, [("RICHT", ("pos", 1, "richt"))], [("N", 0)]),
        "winkel": ("stepperdir_winkel", False, [("RICHT", ("pos", 1, "richt"))], [("GRAD", 0)]),
        "aus": ("stepperdir_aus", False, [], []),
    },
    "stepperuln": {
        "umdrehungen": ("stepperuln_umdr", False, [("RICHT", ("pos", 1, "richt"))], [("N", 0)]),
    },
    "ds18b20": {"messen": ("ds18b20_messen", True, [], [])},
    "dht": {"measure": ("dht_measure", False, [], []), "temperature": ("dht_temp", True, [], []),
            "humidity": ("dht_hum", True, [], [])},
    "puls": {"lesen_roh_mittelwert": ("puls_lesen", True, [], [])},
    "tcs": {"dominante_farbe": ("tcs_farbe", True, [], [])},
    "tof": {"messen_mm": ("tof_mm", True, [], []), "messen_cm": ("tof_cm", True, [], [])},
    "rtc": {"toString": ("rtc_string", True, [("FORMAT", ("pos", 0, "str"))], [])},
    "compass": {"read_heading": ("compass_heading", True, [], [])},
    "as7262": {"messen_roh": ("as7262_messen", True, [], [])},
    "mpu": {
        "calibrate_gyro": ("mpu_calibrate", False, [], []),
        "read_temperature": ("mpu_temp", True, [], []),
        "read_pitch": ("mpu_pitch", True, [], []),
        "read_roll": ("mpu_roll", True, [], []),
        "read_tilt_angle": ("mpu_tilt", True, [], []),
        "is_level": ("mpu_level", True, [], []),
        "read_orientation_text": ("mpu_orient", True, [], []),
    },
    "espnow": {
        "add_peer": ("espnow_peer", False, [("MAC", ("pos", 0, "str"))], []),
        "send": ("espnow_send", False, [("MAC", ("pos", 0, "str"))], [("MSG", 1)]),
    },
    "mqtt": {
        "connect": ("mqtt_connect", False, [], []),
        "check_msg": ("mqtt_check", False, [], []),
        "publish": ("mqtt_publish", False, [("TOPIC", ("pos", 0, "bstr"))], [("WERT", 1)]),
    },
    "mp3": {
        "set_volume": ("mp3_volume", False, [("VOL", ("pos", 0, "int"))], []),
        "volume_up": ("mp3_lauter", False, [], []),
        "volume_down": ("mp3_leiser", False, [], []),
        "play_mp3": ("mp3_play", False, [("NR", ("pos", 0, "int"))], []),
        "play_folder": ("mp3_play_folder", False, [("ORDNER", ("arg", 0, "folder", "int")),
                                                   ("NR", ("arg", 1, "track", "int"))], []),
        "pause": ("mp3_pause", False, [], []),
        "resume": ("mp3_weiter", False, [], []),
        "stop": ("mp3_stop", False, [], []),
        "next": ("mp3_next", False, [], []),
        "previous": ("mp3_prev", False, [], []),
        "set_eq": ("mp3_eq", False, [("MODE", ("pos", 0, "eq"))], []),
        "repeat_current": ("mp3_repeat", False, [("EIN", ("pos", 0, "bool"))], []),
        "loop_all": ("mp3_loop_all", False, [("EIN", ("pos", 0, "bool"))], []),
        "random_all": ("mp3_random", False, [], []),
    },
    "mlearn": {
        "load_csv": ("mlearn_load", False, [("DATEI", ("pos", 0, "str")), ("TARGET", ("kw", "target", "int"))], []),
        "add_sample": ("mlearn_add", False, [], [("FEATURES", 0), ("LABEL", 1)]),
        "clear_data": ("mlearn_clear", False, [], []),
        "split_data": ("mlearn_split", False, [("ANTEIL", ("pos", 0, "raw")), ("SEED", ("pos", 1, "int"))], []),
        "train_knn": ("mlearn_train_knn", False, [], []),
        "predict_knn": ("mlearn_predict_knn", True, [], [("FEATURES", 0)]),
        "train_tree": ("mlearn_train_tree", False, [("DEPTH", ("kw", "max_depth", "int"))], []),
        "predict_tree": ("mlearn_predict_tree", True, [], [("FEATURES", 0)]),
        "train_forest": ("mlearn_train_forest", False, [("NTREES", ("kw", "n_trees", "int")),
                                                        ("DEPTH", ("kw", "max_depth", "int"))], []),
        "predict_forest": ("mlearn_predict_forest", True, [], [("FEATURES", 0)]),
        "train_logreg": ("mlearn_train_logreg", False, [], []),
        "predict_logreg": ("mlearn_predict_logreg", True, [], [("FEATURES", 0)]),
        "train_netz": ("mlearn_train_netz", False, [("HIDDEN", ("kw", "hidden", "int")),
                                                    ("EPOCHS", ("kw", "epochs", "int"))], []),
        "predict_netz": ("mlearn_predict_netz", True, [], [("FEATURES", 0)]),
        "save_model": ("mlearn_save", False, [("DATEI", ("pos", 0, "str")), ("TYP", ("kw", "model_type", "str"))], []),
        "load_model": ("mlearn_load_model", False, [("DATEI", ("pos", 0, "str"))], []),
    },
}

_NITON_NOTES = {"c", "d", "e", "f", "g", "a", "h", "c2"}
_NITON_DAUER = {"viertel", "achtel", "halbe", "ganze", "viertelpunkt", "halbepunkt", "vierteltriole"}

# Kanonische Instanznamen, die die *_init-Blöcke erzeugen (siehe
# nitbw_blocks.js bzw. nit_blocks.js). Heißt die Variable im Quelltext
# genauso, dürfen unbekannte Methoden als Roh-Zeilen stehen bleiben – sie
# verweisen dann auf genau die Instanz, die der Init-Block anlegt.
_LIB_INST = {
    "oled": "oled", "lcd": "lcd", "toene": "speaker", "niton": "niton",
    "mp3": "mp3", "us": "ultraschall", "servo": "servo",
    "stepperdir": "motor", "stepperuln": "motor", "ds18b20": "ds18b20",
    "dht": "dht", "bme280": "bme280", "puls": "puls", "tcs": "farbsensor",
    "tof": "tof", "joy": "joystick", "rtc": "rtc", "compass": "kompass",
    "as7262": "spektral", "mpu": "mpu", "espnow": "espnow",
    "mqtt": "mqtt_client", "mlearn": "model",
}

# Mehrfach-Zuweisungs-Methoden: Die Mess-Blöcke erzeugen FESTE Zielnamen
# (z. B. ``ax, ay, az = mpu.read_accel()``); die Lese-Blöcke (mpu_ax, …)
# greifen auf genau diese Namen zu. Andere Zielnamen → Roh-Zeile.
_MULTI_TARGETS = {
    ("bme280", "read_all"): ("temperatur", "druck", "feuchtigkeit"),
    ("mpu", "read_accel"): ("ax", "ay", "az"),
    ("mpu", "read_gyro"): ("gx", "gy", "gz"),
    ("joy", "daten"): "d",
}


def _canonical_name(kind) -> str:
    if kind[0] == "lib":
        return _LIB_INST.get(kind[1], "")
    if kind[0] == "neopixel":
        return "np"
    return ""


def _lib_init_block(kind, call, st=None):
    if kind == "mp3":
        # Konstruktor bekommt nur das UART-Objekt – die Pins stehen in dessen
        # Zuweisung, die in der Symboltabelle als ("uart", tx, rx) vermerkt ist.
        fields = {}
        arg = call.args[0] if call.args else None
        if isinstance(arg, ast.Name) and st:
            u = st.get(arg.id)
            if u and u[0] == "uart":
                if u[1] is not None:
                    fields["TX"] = u[1]
                if u[2] is not None:
                    fields["RX"] = u[2]
        return _blk("mp3_init", fields=fields or None)
    spec = _LIB_INIT.get(kind)
    if not spec:
        return None
    btype, fspec = spec
    fields = {}
    for fname, src in fspec:
        v = _extract(src, call)
        if v is not None and v is not _MISSING:
            fields[fname] = v
    return _blk(btype, fields=fields or None)


def _apply_method(spec, call, st):
    btype, is_val, fspec, ispec = spec
    fields = {}
    for fname, src in fspec:
        v = _extract(src, call)
        if v is _MISSING:
            continue        # Argument weggelassen → Block-Standardwert
        if v is None:
            return None     # Argument nicht darstellbar → Roh-Code
        fields[fname] = v
    inputs = {}
    for spec_in in ispec:
        iname, pos = spec_in[0], spec_in[1]
        kwname = spec_in[2] if len(spec_in) > 2 else None
        node = _arg_node(call, pos, kwname)
        if node is None:
            return None
        inputs[iname] = _val(_expr(node, st))
    return _blk(btype, fields=fields or None, inputs=inputs or None)


def _lib_method_stmt(kind, method, call, st):
    """Bibliotheks-Methode als Anweisung → Block oder None."""
    if kind == "toene" and method == "ton":
        return _toene_ton(call)
    if kind == "niton" and method == "ton":
        return _niton_ton(call)
    if kind == "mp3" and method == "set_source":
        return _DROP   # gehört zur Instanz-Einrichtung, erzeugt der mp3_init-Block
    spec = _LIB_METHODS.get(kind, {}).get(method)
    if spec and spec[1] is False:
        return _apply_method(spec, call, st)
    return None


def _lib_method_expr(kind, method, call, st):
    """Bibliotheks-Methode als Ausdruck (Wert) → Block oder None."""
    spec = _LIB_METHODS.get(kind, {}).get(method)
    if spec and spec[1] is True:
        return _apply_method(spec, call, st)
    return None


def _toene_ton(call):
    if not (call.args and isinstance(call.args[0], ast.Tuple) and len(call.args[0].elts) == 2):
        return None
    note, dauer = call.args[0].elts
    if not (isinstance(note, ast.Constant) and isinstance(note.value, str)):
        return None
    d = _src(dauer).replace(" ", "")
    return _blk("toene_ton", fields={"NOTE": note.value, "DAUER": d})


def _niton_ton(call):
    if len(call.args) != 2:
        return None
    a0, a1 = call.args
    dauer = _src(a1)
    if dauer not in _NITON_DAUER:
        return None
    if isinstance(a0, ast.Constant) and a0.value == 0:
        return _blk("niton_pause", fields={"DAUER": dauer})
    note = _src(a0)
    if note not in _NITON_NOTES:
        return None
    return _blk("niton_ton", fields={"NOTE": note, "DAUER": dauer})


def _multi_targets_match(tgt, expected) -> bool:
    """Zuweisungsziel(e) gegen die festen Namen des Mess-Blocks prüfen."""
    if isinstance(expected, tuple):
        return (isinstance(tgt, ast.Tuple) and len(tgt.elts) == len(expected)
                and all(isinstance(e, ast.Name) and e.id == x
                        for e, x in zip(tgt.elts, expected)))
    return isinstance(tgt, ast.Name) and tgt.id == expected


_MULTI_BLOCK = {
    ("bme280", "read_all"): "bme280_read",
    ("mpu", "read_accel"): "mpu_accel",
    ("mpu", "read_gyro"): "mpu_gyro",
    ("joy", "daten"): "joy_lesen",
}


def _multi_assign_block(node, st):
    """Mehrfach-Zuweisungen wie ``ax, ay, az = mpu.read_accel()`` → Mess-Block.

    Nur mit den kanonischen Zielnamen (siehe _MULTI_TARGETS) – die erzeugen
    die Blöcke fest, und die zugehörigen Lese-Blöcke greifen darauf zu."""
    if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
        return False
    val = node.value
    if not (isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute)
            and isinstance(val.func.value, ast.Name) and val.func.value.id in st):
        return False
    kind = st[val.func.value.id]
    if not (isinstance(kind, tuple) and kind[0] == "lib"):
        return False
    key = (kind[1], val.func.attr)
    btype = _MULTI_BLOCK.get(key)
    if btype and _multi_targets_match(node.targets[0], _MULTI_TARGETS[key]):
        return _blk(btype)
    return False


def _build_symtab(tree):
    """Erkennt Hardware-/Bibliotheks-Variablen.

    Regel: Eine Variable wird abgebildet, wenn ALLE ihre Verwendungen
    abbildbar sind (sonst würde das Entfernen der Instanz-Zeile undefinierte
    Namen erzeugen) – ODER wenn sie den kanonischen Instanznamen der Blöcke
    trägt (dann erzeugt der Init-Block genau diese Instanz und unbekannte
    Methoden dürfen als Roh-Zeilen darauf verweisen)."""
    cand, callnode = {}, {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            kind = _classify(n.value)
            if kind:
                cand[n.targets[0].id] = kind
                callnode[n.targets[0].id] = n.value
    if not cand:
        return {}
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    ok = {}
    for var, kind in cand.items():
        if kind[0] in ("i2c", "uart"):
            continue
        if _usages_ok(tree, parents, var, kind):
            ok[var] = kind
        elif kind[0] in ("lib", "neopixel") and var == _canonical_name(kind):
            # Teil-Abbildung: nur bei lib/neopixel sicher, weil dort der
            # Init-Block die Instanz IMMER erzeugt (bei Pin/ADC/PWM entsteht
            # sie erst durch einen abgebildeten Operations-Block).
            ok[var] = kind
    # I2C-/UART-Busse nur entfernen, wenn ALLE Verwendungen in gemappte Lib-Konstruktoren gehen
    mapped_calls = {id(callnode[v]) for v in ok}
    for var, kind in cand.items():
        if kind[0] in ("i2c", "uart") and _i2c_droppable(tree, parents, var, mapped_calls):
            ok[var] = kind
    return ok


def _i2c_droppable(tree, parents, var, mapped_calls):
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Name) and n.id == var and isinstance(n.ctx, ast.Load)):
            continue
        p = parents.get(n)
        if isinstance(p, ast.keyword):
            p = parents.get(p)
        if not (isinstance(p, ast.Call) and id(p) in mapped_calls):
            return False
    return True


def _lib_usage_ok(kind, method, call, parents):
    """Prüft eine einzelne Bibliotheks-Verwendung auf echte Abbildbarkeit.

    Statt nur den Methodennamen zu kennen, muss der Aufruf im richtigen
    Kontext (Anweisung/Ausdruck) tatsächlich in einen Block konvertierbar
    sein – sonst entstünde eine Roh-Zeile, deren Instanz entfernt wurde."""
    key = (kind, method)
    if key in _MULTI_TARGETS:
        assign = parents.get(call)
        return (isinstance(assign, ast.Assign) and len(assign.targets) == 1
                and _multi_targets_match(assign.targets[0], _MULTI_TARGETS[key]))
    if isinstance(parents.get(call), ast.Expr):     # Aufruf als Anweisung
        b = _lib_method_stmt(kind, method, call, {})
        return b is _DROP or b is not None
    return _lib_method_expr(kind, method, call, {}) is not None


def _usages_ok(tree, parents, var, kind):
    k = kind[0]
    if k == "lib":
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Name) and n.id == var):
                continue
            if isinstance(n.ctx, ast.Store):
                continue
            p = parents.get(n)
            call = parents.get(p) if isinstance(p, ast.Attribute) else None
            if not (isinstance(call, ast.Call) and call.func is p):
                return False
            if not _lib_usage_ok(kind[1], p.attr, call, parents):
                return False
        return True
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Name) and n.id == var):
            continue
        if isinstance(n.ctx, ast.Store):
            continue                      # Zuweisungsziel – ok
        p = parents.get(n)
        # NeoPixel: np[i] (Subscript) oder np.write()/np.fill()
        if k == "neopixel":
            if isinstance(p, ast.Subscript):
                continue
            if isinstance(p, ast.Attribute) and p.attr in ("write", "fill"):
                continue
            return False
        # Pin/ADC/DAC/PWM: nur Methodenaufruf var.<methode>(...)
        if not (isinstance(p, ast.Attribute) and isinstance(parents.get(p), ast.Call)):
            return False
        call = parents.get(p)
        m = p.attr
        if k == "pin_out":
            if m == "value" and len(call.args) == 1 and _lit_bit(call.args[0]) is not None:
                continue
            if m in ("on", "off") and not call.args:
                continue
        elif k == "pin_in":
            if m == "value" and not call.args:
                continue
        elif k == "adc":
            if m in ("read", "width", "atten"):
                continue
        elif k == "dac":
            if m == "write" and len(call.args) == 1:
                continue
        elif k == "pwm":
            if m == "duty" and len(call.args) == 1:
                continue
        return False
    return True


# ── Funktionen (def → procedures_def*) ────────────────────────────────────────
def _func_returns(node):
    """Alle ``return`` im Funktionsrumpf – ohne in verschachtelte Funktionen/
    Lambdas zu steigen (deren returns gehören nicht zu dieser Funktion)."""
    out = []

    def walk(n):
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Return):
                out.append(child)
            walk(child)

    walk(node)
    return out


def _analyze_func(node):
    """``def`` analysieren. Liefert (params, rumpf_stmts, return_ausdruck|None)
    oder None, wenn Signatur/Rückgabe-Stil nicht sauber als Block darstellbar ist.

    Bewusst konservativ: nur einfache Positionsparameter (keine Defaults, *args,
    **kwargs, keyword-only). Eine Rückgabe wird nur als abschließendes
    ``return wert`` akzeptiert – frühe/mehrfache returns blieben als Block
    mehrdeutig und fallen auf den Roh-Block zurück (weiterhin lauffähig)."""
    a = node.args
    if (a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg
            or a.defaults or a.kw_defaults):
        return None
    params = [arg.arg for arg in a.args]
    body = list(node.body)
    returns = _func_returns(node)
    if not returns:
        return (params, body, None)
    if len(returns) == 1 and body and body[-1] is returns[0]:
        ret = returns[0]
        if ret.value is None:
            return (params, body[:-1], None)      # nacktes ``return`` → ohne Rückgabe
        return (params, body[:-1], ret.value)
    return None                                    # frühe/mehrfache returns → Roh-Block


def _func_def_block(node, st):
    """``def`` → procedures_defnoreturn/-defreturn; None wenn nicht abbildbar."""
    info = _analyze_func(node)
    if info is None:
        return None
    params, body, ret = info
    param_state = []
    for p in params:
        vid = st[" vars"].setdefault(p, "pid_" + p)   # deterministische id je Name
        param_state.append({"name": p, "id": vid})
    inputs = {}
    stack = _chain([b for b in _suite(body, st) if b])
    if stack:
        inputs["STACK"] = _val(stack)
    extra = {"params": param_state} if param_state else None
    if ret is not None:
        inputs["RETURN"] = _val(_expr(ret, st))
        return _blk("procedures_defreturn", fields={"NAME": node.name},
                    inputs=inputs or None, extra_state=extra)
    return _blk("procedures_defnoreturn", fields={"NAME": node.name},
                inputs=inputs or None, extra_state=extra)


def _call_block(call, st, statement):
    """Aufruf einer eigenen Funktion → procedures_call*; None wenn nicht passend.

    Im Anweisungskontext nur void-Funktionen (callnoreturn ist ein
    Anweisungsblock), im Ausdruckskontext nur Funktionen mit Rückgabe
    (callreturn ist ein Wertblock)."""
    if not (isinstance(call.func, ast.Name) and not call.keywords
            and not any(isinstance(a, ast.Starred) for a in call.args)):
        return None
    info = st.get(" funcs", {}).get(call.func.id)
    if info is None or len(call.args) != len(info["params"]):
        return None
    if statement == info["returns"]:
        return None   # void als Ausdruck / Rückgabe als blosse Anweisung: nicht darstellbar
    inputs = {"ARG%d" % i: _val(_expr(a, st)) for i, a in enumerate(call.args)}
    extra = {"name": call.func.id, "params": list(info["params"])}
    typ = "procedures_callnoreturn" if statement else "procedures_callreturn"
    return _blk(typ, inputs=inputs or None, extra_state=extra)


def _cast_block(call, st):
    """``int(x)``/``float(x)``/``str(x)`` → nit_cast; None sonst."""
    if (isinstance(call.func, ast.Name) and call.func.id in ("int", "float", "str")
            and len(call.args) == 1 and not call.keywords):
        return _blk("nit_cast", fields={"TYPE": call.func.id},
                    inputs={"VALUE": _val(_expr(call.args[0], st))})
    return None


# ── Anweisungen ───────────────────────────────────────────────────────────────
def _stmt(node, st):
    try:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Pass)):
            return None  # Importe erzeugen die Blöcke selbst wieder
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            # Mehrfach-Rückgabe (bme280.read_all(), mpu.read_accel(), joystick.daten())
            multi = _multi_assign_block(node, st)
            if multi is not False:
                return multi
            if isinstance(tgt, ast.Name):
                hw = _hw_assign(tgt.id, node.value, st)
                if hw is not False:
                    return hw  # Block (Init) oder None (Instanz entfällt)
                return _blk("variables_set", fields={"VAR": {"name": tgt.id}},
                            inputs={"VALUE": _val(_expr(node.value, st))})
            if isinstance(tgt, ast.Subscript):
                np_set = _neopixel_set(tgt, node.value, st)
                if np_set is not None:
                    return np_set
            return _raw_stmt(node)
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            return _augassign(node, st)
        if isinstance(node, ast.If):
            return _if_block(node, st)
        if isinstance(node, ast.While):
            inputs = {"BOOL": _val(_expr(node.test, st))}
            do = _chain(_suite(node.body, st))
            if do:
                inputs["DO"] = _val(do)
            return _blk("controls_whileUntil", fields={"MODE": "WHILE"}, inputs=inputs)
        if isinstance(node, ast.For):
            return _for_block(node, st)
        if isinstance(node, ast.Break):
            return _blk("controls_flow_statements", fields={"FLOW": "BREAK"})
        if isinstance(node, ast.Continue):
            return _blk("controls_flow_statements", fields={"FLOW": "CONTINUE"})
        if isinstance(node, ast.Expr):
            return _expr_statement(node.value, st)
        return _raw_stmt(node)
    except Exception:
        return _raw_stmt(node)


def _hw_assign(var, value, st):
    """Behandelt eine Hardware-Instanz-Zuweisung.

    Rückgabe: Block (für NeoPixel-Init), None (Instanz entfällt) oder
    ``False`` (keine Hardware-Zuweisung → normal als Variable behandeln).
    """
    if var not in st:
        return False
    kind = st[var]
    if kind[0] == "neopixel":
        return _blk("nit_neopixel_init",
                    fields={"PIN": kind[1], "NUM": kind[2]})
    if kind[0] == "lib":
        return _lib_init_block(kind[1], value, st)   # Init-Block (oled_init, servo_init, …)
    # Pin/ADC/DAC/PWM und I2C-/UART-Bus: Instanz wird vom Operations-/Init-Block erzeugt
    return None


def _augassign(node, st):
    op = _BINOP.get(type(node.op))
    name = node.target.id
    getv = _blk("variables_get", fields={"VAR": {"name": name}})
    if op == "MODULO":
        inner = _blk("math_modulo", inputs={"DIVIDEND": _val(getv),
                                            "DIVISOR": _val(_expr(node.value, st))})
    elif op:
        inner = _arith(op, getv, _expr(node.value, st))
    else:
        return _raw_stmt(node)
    return _blk("variables_set", fields={"VAR": {"name": name}}, inputs={"VALUE": _val(inner)})


def _color_block(value, st):
    """Farbe als Block: RGB-Literal ``(r, g, b)`` → kompakter nit_color_rgb-Block,
    sonst der generische Ausdruck (eigenes Tupel, Variable, …)."""
    if isinstance(value, ast.Tuple) and len(value.elts) == 3 \
            and all(isinstance(e, ast.Constant) and isinstance(e.value, int) for e in value.elts):
        r, g, b = (e.value for e in value.elts)
        return _blk("nit_color_rgb", fields={"R": r, "G": g, "B": b})
    return _expr(value, st)


def _neopixel_set(target, value, st):
    """``np[i] = farbe`` → nit_neopixel_set (Farbe als (R, G, B)-Tupel)."""
    base = target.value
    if not (isinstance(base, ast.Name) and st.get(base.id, ("",))[0] == "neopixel"):
        return None
    return _blk("nit_neopixel_set",
                inputs={"INDEX": _val(_expr(target.slice, st)),
                        "COLOR": _val(_color_block(value, st))})


def _expr_statement(value, st):
    if isinstance(value, ast.Call):
        # Hardware-Methode auf bekannter Variable?
        hw = _hw_call_stmt(value, st)
        if hw is _DROP:
            return None
        if hw is not None:
            return hw
        # time.sleep(x)/time.sleep_ms(x) – wie das nackte sleep()/sleep_ms()
        f = value.func
        if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                and f.value.id in ("time", "utime") and f.value.id not in st
                and len(value.args) == 1 and not value.keywords):
            if f.attr == "sleep":
                return _blk("nit_warte", inputs={"SEK": _val(_expr(value.args[0], st))})
            if f.attr == "sleep_ms":
                return _blk("nit_warte_ms", inputs={"MS": _val(_expr(value.args[0], st))})
        if isinstance(value.func, ast.Name) and not value.keywords:
            fn, args = value.func.id, value.args
            if fn == "print" and len(args) == 1:
                return _blk("text_print", inputs={"TEXT": _val(_expr(args[0], st))})
            if fn == "print" and not args:
                return _blk("text_print", inputs={"TEXT": _val(_blk("text", fields={"TEXT": ""}))})
            if fn == "sleep" and len(args) == 1:
                return _blk("nit_warte", inputs={"SEK": _val(_expr(args[0], st))})
            if fn == "sleep_ms" and len(args) == 1:
                return _blk("nit_warte_ms", inputs={"MS": _val(_expr(args[0], st))})
        cb = _call_block(value, st, statement=True)
        if cb is not None:
            return cb
    return _raw_stmt(value)


def _hw_call_stmt(call, st):
    """Hardware-Befehl (Anweisung) → echter Block, sonst None."""
    f = call.func
    if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in st):
        return None
    kind = st[f.value.id]
    if kind[0] == "lib":
        return _lib_method_stmt(kind[1], f.attr, call, st)
    k, m = kind[0], f.attr
    if k == "pin_out" and m == "value" and len(call.args) == 1:
        bit = _lit_bit(call.args[0])
        if bit is not None:
            return _blk("nit_pin_write", fields={"PIN": kind[1], "VAL": bit})
    if k == "pin_out" and m in ("on", "off") and not call.args:
        return _blk("nit_pin_write",
                    fields={"PIN": kind[1], "VAL": "1" if m == "on" else "0"})
    if k == "dac" and m == "write" and len(call.args) == 1:
        return _blk("nit_dac_write", fields={"PIN": kind[1]},
                    inputs={"WERT": _val(_expr(call.args[0], st))})
    if k == "pwm" and m == "duty" and len(call.args) == 1:
        return _blk("nit_pwm_write", fields={"PIN": kind[1], "FREQ": kind[2]},
                    inputs={"DUTY": _val(_expr(call.args[0], st))})
    if k == "adc" and m in ("width", "atten"):
        return _DROP  # ADC-Konfig erzeugt der ADC-Block selbst – stillschweigend weglassen
    if k == "neopixel" and m == "write" and not call.args:
        return _blk("nit_neopixel_show")
    if k == "neopixel" and m == "fill" and len(call.args) == 1:
        return _blk("nit_neopixel_fill",
                    inputs={"COLOR": _val(_color_block(call.args[0], st))})
    return None


def _if_block(node, st):
    clauses, else_body, cur = [], None, node
    while True:
        clauses.append((cur.test, cur.body))
        orelse = cur.orelse
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            cur = orelse[0]
            continue
        else_body = orelse or None
        break
    inputs = {}
    for i, (test, body) in enumerate(clauses):
        inputs["IF%d" % i] = _val(_expr(test, st))
        do = _chain(_suite(body, st))
        if do:
            inputs["DO%d" % i] = _val(do)
    if else_body:
        e = _chain(_suite(else_body, st))
        if e:
            inputs["ELSE"] = _val(e)
    extra = {"elseIfCount": len(clauses) - 1, "hasElse": bool(else_body)}
    return _blk("controls_if", inputs=inputs, extra_state=extra)


def _for_block(node, st):
    if isinstance(node.target, ast.Name) and isinstance(node.iter, ast.Call) \
            and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
        var = node.target.id
        args = node.iter.args
        do = _chain(_suite(node.body, st))
        if len(args) == 1 and not _name_used(var, node.body):
            inputs = {"TIMES": _val(_expr(args[0], st))}
            if do:
                inputs["DO"] = _val(do)
            return _blk("controls_repeat_ext", inputs=inputs)
        if len(args) == 1:
            frm, to, by = _blk("math_number", fields={"NUM": 0}), _to_incl(args[0], st), \
                _blk("math_number", fields={"NUM": 1})
        else:
            frm = _expr(args[0], st)
            to = _to_incl(args[1], st)
            by = _expr(args[2], st) if len(args) >= 3 else _blk("math_number", fields={"NUM": 1})
        inputs = {"FROM": _val(frm), "TO": _val(to), "BY": _val(by)}
        if do:
            inputs["DO"] = _val(do)
        return _blk("controls_for", fields={"VAR": {"name": var}}, inputs=inputs)
    if isinstance(node.target, ast.Name):
        do = _chain(_suite(node.body, st))
        inputs = {"LIST": _val(_expr(node.iter, st))}
        if do:
            inputs["DO"] = _val(do)
        return _blk("controls_forEach", fields={"VAR": {"name": node.target.id}}, inputs=inputs)
    return _raw_stmt(node)


def _to_incl(arg, st):
    if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
        return _blk("math_number", fields={"NUM": arg.value - 1})
    return _arith("MINUS", _expr(arg, st), _blk("math_number", fields={"NUM": 1}))


def _name_used(var, body):
    for n in body:
        for sub in ast.walk(n):
            if isinstance(sub, ast.Name) and sub.id == var and isinstance(sub.ctx, ast.Load):
                return True
    return False


# ── Ausdrücke ─────────────────────────────────────────────────────────────────
def _expr(node, st):
    try:
        hw = _hw_call_expr(node, st)
        if hw is not None:
            return hw
        if isinstance(node, ast.Call):
            cast = _cast_block(node, st)
            if cast is not None:
                return cast
            cb = _call_block(node, st, statement=False)
            if cb is not None:
                return cb
            return _raw_expr(node)
        if isinstance(node, ast.Constant):
            v = node.value
            if isinstance(v, bool):
                return _blk("logic_boolean", fields={"BOOL": "TRUE" if v else "FALSE"})
            if isinstance(v, (int, float)):
                return _blk("math_number", fields={"NUM": v})
            if isinstance(v, str):
                return _blk("text", fields={"TEXT": v})
            return _raw_expr(node)
        if isinstance(node, ast.Name):
            return _blk("variables_get", fields={"VAR": {"name": node.id}})
        if isinstance(node, ast.JoinedStr):
            return _joinedstr(node, st)
        if isinstance(node, ast.Tuple):
            return _tuple_block(node, st)
        if isinstance(node, ast.Dict):
            return _dict_block(node, st)
        if isinstance(node, ast.BinOp):
            op = _BINOP.get(type(node.op))
            # math_arithmetic/math_modulo haben Number-typisierte Eingänge. Ein
            # String-Literal (Output "String") würde die Verbindung beim Laden
            # sprengen und damit das GANZE Programm verschlucken. Darum String-
            # Verkettung ("a" + x) als "verbinde"-Block, anderes (z. B. "ab" * 3,
            # "%d" % x) als Roh-Ausdruck.
            stringish = _is_stringish(node.left) or _is_stringish(node.right)
            if op == "ADD" and stringish:
                return _text_join2(_expr(node.left, st), _expr(node.right, st))
            if stringish:
                return _raw_expr(node)
            if op == "MODULO":
                return _blk("math_modulo", inputs={
                    "DIVIDEND": _val(_expr(node.left, st)), "DIVISOR": _val(_expr(node.right, st))})
            if op:
                return _arith(op, _expr(node.left, st), _expr(node.right, st))
            return _raw_expr(node)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = _CMP.get(type(node.ops[0]))
            if op:
                return _blk("logic_compare", fields={"OP": op}, inputs={
                    "A": _val(_expr(node.left, st)), "B": _val(_expr(node.comparators[0], st))})
            return _raw_expr(node)
        if isinstance(node, ast.BoolOp):
            op = "AND" if isinstance(node.op, ast.And) else "OR"
            cur = _expr(node.values[0], st)
            for v in node.values[1:]:
                cur = _blk("logic_operation", fields={"OP": op},
                           inputs={"A": _val(cur), "B": _val(_expr(v, st))})
            return cur
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return _blk("logic_negate", inputs={"BOOL": _val(_expr(node.operand, st))})
            if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) \
                    and isinstance(node.operand.value, (int, float)):
                return _blk("math_number", fields={"NUM": -node.operand.value})
            return _raw_expr(node)
        return _raw_expr(node)
    except Exception:
        return _raw_expr(node)


def _joinedstr(node, st):
    """f-String ``f'Text {x}'`` → 'verbinde'-Block (text_join)."""
    parts = []
    for v in node.values:
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            parts.append(_blk("text", fields={"TEXT": v.value}))
        elif isinstance(v, ast.FormattedValue):
            parts.append(_expr(v.value, st))
        else:
            parts.append(_raw_expr(v))
    if not parts:
        return _blk("text", fields={"TEXT": ""})
    if len(parts) == 1:
        return parts[0]
    inputs = {"ADD%d" % i: _val(p) for i, p in enumerate(parts)}
    return _blk("text_join", extra_state={"itemCount": len(parts)}, inputs=inputs)


def _tuple_block(node, st):
    """``(a, b, c)`` → nit_tuple_create (variadisch, itemCount)."""
    elts = node.elts
    inputs = {"ADD%d" % i: _val(_expr(e, st)) for i, e in enumerate(elts)}
    return _blk("nit_tuple_create", inputs=inputs or None,
                extra_state={"itemCount": len(elts)})


def _dict_block(node, st):
    """``{k: v, …}`` → nit_dict_create (variadisch, itemCount)."""
    if any(k is None for k in node.keys):     # {**andere} – nicht abbildbar
        return _raw_expr(node)
    inputs = {}
    for i, (k, v) in enumerate(zip(node.keys, node.values)):
        inputs["KEY%d" % i] = _val(_expr(k, st))
        inputs["VALUE%d" % i] = _val(_expr(v, st))
    return _blk("nit_dict_create", inputs=inputs or None,
                extra_state={"itemCount": len(node.keys)})


def _hw_call_expr(node, st):
    """Hardware-Lesebefehl (Ausdruck) → echter Block, sonst None."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id in st):
        return None
    kind = st[node.func.value.id]
    if kind[0] == "lib":
        return _lib_method_expr(kind[1], node.func.attr, node, st)
    k, m = kind[0], node.func.attr
    if k == "pin_in" and m == "value" and not node.args:
        fields = {"PIN": kind[1], "PULL": kind[2] or "none"}
        return _blk("nit_pin_read", fields=fields)
    if k == "adc" and m == "read" and not node.args:
        return _blk("nit_adc_read", fields={"PIN": kind[1]})
    return None
