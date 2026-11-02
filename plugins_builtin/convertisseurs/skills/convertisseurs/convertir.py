#!/usr/bin/env python3
"""Convertir un fichier d'un format à un autre, avec les outils du Mac et de Naim, en une commande :

    python3 convertir.py <source> <sortie> [--taille 1200] [--qualite 80] [--debut 0:05 --duree 10] [--couleur gris]
    python3 convertir.py image1.jpg image2.png … album.pdf        (plusieurs images -> un PDF)

Images  : png jpg heic webp gif tiff bmp  <->  entre elles ; -> pdf ; pdf -> png/jpg (une image par page)
Docs    : md docx doc rtf odt html txt epub  <->  entre eux (pandoc, textutil) ; -> pdf au style pdf-pro ;
          pdf -> txt / md / docx (son texte) ; pptx / xlsx -> pdf (pdf-pro)
Tableurs: csv xlsx json  <->  entre eux
Audio / vidéo : mp4 mov mkv avi webm  <->  ; -> mp3 m4a wav (le son) ; -> gif (une animation) ; mp3 wav m4a flac ogg <->
La sortie n'écrase jamais la source ; à la fin, la taille (et les pages) du résultat.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
APP = HOME / "Library/Application Support/Naim/app"
PDFPRO = HOME / ".naim/plugins/pdf-pro/skills/pdf-pro/pdfpro.py"
VENV = HOME / ".naim/docs-venv/bin/python"
IMG = {"png", "jpg", "jpeg", "heic", "heif", "webp", "gif", "tiff", "tif", "bmp"}
DOC = {"md", "markdown", "docx", "doc", "rtf", "odt", "html", "htm", "txt", "epub"}
VID = {"mp4", "mov", "mkv", "avi", "webm", "m4v"}
AUD = {"mp3", "wav", "m4a", "aac", "flac", "ogg", "aiff"}
TAB = {"csv", "xlsx", "json"}

def _here(path):
    """« cours-cobol/x.pdf » typed while already in cours-cobol (and no such sub-folder): x.pdf, here."""
    p = Path(str(path)).expanduser()
    if not p.is_absolute() and len(p.parts) > 1 and p.parts[0] == Path.cwd().name and not (Path.cwd() / p.parts[0]).exists():
        return str(Path(*p.parts[1:]))
    return str(path)



def run(cmd, timeout=900):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        sys.exit(f"erreur : {Path(cmd[0]).name} : {(r.stderr or r.stdout).strip()[-400:]}")
    return r.stdout


def need(tool, formula):
    path = shutil.which(tool) or next((p for p in (f"/opt/homebrew/bin/{tool}", f"/usr/local/bin/{tool}") if Path(p).exists()), None)
    if not path:
        sys.exit(f"erreur : l'outil « {tool} » manque : brew install {formula}, puis relance.")
    return path


def opt(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def image(src, dst, a, b):
    size, qual = opt("--taille"), opt("--qualite", "85")
    if b == "webp" or a == "webp":
        cmd = [need("magick", "imagemagick"), str(src)] + (["-resize", f"{size}x{size}>"] if size else []) + ["-quality", qual, str(dst)]
        return run(cmd)
    fmt = {"jpg": "jpeg", "tif": "tiff", "heif": "heic"}.get(b, b)
    cmd = ["sips", "-s", "format", fmt] + (["-s", "formatOptions", qual] if fmt == "jpeg" else []) + (["-Z", size] if size else [])
    run(cmd + [str(src), "--out", str(dst)])


def images_to_pdf(srcs, dst):
    run([need("magick", "imagemagick")] + [str(s) for s in srcs] + ["-auto-orient", str(dst)])


def pdf_to_images(src, dst, b):
    """Each page as an image (Naim's own page renderer): sortie.png -> sortie-1.png, sortie-2.png…"""
    sys.path.insert(0, str(APP))
    import docs
    n, made = 1, []
    while n <= 500:
        try:
            img, _ = docs.preview_png(src, n)
        except Exception:  # noqa: BLE001 — past the last page
            break
        if made and Path(img).read_bytes() == Path(made[-1][0]).read_bytes():
            break
        out = dst.with_name(f"{dst.stem}-{n}.{b}")
        if b == "png":
            shutil.copy(img, out)
        else:
            run(["sips", "-s", "format", "jpeg", str(img), "--out", str(out)])
        made.append((img, out)); n += 1
    if not made:
        sys.exit("erreur : aucune page lue dans ce PDF.")
    print(f"ok : {len(made)} image(s) : {made[0][1].name} … {made[-1][1].name}")
    sys.exit(0)


def pdf_text(src):
    sys.path.insert(0, str(APP))
    import docs
    text, _ = docs.pdf_text(src)
    import re
    return re.sub(r"(?m)^--- Page \d+ ---\s*\n?", "\n", text).strip() + "\n"  # Naim's page marks are not the document's


def document(src, dst, a, b):
    if b == "pdf":  # always the pro style
        if not PDFPRO.exists():
            sys.exit("erreur : pdf-pro manque (Personnaliser › Plugins).")
        args = [sys.executable, str(PDFPRO), "render", str(src), str(dst)] + ([opt("--couleur")] if opt("--couleur") else [])
        return run(args)
    if a == "pdf":
        text = pdf_text(src)
        if b in ("txt", "md"):
            return dst.write_text(text)
        tmp = dst.with_suffix(".tmp.md"); tmp.write_text(text)
        try:
            return run([need("pandoc", "pandoc"), str(tmp), "-o", str(dst)])
        finally:
            tmp.unlink(missing_ok=True)
    if a in ("doc", "rtf") or b in ("doc", "rtf"):  # the Mac's own converter knows these
        kind = {"htm": "html", "md": "txt", "markdown": "txt"}.get(b, b)
        return run(["textutil", "-convert", kind, str(src), "-output", str(dst)])
    fr = {"md": "markdown", "markdown": "markdown", "htm": "html", "txt": "markdown"}.get(a, a)
    to = {"md": "gfm", "markdown": "gfm", "htm": "html", "txt": "plain"}.get(b, b)
    media = [f"--extract-media={dst.with_name(dst.stem + '-images')}"] if a in ("docx", "odt", "epub") and b not in ("docx", "odt") else []
    run([need("pandoc", "pandoc"), "-f", fr, "-t", to, "--standalone" if to == "html" else "--wrap=none", *media, str(src), "-o", str(dst)])


def table(src, dst, a, b):
    import csv
    if a == "xlsx":
        code = ("import openpyxl,json,sys;wb=openpyxl.load_workbook(sys.argv[1],data_only=True,read_only=True);ws=wb.worksheets[0];"
                "print(json.dumps([[('' if c is None else c) for c in r] for r in ws.iter_rows(values_only=True)],default=str))")
        rows = json.loads(run([str(VENV), "-c", code, str(src)]))
    elif a == "csv":
        text = src.read_text(errors="replace")
        rows = list(csv.reader(text.splitlines(), delimiter=";" if text.count(";") > text.count(",") else ","))
    else:
        data = json.loads(src.read_text())
        data = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), [data])
        keys = list(dict.fromkeys(k for d in data if isinstance(d, dict) for k in d))
        rows = [keys] + [[d.get(k, "") for k in keys] for d in data] if keys else data
    if b == "csv":
        with open(dst, "w", newline="") as f:
            csv.writer(f, delimiter=";").writerows(rows)
    elif b == "json":
        head, *body = rows
        dst.write_text(json.dumps([dict(zip(head, r)) for r in body], ensure_ascii=False, indent=2))
    else:
        code = ("import openpyxl,json,sys;wb=openpyxl.Workbook();ws=wb.active;"
                "[ws.append([float(c) if isinstance(c,str) and c.replace('.','',1).replace('-','',1).isdigit() else c for c in r]) for r in json.loads(sys.stdin.read())];"
                "wb.save(sys.argv[1])")
        r = subprocess.run([str(VENV), "-c", code, str(dst)], input=json.dumps(rows, default=str), capture_output=True, text=True)
        if r.returncode:
            sys.exit("erreur : " + r.stderr[-300:])
    print(f"{len(rows)} ligne(s)")


def media(src, dst, a, b):
    ff = need("ffmpeg", "ffmpeg")
    cut = (["-ss", opt("--debut")] if opt("--debut") else []) + (["-t", opt("--duree")] if opt("--duree") else [])
    if b == "gif":  # a light, clean animation: 12 images a second, width 480 (or --taille), its own palette
        w = opt("--taille", "480")
        return run([ff, "-y"] + cut + ["-i", str(src), "-vf", f"fps=12,scale={w}:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse", str(dst)])
    if b in AUD:
        return run([ff, "-y"] + cut + ["-i", str(src), "-vn"] + (["-b:a", "192k"] if b in ("mp3", "m4a", "aac") else []) + [str(dst)])
    run([ff, "-y"] + cut + ["-i", str(src)] + (["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"] if b in ("mp4", "m4v", "mov") else []) + [str(dst)])


def main():
    args = [x for i, x in enumerate(sys.argv[1:], 1) if not x.startswith("--") and not (i > 1 and sys.argv[i - 1].startswith("--"))]
    if len(args) < 2:
        sys.exit(__doc__)
    *srcs, dst = [Path(_here(x)).expanduser() for x in args]
    for s in srcs:
        if not s.is_file():
            sys.exit(f"erreur : fichier introuvable : {s}")
        if s.resolve() == dst.resolve():
            sys.exit("erreur : la sortie doit avoir un autre nom que la source (l'original n'est jamais écrasé).")
    dst.parent.mkdir(parents=True, exist_ok=True)
    b = dst.suffix.lower().lstrip(".")
    if len(srcs) > 1:
        if b == "pdf" and all(s.suffix.lower().lstrip(".") in IMG for s in srcs):
            images_to_pdf(srcs, dst)
        elif b == "pdf":
            run([sys.executable, str(PDFPRO), "render"] + [str(s) for s in srcs] + [str(dst)])
        else:
            sys.exit("erreur : plusieurs fichiers : seulement vers un .pdf (images en album, documents en un seul PDF).")
    else:
        src = srcs[0]; a = src.suffix.lower().lstrip(".")
        if a == "pdf" and b in ("png", "jpg", "jpeg"):
            pdf_to_images(src, dst, "jpg" if b == "jpeg" else b)
        elif a in IMG and b in IMG:
            image(src, dst, a, b)
        elif a in IMG and b == "pdf":
            images_to_pdf([src], dst)
        elif (a in DOC and (b in DOC or b == "pdf")) or (a == "pdf" and b in DOC) or (a in ("pptx", "xlsx", "csv") and b == "pdf"):
            document(src, dst, a, b)
        elif a in TAB and b in TAB:
            table(src, dst, a, b)
        elif (a in VID | AUD) and (b in VID | AUD | {"gif"}):
            media(src, dst, a, b)
        else:
            sys.exit(f"erreur : {a} -> {b} : pas pris en charge. Possibles : images, documents, tableurs, audio/vidéo (voir l'aide).")
    if not dst.exists() or dst.stat().st_size == 0:
        sys.exit(f"erreur : {dst.name} n'a pas été créé.")
    size = dst.stat().st_size
    print(f"ok : {dst} ({size / 1024:.0f} Ko). Vérifie-le avec look_at.")


if __name__ == "__main__":
    main()
