"""Diagrams and visuals as real files: Mermaid (architecture, flow, sequence, database, Gantt, mind map…) and Graphviz
rendered to SVG / PNG / PDF, and SVG or HTML visuals rendered to PNG / PDF. Everything runs on the Mac: Mermaid is
kept in DATA/vendor (downloaded once), drawing and export go through WebKit (naim-pdf, see docs.py).
"""
import html
import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import docs
import extensions as ext

VENDOR = ext.DATA / "vendor"
MERMAID_JS = VENDOR / "mermaid.min.js"
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
FORMATS = {".svg", ".png", ".pdf"}
THEMES = {"default", "neutral", "dark", "forest", "base"}
VH_RE = re.compile(r"(?<![\w-])(\d*\.?\d+)[dsl]?vh\b")  # 100vh, 50dvh…: screen heights in a page's CSS
SCREEN_H = 800  # a laptop screen, for those heights when a whole page is captured
LAST_REPORT = {}  # the last page rendered: its errors, its canvases, how many stayed blank


class DiagramError(Exception):
    pass


def mermaid_js():
    """Local copy of Mermaid (downloaded on first use: diagrams then work offline)."""
    if MERMAID_JS.exists() and MERMAID_JS.stat().st_size > 100_000:
        return MERMAID_JS
    VENDOR.mkdir(parents=True, exist_ok=True)
    tmp = MERMAID_JS.with_suffix(".part")
    try:
        with urllib.request.urlopen(MERMAID_URL, timeout=60) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
    except OSError as e:
        raise DiagramError(f"téléchargement de Mermaid impossible ({e}) : connexion internet nécessaire la première fois")
    tmp.replace(MERMAID_JS)
    return MERMAID_JS


HLJS_JS = VENDOR / "highlight.min.js"
HLJS_URL = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"  # BSD-3, the common languages


def highlight_js():
    """Local copy of highlight.js (code coloured in the window: Python, JavaScript, HTML, Swift, SQL…), downloaded
    once, then read from the Mac."""
    if HLJS_JS.exists() and HLJS_JS.stat().st_size > 50_000:
        return HLJS_JS
    VENDOR.mkdir(parents=True, exist_ok=True)
    tmp = HLJS_JS.with_suffix(".part")
    try:
        with urllib.request.urlopen(HLJS_URL, timeout=60) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
    except OSError as e:
        raise DiagramError(f"téléchargement de highlight.js impossible ({e})")
    tmp.replace(HLJS_JS)
    return HLJS_JS


KATEX_DIR = VENDOR / "katex"
KATEX_URL = "https://registry.npmjs.org/katex/-/katex-0.16.11.tgz"
KATEX_FILE_RE = re.compile(r"(katex\.min\.(js|css)|fonts/KaTeX_[A-Za-z0-9_-]+\.woff2)")


def katex_file(name):
    """A file of KaTeX (formulas drawn like in a maths book), downloaded once from npm then read from the Mac: only
    katex.min.js, katex.min.css and its woff2 fonts are kept and served."""
    if not KATEX_FILE_RE.fullmatch(name or ""):
        raise DiagramError("fichier KaTeX inconnu")
    if not (KATEX_DIR / "katex.min.js").exists():
        import io
        import tarfile
        try:
            with urllib.request.urlopen(KATEX_URL, timeout=60) as r:
                data = r.read(20_000_000)
        except OSError as e:
            raise DiagramError(f"téléchargement de KaTeX impossible ({e}) : connexion internet nécessaire la première fois")
        tmp = KATEX_DIR.with_name("katex.part")
        shutil.rmtree(tmp, ignore_errors=True)
        (tmp / "fonts").mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for m in tar.getmembers():
                rel = m.name.removeprefix("package/dist/")
                if m.isfile() and rel != m.name and KATEX_FILE_RE.fullmatch(rel):
                    (tmp / rel).write_bytes(tar.extractfile(m).read())
        if not (tmp / "katex.min.js").exists():
            shutil.rmtree(tmp, ignore_errors=True)
            raise DiagramError("archive KaTeX incomplète")
        shutil.rmtree(KATEX_DIR, ignore_errors=True)
        tmp.replace(KATEX_DIR)
    f = KATEX_DIR / name
    if not f.is_file():
        raise DiagramError("fichier KaTeX absent")
    return f


FONTS_DIR = VENDOR / "fonts"
INTER_URL = "https://registry.npmjs.org/@fontsource-variable/inter/-/inter-5.3.0.tgz"
FONT_FILE_RE = re.compile(r"inter-latin(-ext)?-wght-(normal|italic)\.woff2")


def font_file(name):
    """Naim's text font (Inter, SIL OFL licence), downloaded once from npm then read from the Mac: only its woff2 files
    for Latin and Latin Extended (French and its accents), upright and italic, all weights in one variable file."""
    if not FONT_FILE_RE.fullmatch(name or ""):
        raise DiagramError("police inconnue")
    f = FONTS_DIR / name
    if not f.is_file():
        import io
        import tarfile
        try:
            with urllib.request.urlopen(INTER_URL, timeout=60) as r:
                data = r.read(30_000_000)
        except OSError as e:
            raise DiagramError(f"téléchargement de la police impossible ({e})")
        FONTS_DIR.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for m in tar.getmembers():
                n = m.name.rsplit("/", 1)[-1]
                if m.isfile() and m.name.startswith("package/files/") and FONT_FILE_RE.fullmatch(n):
                    (FONTS_DIR / n).write_bytes(tar.extractfile(m).read())
        if not f.is_file():
            raise DiagramError("police absente de l'archive")
    return f


def _clean(code):
    code = str(code or "").strip()
    if code.startswith("```"):  # a fenced block pasted as is
        code = code.split("\n", 1)[1] if "\n" in code else ""
        code = code.rsplit("```", 1)[0]
    return code.strip()


# Naim's own style for diagrams (the default), the one of its PDFs (pdf-pro theme.css): warm and quiet — groups on
# one cream with a hairline border and a small title in the accent (like the date above a PDF's title), white boxes
# with a thin warm border, light arrows, the title in the PDF's serif. Colour only where it means something (an
# artery, a danger), in the PDF's soft tones: a colour a diagram asks for is brought into them.
INK, MUTED, LINE, CREAM, ACCENT = "#1f1e1d", "#6b6a65", "#e6e2d8", "#faf7f1", "#c96442"
SERIF = '"Iowan Old Style", "Charter", "Palatino", Georgia, serif'
HOUSE_VARS = {"background": "#ffffff", "fontSize": "17px", "primaryColor": "#ffffff", "primaryTextColor": INK,
              "primaryBorderColor": "#d3ccbd", "secondaryColor": CREAM, "tertiaryColor": CREAM, "lineColor": "#aaa396",
              "textColor": INK, "titleColor": INK, "clusterBkg": CREAM, "clusterBorder": LINE,
              "edgeLabelBackground": "#ffffff", "nodeTextColor": INK, "mainBkg": "#ffffff", "noteBkgColor": "#f4e3db",
              "noteBorderColor": "#e6c9bb", "noteTextColor": INK, "actorBkg": "#ffffff", "actorBorder": "#d3ccbd",
              "actorTextColor": INK, "signalColor": MUTED, "signalTextColor": INK, "labelBoxBkgColor": CREAM,
              "labelBoxBorderColor": LINE, "pie1": ACCENT, "pie2": "#4f7fae", "pie3": "#6f8452", "pie4": "#b7862b",
              "pie5": "#8a7f72", "pie6": "#b4473f", "pie7": "#a99f8f", "pie8": "#d9d2c3", "pieStrokeColor": "#ffffff"}
HOUSE_CSS = (".node rect,.node polygon,.node circle,.node path{stroke-width:1px} .node rect{rx:6px;ry:6px}"
             ".cluster rect{rx:10px;ry:10px;stroke-width:1px}"
             f".cluster-label text,.cluster text{{fill:{ACCENT}!important;font-size:11px;font-weight:600;"
             "letter-spacing:.14em;text-transform:uppercase}"
             ".flowchart-link,.edgePath .path{stroke-width:1.2px} .marker{fill:#aaa396;stroke:#aaa396}"
             f".edgeLabel,.edgeLabel text{{fill:{MUTED};color:{MUTED};font-size:13px}}"
             f".titleText,.flowchartTitleText{{font-family:{SERIF}!important;font-size:22px;font-weight:500;fill:{INK}}}")
# the palette a diagram's own colours are brought into (pdf-pro's soft tones): (fill, border, text)
TONES = {"rouge": ("#f6e1df", "#c98a84", "#7e2b25"), "bleu": ("#e5edf5", "#9db5cf", "#2c4a74"),
         "vert": ("#e9eee0", "#a9b894", "#44552f"), "ambre": ("#f5ecd9", "#d6bb86", "#6e4f14"),
         "violet": ("#eeeaf2", "#b7abc9", "#4f3a73"), "turquoise": ("#e4efec", "#9cc0b6", "#2f5c52"),
         "accent": ("#f4e3db", ACCENT, INK), "doux": (CREAM, "#e0d9cb", MUTED), "fonce": (INK, INK, "#ffffff")}
_HEX_RE = re.compile(r"fill\s*:\s*#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")


def _tone(hexa):
    """The house tone nearest to a colour: by its hue, grey when it has none."""
    import colorsys
    h = hexa if len(hexa) == 6 else "".join(c * 2 for c in hexa)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    if sat < 0.15 or (light > 0.93 and sat < 0.5 and max(r, g, b) - min(r, g, b) < 0.06):
        return "fonce" if light < 0.3 else "doux"
    deg = hue * 360
    return ("rouge" if deg < 20 or deg >= 330 else "ambre" if deg < 65 else "vert" if deg < 150 else
            "turquoise" if deg < 190 else "bleu" if deg < 255 else "violet")


def house_code(code):
    """A flowchart in Naim's style: its classDef / style colours brought into the house palette, and the house
    classes (rouge, bleu, vert, ambre, violet, turquoise, accent, doux, fonce) ready to use with « class X rouge »."""
    if not re.match(r"\s*(?:---[\s\S]*?---\s*)?(flowchart|graph)\b", code):
        return code

    def tone_props(name):
        fill, stroke, text = TONES[name]
        return f"fill:{fill},stroke:{stroke},color:{text}"

    def fix(m):
        head, props = m.group(1), m.group(2)
        found = _HEX_RE.search(props)
        if not found:
            return m.group(0)
        rest = ",".join(x for x in props.split(",") if x.split(":")[0].strip() not in ("fill", "stroke", "color", "stroke-width"))
        return f"{head} {tone_props(_tone(found.group(1)))}" + (f",{rest}" if rest else "")
    out = re.sub(r"^(\s*(?:classDef|style)\s+\S+)\s+(.+)$", fix, code, flags=re.M)
    # one colour put on every box of a diagram with groups says nothing: it gives way to the plain style
    if len(re.findall(r"^\s*subgraph\b", out, re.M)) >= 2:
        own = [n for n in re.findall(r"^\s*classDef\s+(\S+)", out, re.M) if n not in TONES]
        if len(own) == 1:
            out = re.sub(rf"^\s*classDef\s+{re.escape(own[0])}\b.*$\n?", "", out, flags=re.M)
            out = re.sub(rf"^\s*class\s+[\w,\s-]+\s+{re.escape(own[0])}\s*$\n?", "", out, flags=re.M)
            out = out.replace(f":::{own[0]}", "")
    defined = set(re.findall(r"^\s*classDef\s+(\S+)", out, re.M))
    extra = "\n".join(f"  classDef {n} {tone_props(n)}" for n in TONES if n not in defined)
    return out.rstrip() + "\n" + extra + "\n"


def mermaid_page(code, theme="default", background="white", zoom=1):
    if theme == "default":  # Naim's own style
        code = house_code(code)
        style = (f"theme: 'base', themeVariables: {json.dumps(HOUSE_VARS)}, themeCSS: {json.dumps(HOUSE_CSS)},")
        # Mermaid packs groups one against the other: each frame drawn a little inside, so they breathe
        inset = ("document.querySelectorAll('#naim-capture .cluster > rect').forEach(r => { const g = 6;"
                 " for (const [k, d] of [['x', g], ['y', g], ['width', -2 * g], ['height', -2 * g]])"
                 " r.setAttribute(k, parseFloat(r.getAttribute(k)) + d); });")
    else:
        style, inset = f"theme: {json.dumps(theme)},", ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:{background}}} #naim-capture{{display:inline-block;padding:16px;background:{background};zoom:{zoom}}}
#naim-capture svg{{max-width:none !important;height:auto}}</style>
<script src="{MERMAID_JS.as_uri()}"></script></head><body><div id="naim-capture"></div>
<script id="src" type="text/plain">{html.escape(code)}</script>
<script>
window.__naimWait = true;
(async () => {{
  try {{
    const txt = document.createElement('textarea'); txt.innerHTML = document.getElementById('src').textContent;
    mermaid.initialize({{startOnLoad: false, securityLevel: 'strict', {style}
      fontFamily: '-apple-system, "SF Pro Text", Helvetica, Arial, sans-serif',
      flowchart: {{htmlLabels: false, curve: 'basis', nodeSpacing: 34, rankSpacing: 44, padding: 12, diagramPadding: 6,
        subGraphTitleMargin: {{top: 16, bottom: 8}}}}}});
    const {{svg}} = await mermaid.render('naim-diagram', txt.value);
    document.getElementById('naim-capture').innerHTML = svg;
    {inset}
    window.__naimReady = true;
  }} catch (e) {{ window.__naimError = 'Mermaid : ' + (e && e.message ? e.message : e); }}
}})();
</script></body></html>"""


def _render_page(page_html, out, workdir=None):
    """Render an HTML page (string) to out (.svg/.png/.pdf) with naim-pdf."""
    with tempfile.TemporaryDirectory(dir=workdir) as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(page_html)
        return _run(page, out, "fit")


def _run(page, out, paper):
    r = subprocess.run([docs.pdf_tool(), str(page), str(out), paper], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise DiagramError(r.stderr.strip()[-600:] or "rendu impossible")
    return json.loads(r.stdout or "{}")


def _describe(out, info):
    size = f"{out.stat().st_size // 1024 or 1} Ko"
    dims = f", {info['width']}×{info['height']} px" if info.get("width") else ""
    return f"{out} créé ({size}{dims})"


def render(code, output, engine="mermaid", theme="default", background="white"):
    """Draw a diagram into output (.svg, .png or .pdf). engine: mermaid | graphviz. Returns a description."""
    out = Path(output)
    fmt = out.suffix.lower()
    if fmt not in FORMATS:
        raise DiagramError(f"format {fmt or '?'} : choisis .svg, .png ou .pdf")
    code = _clean(code)
    if not code:
        raise DiagramError("code du schéma vide")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Graphviz: « digraph G { … } » / « graph { … } ». Mermaid also starts with « graph TD » or « flowchart LR » but has
    # no brace: written in Mermaid, it is drawn by Mermaid even when Graphviz was asked for
    dot_like = bool(re.match(r"\s*(strict\s+)?(di)?graph\b[^\n{]*\{", code))
    mermaid_like = bool(re.match(r"\s*((graph|flowchart)\s+(TD|TB|BT|LR|RL)\b|(sequenceDiagram|classDiagram|stateDiagram"
                                 r"(-v2)?|erDiagram|gantt|pie|mindmap|journey|timeline|gitGraph|quadrantChart)\b)", code))
    if dot_like or (engine == "graphviz" and not mermaid_like):
        dot = shutil.which("dot") or next((p for p in ("/opt/homebrew/bin/dot", "/usr/local/bin/dot") if Path(p).exists()), None)
        if not dot:
            raise DiagramError("Graphviz n'est pas installé (brew install graphviz) : écris plutôt le schéma en Mermaid")
        r = subprocess.run([dot, f"-T{fmt[1:]}", "-Gdpi=192" if fmt == ".png" else "-Gdpi=96", "-o", str(out)],
                           input=code, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise DiagramError("Graphviz : " + r.stderr.strip()[-400:])
        return _describe(out, {})
    theme = theme if theme in THEMES else "default"
    mermaid_js()
    # a PNG is drawn twice as large: sharp and readable in a document or on a big screen (the SVG and PDF are vectors)
    info = _render_page(mermaid_page(code, theme, background or "white", zoom=2 if fmt == ".png" else 1), out)
    return _describe(out, info)


def export_visual(source, output):
    """An .svg or .html visual (logo, banner, poster, chart page) -> .png (2x) or single-page .pdf."""
    src, out = Path(source), Path(output)
    fmt = out.suffix.lower()
    if fmt not in (".png", ".pdf"):
        raise DiagramError("export d'un visuel : .png ou .pdf")
    if src.suffix.lower() == ".svg":
        page = (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:transparent}}'
                f'#naim-capture{{display:inline-flex}}#naim-capture svg{{display:block}}</style></head><body><div id="naim-capture">'
                f'{src.read_text(errors="replace")}</div></body></html>')
        info = _render_page(page, out, workdir=None)
    elif src.suffix.lower() in (".html", ".htm"):
        text = src.read_text(errors="replace")
        if not VH_RE.search(text):
            info = _run(src, out, "fit")
        else:  # the capture grows the window to the whole page, so 100vh would become the page height: a real screen's
            tmp = src.with_name(f".naim-rendu-{src.stem}.html")  # beside it: its images keep their relative paths
            try:
                tmp.write_text(VH_RE.sub(lambda m: f"{float(m.group(1)) * SCREEN_H / 100:g}px", text))
                info = _run(tmp, out, "fit")
            finally:
                tmp.unlink(missing_ok=True)
    else:
        raise DiagramError("source d'un visuel : fichier .svg ou .html")
    global LAST_REPORT
    LAST_REPORT = info
    return _describe(out, info)
