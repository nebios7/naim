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


def _clean(code):
    code = str(code or "").strip()
    if code.startswith("```"):  # a fenced block pasted as is
        code = code.split("\n", 1)[1] if "\n" in code else ""
        code = code.rsplit("```", 1)[0]
    return code.strip()


def mermaid_page(code, theme="default", background="white"):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:{background}}} #naim-capture{{display:inline-block;padding:16px;background:{background}}}
#naim-capture svg{{max-width:none !important;height:auto}}</style>
<script src="{MERMAID_JS.as_uri()}"></script></head><body><div id="naim-capture"></div>
<script id="src" type="text/plain">{html.escape(code)}</script>
<script>
window.__naimWait = true;
(async () => {{
  try {{
    const txt = document.createElement('textarea'); txt.innerHTML = document.getElementById('src').textContent;
    mermaid.initialize({{startOnLoad: false, theme: {json.dumps(theme)}, securityLevel: 'strict',
      fontFamily: '-apple-system, Helvetica, Arial, sans-serif', flowchart: {{htmlLabels: false}}}});
    const {{svg}} = await mermaid.render('naim-diagram', txt.value);
    document.getElementById('naim-capture').innerHTML = svg;
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
    info = _render_page(mermaid_page(code, theme, background or "white"), out)
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
        info = _run(src, out, "fit")
    else:
        raise DiagramError("source d'un visuel : fichier .svg ou .html")
    return _describe(out, info)
