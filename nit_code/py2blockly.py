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
        # Bleiben Roh-Blöcke übrig (z. B. nicht abgebildete Bibliothek), so
        # werden die Original-Importe als Blöcke vorangestellt, damit der
        # erzeugte Code lauffähig bleibt. Bei vollständig abgebildeten
        # Programmen (alle Befehle als echte Blöcke) bleibt die Ansicht sauber –
        # die echten Blöcke fügen ihre Importe selbst hinzu.
        if any("nit_raw" in _json.dumps(b) for b in blocks):
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
    return None


def _lit_bit(node):
    """Liefert '1'/'0' für literal 1/0/True/False, sonst None."""
    if isinstance(node, ast.Constant):
        if node.value in (1, True):
            return "1"
        if node.value in (0, False):
            return "0"
    return None


def _build_symtab(tree):
    """Erkennt Hardware-Variablen, aber nur wenn ALLE ihre Verwendungen abbildbar
    sind (sonst würde das Entfernen der Instanz-Zeile undefinierte Namen erzeugen)."""
    cand = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            kind = _classify(n.value)
            if kind:
                cand[n.targets[0].id] = kind
    if not cand:
        return {}
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    ok = {}
    for var, kind in cand.items():
        if _usages_ok(tree, parents, var, kind):
            ok[var] = kind
    return ok


def _usages_ok(tree, parents, var, kind):
    k = kind[0]
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
            if isinstance(tgt, ast.Name):
                hw = _hw_assign(tgt.id, node.value, st)
                if hw is not False:
                    return hw  # Block (NeoPixel-Init) oder None (Instanz entfällt)
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
    return None  # Pin/ADC/DAC/PWM: Instanz wird vom Operations-Block erzeugt


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


def _hw_call_expr(node, st):
    """Hardware-Lesebefehl (Ausdruck) → echter Block, sonst None."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id in st):
        return None
    kind = st[node.func.value.id]
    k, m = kind[0], node.func.attr
    if k == "pin_in" and m == "value" and not node.args:
        fields = {"PIN": kind[1], "PULL": kind[2] or "none"}
        return _blk("nit_pin_read", fields=fields)
    if k == "adc" and m == "read" and not node.args:
        return _blk("nit_adc_read", fields={"PIN": kind[1]})
    return None
