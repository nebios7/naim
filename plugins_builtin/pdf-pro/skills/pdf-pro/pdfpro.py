#!/usr/bin/env python3
"""pdf-pro: Naim's professional PDFs, with nothing to install (Python's standard library, the Mac's print engine
naim-pdf, the KaTeX already shipped with Naim).

  pdfpro.py render <page.html> <sortie.pdf>       the theme, the formulas, the coloured code, then the A4 PDF
  pdfpro.py chart <bars|hbars|line|donut> <données.json> <sortie.svg> ["titre"] [small]
                                                  a chart in the theme's colours, to put in a <figure>
                                                  (small: for two charts side by side in <div class="grid2">)
  pdfpro.py check <sortie.pdf>                    the number of pages and a PNG of page 1 and 2 to look at

page.html holds only the body (cover, sections…): no <html>, no <style> needed. Formulas: <span class="tex">x^2</span>
in a line, <div class="tex-block">\\int_0^1 x\\,dx</div> on their own. Code: <pre class="code python">…</pre>.
Data for a chart: [["janv", 12], ["févr", 18]] or {"series": {"2025": [["T1", 3], …], "2026": […]}} for several lines.
"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = Path.home() / "Library/Application Support/Naim"
NAIM_PDF = APP / "bin/naim-pdf"
KATEX = APP / "vendor/katex"
SIZE = {"W": 760}  # « small » (two charts side by side): 440, so the text stays readable
COLORS = ["#c96442", "#4f7fae", "#6f8452", "#b7862b", "#8a6fb0", "#b4473f", "#5b9a8b", "#9b968c"]
INK, MUTED, LINE = "#1f1e1d", "#6b6a65", "#e6e2d8"
FONT = "-apple-system, Helvetica Neue, Helvetica, Arial, sans-serif"


# ------------------------------------------------------------------ code colouring (Python, JS, SQL, shell…)
KEYWORDS = {
    "python": "and as assert async await break class continue def del elif else except False finally for from global if "
              "import in is lambda None nonlocal not or pass raise return True try while with yield match case self",
    "js": "async await break case catch class const continue default delete do else export extends false finally for "
          "function if import in instanceof let new null return super switch this throw true try typeof undefined var "
          "void while yield",
    "sql": "select from where and or not insert into values update set delete create table drop alter join left right "
           "inner outer on group by order having limit as distinct count sum avg min max null primary key",
    "bash": "if then else elif fi for while do done case esac function in return export local echo cd",
}
KEYWORDS["javascript"] = KEYWORDS["ts"] = KEYWORDS["js"]
KEYWORDS["sh"] = KEYWORDS["shell"] = KEYWORDS["bash"]


def highlight(code, lang):
    words = set(KEYWORDS.get(lang, KEYWORDS["python"]).split())
    comment = r"--[^\n]*" if lang == "sql" else r"//[^\n]*|/\*.*?\*/" if lang in ("js", "javascript", "ts") else r"#[^\n]*"
    rx = re.compile(rf"(?P<c>{comment})|(?P<s>\"\"\".*?\"\"\"|'''.*?'''|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`[^`]*`)"
                    r"|(?P<n>\b\d+(?:\.\d+)?\b)|(?P<w>\b[A-Za-z_]\w*\b)(?P<call>\s*\()?", re.S)
    out, last = [], 0
    for m in rx.finditer(code):
        out.append(html.escape(code[last:m.start()]))
        last = m.end()
        if m.group("c"):
            out.append(f'<span class="c">{html.escape(m.group("c"))}</span>')
        elif m.group("s"):
            out.append(f'<span class="s">{html.escape(m.group("s"))}</span>')
        elif m.group("n"):
            out.append(f'<span class="n">{m.group("n")}</span>')
        else:
            w = m.group("w")
            low = w.lower() if lang == "sql" else w
            cls = "k" if low in words else "f" if m.group("call") else ""
            out.append(f'<span class="{cls}">{html.escape(w)}</span>' if cls else html.escape(w))
            if m.group("call"):
                out.append(html.escape(m.group("call")))
    out.append(html.escape(code[last:]))
    return "".join(out)


def color_code(body):
    def one(m):
        attrs, code = m.group(1), m.group(2)
        lang = next((x for x in re.findall(r"[\w+-]+", re.search(r'class="([^"]*)"', attrs).group(1)) if x != "code"), "python")
        label = re.search(r'<span class="file">(.*?)</span>', code, re.S)
        code = code.replace(label.group(0), "") if label else code
        raw = html.unescape(re.sub(r"<[^>]+>", "", code))
        head = f'<span class="file">{label.group(1)}</span>' if label else ""
        return f"<pre{attrs}>{head}<code>{highlight(raw.strip(chr(10)), lang.lower())}</code></pre>"
    return re.sub(r'<pre(\s[^>]*class="[^"]*\bcode\b[^"]*"[^>]*)>(.*?)</pre>', one, body, flags=re.S)


# ------------------------------------------------------------------ the page
def page(body, title="Document"):
    if re.search(r"<html[\s>]", body, re.I):  # a whole page already: the theme joins its head
        head_extra = f'<style>{(HERE / "theme.css").read_text()}</style>'
        return re.sub(r"</head>", head_extra + _katex() + "</head>", body, count=1, flags=re.I) if "</head>" in body.lower() else body
    t = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    title = re.sub(r"<[^>]+>", "", t.group(1)).strip() if t else title
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f'<style>{(HERE / "theme.css").read_text()}</style>{_katex()}</head><body>{color_code(body)}</body></html>')


def _katex():
    if not (KATEX / "katex.min.js").is_file():
        return ""
    return (f'<link rel="stylesheet" href="{(KATEX / "katex.min.css").as_uri()}">'
            f'<script src="{(KATEX / "katex.min.js").as_uri()}"></script>'
            "<script>window.__naimWait = true;"
            "document.addEventListener('DOMContentLoaded', function () {"
            "  try { document.querySelectorAll('.tex, .tex-block').forEach(function (e) {"
            "    katex.render(e.textContent, e, { displayMode: e.classList.contains('tex-block'), throwOnError: false }); });"
            "  } catch (err) { window.__naimError = String(err); }"
            "  (document.fonts ? document.fonts.ready : Promise.resolve()).then(function () { window.__naimReady = true; });"
            "});</script>")


def render(src, out):
    src, out = Path(src).expanduser().resolve(), Path(out).expanduser().resolve()
    full = src.with_name(src.stem + ".pro.html")  # next to the page: its images (img/…) keep their relative paths
    full.write_text(page(src.read_text()))
    r = subprocess.run([str(NAIM_PDF), str(full), str(out), "A4"], capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not out.is_file():
        sys.exit("erreur : " + (r.stderr or r.stdout).strip()[-400:])
    info = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
    print(f"PDF : {out} ({info.get('pages', '?')} pages). Vérifie-le : pdfpro.py check \"{out}\"")


def check(pdf):
    pdf = Path(pdf).expanduser().resolve()
    for n in (1, 2):
        png = pdf.with_name(f"{pdf.stem}.page{n}.png")
        r = subprocess.run([str(NAIM_PDF), str(pdf), str(png), str(n), "1100"], capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            print(f"page {n} : {png}  (regarde-la avec look_at)")


# ------------------------------------------------------------------ charts (SVG, the theme's colours)
def _esc(s):
    return html.escape(str(s))


def _nice(v):
    if v <= 0:
        return 1
    import math
    e = 10 ** math.floor(math.log10(v))
    return next(m * e for m in (1, 2, 2.5, 5, 10) if m * e >= v)


def _fmt(v):
    return f"{v:,.0f}".replace(",", " ") if abs(v) >= 100 or float(v).is_integer() else f"{v:.1f}".replace(".", ",")


def _frame(w, h, title, inner):
    t = f'<text x="0" y="16" font-size="15" font-weight="600" fill="{INK}">{_esc(title)}</text>' if title else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="{FONT}" font-size="12">'
            f"{t}{inner}</svg>")


def _pairs(data):
    return [(str(a), float(b)) for a, b in (data.items() if isinstance(data, dict) else data)]


def bars(data, title="", horizontal=False):
    d = _pairs(data)
    W, top = SIZE["W"], 34 if title else 10
    if horizontal:
        lab = max((len(a) for a, _ in d), default=4) * 7 + 10
        H = top + len(d) * 30 + 10
        mx = _nice(max((v for _, v in d), default=1))
        g = []
        for i, (a, v) in enumerate(d):
            y, bw = top + i * 30, (W - lab - 60) * v / mx
            g.append(f'<text x="{lab - 8}" y="{y + 17}" text-anchor="end" fill="{MUTED}">{_esc(a)}</text>'
                     f'<rect x="{lab}" y="{y + 5}" width="{max(bw, 1):.1f}" height="18" rx="3" fill="{COLORS[0]}"/>'
                     f'<text x="{lab + bw + 6:.1f}" y="{y + 18}" fill="{INK}">{_fmt(v)}</text>')
        return _frame(W, H, title, "".join(g))
    H, left, bottom = (300 if W > 500 else 260), 46, 34
    mx = _nice(max((v for _, v in d), default=1))
    ph, pw = H - top - bottom, W - left - 10
    g = []
    for k in range(5):  # light grid with its values
        y = top + ph - ph * k / 4
        g.append(f'<line x1="{left}" x2="{W - 10}" y1="{y:.1f}" y2="{y:.1f}" stroke="{LINE}"/>'
                 f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" fill="{MUTED}" font-size="11">{_fmt(mx * k / 4)}</text>')
    bw = pw / max(len(d), 1)
    for i, (a, v) in enumerate(d):
        h = ph * v / mx
        x = left + i * bw + bw * .18
        g.append(f'<rect x="{x:.1f}" y="{top + ph - h:.1f}" width="{bw * .64:.1f}" height="{max(h, .5):.1f}" rx="3" fill="{COLORS[0]}"/>')
        if len(d) <= 14:
            g.append(f'<text x="{x + bw * .32:.1f}" y="{top + ph - h - 5:.1f}" text-anchor="middle" fill="{INK}" font-size="11">{_fmt(v)}</text>')
        if len(d) <= 16 or i % max(1, len(d) // 10) == 0:
            g.append(f'<text x="{left + i * bw + bw / 2:.1f}" y="{H - 12}" text-anchor="middle" fill="{MUTED}" font-size="11">{_esc(a)}</text>')
    return _frame(W, H, title, "".join(g))


def line(data, title=""):
    series = data["series"] if isinstance(data, dict) and "series" in data else {"": data}
    series = {k: _pairs(v) for k, v in series.items()}
    labels = [a for a, _ in next(iter(series.values()))]
    W, H, top, left, bottom = SIZE["W"], 300 if SIZE["W"] > 500 else 260, 34 if title else 10, 46, 34 + (18 if len(series) > 1 else 0)
    mx = _nice(max((v for s in series.values() for _, v in s), default=1))
    ph, pw = H - top - bottom, W - left - 16
    g = []
    for k in range(5):
        y = top + ph - ph * k / 4
        g.append(f'<line x1="{left}" x2="{W - 10}" y1="{y:.1f}" y2="{y:.1f}" stroke="{LINE}"/>'
                 f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" fill="{MUTED}" font-size="11">{_fmt(mx * k / 4)}</text>')
    step = pw / max(len(labels) - 1, 1)
    for i, a in enumerate(labels):
        if len(labels) <= 14 or i % max(1, len(labels) // 10) == 0:
            g.append(f'<text x="{left + i * step:.1f}" y="{top + ph + 18}" text-anchor="middle" fill="{MUTED}" font-size="11">{_esc(a)}</text>')
    for n, (name, s) in enumerate(series.items()):
        c = COLORS[n % len(COLORS)]
        pts = [(left + i * step, top + ph - ph * v / mx) for i, (_, v) in enumerate(s)]
        g.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="none" stroke="{c}" stroke-width="2.4" stroke-linejoin="round"/>')
        g += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#fff" stroke="{c}" stroke-width="2"/>' for x, y in pts]
        if len(series) > 1:
            lx = left + sum(len(k) * 6.6 + 34 for k in list(series)[:n])
            g.append(f'<rect x="{lx:.0f}" y="{H - 14}" width="10" height="10" rx="2" fill="{c}"/>'
                     f'<text x="{lx + 15:.0f}" y="{H - 5}" fill="{INK}" font-size="11">{_esc(name)}</text>')
    return _frame(W, H, title, "".join(g))


def donut(data, title=""):
    import math
    d = [(a, v) for a, v in _pairs(data) if v > 0]
    total = sum(v for _, v in d) or 1
    W, top = (SIZE["W"] if SIZE["W"] < 500 else 600), 34 if title else 10
    H = max(220, top + 30 + len(d) * 24)
    cx, cy, R, r = 120, top + 95, 88, 54
    g, a0 = [], -math.pi / 2
    for i, (a, v) in enumerate(d):
        a1 = a0 + v / total * 2 * math.pi
        big = 1 if a1 - a0 > math.pi else 0
        P = lambda ang, rad: f"{cx + rad * math.cos(ang):.2f} {cy + rad * math.sin(ang):.2f}"
        path = (f"M{cx} {cy - R} A{R} {R} 0 1 1 {cx - .01} {cy - R} L{cx - .01} {cy - r} A{r} {r} 0 1 0 {cx} {cy - r} Z"
                if len(d) == 1 else f"M{P(a0, R)} A{R} {R} 0 {big} 1 {P(a1, R)} L{P(a1, r)} A{r} {r} 0 {big} 0 {P(a0, r)} Z")
        g.append(f'<path d="{path}" fill="{COLORS[i % len(COLORS)]}" stroke="#fff" stroke-width="1.5"/>')
        y = top + 30 + i * 24
        g.append(f'<rect x="270" y="{y - 10}" width="12" height="12" rx="2" fill="{COLORS[i % len(COLORS)]}"/>'
                 f'<text x="290" y="{y}" fill="{INK}">{_esc(a)}</text>'
                 f'<text x="{W - 10}" y="{y}" text-anchor="end" fill="{MUTED}">{_fmt(v)} · {v / total * 100:.0f} %</text>')
        a0 = a1
    g.append(f'<text x="{cx}" y="{cy + 6}" text-anchor="middle" font-size="20" font-weight="600" fill="{INK}">{_fmt(total)}</text>')
    return _frame(W, H, title, "".join(g))


def chart(kind, data_file, out, title="", size=""):
    if size == "small":
        SIZE["W"] = 440
    data = json.loads(Path(data_file).expanduser().read_text())
    svg = {"bars": lambda: bars(data, title), "hbars": lambda: bars(data, title, horizontal=True),
           "line": lambda: line(data, title), "donut": lambda: donut(data, title)}.get(kind)
    if not svg:
        sys.exit("erreur : type de graphique inconnu (bars, hbars, line, donut)")
    Path(out).expanduser().write_text(svg())
    print(f'Graphique : {out}  → dans la page : <figure><img src="{Path(out).name}"><figcaption>…</figcaption></figure>')


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "render":
        render(a[1], a[2])
    elif len(a) >= 4 and a[0] == "chart":
        chart(a[1], a[2], a[3], a[4] if len(a) > 4 else "", a[5] if len(a) > 5 else "")
    elif len(a) >= 2 and a[0] == "check":
        check(a[1])
    else:
        sys.exit(__doc__)
