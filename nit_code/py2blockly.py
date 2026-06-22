"""Wandelt Python-Quelltext in einen Blockly-Serialisierungs-State (dict) um.

Wird genutzt, um aus dem vom KI-Codegenerator erzeugten Python-Code Blöcke im
Block-Editor zu erzeugen ("Coder → Blockly"). Erkannt werden:

- Kontrollstrukturen: if/elif/else, while, for/range, for-each, break/continue
- Variablen (=, +=), Vergleiche, Arithmetik, Logik, print, sleep/sleep_ms
- Hardware-BEFEHLE werden auf die echten Blöcke abgebildet (nicht Roh-Text):
  digitale Aus-/Eingänge (Pin), ADC, DAC, PWM, NeoPixel. Dafür wird vorab eine
  kleine Symboltabelle aufgebaut (welche Variable ist welcher Pin/ADC/…), die
  Instanz-Zeilen (z. B. ``led = Pin(2, Pin.OUT)``) entfallen dann, weil die
  Operations-Blöcke sie selbst erzeugen – inklusive der nötigen Importe.

Alles übrige fällt auf einen Roh-Python-Block (``nit_raw``/``nit_raw_expr``)
zurück, der den Quelltext unverändert enthält – so bleibt das Programm immer
vollständig und ausführbar. Bewusst deterministisch (Python ``ast``).
"""
import ast

_DROP = object()   # Signal: diese Zeile bewusst weglassen (Block erzeugt sie selbst)

_BINOP = {ast.Add: "ADD", ast.Sub: "MINUS", ast.Mult: "MULTIPLY",
          ast.Div: "DIVIDE", ast.Pow: "POWER", ast.Mod: "MODULO"}
_CMP = {ast.Eq: "EQ", ast.NotEq: "NEQ", ast.Lt: "LT",
        ast.LtE: "LTE", ast.Gt: "GT", ast.GtE: "GTE"}


def python_to_block_state(code: str) -> dict:
    """Python-Quelltext → Blockly-Serialisierungs-State."""
    import json as _json
    try:
        tree = ast.parse(code)
        st = _build_symtab(tree)
        blocks = [b for b in _suite(tree.body, st) if b]
        # Bleiben Roh-ANWEISUNGEN übrig (z. B. nicht abgebildete Bibliotheks-
        # methode), so werden die Original-Importe als Blöcke vorangestellt, damit
        # der erzeugte Code lauffähig bleibt. Roh-AUSDRÜCKE (z. B. int(input()))
        # zählen NICHT – sie nutzen nur Builtins/vorhandene Variablen und brauchen
        # keine Bibliotheks-Importe. Vollständig abgebildete Programme bleiben sauber.
        if any('"nit_raw"' in _json.dumps(b) for b in blocks):
            blocks = _collect_imports(tree) + blocks
        head = _chain(blocks)
    except Exception:
        head = _raw_stmt(code or "")
    return {"blocks": {"languageVersion": 0, "blocks": [head] if head else []}}


def _collect_imports(tree):
    out = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
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
    return None


def _arg_node(call, pos, kwname):
    """Holt ein Argument positional ODER per Schlüsselwort."""
    if pos is not None and pos < len(call.args):
        return call.args[pos]
    if kwname:
        return _kw(call, kwname)
    return None


def _extract(src, call):
    tag = src[0]
    if tag == "const":
        return src[1]
    if tag == "pos":
        i, conv = src[1], src[2]
        return _conv(call.args[i], conv) if i < len(call.args) else None
    if tag == "kw":
        return _conv(_kw(call, src[1]), src[2])
    if tag == "arg":            # positional ODER Schlüsselwort: ('arg', pos, kwname, conv)
        return _conv(_arg_node(call, src[1], src[2]), src[3])
    if tag == "pin":            # Pin-Nummer aus Pin(N) an Position i
        i = src[1]
        return _pin_num(call.args[i]) if i < len(call.args) else None
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
    "stepperuln": ("stepperuln_init", [("I1", ("pos", 0, "int")), ("I2", ("pos", 1, "int")),
                                       ("I3", ("pos", 2, "int")), ("I4", ("pos", 3, "int"))]),
    "ds18b20": ("ds18b20_init", [("PIN", ("pin", 0))]),
    "dht": ("dht_init", [("PIN", ("pin", 0))]),
    "bme280": ("bme280_init", []),
    "puls": ("puls_init", [("PIN", ("kw", "adc_pin", "int"))]),
    "tcs": ("tcs_init", [("OUT", ("kw", "out", "int")), ("S2", ("kw", "s2", "int")), ("S3", ("kw", "s3", "int")),
                         ("S0", ("kw", "s0", "int")), ("S1", ("kw", "s1", "int"))]),
    "tof": ("tof_init", []),
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

# Zusätzlich erlaubte (speziell behandelte) Methoden je Bibliothek
_LIB_SPECIAL = {
    "toene": {"ton"}, "niton": {"ton"}, "bme280": {"read_all"},
    "mpu": {"read_accel", "read_gyro"}, "joy": {"daten"},
}
_NITON_NOTES = {"c", "d", "e", "f", "g", "a", "h", "c2"}
_NITON_DAUER = {"viertel", "achtel", "halbe", "ganze", "viertelpunkt", "halbepunkt", "vierteltriole"}


def _lib_allowed(kind):
    return set(_LIB_METHODS.get(kind, {})) | _LIB_SPECIAL.get(kind, set())


def _lib_init_block(kind, call):
    spec = _LIB_INIT.get(kind)
    if not spec:
        return None
    btype, fspec = spec
    fields = {}
    for fname, src in fspec:
        v = _extract(src, call)
        if v is not None:
            fields[fname] = v
    return _blk(btype, fields=fields or None)


def _apply_method(spec, call, st):
    btype, is_val, fspec, ispec = spec
    fields = {}
    for fname, src in fspec:
        v = _extract(src, call)
        if v is None:
            return None
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


def _multi_assign_block(node, st):
    """Mehrfach-Zuweisungen wie ``ax, ay, az = mpu.read_accel()`` → Mess-Block."""
    if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
        return False
    val = node.value
    if not (isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute)
            and isinstance(val.func.value, ast.Name) and val.func.value.id in st):
        return False
    kind = st[val.func.value.id]
    if not (isinstance(kind, tuple) and kind[0] == "lib"):
        return False
    k, m = kind[1], val.func.attr
    tgt = node.targets[0]
    if k == "bme280" and m == "read_all" and isinstance(tgt, ast.Tuple):
        return _blk("bme280_read")
    if k == "mpu" and m == "read_accel" and isinstance(tgt, ast.Tuple):
        return _blk("mpu_accel")
    if k == "mpu" and m == "read_gyro" and isinstance(tgt, ast.Tuple):
        return _blk("mpu_gyro")
    if k == "joy" and m == "daten" and isinstance(tgt, ast.Name):
        return _blk("joy_lesen")
    return False


def _build_symtab(tree):
    """Erkennt Hardware-/Bibliotheks-Variablen, aber nur wenn ALLE ihre
    Verwendungen abbildbar sind (sonst würde das Entfernen der Instanz-Zeile
    undefinierte Namen erzeugen)."""
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
        if kind[0] == "i2c":
            continue
        if _usages_ok(tree, parents, var, kind):
            ok[var] = kind
    # I2C-Busse nur entfernen, wenn ALLE Verwendungen in gemappte Lib-Konstruktoren gehen
    mapped_calls = {id(callnode[v]) for v in ok}
    for var, kind in cand.items():
        if kind[0] == "i2c" and _i2c_droppable(tree, parents, var, mapped_calls):
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


def _usages_ok(tree, parents, var, kind):
    k = kind[0]
    if k == "lib":
        allowed = _lib_allowed(kind[1])
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Name) and n.id == var):
                continue
            if isinstance(n.ctx, ast.Store):
                continue
            p = parents.get(n)
            if not (isinstance(p, ast.Attribute) and isinstance(parents.get(p), ast.Call)
                    and p.attr in allowed):
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
        return _lib_init_block(kind[1], value)   # Init-Block (oled_init, servo_init, …)
    # Pin/ADC/DAC/PWM und I2C-Bus: Instanz wird vom Operations-/Init-Block erzeugt
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


def _neopixel_set(target, value, st):
    """``np[i] = (r, g, b)`` → nit_neopixel_set."""
    base = target.value
    if not (isinstance(base, ast.Name) and st.get(base.id, ("",))[0] == "neopixel"):
        return None
    if not (isinstance(value, ast.Tuple) and len(value.elts) == 3
            and all(isinstance(e, ast.Constant) and isinstance(e.value, int) for e in value.elts)):
        return None
    idx = target.slice
    r, g, b = (e.value for e in value.elts)
    return _blk("nit_neopixel_set", fields={"R": r, "G": g, "B": b},
                inputs={"INDEX": _val(_expr(idx, st))})


def _expr_statement(value, st):
    if isinstance(value, ast.Call):
        # Hardware-Methode auf bekannter Variable?
        hw = _hw_call_stmt(value, st)
        if hw is _DROP:
            return None
        if hw is not None:
            return hw
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
    if k == "neopixel" and m == "fill" and len(call.args) == 1 \
            and isinstance(call.args[0], ast.Tuple) and len(call.args[0].elts) == 3 \
            and all(isinstance(e, ast.Constant) for e in call.args[0].elts):
        r, g, b = (e.value for e in call.args[0].elts)
        return _blk("nit_neopixel_fill", fields={"R": r, "G": g, "B": b})
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
        if isinstance(node, ast.BinOp):
            op = _BINOP.get(type(node.op))
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
