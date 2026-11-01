#!/usr/bin/env python3
"""pdf-pro: Naim's professional PDFs, with nothing to install (Python's standard library, the Mac's print engine
naim-pdf, the KaTeX already shipped with Naim).

  pdfpro.py render <page.html> <sortie.pdf> [couleur]   the theme, the formulas, the coloured code, then the A4 PDF
  pdfpro.py render 01.md 02.md … <sortie.pdf> [couleur]  .md files (a course in chapters) -> ONE PDF: cover, contents,
                                                  one chapter per file in that order (README.md: the title)
                                                  (couleur: gris, bleu, vert, rouge, noir, marine… or #rrggbb; orange by default)
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
KEYWORDS["cobol"] = ("identification division program-id data working-storage linkage file section procedure using "
                     "pic picture value values move to add subtract multiply divide compute giving display accept if else "
                     "end-if perform until varying from by times end-perform evaluate when other end-evaluate call goback "
                     "stop run string delimited size into end-string open close read write rewrite delete input output "
                     "extend at end not invalid key fd select assign organization sequential indexed relative access "
                     "record is are copy occurs redefines function set true false zero zeros spaces space")
KEYWORDS["javascript"] = KEYWORDS["ts"] = KEYWORDS["js"]
KEYWORDS["sh"] = KEYWORDS["shell"] = KEYWORDS["bash"]


def highlight(code, lang):
    words = set(re.split(r"[\s-]+", KEYWORDS.get(lang, KEYWORDS["python"])))
    comment = (r"--[^\n]*" if lang == "sql" else r"//[^\n]*|/\*.*?\*/" if lang in ("js", "javascript", "ts")
               else r"\*>[^\n]*|(?:^|(?<=\n)) {6}\*[^\n]*" if lang in ("cobol", "cbl", "cob") else r"#[^\n]*")
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
            low = w.lower() if lang in ("sql", "cobol", "cbl", "cob") else w
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


# ------------------------------------------------------------------ Markdown -> the theme's HTML (a course written in .md files)
def _inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*\s][^*]*?)\*(?!\w)", r"<em>\1</em>", t)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)


def md_html(text, shift=1):
    """Markdown (titles, paragraphs, lists, tables, code blocks, quotes) -> HTML with the theme's classes.
    shift: « # » becomes <h(1+shift)> (in a chapter, the file's own title is the chapter's)."""
    out, lines, i = [], text.replace("\r", "").split("\n"), 0
    para, items, kind = [], [], None

    def flush():
        nonlocal para, items, kind
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
        if items:
            out.append(f"<{kind}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{kind}>")
        para, items, kind = [], [], None
    while i < len(lines):
        ln = lines[i]
        fence = re.match(r"^\s*```\s*([\w+-]*)", ln)
        if fence:
            flush()
            lang, code, i = (fence.group(1) or "text").lower(), [], i + 1
            while i < len(lines) and not re.match(r"^\s*```", lines[i]):
                code.append(lines[i]); i += 1
            out.append(f'<pre class="code {html.escape(lang)}">{html.escape(chr(10).join(code))}</pre>')
        elif re.match(r"^#{1,6}\s", ln):
            flush()
            n = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{min(6, n + shift)}>{_inline(ln[n:].strip())}</h{min(6, n + shift)}>")
        elif ln.strip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            i -= 1
            if rows:
                out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>"
                           + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:]) + "</tbody></table>")
        elif re.match(r"^\s*>\s?", ln):
            flush()
            quote = []
            while i < len(lines) and re.match(r"^\s*>\s?", lines[i]):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            i -= 1
            out.append('<div class="callout info"><p>' + _inline(" ".join(quote)) + "</p></div>")
        elif re.match(r"^\s*([-*+]|\d+[.)])\s+", ln):
            k = "ol" if re.match(r"^\s*\d", ln) else "ul"
            if para or (kind and kind != k):
                flush()
            kind = k
            items.append(re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", ln))
        elif re.match(r"^\s*(-{3,}|\*{3,})\s*$", ln):
            flush(); out.append("<hr>")
        elif not ln.strip():
            flush()
        elif items and ln.startswith((" ", "\t")):
            items[-1] += " " + ln.strip()
        else:
            if items:
                flush()
            para.append(ln.strip())
        i += 1
    flush()
    return "\n".join(out)


def render_md(files, out, couleur=""):
    """Several .md files (a course written chapter by chapter) -> ONE PDF: a cover, a table of contents, one chapter
    per file in the order given (a README gives the title and the subtitle, it is not a chapter)."""
    import datetime
    files = [Path(f).expanduser() for f in files]
    readme = next((f for f in files if f.name.lower() == "readme.md"), None)
    chapters = [f for f in files if f is not readme]
    if not chapters:
        sys.exit("erreur : aucun chapitre .md à mettre dans le PDF.")
    texts = [f.read_text(errors="replace") for f in chapters]
    titles = [(re.search(r"^#\s+(.+)$", t, re.M) or [None, f.stem.replace("-", " ").replace("_", " ")])[1].strip() for t, f in zip(texts, chapters)]
    common = ""
    if len(titles) > 1:  # « Cours COBOL - Introduction », « Cours COBOL - Fichiers »: the course's name, said once
        cut = re.match(r"^(.+?\s[-–—:]\s)", titles[0])
        if cut and all(t.startswith(cut.group(1)) for t in titles):
            common = cut.group(1)
    title, subtitle = re.sub(r"\s[-–—:]\s$", "", common).strip(), ""
    if readme:
        rt = readme.read_text(errors="replace")
        m = re.search(r"^#\s+(.+)$", rt, re.M)
        title = m.group(1).strip() if m else title
        para = next((p.strip() for p in re.split(r"\n\s*\n", re.sub(r"^#.*$", "", rt, flags=re.M)) if p.strip() and not p.strip().startswith(("-", "*", "|", "```", ">"))), "")
        subtitle = re.sub(r"\s*:\s*$", ".", re.sub(r"\s+", " ", para)[:220])  # it introduced a list: a sentence on the cover
    title = title or titles[0]
    d = datetime.date.today()
    when = f"{d.day} {'janvier février mars avril mai juin juillet août septembre octobre novembre décembre'.split()[d.month - 1]} {d.year}"
    names = [t[len(common):].strip() if common else t for t in titles]
    body = [f'<section class="cover"><div><div class="kicker">Cours</div><h1>{html.escape(title)}</h1>'
            + (f'<div class="subtitle">{_inline(subtitle)}</div>' if subtitle else "") + '<div class="band"></div></div>'
            f'<div class="meta"><div><b>Auteur</b>Naim</div><div><b>Date</b>{when}</div><div><b>Chapitres</b>{len(chapters)}</div></div></section>',
            '<section class="toc"><h2>Sommaire</h2><ol>' + "".join(f'<li><a href="#c{k + 1}">{html.escape(n)}</a></li>' for k, n in enumerate(names)) + "</ol></section>"]
    for k, (t, n) in enumerate(zip(texts, names)):
        rest = re.sub(r"^#\s+.+$", "", t, count=1, flags=re.M)
        body.append(f'<section class="chapter" id="c{k + 1}"><h2><span class="num">{k + 1:02d}</span>{html.escape(n)}</h2>\n{md_html(rest)}</section>')
    out = Path(out).expanduser().resolve()
    page_file = out.with_suffix(".html")
    page_file.write_text("\n".join(body))
    render(page_file, out, couleur)


# ------------------------------------------------------------------ the page
def page(body, title="Document"):
    if re.search(r"<html[\s>]", body, re.I):  # a whole page already: the theme joins its head
        head_extra = f'<style>{(HERE / "theme.css").read_text()}</style>'
        asked = "".join(re.findall(r"<style>:root\{--clay:[^<]*</style>", body))  # a colour asked (« gris »): after the theme, it wins
        return re.sub(r"</head>", lambda m: head_extra + asked + _katex() + "</head>", body, count=1, flags=re.I) if "</head>" in body.lower() else body
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


# the accent of the theme (lines, small titles, numbers), orange unless the user asks for another colour
ACCENTS = {"orange": "#c96442", "gris": "#7a7a74", "noir": "#2b2a28", "bleu": "#3b6ea8", "marine": "#2c4a74",
           "vert": "#4f8a5b", "rouge": "#b4473f", "bordeaux": "#8a2e3b", "violet": "#7a5aa6", "turquoise": "#2a8c8c",
           "jaune": "#b7862b", "or": "#a8842c", "rose": "#c25b86", "marron": "#8a5a3c"}


def accent_css(name):
    """« gris », « bleu », « #4a7bd0 »… -> the style that gives the theme that accent ("" for the default orange)."""
    name = str(name or "").strip().lower()
    if not name or name == "orange":
        return ""
    col = ACCENTS.get(name) or (name if re.fullmatch(r"#[0-9a-f]{6}", name) else None)
    if not col:
        sys.exit(f"erreur : couleur inconnue « {name} ». Possibles : {', '.join(ACCENTS)}, ou un code #rrggbb.")
    r, g, b = (int(col[i:i + 2], 16) for i in (1, 3, 5))
    soft = "#%02x%02x%02x" % tuple(round(v + (255 - v) * .84) for v in (r, g, b))
    return f"<style>:root{{--clay:{col};--clay-soft:{soft}}}</style>"


def render(src, out, couleur=""):
    src, out = Path(src).expanduser().resolve(), Path(out).expanduser().resolve()
    full = src.with_name(src.stem + ".pro.html")  # next to the page: its images (img/…) keep their relative paths
    built = page(src.read_text())
    if couleur:
        built = re.sub(r"</head>", lambda m: accent_css(couleur) + "</head>", built, count=1, flags=re.I)
    full.write_text(built)
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
    if len(a) >= 3 and a[0] == "render" and any(x.lower().endswith(".md") for x in a[1:]):  # .md files -> one PDF
        mds = [x for x in a[1:] if x.lower().endswith(".md")]
        pdf = next((x for x in a[1:] if x.lower().endswith(".pdf")), None) or sys.exit("erreur : donne le PDF à faire (… cours.pdf).")
        rest = [x for x in a[1:] if x not in mds and x != pdf]
        render_md(mds, pdf, rest[0] if rest else "")
    elif len(a) >= 3 and a[0] == "render":
        render(a[1], a[2], a[3] if len(a) > 3 else "")
    elif len(a) >= 4 and a[0] == "chart":
        chart(a[1], a[2], a[3], a[4] if len(a) > 4 else "", a[5] if len(a) > 5 else "")
    elif len(a) >= 2 and a[0] == "check":
        check(a[1])
    else:
        sys.exit(__doc__)
