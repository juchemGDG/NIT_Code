"""Wandelt Python-Quelltext in einen Blockly-Serialisierungs-State (dict) um.

Wird genutzt, um aus dem vom KI-Codegenerator erzeugten Python-Code Blöcke im
Block-Editor zu erzeugen ("Coder → Blockly"). Erkannte Kernkonstrukte (Variablen,
print, if/elif/else, while, for/range, Arithmetik, Vergleiche, Logik, sleep)
werden in echte Blockly-Blöcke übersetzt. Alles Unbekannte (z. B. Bibliotheks-
aufrufe) fällt auf einen Roh-Python-Block (`nit_raw` / `nit_raw_expr`) zurück, der
den Quelltext unverändert enthält – so bleibt das Programm immer vollständig und
ausführbar.

Bewusst deterministisch (Python `ast`), KEINE zweite KI-Anfrage.
"""
import ast

_BINOP = {ast.Add: "ADD", ast.Sub: "MINUS", ast.Mult: "MULTIPLY",
          ast.Div: "DIVIDE", ast.Pow: "POWER", ast.Mod: "MODULO"}
_CMP = {ast.Eq: "EQ", ast.NotEq: "NEQ", ast.Lt: "LT",
        ast.LtE: "LTE", ast.Gt: "GT", ast.GtE: "GTE"}


def python_to_block_state(code: str) -> dict:
    """Python-Quelltext → Blockly-Serialisierungs-State."""
    try:
        tree = ast.parse(code)
        head = _chain(_suite(tree.body))
    except Exception:
        head = _raw_stmt(code or "")
    return {"blocks": {"languageVersion": 0, "blocks": [head] if head else []}}


# ── Hilfen ────────────────────────────────────────────────────────────────────
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


def _raw_stmt(text: str):
    return _blk("nit_raw", fields={"CODE": text})


def _raw_expr(node):
    return _blk("nit_raw_expr", fields={"CODE": _src(node)})


def _val(block):
    """Verpackt einen Block als Eingabe-Wert."""
    return {"block": block}


def _arith(op, a, b):
    return _blk("math_arithmetic", fields={"OP": op}, inputs={"A": _val(a), "B": _val(b)})


def _chain(blocks):
    """Verkettet eine Liste von Block-dicts über 'next' und gibt den Kopf zurück."""
    blocks = [b for b in blocks if b]
    if not blocks:
        return None
    head = cur = blocks[0]
    for b in blocks[1:]:
        cur["next"] = {"block": b}
        cur = b
    return head


def _suite(stmts):
    return [_stmt(s) for s in stmts]


# ── Anweisungen ───────────────────────────────────────────────────────────────
def _stmt(node):
    try:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Pass)):
            return None  # Importe erzeugen die Blöcke selbst wieder
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            return _blk("variables_set",
                        fields={"VAR": {"name": node.targets[0].id}},
                        inputs={"VALUE": _val(_expr(node.value))})
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            op = _BINOP.get(type(node.op))
            name = node.target.id
            if op == "MODULO":
                inner = _blk("math_modulo", inputs={
                    "DIVIDEND": _val(_blk("variables_get", fields={"VAR": {"name": name}})),
                    "DIVISOR": _val(_expr(node.value))})
            elif op:
                inner = _arith(op, _blk("variables_get", fields={"VAR": {"name": name}}),
                               _expr(node.value))
            else:
                return _raw_stmt(_src(node))
            return _blk("variables_set", fields={"VAR": {"name": name}},
                        inputs={"VALUE": _val(inner)})
        if isinstance(node, ast.If):
            return _if_block(node)
        if isinstance(node, ast.While):
            inputs = {"BOOL": _val(_expr(node.test))}
            do = _chain(_suite(node.body))
            if do:
                inputs["DO"] = _val(do)
            return _blk("controls_whileUntil", fields={"MODE": "WHILE"}, inputs=inputs)
        if isinstance(node, ast.For):
            return _for_block(node)
        if isinstance(node, ast.Break):
            return _blk("controls_flow_statements", fields={"FLOW": "BREAK"})
        if isinstance(node, ast.Continue):
            return _blk("controls_flow_statements", fields={"FLOW": "CONTINUE"})
        if isinstance(node, ast.Expr):
            return _expr_statement(node.value)
        return _raw_stmt(_src(node))
    except Exception:
        return _raw_stmt(_src(node))


def _expr_statement(value):
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and not value.keywords:
        fn, args = value.func.id, value.args
        if fn == "print":
            if len(args) == 1:
                return _blk("text_print", inputs={"TEXT": _val(_expr(args[0]))})
            if len(args) == 0:
                return _blk("text_print", inputs={"TEXT": _val(_blk("text", fields={"TEXT": ""}))})
        if fn == "sleep" and len(args) == 1:
            return _blk("nit_warte", inputs={"SEK": _val(_expr(args[0]))})
        if fn == "sleep_ms" and len(args) == 1:
            return _blk("nit_warte_ms", inputs={"MS": _val(_expr(args[0]))})
    return _raw_stmt(_src(value))


def _if_block(node):
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
        inputs["IF%d" % i] = _val(_expr(test))
        do = _chain(_suite(body))
        if do:
            inputs["DO%d" % i] = _val(do)
    if else_body:
        e = _chain(_suite(else_body))
        if e:
            inputs["ELSE"] = _val(e)
    extra = {"elseIfCount": len(clauses) - 1, "hasElse": bool(else_body)}
    return _blk("controls_if", inputs=inputs, extra_state=extra)


def _for_block(node):
    if isinstance(node.target, ast.Name) and isinstance(node.iter, ast.Call) \
            and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
        var = node.target.id
        args = node.iter.args
        do = _chain(_suite(node.body))
        if len(args) == 1 and not _name_used(var, node.body):
            inputs = {"TIMES": _val(_expr(args[0]))}
            if do:
                inputs["DO"] = _val(do)
            return _blk("controls_repeat_ext", inputs=inputs)
        if len(args) == 1:
            frm, to, by = _blk("math_number", fields={"NUM": 0}), _to_incl(args[0]), \
                _blk("math_number", fields={"NUM": 1})
        else:
            frm = _expr(args[0])
            to = _to_incl(args[1])
            by = _expr(args[2]) if len(args) >= 3 else _blk("math_number", fields={"NUM": 1})
        inputs = {"FROM": _val(frm), "TO": _val(to), "BY": _val(by)}
        if do:
            inputs["DO"] = _val(do)
        return _blk("controls_for", fields={"VAR": {"name": var}}, inputs=inputs)
    if isinstance(node.target, ast.Name):
        do = _chain(_suite(node.body))
        inputs = {"LIST": _val(_expr(node.iter))}
        if do:
            inputs["DO"] = _val(do)
        return _blk("controls_forEach", fields={"VAR": {"name": node.target.id}}, inputs=inputs)
    return _raw_stmt(_src(node))


def _to_incl(arg):
    """range-Ende (exklusiv) → controls_for TO (inklusiv)."""
    if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
        return _blk("math_number", fields={"NUM": arg.value - 1})
    return _arith("MINUS", _expr(arg), _blk("math_number", fields={"NUM": 1}))


def _name_used(var, body):
    for n in body:
        for sub in ast.walk(n):
            if isinstance(sub, ast.Name) and sub.id == var and isinstance(sub.ctx, ast.Load):
                return True
    return False


# ── Ausdrücke ─────────────────────────────────────────────────────────────────
def _expr(node):
    try:
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
                    "DIVIDEND": _val(_expr(node.left)), "DIVISOR": _val(_expr(node.right))})
            if op:
                return _arith(op, _expr(node.left), _expr(node.right))
            return _raw_expr(node)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = _CMP.get(type(node.ops[0]))
            if op:
                return _blk("logic_compare", fields={"OP": op}, inputs={
                    "A": _val(_expr(node.left)), "B": _val(_expr(node.comparators[0]))})
            return _raw_expr(node)
        if isinstance(node, ast.BoolOp):
            op = "AND" if isinstance(node.op, ast.And) else "OR"
            cur = _expr(node.values[0])
            for v in node.values[1:]:
                cur = _blk("logic_operation", fields={"OP": op},
                           inputs={"A": _val(cur), "B": _val(_expr(v))})
            return cur
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return _blk("logic_negate", inputs={"BOOL": _val(_expr(node.operand))})
            if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) \
                    and isinstance(node.operand.value, (int, float)):
                return _blk("math_number", fields={"NUM": -node.operand.value})
            return _raw_expr(node)
        return _raw_expr(node)
    except Exception:
        return _raw_expr(node)
