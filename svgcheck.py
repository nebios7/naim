#!/usr/bin/env python3
"""Measures a drawing in SVG the way a person looks at it: what goes out of the frame, labels on top of each other,
a label cut by a line, a point's name far from its point, a figure lost in a corner of its frame, text too small,
shapes of no size. A small model writes coordinates without seeing them; this gives it its eyes back, in numbers.

  python3 svgcheck.py figure.svg        → the problems found (nothing printed: the drawing is clean)
  check(svg_text) → [problem, …]        → used by Naim before showing a ```svg block or after writing a .svg file
"""
import math
import re
import sys
import xml.etree.ElementTree as ET

NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def _f(v, default=0.0):
    try:
        return float(re.match(NUM, str(v).strip()).group(0))
    except (AttributeError, ValueError, TypeError):
        return default


def _style(el, key):
    m = re.search(rf"(?:^|;)\s*{key}\s*:\s*([^;]+)", el.get("style", "") or "")
    return m.group(1).strip() if m else el.get(key)


def _transform(t):
    """translate(x[,y]) and scale(s[,t]) only; anything else (rotate, matrix, skew) → None (the element is not measured)."""
    dx = dy = 0.0
    sx = sy = 1.0
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", t or ""):
        a = [float(x) for x in re.findall(NUM, args)]
        if name == "translate" and a:
            dx, dy = dx + a[0] * sx, dy + (a[1] if len(a) > 1 else 0) * sy
        elif name == "scale" and a:
            sx, sy = sx * a[0], sy * (a[1] if len(a) > 1 else a[0])
        else:
            return None
    return dx, dy, sx, sy


def _path_points(d):
    """The points a path goes through (curve control points included: a little larger than the curve itself)."""
    pts, x, y, sx, sy = [], 0.0, 0.0, 0.0, 0.0
    tokens = re.findall(rf"[MmLlHhVvCcSsQqTtAaZz]|{NUM}", d or "")
    i, cmd = 0, None
    nargs = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
    while i < len(tokens):
        if re.match(r"[A-Za-z]", tokens[i]):
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                x, y = sx, sy
                pts.append((x, y))
                continue
        if cmd is None:
            break
        n = nargs[cmd.upper()]
        a = [float(t) for t in tokens[i:i + n]]
        if len(a) < n:
            break
        i += n
        rel = cmd.islower()
        C = cmd.upper()
        if C == "H":
            x = x + a[0] if rel else a[0]
        elif C == "V":
            y = y + a[0] if rel else a[0]
        elif C == "A":
            x, y = (x + a[5], y + a[6]) if rel else (a[5], a[6])
        else:
            for k in range(0, n, 2):
                px, py = (x + a[k], y + a[k + 1]) if rel else (a[k], a[k + 1])
                if k < n - 2:
                    pts.append((px, py))
            x, y = (x + a[-2], y + a[-1]) if rel else (a[-2], a[-1])
        if C == "M":
            sx, sy = x, y
            if cmd == "M":
                cmd = "L"
            elif cmd == "m":
                cmd = "l"
        pts.append((x, y))
    return pts


def _segments_of(kind, el, pts):
    if kind == "line" or kind == "polyline" or kind == "path":
        return list(zip(pts, pts[1:]))
    if kind in ("polygon", "rect"):
        return list(zip(pts, pts[1:] + pts[:1]))
    return []


def _seg_hits_box(p, q, box):
    """does the segment pq cross the inside of the box (x1, y1, x2, y2)? (Liang-Barsky clipping)"""
    x1, y1, x2, y2 = box
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x1), (dx, x2 - p[0]), (-dy, p[1] - y1), (dy, y2 - p[1])):
        if pp == 0:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def measure(svg):
    """{frame, shapes: [{kind, box, pts, segs, label}], texts: [{text, box, x, y, size}], points: [(x, y)]}"""
    svg = re.sub(r"<!DOCTYPE[^>]*>", "", svg)
    svg = re.sub(r"\sxmlns(:\w+)?=\"[^\"]*\"", "", svg, count=0)
    root = ET.fromstring(svg)
    vb = [float(v) for v in re.findall(NUM, root.get("viewBox", ""))]
    if len(vb) == 4:
        frame = (vb[0], vb[1], vb[0] + vb[2], vb[1] + vb[3])
    else:
        frame = (0, 0, _f(root.get("width"), 300), _f(root.get("height"), 150))
    shapes, texts, points, unmeasured = [], [], [], 0

    def walk(el, tr, fs):
        nonlocal unmeasured
        tag = el.tag.split("}")[-1]
        t = _transform(el.get("transform"))
        if t is None:
            unmeasured += 1
            return
        dx, dy, sx, sy = tr[0] + t[0] * tr[2], tr[1] + t[1] * tr[3], tr[2] * t[2], tr[3] * t[3]
        fs = _f(_style(el, "font-size"), fs) if _style(el, "font-size") else fs
        P = lambda x, y: (dx + x * sx, dy + y * sy)
        if tag in ("defs", "marker", "clipPath", "mask", "pattern", "symbol", "style", "title", "desc", "linearGradient", "radialGradient"):
            return
        pts = None
        if tag == "rect":
            x, y, w, h = (_f(el.get(k)) for k in ("x", "y", "width", "height"))
            pts = [P(x, y), P(x + w, y), P(x + w, y + h), P(x, y + h)]
        elif tag == "circle" or tag == "ellipse":
            cx, cy = _f(el.get("cx")), _f(el.get("cy"))
            rx = _f(el.get("r") or el.get("rx")) * abs(sx)
            ry = _f(el.get("r") or el.get("ry")) * abs(sy)
            c = P(cx, cy)
            pts = [(c[0] - rx, c[1] - ry), (c[0] + rx, c[1] + ry)]
            if max(rx, ry) <= 7 and (el.get("fill") or _style(el, "fill") or "black") not in ("none", "transparent"):
                points.append(c)
            shapes.append({"kind": tag, "box": (c[0] - rx, c[1] - ry, c[0] + rx, c[1] + ry), "pts": [], "segs": [], "r": max(rx, ry)})
            pts = None
        elif tag == "line":
            pts = [P(_f(el.get("x1")), _f(el.get("y1"))), P(_f(el.get("x2")), _f(el.get("y2")))]
        elif tag in ("polyline", "polygon"):
            v = [float(n) for n in re.findall(NUM, el.get("points", ""))]
            pts = [P(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2)]
        elif tag == "path":
            pts = [P(x, y) for x, y in _path_points(el.get("d"))]
        elif tag == "text":
            txt = "".join(el.itertext()).strip()
            if txt:
                size = fs * abs(sy)
                x, y = P(_f(el.get("x")), _f(el.get("y")))
                x += _f(el.get("dx")) * sx
                y += _f(el.get("dy")) * sy
                w = len(txt) * size * 0.56
                anchor = _style(el, "text-anchor") or "start"
                x1 = x - w / 2 if anchor == "middle" else x - w if anchor == "end" else x
                texts.append({"text": txt[:40], "box": (x1, y - size * 0.78, x1 + w, y + size * 0.22), "x": x, "y": y, "size": size})
            return
        if pts:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            shapes.append({"kind": tag, "box": (min(xs), min(ys), max(xs), max(ys)), "pts": pts, "segs": _segments_of(tag, el, pts),
                           "stroke": (el.get("stroke") or _style(el, "stroke") or "") not in ("", "none")})
        for ch in el:
            walk(ch, (dx, dy, sx, sy), fs)

    root_fs = _f(_style(root, "font-size"), 16) if _style(root, "font-size") else 16
    for ch in root:
        walk(ch, (0, 0, 1, 1), root_fs)
    return {"frame": frame, "shapes": shapes, "texts": texts, "points": points, "unmeasured": unmeasured}


def check(svg):
    """The problems of a drawing, said with their place and what to do (French, for the model)."""
    try:
        m = measure(svg)
    except ET.ParseError as e:
        return [f"le SVG ne se lit pas (XML invalide : {e}) — vérifie les balises fermées et les guillemets"]
    fx1, fy1, fx2, fy2 = m["frame"]
    W, H = fx2 - fx1, fy2 - fy1
    if W <= 0 or H <= 0:
        return ["le cadre n'a pas de taille : mets viewBox=\"0 0 largeur hauteur\" sur la balise <svg>"]
    out = []
    tol = max(W, H) * 0.01
    q = lambda v: f"{v:.0f}"
    # 1. out of the frame
    for t in m["texts"]:
        x1, y1, x2, y2 = t["box"]
        if x1 < fx1 - tol or x2 > fx2 + tol or y1 < fy1 - tol or y2 > fy2 + tol:
            out.append(f"le texte « {t['text']} » sort du cadre (il va de x={q(x1)} à {q(x2)}, y={q(y1)} à {q(y2)} ; le cadre : "
                       f"{q(fx1)} à {q(fx2)} en x, {q(fy1)} à {q(fy2)} en y) — rapproche-le ou agrandis le viewBox")
    for s in m["shapes"]:
        x1, y1, x2, y2 = s["box"]
        if x1 < fx1 - tol * 2 or x2 > fx2 + tol * 2 or y1 < fy1 - tol * 2 or y2 > fy2 + tol * 2:
            out.append(f"un {s['kind']} sort du cadre (de ({q(x1)},{q(y1)}) à ({q(x2)},{q(y2)}), cadre {q(fx1)},{q(fy1)} → {q(fx2)},{q(fy2)})")
    # 2. labels on top of each other
    T = m["texts"]
    for i in range(len(T)):
        for j in range(i + 1, len(T)):
            a, b = T[i]["box"], T[j]["box"]
            ix, iy = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
            if ix > 0 and iy > 0:
                small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])) or 1
                if ix * iy / small > 0.25:
                    out.append(f"les textes « {T[i]['text']} » et « {T[j]['text']} » se chevauchent vers ({q(max(a[0], b[0]))},{q(max(a[1], b[1]))}) — écarte-les d'au moins {q(T[i]['size'])}")
    # 3. a label cut by a line (the middle of the text crossed by a stroke)
    for t in T:
        x1, y1, x2, y2 = t["box"]
        mx, my = (x2 - x1) * 0.2, (y2 - y1) * 0.25
        core = (x1 + mx, y1 + my, x2 - mx, y2 - my)
        for s in m["shapes"]:
            if s.get("stroke") or s["kind"] in ("line", "polyline", "path"):
                if any(_seg_hits_box(p, r, core) for p, r in s["segs"]):
                    out.append(f"le texte « {t['text']} » est coupé par un trait ({s['kind']}) — décale-le de quelques unités (au-dessus, à côté)")
                    break
    # 4. a point's name far from any point, or right on it
    singles = [t for t in T if re.fullmatch(r"[A-Z][0-9]?['’′]*", t["text"])]
    anchors = list(m["points"]) + [p for s in m["shapes"] if s["kind"] in ("polygon", "polyline", "line", "rect") for p in s["pts"]]
    if singles and anchors:
        for t in singles:
            cx, cy = (t["box"][0] + t["box"][2]) / 2, (t["box"][1] + t["box"][3]) / 2
            dist = min(math.hypot(cx - x, cy - y) for x, y in anchors)
            if dist > max(3.2 * t["size"], 0.12 * max(W, H)):
                out.append(f"l'étiquette « {t['text']} » est loin de tout point ou sommet ({q(dist)} unités du plus proche) — place-la à côté du point qu'elle nomme")
            elif dist < t["size"] * 0.25 and m["points"]:
                out.append(f"l'étiquette « {t['text']} » est posée sur le point — décale-la d'environ {q(t['size'] * 0.7)} unités")
    # 5. the figure lost in its frame, or squeezed
    drawn = [s["box"] for s in m["shapes"] if not (s["box"][0] <= fx1 + tol and s["box"][1] <= fy1 + tol and s["box"][2] >= fx2 - tol and s["box"][3] >= fy2 - tol)]
    if drawn:
        ux1, uy1 = min(b[0] for b in drawn), min(b[1] for b in drawn)
        ux2, uy2 = max(b[2] for b in drawn), max(b[3] for b in drawn)
        cw, ch = (ux2 - ux1) / W, (uy2 - uy1) / H
        if cw < 0.4 and ch < 0.4:
            out.append(f"la figure n'occupe que {cw * 100:.0f} % × {ch * 100:.0f} % du cadre (de ({q(ux1)},{q(uy1)}) à ({q(ux2)},{q(uy2)})) — agrandis-la ou réduis le viewBox")
    # 6. shapes of no size, text too small
    for s in m["shapes"]:
        x1, y1, x2, y2 = s["box"]
        if s["kind"] in ("rect", "circle", "ellipse", "polygon") and ((x2 - x1) < 0.5 or (y2 - y1) < 0.5):
            out.append(f"un {s['kind']} n'a pas de taille (de ({q(x1)},{q(y1)}) à ({q(x2)},{q(y2)}))")
    for t in T:
        if t["size"] < max(W, H) * 0.028:
            out.append(f"le texte « {t['text']} » est trop petit ({t['size']:.0f} pour un cadre de {q(max(W, H))}) — au moins {q(max(W, H) * 0.04)}")
            break
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq[:12]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    src = sys.stdin.read() if sys.argv[1] == "-" else open(sys.argv[1], encoding="utf-8").read()
    probs = check(src)
    if probs:
        print("PROBLÈMES du dessin :")
        for p in probs:
            print(" -", p)
        sys.exit(1)
    print("Dessin vérifié : rien ne sort du cadre, aucun texte ne se chevauche ni n'est coupé.")
