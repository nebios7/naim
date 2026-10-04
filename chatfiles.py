"""Files made in Chat mode: Naim creates the document the user asks for (PDF, Word, Excel, ZIP, image, code…)
in ~/Documents/Naim/Fichiers, and the app shows it as a card (preview, open, download, send by email).

One tool, creer_fichier: the extension of the name decides the format.
  .pdf .docx .odt .rtf    content in Markdown (or HTML) -> laid-out document (WebKit / textutil, see docs.py)
  .html .htm              content in Markdown or HTML -> styled page
  .png                    content in HTML or SVG -> image (WebKit)
  .xlsx                   content as CSV (separator , or ;) -> Excel sheet
  .zip                    fichiers = [{nom, contenu}, …] (each one created with the same rules) or names already made
  anything else           content written as is (txt, md, csv, json, py, js, swift, sh, svg, xml, yaml…)
"""
import csv
import io
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import docs

OUT = Path.home() / "Documents" / "Naim" / "Fichiers"

FILE_TOOL = {"type": "function", "function": {
    "name": "creer_fichier",
    "description": (
        "Create a real file for the user and give it to them (they can open, download or send it). Use it whenever the "
        "user wants a document or file: PDF, Word (.docx), .odt, .rtf, Excel (.xlsx), CSV, ZIP, image (.png, .svg), "
        "HTML page, Markdown, text, JSON, code in any language… NEVER write Python or shell code to make the file: call "
        "this tool. The extension of `nom` decides the format. For .pdf/.docx/.odt/.rtf/.html give `contenu` in Markdown "
        "(titles #, lists, **bold**, tables) or HTML; for .png give HTML or SVG; for .xlsx give CSV; for .zip give "
        "`fichiers` (each {nom, contenu}). Write the COMPLETE content, never a summary or a placeholder."),
    "parameters": {"type": "object", "properties": {
        "nom": {"type": "string", "description": "File name with its extension, e.g. rapport.pdf, cv.docx, ventes.xlsx, projet.zip"},
        "contenu": {"type": "string", "description": "Complete content (Markdown/HTML for documents, CSV for .xlsx, text or code otherwise)"},
        "fichiers": {"type": "array", "description": "For a .zip only: the files to put inside",
                     "items": {"type": "object", "properties": {"nom": {"type": "string"}, "contenu": {"type": "string"}},
                               "required": ["nom"]}},
    }, "required": ["nom"]}}}

DOCS = {".pdf", ".docx", ".odt", ".rtf", ".doc"}


def _safe(name):
    name = re.sub(r"[/\\:\0]", "-", str(name or "").strip()).lstrip(".") or "fichier.txt"
    return name[:120]


def _unique(folder, name):
    p = folder / name
    n = 2
    while p.exists():
        p = folder / f"{Path(name).stem} ({n}){Path(name).suffix}"
        n += 1
    return p


def _html(content, title):
    content = content or ""
    if re.search(r"<(html|body|div|p|h1|table|section)\b", content, re.I):
        return content if "<html" in content.lower() else f"<!doctype html><meta charset='utf-8'><title>{escape(title)}</title>{content}"
    return docs.markdown_html(content, title)


def _xlsx(csv_text, dst):
    """A minimal valid .xlsx (one sheet, numbers as numbers) from CSV text, without extra libraries."""
    text = (csv_text or "").strip()
    sep = ";" if text.count(";") > text.count(",") else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=sep))
    def col(i):
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s
    xml_rows = []
    for r, row in enumerate(rows, 1):
        cells = []
        for c, v in enumerate(row):
            ref = f"{col(c)}{r}"
            num = v.strip().replace(" ", "").replace(",", ".") if sep == ";" else v.strip()
            if re.fullmatch(r"-?\d+(\.\d+)?", num or "x"):
                cells.append(f'<c r="{ref}"><v>{num}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"{" s=\"1\"" if r == 1 else ""}><is><t xml:space="preserve">{escape(v)}</t></is></c>')
        xml_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Feuille1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0"/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>',
        "xl/worksheets/sheet1.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(xml_rows) + "</sheetData></worksheet>",
    }
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            z.writestr(k, v)


def _make(dst, content):
    """Write one file at dst in the format given by its extension."""
    ext = dst.suffix.lower()
    if ext in DOCS or ext == ".png":
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / f"{dst.stem}.html"
            if ext == ".png" and (content or "").lstrip().startswith("<svg"):
                page.write_text(f"<!doctype html><meta charset='utf-8'><body style='margin:0'>{content}</body>")
            else:
                page.write_text(_html(content, dst.stem))
            if ext == ".png":
                r = subprocess.run([docs.pdf_tool(), str(page), str(dst)], capture_output=True, text=True, timeout=120)
                if r.returncode != 0 or not dst.exists():
                    raise docs.DocError("image impossible : " + (r.stderr or r.stdout)[-200:])
            else:
                docs.convert(page, dst.with_suffix(".docx") if ext == ".doc" else dst)
    elif ext in (".html", ".htm"):
        dst.write_text(_html(content, dst.stem))
    elif ext == ".xlsx":
        _xlsx(content, dst)
    else:
        dst.write_text(content or "")


def create(nom, contenu="", fichiers=None, folder=None):
    """Create the file (in the user's working folder when there is one, else in OUT);
    returns (message for Naim, file info for the app)."""
    out = Path(folder) if folder else OUT
    out.mkdir(parents=True, exist_ok=True)
    name = _safe(nom)
    if not Path(name).suffix:
        name += ".txt"
    dst = _unique(out, name)
    if dst.suffix.lower() == ".zip":
        items = fichiers or []
        if not items and contenu:
            items = [{"nom": Path(name).stem + ".txt", "contenu": contenu}]
        if not items:
            raise ValueError("pour un .zip, donne `fichiers` (chacun {nom, contenu})")
        with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for it in items:
                inner = str(it.get("nom") or "fichier.txt").strip().lstrip("/").replace("..", "")
                existing = out / _safe(inner)
                if it.get("contenu") is None and existing.is_file():
                    z.write(existing, inner)
                    continue
                f = Path(tmp) / _safe(Path(inner).name)
                _make(f, it.get("contenu") or "")
                z.write(f, inner)
    else:
        _make(dst, contenu)
    info = {"path": dst.name, "size": dst.stat().st_size, "ext": dst.suffix.lower()[1:]}
    where = "dans le dossier de travail de l'utilisateur" if folder else f"dans le dossier des fichiers du mode Chat ({OUT})"
    return (f"fichier créé : {dst} ({info['size']} octets), {where}. Il est affiché à l'utilisateur, prêt à ouvrir "
            "ou télécharger. Quand tu en parles, donne exactement ce nom et cet emplacement.", info)
