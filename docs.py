"""Read office documents attached in the chat: PDF (scanned pages with OCR), Word, Excel, PowerPoint, RTF, ODT.

Naim is a text model: the document's text is extracted here and sent to it. In agent mode the original file is
also saved into the project (.naim/pieces-jointes/) so Naim can process it with its tools (scripts, skills).
"""
import csv
import io
import re
import subprocess
import tempfile
import threading
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import computer as cu

MAX_CHARS = 60_000   # ~15k tokens: the rest is cut (the whole file stays available in the project in agent mode)
ATTACH_HEAD = 12_000  # a document joined to a message that is longer than MAX_CHARS: only this beginning is pasted
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


def pictures_of(path):
    """The pictures inside a Word file (a CV's photo…), told after its text: the text alone does not show them."""
    import zipfile
    try:
        with zipfile.ZipFile(path) as z:
            pics = [i for i in z.infolist() if i.filename.startswith("word/media/") and not i.filename.endswith("/")]
    except (OSError, zipfile.BadZipFile):
        return ""
    if not pics:
        return ""
    names = ", ".join(f"{Path(i.filename).name} ({max(1, i.file_size // 1024)} Ko)" for i in pics[:8])
    return (f"\n\n[Images dans ce document : {names}. Elles sont DANS le fichier (une photo de CV en fait partie) : "
            f"pour en sortir une, unzip -o -j \"{path}\" word/media/<nom> -d <dossier>.]")


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
        if ext == ".docx":
            text += pictures_of(path)
    else:
        raise DocError(f"format {ext or 'inconnu'} non pris en charge")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise DocError("aucun texte trouvé dans le document")
    if len(text) > MAX_CHARS:
        note += f" · tronqué à {MAX_CHARS // 1000}k caractères sur {len(text) // 1000}k"
        text = text[:MAX_CHARS] + "\n… (suite coupée)"
    return text, note


def extract_bytes(name, data, project=None, keep=None):
    """Extract from uploaded bytes. keep: a function saving the original (its path back), so Naim can open it later.
    Returns a dict."""
    safe = re.sub(r"[^\w.\- ]", "_", Path(name).name) or "document"
    saved = None
    if keep:
        dest = Path(keep(safe, data))
        saved = str(dest)
        text, note = extract(dest)
    elif project and Path(project).is_dir():
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
    if saved and len(text) > MAX_CHARS:
        # a book-sized document (cut anyway): only its beginning goes into the message. 60k characters pasted there
        # were ~17k tokens read again at every step of the conversation (minutes each time); the whole file is saved,
        # Naim reads the rest by pieces with its tools
        text = (text[:ATTACH_HEAD] + f"\n\n[… seul le début du document est collé ici (il est bien plus long). Le document "
                f"entier est enregistré : {saved}. Lis la suite par morceaux avec tes outils (read_file sur ce fichier, ou "
                "run_command avec un script) ; pour traduire un livre, le skill traduction-livre.]")
        note = re.sub(r"tronqué à \d+k caractères", f"début collé : {ATTACH_HEAD // 1000}k caractères", note)
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
    """Minimal Markdown -> styled HTML (titles, lists, bold, italic, code, links, images, tables)."""
    import html as H
    out, in_list, table = [], None, []

    def inline(s):
        s = H.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        # an image (a diagram in a course): drawn, not its Markdown text printed in the PDF
        s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" style="max-width:100%;height:auto">', s)
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)

    def flush_table():
        if table:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in table if not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", r)]
            out.append("<table>" + "".join(("<tr>" + "".join(f"<{'th' if i == 0 else 'td'}>{inline(c)}</{'th' if i == 0 else 'td'}>" for c in row) + "</tr>")
                                            for i, row in enumerate(rows)) + "</table>")
            table.clear()
    # an image with its credit line under it (« ![Le cœur](coeur.jpg) » then « *Source : Wikimedia Commons — …* »):
    # one figure, its caption and its credit — as the HTML figure the images tool gives
    text = re.sub(r"^[ \t]*!\[([^\]]*)\]\(([^)\s]+)\)[ \t]*\n[ \t]*\*{0,2}((?:Source|Crédit|Credit)\s*:[^\n]*?)\*{0,2}[ \t]*$",
                  lambda m: (f'<figure><img src="{H.escape(m.group(2))}" alt="{H.escape(m.group(1))}"><figcaption>'
                             + (f"{H.escape(m.group(1))}. " if m.group(1).strip() else "")
                             + f'<span class="credit">{H.escape(m.group(3).strip())}</span></figcaption></figure>'),
                  text or "", flags=re.M | re.I)
    for line in text.splitlines():
        if re.match(r"\s*</?(figure|img|div|table|section|figcaption|svg|br|hr|span|p)\b", line, re.I):
            out.append(line)  # HTML written in the Markdown (a figure pasted from the images tool): kept as it is
            continue
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
        elif (im := re.match(r"^\s*!\[([^\]]*)\]\(([^)\s]+)\)\s*$", line)):
            # an image alone: a figure (no caption under it — a diagram already has its title, said twice it looks amateur)
            out.append(f'<figure style="margin:10pt 0;text-align:center;break-inside:avoid">'
                       f'<img src="{H.escape(im.group(2))}" alt="{H.escape(im.group(1))}" style="max-width:100%;max-height:170mm;height:auto;object-fit:contain"></figure>')
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


PDFPRO = Path.home() / ".naim/plugins/pdf-pro/skills/pdf-pro/pdfpro.py"


def pro_html(text, title="Document"):
    """Text, Markdown or an HTML fragment -> a page in the pdf-pro look (the default style of Naim's PDFs);
    the plain look only if pdf-pro is missing."""
    import importlib.util
    text = text or ""
    is_html = bool(re.search(r"<(div|p|h[1-6]|table|section|ul|ol|header|main|article)\b", text, re.I))
    try:
        spec = importlib.util.spec_from_file_location("naim_pdfpro", PDFPRO)
        pro = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pro)
    except Exception:
        return text if is_html else markdown_html(text, title)
    if is_html:
        body = text
    else:
        m = re.search(r"<body[^>]*>(.*)</body>", markdown_html(text, title), re.S | re.I)
        body = m.group(1) if m else text
        course = _as_course(body, text)
        if course:  # a course, a lesson, a revision sheet: the pdf-pro course every time (cover, contents, chapters)
            return pro.page(course, title)
        # the first title as the pdf-pro head: the small clay line above, the band under it (as the covers, compact)
        import datetime
        d = datetime.date.today()
        when = f"{d.day} {'janvier février mars avril mai juin juillet août septembre octobre novembre décembre'.split()[d.month - 1]} {d.year}"
        body = re.sub(r"^\s*<h1[^>]*>(.*?)</h1>", lambda h: f'<header class="prohead"><div class="kicker">{when}</div><h1>{h.group(1)}</h1>'
                      '<div class="band"></div></header>', body, count=1, flags=re.S)
        body = ("<style>.prohead{margin:0 0 8mm}.prohead .kicker{font-size:9pt;letter-spacing:.14em;text-transform:uppercase;"
                "color:var(--clay);font-weight:600}.prohead h1{font-size:26pt;line-height:1.15;margin:3mm 0 0}.prohead .band"
                "{height:3px;width:40mm;background:var(--clay);border-radius:2px;margin-top:5mm}</style>") + body
    return pro.page(body, title)


COURSE_RE = re.compile(r"\b(cours|le[çc]ons?|fiche de r[ée]vision|polycopi\w*|support de cours|module|tutoriel|formation)\b", re.I)


def _as_course(body, md):
    """A course written in Markdown -> the pdf-pro course (the model every course follows): a cover (kicker, title,
    subtitle, Auteur / Date / Durée), a contents page, one numbered chapter per « ## ». None when it is not a course
    (one title, then its chapters). A PDF made from Markdown looked different from one made from the model."""
    import datetime
    import html as H
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    if not h1 or not COURSE_RE.search(re.sub(r"<[^>]+>", "", h1.group(1)) + " " + md[:300]):
        return None
    rest = body[h1.end():]
    sub = ""
    first = re.match(r"\s*(?:<hr>\s*)*<h2[^>]*>(.*?)</h2>", rest, re.S)
    if first and not re.search(r"<h2", rest[first.end():first.end() + 400]) and re.match(r"\s*(?:<hr>\s*)*<h[23]", rest[first.end():]):
        sub, rest = first.group(1), rest[first.end():]  # a second title right under the first one: the subtitle
    rest = re.sub(r"<hr>", "", rest)
    lv = "h2" if "<h2" in rest else "h3"  # the chapters: the biggest titles left (« ## », or « ### » under a subtitle)
    parts = re.split(rf"(<{lv}[^>]*>.*?</{lv}>)", rest, flags=re.S)
    intro, chapters = parts[0], [(parts[i], parts[i + 1] if i + 1 < len(parts) else "") for i in range(1, len(parts), 2)]
    if len(chapters) < 2:
        return None
    d = datetime.date.today()
    when = f"{d.day} {'janvier février mars avril mai juin juillet août septembre octobre novembre décembre'.split()[d.month - 1]} {d.year}"
    level = re.search(r"\b((?:\d+(?:re|ère|e)|premi[eè]re|deuxi[eè]me|troisi[eè]me|quatri[eè]me|cinqui[eè]me)\s+ann[ée]e|"
                      r"niveau\s+\w+|d[ée]butant|interm[ée]diaire|avanc[ée])\b",
                      re.sub(r"<[^>]+>", " ", h1.group(1) + " " + sub + " " + md[:400]), re.I)
    dur = re.search(r"^\s*(?:\*\*)?Dur[ée]e(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.+)$", md, re.M | re.I)
    meta = [("Auteur", "Naim"), ("Date", when)] + ([("Durée", H.escape(dur.group(1).strip(" *")))] if dur else [])
    cover = ('<section class="cover"><div><div class="kicker">Cours' + (f" · {H.escape(level.group(1))}" if level else "")
             + f'</div><h1>{h1.group(1)}</h1>' + (f'<div class="subtitle">{sub}</div>' if sub else "")
             + '<div class="band"></div></div><div class="meta">'
             + "".join(f"<div><b>{k}</b>{v}</div>" for k, v in meta) + "</div></section>")
    names = [re.sub(r"<[^>]+>", "", h) for h, _ in chapters]
    # a short course: its chapters follow one another (one per page left them nearly empty), no contents page
    short = len(re.sub(r"<[^>]+>|\s+", " ", rest)) < 6000 or len(chapters) < 3
    toc = "" if short else ('<section class="toc"><h2>Sommaire</h2><ol>'
                            + "".join(f'<li><a href="#c{i}">{n}</a></li>' for i, n in enumerate(names, 1)) + "</ol></section>")
    flow = ' style="page-break-before:auto;break-before:auto;margin-top:9mm"' if short else ""
    out = "".join(f'<section class="chapter" id="c{i}"{flow}><h2><span class="num">{i:02d}</span>{n}</h2>'
                  + (f'<p class="lead">{re.sub(r"<[^>]+>", "", intro).strip()}</p>' if i == 1 and re.sub(r"<[^>]+>|\s", "", intro) else "")
                  + content + "</section>" for i, (n, (_, content)) in enumerate(zip(names, chapters), 1))
    return cover + toc + out


def _figure_trouble(page, base):
    """The figures of a document checked: an image that does not exist (an empty frame in the PDF), and ONE image put
    under several different subjects (the digestive system shown as « appareil urinaire » and « système nerveux »)."""
    import html as H
    said, uses = [], {}
    for tag in re.findall(r"<img\b[^>]*>", page, re.I):
        src = re.search(r"""src=["']([^"']+)["']""", tag)
        if not src or re.match(r"[a-z]+:", src.group(1)):
            continue
        alt = re.search(r"""alt=(["'])(.*?)\1""", tag)  # « l'appareil urinaire »: the apostrophe is part of it
        uses.setdefault(src.group(1), []).append(H.unescape(alt.group(2)).strip() if alt else "")
    missing = [x for x in uses if not (base / x).is_file()]
    # downloaded into a sub-folder (images/cœur.jpg) but written « cœur.jpg »: the right path said, nothing to redraw
    def plain(n):  # « cœur.jpg » and « coeur.jpg », « néphron » and « nephron »: the same name typed two ways
        import unicodedata
        n = n.lower().replace("œ", "oe").replace("æ", "ae")
        return "".join(c for c in unicodedata.normalize("NFD", n) if not unicodedata.combining(c))
    pics = [f for f in base.rglob("*") if f.is_file() and ".git" not in f.parts
            and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".svg", ".gif", ".webp")] if missing else []
    moved = {x: next((f for f in pics if f.name == Path(x).name), None)
             or next((f for f in pics if plain(f.name) == plain(Path(x).name)), None) for x in missing}
    for x, f in moved.items():
        if f:
            said.append(f"image {x} introuvable à cet endroit (cadre vide dans le PDF) : elle est dans "
                        f"{f.relative_to(base)} — écris exactement ce chemin-là dans le document (même orthographe, œ compris), "
                        "puis refais le PDF. Ne copie jamais une autre image sous ce nom")
    missing = [x for x in missing if not moved[x]]
    if missing:
        photos = [x for x in missing if Path(x).suffix.lower() in (".jpg", ".jpeg", ".webp")]
        said.append("image(s) introuvable(s), le cadre est vide dans le PDF : " + ", ".join(missing[:6])
                    + (" — une photo : reprends-la avec images.py (chercher puis prendre vers ce chemin) ;" if photos else " —")
                    + " un schéma : make_diagram vers ce fichier ; sinon retire la figure. Ne mets jamais une autre image "
                    "à la place (une image de poumons sous le nom du cœur est fausse)")
    for x, alts in uses.items():
        subjects = {a.lower() for a in alts if a}
        if len(subjects) > 1:
            said.append(f"la même image {x} est mise pour {len(subjects)} sujets différents ("
                        + ", ".join(sorted(subjects)[:4]) + ") : c'est faux pour tous sauf un. Fais un schéma par sujet, "
                        "chacun dans son fichier, avec son propre contenu")
    return said


def _fresh_diagrams(page, base):
    """The diagrams a PDF shows, drawn again from their kept code (.mmd) just before: an image made in an older style
    (yellow boxes, titles on the line) never comes back into a new document. One without its code stays as it is."""
    import diagrams
    for src in dict.fromkeys(re.findall(r"""<img[^>]+src=["']([^"':]+\.png)["']""", page, re.I)):
        img = base / src
        code = img.with_suffix(".mmd")
        if not code.is_file():  # a copy of a diagram kept elsewhere in the work folder (schemas/x.mmd for ./x.png)
            code = next((c for c in base.rglob(img.stem + ".mmd") if ".git" not in c.parts), None)
        if code and code.is_file() and img.parent.is_dir():
            try:
                diagrams.render(code.read_text(errors="replace"), img)
            except Exception:  # noqa: BLE001 — the old image is better than none
                pass


def _true_size(page, base):
    """Naim's diagrams and images are drawn at twice their size (sharp in print): shown at their real size in the
    PDF, not squeezed from their pixel width (a diagram's text came out at 8 px)."""
    def sized(m):
        src = m.group(1)
        f = (base / src) if not re.match(r"[a-z]+:", src) else None
        if not f or not f.is_file() or f.suffix.lower() != ".png" or "width=" in m.group(0):
            return m.group(0)
        w, _ = _png_size(f)
        return m.group(0).replace("<img ", f'<img width="{w // 2}" ', 1) if w >= 800 else m.group(0)
    return re.sub(r'<img src="([^"]+)"[^>]*>', sized, page)


_BLANK_SEEN = {}


def _blank_pdf(pdf, page=None):
    """A PDF with no text at all, made from a page that has some: an empty print (it said « 2 pages » and was blank)."""
    pdf = Path(pdf)
    if page is not None:
        _BLANK_SEEN.pop(str(pdf), None)
    if str(pdf) in _BLANK_SEEN:
        return _BLANK_SEEN[str(pdf)]
    try:
        if not pdf.is_file() or pdf.stat().st_size > 8000:
            blank = False
        else:
            had_text = page is None or len(re.sub(r"<[^>]+>|\s+", "", Path(page).read_text(errors="replace"))) > 40
            blank = had_text and not pdf_text(pdf)[0].strip()
    except Exception:  # noqa: BLE001 — no verdict: not called empty
        blank = False
    _BLANK_SEEN[str(pdf)] = blank
    return blank


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
                page.write_text(_true_size(pro_html(src.read_text(errors="replace"), src.stem), src.parent))
            elif a in TEXTUTIL_IN:
                page = Path(tmp) / "page.html"
                r = subprocess.run(["textutil", "-convert", "html", str(src), "-output", str(page)], capture_output=True, timeout=120)
                if r.returncode != 0:
                    raise DocError("conversion en HTML impossible : " + r.stderr.decode(errors="replace")[-200:])
                html = page.read_text(errors="replace")
                page.write_text(html.replace("</head>", "<style>@page{size:A4;margin:16mm}body{-webkit-print-color-adjust:exact}</style></head>", 1))
            else:
                raise DocError(f"conversion {a} -> PDF non prise en charge (formats : .html .md .docx .doc .rtf .odt .txt)")
            page_text = page.read_text(errors="replace")
            _fresh_diagrams(page_text, src.parent)
            try:
                for _ in range(2):  # a PDF that came out empty (WebKit busy printing elsewhere): made again once
                    r = subprocess.run([pdf_tool(), str(page), str(dst), paper, orientation], capture_output=True, text=True, timeout=120)
                    if r.returncode != 0 or not _blank_pdf(dst, page):
                        break
            finally:
                if page.name.endswith("-naim.html"):
                    page.unlink(missing_ok=True)
        if r.returncode != 0:
            raise DocError("création du PDF impossible : " + r.stderr.strip()[-300:])
        if _blank_pdf(dst):
            raise DocError(f"le PDF {dst.name} est sorti vide (aucun texte) : relance convert_document ; si ça recommence, "
                           "vérifie la page source avec look_at")
        import json
        pages = json.loads(r.stdout).get("pages", 0)
        said = _figure_trouble(page_text, src.parent)
        return (f"{dst} créé ({pages} page{'s' if pages > 1 else ''}, {dst.stat().st_size // 1024} Ko)"
                + (f"\nPROBLÈME À CORRIGER avant de dire que c'est fini : {' ; '.join(said)}." if said else ""))
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


_PRUNE_LOCK = threading.Lock()


def _prune_previews():
    """Keep the cache small — one at a time, and a file another request just removed is no error: twelve thumbnails
    asked at once (a course's deliverables) made some fail at random, and their cards showed no picture."""
    if not _PRUNE_LOCK.acquire(blocking=False):
        return
    try:
        def age(f):
            try:
                return f.stat().st_mtime
            except OSError:
                return 0
        for old in sorted(PREVIEWS.glob("*.png"), key=age)[:-120]:
            old.unlink(missing_ok=True)
    finally:
        _PRUNE_LOCK.release()


def preview_png(path, page=1, width=1100):
    """(png path, note): an image of a deliverable, to look at it. PDF page, image, SVG / HTML, Office (Quick Look)."""
    import diagrams
    import hashlib
    path = Path(path)
    ext = path.suffix.lower()
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{path}:{path.stat().st_mtime}:{page}:{width}".encode()).hexdigest()[:16]
    out = PREVIEWS / f"{key}.png"
    _prune_previews()
    note, trouble = "", ""
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
        diagrams.LAST_REPORT = {}
        diagrams.export_visual(path, out)
        note = "rendu de la page" if ext != ".svg" else "rendu du SVG"
        trouble = page_trouble(diagrams.LAST_REPORT, path) if ext != ".svg" else ""
        w, h = _png_size(out)
        screen = int(w * 1.25)
        if ext != ".svg" and h > screen * 1.2:  # a long page squeezed into one image is unreadable: one screen at a time
            screens = -(-h // screen)
            page = max(1, min(int(page or 1), screens))
            top = (page - 1) * screen  # sips reads an offset of 0 as « centred »: 1 at least
            subprocess.run(["sips", "-c", str(min(screen, h - top - 1)), str(w), "--cropOffset", str(max(top, 1)), "0", str(out), "--out", str(out)],
                           capture_output=True, timeout=60)
            note = (f"écran {page} sur {screens} de la page" +
                    (f" ; la suite : look_at avec page={page + 1}" if page < screens else " (fin de la page)"))
        subprocess.run(["sips", "-Z", str(width), str(out)], capture_output=True, timeout=60)
    else:  # Word, PowerPoint, Excel, Pages, Keynote, Numbers, RTF…: Quick Look thumbnail of the first page
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(["qlmanage", "-t", "-s", str(width), "-o", tmp, str(path)], capture_output=True, timeout=60)
            made = list(Path(tmp).glob("*.png"))
            if not made:
                raise DocError(f"aperçu impossible pour {path.name}")
            made[0].replace(out)
        note = "première page (aperçu Quick Look)"
    w, h = _png_size(out)
    return out, f"{note}, {w}×{h} px{trouble}"


SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)


def page_trouble(info, path):
    """What the image alone does not say: the page's errors, a canvas (3D, chart, game) where nothing was drawn."""
    said = []
    for attrs, code in SCRIPT_RE.findall(Path(path).read_text(errors="replace")):
        if not re.search(r"src=|module|importmap", attrs) and re.search(r"^\s*import\s.+\sfrom\s|^\s*import\s+[\"']", code, re.M):
            said.append('un <script> sans type="module" contient des import : il ne s\'exécute pas du tout')
            break
    if info.get("errors"):
        said.append("erreurs de la page : " + " ; ".join(e[:200].rstrip(".") for e in info["errors"][:6]))
    if not info.get("canvas") and re.search(r"WebGLRenderer|getContext\(|new\s+Chart\(|three(?:\.module)?\.js", Path(path).read_text(errors="replace")):
        said.append("la page doit dessiner (3D, graphique) mais AUCUNE zone de dessin n'apparaît : le canvas n'est pas mis "
                    "dans la page (renderer.domElement ajouté à la scène au lieu du document ?), ou le script s'arrête avant")
    if info.get("blank"):
        said.append(f"{info['blank']} zone(s) de dessin (canvas) VIDE(S) : rien n'y est dessiné, la 3D, le graphique ou "
                    "le jeu ne s'affiche pas. Trouve la cause (rendu jamais appelé, taille jamais donnée, objet hors champ, "
                    "erreur) ; si la page vient du modèle d'un skill, repars du modèle et change seulement le bloc prévu")
    return ("\nPROBLÈME À CORRIGER avant de dire que c'est fini : " + " ; ".join(said) + ".") if said else ""


def _png_size(png):
    with open(png, "rb") as f:
        head = f.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
