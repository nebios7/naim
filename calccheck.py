#!/usr/bin/env python3
"""Checks the arithmetic written in an answer: every « a op b … = c » (+ − × ÷ :, whole numbers or decimals with a
comma) is computed again, and a division's remainder too (« 854 ÷ 7 = 121 reste 4 »). A small model makes mental
calculation mistakes; this finds them before the user reads them, and says the right result.

  check(text) → [« 854 ÷ 7 = 121, reste 4 » est faux : 854 ÷ 7 = 122, reste 0, …]
"""
import re
from fractions import Fraction

NUM = r"\d{1,3}(?:[   ]\d{3})+(?:,\d+)?|\d+(?:,\d+)?"
OP = r"[+×÷*/:−-]|\bx\b"
EXPR = re.compile(
    rf"(?<![\w,.$\\^_{{(])((?:(?:{NUM})\s*(?:{OP})\s*)+(?:{NUM}))(?![\w,]|\s*[(\[^])\s*=\s*({NUM})(?![\w,.]\d|\w)"
    rf"((?:\s*(?:,|et|avec)?\s*(?:un\s+|le\s+)?reste\s*(?:de\s*|est\s*|=\s*|:\s*)?)({NUM}))?", re.I)


def _num(s):
    return Fraction(re.sub(r"[   ]", "", s).replace(",", "."))


def _fmt(f):
    if f.denominator == 1:
        return f"{f.numerator:,}".replace(",", " ")
    return f"{float(f):.4f}".rstrip("0").replace(".", ",")


def _eval(expr):
    toks = re.findall(rf"{NUM}|{OP}", expr, re.I)
    vals, ops = [], []
    for t in toks:
        if re.fullmatch(NUM, t):
            vals.append(_num(t))
        else:
            ops.append({"×": "*", "x": "*", "X": "*", "*": "*", "÷": "/", ":": "/", "/": "/", "−": "-", "-": "-", "+": "+"}[t])
    if len(vals) != len(ops) + 1:
        return None
    # × and ÷ first, then + and −
    v, o = [vals[0]], []
    for op, b in zip(ops, vals[1:]):
        if op in "*/":
            if op == "/" and b == 0:
                return None
            v[-1] = v[-1] * b if op == "*" else v[-1] / b
        else:
            v.append(b)
            o.append(op)
    r = v[0]
    for op, b in zip(o, v[1:]):
        r = r + b if op == "+" else r - b
    return r, vals, ops


GRAPH_RE = re.compile(r"```(?:graphe|graph|courbe|fonction)[ \t]*\n([\s\S]*?)```", re.I)
_MATH = {"sqrt": __import__("math").sqrt, "sin": __import__("math").sin, "cos": __import__("math").cos,
         "tan": __import__("math").tan, "exp": __import__("math").exp, "ln": __import__("math").log,
         "log": __import__("math").log10, "abs": abs, "pi": __import__("math").pi, "e": __import__("math").e}


def _fn(expr):
    """y = f(x) as written in a graph block (3/4x - 5, 2x^2+1, sqrt(x)), as a Python function; None when unreadable."""
    import ast
    t = expr.strip().replace("^", "**").replace("×", "*").replace("−", "-").replace("÷", "/").replace("π", "pi")
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    t = re.sub(r"(\d|\))\s*(?=[a-zA-Z(])", r"\1*", t)          # 3x, 2(x+1), )( and )x
    t = re.sub(r"\bx\s*(?=[\d(])", "x*", t)
    try:
        tree = ast.parse(t, mode="eval")
    except SyntaxError:
        return None
    ok = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.Call, ast.Add, ast.Sub, ast.Mult,
          ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Mod)
    if any(not isinstance(n, ok) or (isinstance(n, ast.Name) and n.id != "x" and n.id not in _MATH) for n in ast.walk(tree)):
        return None
    code = compile(tree, "f", "eval")
    return lambda x: eval(code, {"__builtins__": {}}, dict(_MATH, x=x))  # noqa: S307 — only x, numbers and math names


def graph_points(text):
    """In a graph block with one curve y = f(x), each named point A(a;b) said to be on it is checked: f(a) must be b.
    « B(7;0) » on y = 3/4x - 5 is off the line (f(7) = 0,25): the point the model meant is (20/3 ; 0)."""
    out = []
    for blk in GRAPH_RE.finditer(str(text or "")):
        lines = [l.strip() for l in blk.group(1).splitlines() if l.strip()]
        curves = [m.group(1) for l in lines if (m := re.match(r"^(?:[a-zA-Z]\w*\s*\(\s*x\s*\)|y)\s*=\s*(.+)$", l))]
        if len(curves) != 1 or not (f := _fn(curves[0])):
            continue
        for l in lines:
            m = re.match(r"^([A-Z]\w?['’]?)\s*\(\s*([^;|)]+?)\s*[;|]\s*([^)]+?)\s*\)$", l)
            if not m:
                continue
            fx, fy = _fn(m.group(2)), _fn(m.group(3))
            try:
                a, b = fx(0), fy(0)
                v = f(a)
            except Exception:  # noqa: BLE001 — outside the domain (sqrt of a negative…): not checked
                continue
            if abs(v - b) > 0.01 * max(1, abs(v)):
                out.append(f"le point {m.group(1)}({m.group(2)} ; {m.group(3)}) du graphe n'est pas sur la courbe y = {curves[0]} : "
                           f"pour x = {_fmt(Fraction(a).limit_denominator(1000))}, y = {_fmt(Fraction(v).limit_denominator(1000))}. "
                           "Donne les coordonnées exactes du point que tu veux montrer (une fraction s'écrit 20/3) ; "
                           "si ce point est volontairement hors de la courbe, dis-le dans le texte")
    return out


def check(text):
    out = graph_points(text)
    plain = re.sub(r"```[\s\S]*?```", " ", str(text or ""))  # blocks the application computes itself are not read
    plain = re.sub(r"\$[^$\n]*\$", lambda m: m.group(0) if re.fullmatch(r"\$[\d\s+×÷:*/=,−-]+\$", m.group(0)) else " ", plain)
    for m in EXPR.finditer(plain):
        expr, claim, rest = m.group(1), _num(m.group(2)), m.group(4)
        if re.search(r"\d+\s*:\s*\d+\s*:", expr) or re.fullmatch(r"\s*\d{1,2}\s*:\s*\d{2}\s*", expr):  # an hour 10:30
            continue
        e = _eval(expr)
        if not e:
            continue
        val, vals, ops = e
        said = m.group(0).strip()
        if ops == ["/"] and all(x.denominator == 1 for x in vals) and claim.denominator == 1:
            a, b = int(vals[0]), int(vals[1])
            q, r = divmod(a, b)
            if rest is not None:
                if int(claim) != q or int(_num(rest)) != r:
                    out.append(f"« {said} » est faux : {_fmt(vals[0])} ÷ {_fmt(vals[1])} = {_fmt(Fraction(q))}, reste {_fmt(Fraction(r))}")
                continue
            if int(claim) == q:  # the quotient of a division with a remainder, the remainder not said: right
                continue
        if abs(val - claim) > Fraction(1, 1000) * max(1, abs(val)):
            out.append(f"« {said} » est faux : le bon résultat est {_fmt(val)}")
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq[:6]


if __name__ == "__main__":
    import sys
    for p in check(sys.stdin.read()):
        print("-", p)
