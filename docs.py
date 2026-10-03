"""Read office documents attached in the chat: PDF (scanned pages with OCR), Word, Excel, PowerPoint, RTF, ODT.

Naim is a text model: the document's text is extracted here and sent to it. In agent mode the original file is
also saved into the project (.naim/pieces-jointes/) so Naim can process it with its tools (scripts, skills).
"""
import csv
import io
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import computer as cu

MAX_CHARS = 60_000   # ~15k tokens: the rest is cut (the whole file stays available in the project in agent mode)
KINDS = {".pdf": "PDF", ".docx": "Word", ".doc": "Word", ".rtf": "RTF", ".odt": "OpenDocument", ".pages": "Pages",
         ".xlsx": "Excel", ".xlsm": "Excel", ".pptx": "PowerPoint", ".html": "HTML"}


class DocError(Exception):
    pass


def _ns(tag):
    return tag.split("}", 1)[-1]


def pdf_text(path):
    r = subprocess.run([cu.helper(), "pdf", str(path), "200"], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise DocError("PDF illisible : " + r.stderr.strip()[-200:])
    import json
    data = json.loads(r.stdout)
    pages = [t.strip() for t in data["text"]]
    body = "\n\n".join(f"--- Page {i + 1} ---\n{t}" for i, t in enumerate(pages) if t)
    note = f"{data['pages']} page{'s' if data['pages'] > 1 else ''}" + (f" (lues : {len(pages)})" if data["pages"] > len(pages) else "")
    return body, note


def textutil(path):
    r = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(path)], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise DocError("document illisible : " + r.stderr.decode(errors="replace")[-200:])
    return r.stdout.decode("utf-8", errors="replace"), ""


def xlsx_text(path):
    """Every sheet as CSV (values, not formulas)."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
                shared.append("".join(t.text or "" for t in si.iter() if _ns(t.tag) == "t"))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        names = [s.get("name") for s in wb.iter() if _ns(s.tag) == "sheet"]
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        sheet_files = []
        for s in (s for s in wb.iter() if _ns(s.tag) == "sheet"):
            rid = next((v for k, v in s.attrib.items() if k.endswith("}id")), None)
            t = targets.get(rid, "")
            sheet_files.append("xl/" + t.lstrip("/").removeprefix("xl/"))
        parts = []
        for name, f in zip(names, sheet_files):
            if f not in z.namelist():
                continue
            rows = []
            for row in (e for e in ET.fromstring(z.read(f)).iter() if _ns(e.tag) == "row"):
                cells = {}
                for c in (e for e in row if _ns(e.tag) == "c"):
                    col = re.match(r"[A-Z]+", c.get("r", "A"))
                    idx = 0
                    for ch in (col.group(0) if col else "A"):
                        idx = idx * 26 + ord(ch) - 64
                    v = next((e.text for e in c if _ns(e.tag) == "v"), None)
                    if c.get("t") == "s" and v is not None:
                        v = shared[int(v)]
                    elif c.get("t") == "inlineStr":
                        v = "".join(t.text or "" for t in c.iter() if _ns(t.tag) == "t")
                    cells[idx] = v or ""
                if cells:
                    rows.append([cells.get(i, "") for i in range(1, max(cells) + 1)])
            buf = io.StringIO()
            csv.writer(buf, lineterminator="\n").writerows(rows)
            parts.append(f"--- Feuille « {name} » ({len(rows)} lignes) ---\n{buf.getvalue()}")
    return "\n".join(parts), f"{len(parts)} feuille{'s' if len(parts) > 1 else ''}"


def pptx_text(path):
    with zipfile.ZipFile(path) as z:
        slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
        parts = []
        for i, n in enumerate(slides, 1):
            paras = []
            for p in (e for e in ET.fromstring(z.read(n)).iter() if _ns(e.tag) == "p"):
                t = "".join(r.text or "" for r in p.iter() if _ns(r.tag) == "t").strip()
                if t:
                    paras.append(t)
            parts.append(f"--- Diapositive {i} ---\n" + "\n".join(paras))
    return "\n\n".join(parts), f"{len(slides)} diapositives"


def extract(path):
    """(text, short note) of a document; raises DocError."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        text, note = pdf_text(path)
    elif ext in (".xlsx", ".xlsm"):
        text, note = xlsx_text(path)
    elif ext == ".pptx":
        text, note = pptx_text(path)
    elif ext in (".docx", ".doc", ".rtf", ".odt", ".html", ".webarchive", ".pages"):
        text, note = textutil(path)
    else:
        raise DocError(f"format {ext or 'inconnu'} non pris en charge")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise DocError("aucun texte trouvé dans le document")
    if len(text) > MAX_CHARS:
        note += f" · tronqué à {MAX_CHARS // 1000}k caractères sur {len(text) // 1000}k"
        text = text[:MAX_CHARS] + "\n… (suite coupée)"
    return text, note


def extract_bytes(name, data, project=None):
    """Extract from uploaded bytes; in agent mode also save the original into the project. Returns a dict."""
    safe = re.sub(r"[^\w.\- ]", "_", Path(name).name) or "document"
    saved = None
    if project and Path(project).is_dir():
        dest_dir = Path(project) / ".naim" / "pieces-jointes"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / safe
        dest.write_bytes(data)
        saved = str(dest.relative_to(project))
        text, note = extract(dest)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / safe
            p.write_bytes(data)
            text, note = extract(p)
    return {"text": text, "note": note, "kind": KINDS.get(Path(safe).suffix.lower(), "Document"), "saved": saved}


# ============================================================================ conversions (all native to macOS)
PDF_SRC = Path(__file__).with_name("naim_pdf.swift")
PDF_BIN = cu.ext.DATA / "bin" / "naim-pdf"
TEXTUTIL_IN = {".docx", ".doc", ".rtf", ".odt", ".html", ".htm", ".txt", ".webarchive", ".pages"}
TEXTUTIL_OUT = {".docx": "docx", ".doc": "doc", ".rtf": "rtf", ".odt": "odt", ".html": "html", ".txt": "txt"}


def pdf_tool():
    """naim-pdf (HTML -> paginated PDF with WebKit), compiled on first use and when its source changes."""
    import hashlib
    h = hashlib.sha1(PDF_SRC.read_bytes()).hexdigest()[:16]
    stamp = PDF_BIN.with_name(".naim-pdf.hash")
    if PDF_BIN.exists() and stamp.exists() and stamp.read_text().strip() == h:
        return str(PDF_BIN)
    PDF_BIN.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["swiftc", "-O", str(PDF_SRC), "-o", str(PDF_BIN)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise DocError("compilation de naim-pdf impossible : " + r.stderr[-400:])
    stamp.write_text(h)
    return str(PDF_BIN)


def markdown_html(text, title="Document"):
    """Minimal Markdown -> styled HTML (titles, lists, bold, italic, code, links, tables)."""
    import html as H
    out, in_list, table = [], None, []

    def inline(s):
        s = H.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)

    def flush_table():
        if table:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in table if not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", r)]
            out.append("<table>" + "".join(("<tr>" + "".join(f"<{'th' if i == 0 else 'td'}>{inline(c)}</{'th' if i == 0 else 'td'}>" for c in row) + "</tr>")
                                            for i, row in enumerate(rows)) + "</table>")
            table.clear()
    for line in text.splitlines():
        if line.strip().startswith("|"):
            table.append(line)
            continue
        flush_table()
        m = re.match(r"^\s*([-*]|\d+\.)\s+(.*)", line)
        kind = ("ol" if m and m.group(1)[0].isdigit() else "ul") if m else None
        if in_list and kind != in_list:
            out.append(f"</{in_list}>")
            in_list = None
        if m:
            if not in_list:
                out.append(f"<{kind}>")
                in_list = kind
            out.append(f"<li>{inline(m.group(2))}</li>")
        elif (h := re.match(r"^(#{1,6})\s+(.*)", line)):
            out.append(f"<h{len(h.group(1))}>{inline(h.group(2))}</h{len(h.group(1))}>")
        elif re.match(r"^\s*(---|\*\*\*)\s*$", line):
            out.append("<hr>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    flush_table()
    if in_list:
        out.append(f"</{in_list}>")
    css = ("@page{size:A4;margin:18mm 16mm}body{font-family:-apple-system,Helvetica,Arial,sans-serif;font-size:11pt;"
           "line-height:1.45;color:#222}h1{font-size:22pt;color:#1f3a5f;margin:0 0 6pt}h2{font-size:14pt;color:#1f3a5f;"
           "border-bottom:1.5pt solid #1f3a5f;padding-bottom:2pt;margin:14pt 0 6pt}h3{font-size:12pt;margin:10pt 0 4pt}"
           "p{margin:4pt 0}ul,ol{margin:4pt 0 4pt 16pt;padding:0}li{margin:2pt 0}table{border-collapse:collapse;width:100%;"
           "margin:6pt 0}th,td{border:1px solid #ccc;padding:4pt 6pt;text-align:left}th{background:#eef2f7}"
           "code{font-family:Menlo,monospace;font-size:9.5pt;background:#f3f3f3;padding:0 3px}a{color:#1f5fa8}")
    return (f"<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\"><title>{H.escape(title)}</title>"
            f"<style>{css}</style></head><body>{''.join(out)}</body></html>")


def convert(src, dst, paper="A4", orientation="portrait"):
    """Convert a document: HTML / Word / RTF / ODT / Markdown / text -> PDF, and between Word, RTF, ODT, HTML, text.

    Returns a short description of the result; raises DocError.
    """
    src, dst = Path(src), Path(dst)
    if not src.is_file():
        raise DocError(f"fichier introuvable : {src}")
    a, b = src.suffix.lower(), dst.suffix.lower()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if b == ".pdf":
        with tempfile.TemporaryDirectory() as tmp:
            if a in (".html", ".htm"):
                page = src  # keep it next to its images / CSS
            elif a in (".md", ".markdown"):
                page = src.with_name(f".{src.stem}-naim.html")
                page.write_text(markdown_html(src.read_text(errors="replace"), src.stem))
            elif a in TEXTUTIL_IN:
                page = Path(tmp) / "page.html"
                r = subprocess.run(["textutil", "-convert", "html", str(src), "-output", str(page)], capture_output=True, timeout=120)
                if r.returncode != 0:
                    raise DocError("conversion en HTML impossible : " + r.stderr.decode(errors="replace")[-200:])
                html = page.read_text(errors="replace")
                page.write_text(html.replace("</head>", "<style>@page{size:A4;margin:16mm}body{-webkit-print-color-adjust:exact}</style></head>", 1))
            else:
                raise DocError(f"conversion {a} -> PDF non prise en charge (formats : .html .md .docx .doc .rtf .odt .txt)")
            try:
                r = subprocess.run([pdf_tool(), str(page), str(dst), paper, orientation], capture_output=True, text=True, timeout=120)
            finally:
                if page.name.endswith("-naim.html"):
                    page.unlink(missing_ok=True)
        if r.returncode != 0:
            raise DocError("création du PDF impossible : " + r.stderr.strip()[-300:])
        import json
        pages = json.loads(r.stdout).get("pages", 0)
        return f"{dst} créé ({pages} page{'s' if pages > 1 else ''}, {dst.stat().st_size // 1024} Ko)"
    if b in TEXTUTIL_OUT and a in TEXTUTIL_IN:
        r = subprocess.run(["textutil", "-convert", TEXTUTIL_OUT[b], str(src), "-output", str(dst)], capture_output=True, timeout=120)
        if r.returncode != 0:
            raise DocError("conversion impossible : " + r.stderr.decode(errors="replace")[-200:])
        return f"{dst} créé ({dst.stat().st_size // 1024} Ko)"
    if a == ".pdf" and b in (".txt", ".md"):
        text, note = pdf_text(src)
        dst.write_text(text)
        return f"{dst} créé (texte du PDF, {note})"
    raise DocError(f"conversion {a} -> {b} non prise en charge. Possible : .html/.md/.docx/.doc/.rtf/.odt/.txt -> .pdf ; "
                   f"entre .docx .doc .rtf .odt .html .txt ; .pdf -> .txt. Pour .xlsx / .pptx, écris un script Python.")


PREVIEWS = cu.ext.DATA / "apercus"


def preview_png(path, page=1, width=1100):
    """(png path, note): an image of a deliverable, to look at it. PDF page, image, SVG / HTML, Office (Quick Look)."""
    import diagrams
    import hashlib
    path = Path(path)
    ext = path.suffix.lower()
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{path}:{path.stat().st_mtime}:{page}:{width}".encode()).hexdigest()[:16]
    out = PREVIEWS / f"{key}.png"
    for old in sorted(PREVIEWS.glob("*.png"), key=lambda f: f.stat().st_mtime)[:-60]:
        old.unlink(missing_ok=True)  # keep the cache small
    note = ""
    if ext == ".pdf":
        r = subprocess.run([pdf_tool(), str(path), str(out), str(page), str(width)], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise DocError(r.stderr.strip()[-300:] or "rendu du PDF impossible")
        import json
        info = json.loads(r.stdout)
        note = f"page {info['page']} sur {info['pages']}"
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".heic", ".webp", ".tiff", ".bmp"):
        r = subprocess.run(["sips", "-s", "format", "png", "-Z", str(width), str(path), "--out", str(out)], capture_output=True, timeout=60)
        if r.returncode != 0:
            raise DocError("image illisible")
        note = "image"
    elif ext in (".svg", ".html", ".htm"):
        diagrams.export_visual(path, out)
        subprocess.run(["sips", "-Z", str(width), str(out)], capture_output=True, timeout=60)
        note = "rendu de la page" if ext != ".svg" else "rendu du SVG"
    else:  # Word, PowerPoint, Excel, Pages, Keynote, Numbers, RTF…: Quick Look thumbnail of the first page
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(["qlmanage", "-t", "-s", str(width), "-o", tmp, str(path)], capture_output=True, timeout=60)
            made = list(Path(tmp).glob("*.png"))
            if not made:
                raise DocError(f"aperçu impossible pour {path.name}")
            made[0].replace(out)
        note = "première page (aperçu Quick Look)"
    with open(out, "rb") as f:
        head = f.read(24)
    w, h = int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
    return out, f"{note}, {w}×{h} px"
