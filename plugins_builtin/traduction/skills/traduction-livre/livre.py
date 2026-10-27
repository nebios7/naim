#!/usr/bin/env python3
"""Translate a book (scanned or not) page by page, keeping its drawings, tables and symbols.

Run it with the venv of the work folder (pdfplumber brings pypdfium2, which renders the pages):
  livre.py inventaire <livre.pdf> <dossier>     what each page holds; pages to LOOK AT (figure, table, symbols)
  livre.py suivant <dossier>                    the next page to translate: its text, what to check, the glossary
  livre.py page <dossier> <n>                   page n as an image (pages/p017.png) to look at it
  livre.py figure <dossier> <n> [x0 y0 x1 y1]   the drawing of page n cut out (figures/p017.png); the box in fractions
                                                of the page (0 0 1 1 = whole page), found by itself when not given
  livre.py etat <dossier>                       pages done, pages left, figures not placed
  livre.py assembler <dossier> "<titre>" <sortie.html>   the translated pages in order → one book page, then PDF
The work survives a stop: each page is its own file (fr/p017.md), « suivant » gives the first one missing.
"""
import html
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

# signs an OCR makes of a drawing or of a symbol it does not know (☉ ♈ 🜂 …)
ODD = set("■□▪△▲▼♦◆●○◊¤¦§¿¡ÿÄÖÜäöüØø¬«»©®™€£¥|\\^~<>{}[]_=+*#@")
LOOK_WORDS = re.compile(r"\b(fig\.|figure \d|plate\b|diagram|subjoined|(following|annexed|accompanying) (figure|table|"
                        r"diagram|plate|scheme)|as (here )?(shown|figured|depicted))", re.I)


def clean(text):
    """The text of a page as a reader sees it: words cut at the line end joined again."""
    text = (text or "").replace("\r", "")
    text = re.sub(r"[\xad-]\n(?=[a-zà-ÿ])", "", text)  # « con-\ndensive » → « condensive »
    return text.replace("\xad", "")


def odd_share(text):
    words = text.split()
    if not words:
        return 0.0
    bad = sum(1 for w in words if any(c in ODD for c in w) or not re.search(r"[A-Za-zÀ-ÿ]{2}", w))
    return bad / len(words)


def folder(d):
    d = Path(d).expanduser().resolve()
    inv = d / "inventaire.json"
    if not inv.exists():
        sys.exit(f"pas d'inventaire dans {d} : lance d'abord « livre.py inventaire <livre.pdf> {d} »")
    return d, json.loads(inv.read_text())


def inventaire(pdf, d):
    import pdfplumber
    d = Path(d).expanduser().resolve()
    for sub in ("orig", "fr", "pages", "figures"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    pages = []
    with pdfplumber.open(pdf) as doc:
        for i, p in enumerate(doc.pages, 1):
            t = clean(p.extract_text() or "")
            area = float(p.width * p.height) or 1.0
            imgs = [im for im in p.images if 0.02 < (im["x1"] - im["x0"]) * (im["bottom"] - im["top"]) / area < 0.85]
            pages.append({"n": i, "text": t, "boxes": [[round(im["x0"] / p.width, 3), round(im["top"] / p.height, 3),
                                                        round(im["x1"] / p.width, 3), round(im["bottom"] / p.height, 3)]
                                                       for im in imgs],
                          "scan": any((im["x1"] - im["x0"]) * (im["bottom"] - im["top"]) / area >= 0.85 for im in p.images)})
    # the running head (« The Sun Book. 46 ») repeated on many pages: not part of the text
    firsts = Counter(re.sub(r"[\d\W_]+", " ", (pg["text"].strip().split("\n") or [""])[0]).strip().lower() for pg in pages)
    heads = {h for h, c in firsts.items() if h and c >= max(3, len(pages) // 5)}
    sizes = [len(pg["text"]) for pg in pages if len(pg["text"]) > 200]
    usual = statistics.median(sizes) if sizes else 1500
    out = []
    for pg in pages:
        lines = pg["text"].strip().split("\n")
        while lines and (re.sub(r"[\d\W_]+", " ", lines[0]).strip().lower() in heads or re.fullmatch(r"\W*[\divxlc]{1,4}\W*", lines[0].strip(), re.I)):
            lines = lines[1:]  # the running head, a page number alone
        text = "\n".join(lines).strip()
        why = []
        if pg["boxes"]:
            why.append("image")
        if text and len(text) < usual * 0.45:
            why.append("peu de texte (dessin ou planche ?)")
        if odd_share(text) > 0.08:
            why.append("signes bizarres (dessin lu comme du texte, ou symboles)")
        if LOOK_WORDS.search(text):
            why.append("annonce une figure ou un tableau")
        if (sum(bool(re.match(r"\S+( \S+)? \([^)]{2,30}\) \S", x)) for x in lines) >= 3
                or (len(lines) > 3 and sum(len(x) < 40 for x in lines) > len(lines) * 0.4)):
            why.append("lignes courtes (tableau ou liste ?)")
        (d / "orig" / f"p{pg['n']:03d}.txt").write_text(text)
        empty = len(text) < 15 and not pg["boxes"]
        if empty and not (d / "fr" / f"p{pg['n']:03d}.md").exists():
            (d / "fr" / f"p{pg['n']:03d}.md").write_text("")  # a blank page: nothing to translate
        out.append({"n": pg["n"], "chars": len(text), "look": why, "boxes": pg["boxes"], "empty": empty})
    meta = {"pdf": str(Path(pdf).expanduser().resolve()), "pages": out, "scan": sum(p["scan"] for p in pages) > len(pages) / 2}
    (d / "inventaire.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    g = d / "glossaire.md"
    if not g.exists():
        g.write_text("# Glossaire (anglais → français) — le même mot traduit toujours de la même façon\n\n")
    look = [p for p in out if p["look"]]
    print(f"{len(out)} pages ({'livre scanné : le texte vient d’une reconnaissance (OCR), à vérifier sur l’image' if meta['scan'] else 'texte natif'})")
    print(f"pages vides : {sum(p['empty'] for p in out)} · pages à REGARDER avant de traduire : {len(look)}")
    for p in look[:60]:
        print(f"  p{p['n']:03d} : {', '.join(p['look'])}")
    if len(look) > 60:
        print(f"  … et {len(look) - 60} autres (livre.py etat)")
    print(f"Ensuite : livre.py suivant {d}")


def render(pdf, n, dpi=150):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    return doc[n - 1].render(scale=dpi / 72).to_pil()


def page(d, n):
    d, inv = folder(d)
    out = d / "pages" / f"p{int(n):03d}.png"
    render(inv["pdf"], int(n)).save(out)
    print(f"{out}\nRegarde-la (look_at) : dessin, tableau, symboles exacts.")


def figure(d, n, box=None):
    from PIL import ImageOps
    d, inv = folder(d)
    n = int(n)
    img = render(inv["pdf"], n, 200)
    w, h = img.size
    if box:
        x0, y0, x1, y1 = (float(v) for v in box)
    elif (pg := inv["pages"][n - 1])["boxes"]:
        x0, y0, x1, y1 = max(pg["boxes"], key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    else:  # a scanned page: the inked part, without the running head and the page number
        g = ImageOps.invert(img.convert("L")).point(lambda v: 255 if v > 110 else 0)
        rows = [sum(1 for x in range(0, w, 4) if g.getpixel((x, y))) > 2 for y in range(h)]
        bands, y = [], 0  # the inked bands of the page, separated by blank space
        while y < h:
            if rows[y]:
                y0 = y
                while y < h and any(rows[y:y + int(h * 0.008) + 1]):
                    y += 1
                bands.append((y0, y))
            y += 1
        while len(bands) > 1 and bands[0][1] - bands[0][0] < h * 0.035:
            bands.pop(0)  # the running head
        while len(bands) > 1 and bands[-1][1] - bands[-1][0] < h * 0.035:
            bands.pop()  # the page number, a catchword
        if not bands:
            sys.exit("rien d'encré sur cette page : donne la zone, livre.py figure <dossier> <n> x0 y0 x1 y1")
        top, bottom = bands[0][0], bands[-1][1]
        bb = g.crop((0, top, w, bottom)).getbbox()
        x0, y0, x1, y1 = bb[0] / w, (bb[1] + top) / h, bb[2] / w, (bb[3] + top) / h
    pad = 0.01
    crop = (max(0, int((x0 - pad) * w)), max(0, int((y0 - pad) * h)), min(w, int((x1 + pad) * w)), min(h, int((y1 + pad) * h)))
    out = d / "figures" / f"p{n:03d}.png"
    img.crop(crop).save(out)
    print(f"{out}  (zone {x0:.2f} {y0:.2f} {x1:.2f} {y1:.2f})\n"
          f"Regarde-la (look_at). Si elle prend aussi des paragraphes, recoupe avec une zone : livre.py figure {d} {n} x0 y0 x1 y1\n"
          f"Dans fr/p{n:03d}.md, à sa place : ![Légende traduite](figures/p{n:03d}.png)")


def suivant(d):
    d, inv = folder(d)
    todo = [p for p in inv["pages"] if not (d / "fr" / f"p{p['n']:03d}.md").exists()]
    if not todo:
        print(f"Toutes les pages sont traduites. Ensuite : livre.py assembler {d} \"<titre>\" {d}/livre_fr.html")
        return
    p = todo[0]
    n = p["n"]
    total = len(inv["pages"])
    print(f"PAGE {n}/{total} · reste {len(todo)} page(s)")
    if p["look"]:
        print(f"À REGARDER D'ABORD ({', '.join(p['look'])}) : livre.py page {d} {n}, puis look_at sur l'image.\n"
              "  - un dessin → livre.py figure (il garde l'original), légendes et mots du dessin traduits sous l'image ;\n"
              "  - un tableau → refais-le en tableau Markdown d'après l'IMAGE (pas d'après le texte) ;\n"
              "  - des symboles → écris les vrais caractères vus sur l'image (☉ ☽ ☿ ♀ ♂ ♃ ♄ ♈…♓ 🜁 🜂 🜃 🜄 △ ▽ ✠ …).")
    prev = d / "fr" / f"p{n - 1:03d}.md"
    if prev.exists() and prev.read_text().strip():
        print("\n--- fin de la page précédente (déjà traduite, pour enchaîner la phrase) ---\n" + prev.read_text().strip()[-300:])
    print("\n--- texte original ---\n" + ((d / "orig" / f"p{n:03d}.txt").read_text() or "(aucun texte : regarde l'image)"))
    gl = (d / "glossaire.md").read_text().strip()
    print("\n--- glossaire ---\n" + gl)
    print(f"\nÉcris la traduction COMPLÈTE de cette page dans {d}/fr/p{n:03d}.md (Markdown : # titre de chapitre, ## section, "
          "*italique* comme l'original, notes en fin de page). Une phrase coupée en bas de page : traduis-la jusqu'où elle "
          "va ; la page suivante la continue. Un terme nouveau et récurrent : ajoute-le au glossaire. "
          f"Puis relance : livre.py suivant {d}")


def etat(d):
    d, inv = folder(d)
    done = [p for p in inv["pages"] if (d / "fr" / f"p{p['n']:03d}.md").exists()]
    left = [p["n"] for p in inv["pages"] if p not in done]
    print(f"{len(done)}/{len(inv['pages'])} pages traduites")
    if left:
        print("à faire : " + ", ".join(map(str, left[:40])) + (" …" if len(left) > 40 else ""))
    figs = sorted(f.stem for f in (d / "figures").glob("p*.png"))
    used = " ".join((d / "fr" / f"{s}.md").read_text() for s in figs if (d / "fr" / f"{s}.md").exists())
    lost = [s for s in figs if f"figures/{s}.png" not in used]
    if lost:
        print("figures découpées mais pas placées dans leur page : " + ", ".join(lost))
    unseen = [p["n"] for p in inv["pages"] if p in done and p["look"] and not (d / "pages" / f"p{p['n']:03d}.png").exists()
              and not (d / "figures" / f"p{p['n']:03d}.png").exists()]
    if unseen:
        print("pages à regarder traduites SANS avoir été regardées : " + ", ".join(map(str, unseen)))


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def md_html(md):
    out, para, lines, i = [], [], md.split("\n"), 0

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush()
        elif m := re.match(r"(#{1,3})\s+(.*)", ln):
            flush()
            k = len(m.group(1))
            out.append(f"<h{k}>{inline(m.group(2))}</h{k}>")
        elif m := re.match(r"!\[(.*?)\]\((.+?)\)", ln.strip()):
            flush()
            cap = f"<figcaption>{inline(m.group(1))}</figcaption>" if m.group(1) else ""
            out.append(f'<figure><img src="{html.escape(m.group(2))}" alt="">{cap}</figure>')
        elif ln.lstrip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            out.append("<table>" + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows) + "</table>")
            continue
        elif ln.startswith(">"):
            flush()
            out.append(f"<blockquote>{inline(ln.lstrip('> '))}</blockquote>")
        else:
            para.append(ln.strip())
        i += 1
    flush()
    return "\n".join(out)


def assembler(d, titre, sortie):
    d, inv = folder(d)
    parts = []
    for p in inv["pages"]:
        f = d / "fr" / f"p{p['n']:03d}.md"
        t = f.read_text().strip() if f.exists() else f"*[page {p['n']} non traduite]*"
        if not t:
            continue
        if parts and not re.search(r"[.!?:;»”)\]…]\s*$", parts[-1]) and re.match(r"[a-zà-ÿ,;]", t):
            parts[-1] = parts[-1].rstrip() + " " + t  # a sentence cut by the page goes on in the same paragraph
        else:
            parts.append(t)
    body = md_html("\n\n".join(parts))
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{html.escape(titre)}</title><style>
@page {{ size: A4; margin: 22mm 20mm; }}
body {{ font-family: "Iowan Old Style", "Palatino", Georgia, "Apple Symbols", "Apple Color Emoji", serif;
  font-size: 11.5pt; line-height: 1.55; color: #1a1a1a; text-align: justify; hyphens: auto; }}
h1 {{ page-break-before: always; font-size: 20pt; text-align: center; margin: 30mm 0 12mm; font-weight: 600; }}
h1:first-child {{ page-break-before: avoid; }}
h2 {{ font-size: 14pt; margin: 9mm 0 3mm; }} h3 {{ font-size: 12pt; margin: 6mm 0 2mm; }}
p {{ margin: 0 0 2.5mm; text-indent: 6mm; }}
figure {{ margin: 6mm 0; text-align: center; page-break-inside: avoid; }}
figure img {{ max-width: 100%; max-height: 225mm; }}
figcaption {{ font-size: 9.5pt; font-style: italic; margin-top: 2mm; text-align: center; }}
table {{ border-collapse: collapse; margin: 4mm auto; page-break-inside: avoid; }}
td {{ padding: 1.2mm 4mm; border-bottom: 1px solid #ccc; text-align: left; }}
blockquote {{ margin: 3mm 10mm; font-style: italic; }}
.titre {{ text-align: center; margin-top: 70mm; }} .titre h1 {{ margin: 0; font-size: 26pt; page-break-before: avoid; }}
</style></head><body>
<section class="titre"><h1>{html.escape(titre)}</h1></section>
{body}
</body></html>"""
    out = Path(sortie).expanduser()
    if not out.is_absolute():
        out = d / out
    if out.parent.resolve() != d:
        page = page.replace('src="figures/', f'src="{d}/figures/')  # the drawings found wherever the page goes
    out.write_text(page)
    missing = sum(1 for p in inv["pages"] if not (d / "fr" / f"p{p['n']:03d}.md").exists())
    print(f"{out}" + (f"\nATTENTION : {missing} page(s) pas encore traduites (marquées dans le livre)" if missing else ""))
    print(f"PDF : \"$HOME/Library/Application Support/Naim/bin/naim-pdf\" \"{out}\" \"{out.with_suffix('.pdf')}\" A4\n"
          "Puis regarde (look_at) le PDF : la page de titre, une page avec figure, une page avec tableau ou symboles.")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmds = {"inventaire": (inventaire, 2), "suivant": (suivant, 1), "page": (page, 2), "etat": (etat, 1),
            "assembler": (assembler, 3)}
    if a and a[0] == "figure" and len(a) in (3, 7):
        figure(a[1], a[2], a[3:] or None)
    elif a and a[0] in cmds and len(a) - 1 == cmds[a[0]][1]:
        cmds[a[0]][0](*a[1:])
    else:
        sys.exit(__doc__)
