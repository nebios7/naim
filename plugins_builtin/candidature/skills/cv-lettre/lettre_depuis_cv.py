"""A cover letter in the exact style of a CV page: same <head> (fonts, colours, CSS), same header (name, contact
details), and in place of the CV's sections, one card with the letter. Nothing of the CV's content is kept.

    python3 lettre_depuis_cv.py CV.html lettre.txt Lettre.html
    python3 lettre_depuis_cv.py moi.json lettre.txt Lettre.html     (no CV made: the pdf-pro head from
                                         {"nom": …, "titre": …, "contact": [["Tél.", …], ["E-mail", …], ["Ville", …]]})

lettre.txt, in this order, blocks separated by an empty line:
    Bordeaux, le 22 octobre 2026                 (place and date)
    Collège Georges Lapierre                     (recipient: one or more lines)
    Madame la Principale
    Objet : candidature au poste de …            (a line that starts with « Objet »)
    Madame,                                      (salutation)
    First paragraph…
    …
    Je vous prie d'agréer…                       (closing)
    Mohamed Abdessemed                           (signature: the last block)
"""
import html
import re
import sys
from pathlib import Path


def parts(cv):
    """(the page up to its first content tag, the header block, the card and badge classes, the closing tags)."""
    head_end = re.search(r"<main\b[^>]*>|<body\b[^>]*>", cv, re.I)
    if not head_end:
        sys.exit("error: no <body> in the CV")
    top = cv[:head_end.end()]
    header = re.search(r"<header\b.*?</header>", cv[head_end.end():], re.I | re.S)
    if not header:  # no <header>: the name and what follows it up to the first section
        header = re.search(r"<h1\b.*?(?=<section\b|<div class=\"[^\"]*(?:carte|card|section)[^\"]*\")", cv[head_end.end():], re.I | re.S)
    card = re.search(r"<section\s+class=\"([^\"]+)\"", cv) or re.search(r"class=\"([^\"]*(?:carte|card)[^\"]*)\"", cv)
    badge = re.search(r"<h2\s+class=\"([^\"]+)\"", cv)
    close = ("</main>\n" if head_end.group(0).lower().startswith("<main") else "") + "</body>\n</html>\n"
    return top, header.group(0) if header else "", card.group(1) if card else "carte", badge.group(1) if badge else "", close


def letter_html(text):
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    if len(blocks) < 4:
        sys.exit("error: lettre.txt needs at least: place and date, recipient, subject, one paragraph (blocks separated by an empty line)")
    esc = lambda s: html.escape(s).replace("\n", "<br>")  # noqa: E731
    out = [f'<p class="l-date">{esc(blocks[0])}</p>']
    rest = blocks[1:]
    if not rest[0].lower().startswith("objet"):
        out.append(f'<p class="l-dest">{esc(rest[0])}</p>')
        rest = rest[1:]
    if rest and rest[0].lower().startswith("objet"):
        out.append(f'<p class="l-objet"><b>{esc(rest[0])}</b></p>')
        rest = rest[1:]
    *body, signature = rest if len(rest) > 1 else (rest + [""])
    out += [f"<p>{esc(p)}</p>" for p in body]
    if signature:
        out.append(f'<p class="l-sign">{esc(signature)}</p>')
    return "\n      ".join(out), sum(len(b.split()) for b in blocks)


PDFPRO = Path.home() / ".naim/plugins/pdf-pro/skills/pdf-pro/pdfpro.py"


def to_pdf(page):
    """The PDF next to the page, in the same step (pdf-pro): nothing left to convert. If it fails, the page is still
    there and convert_document does it."""
    page = page.resolve()
    pdf = page.with_suffix(".pdf")
    if not PDFPRO.exists():
        return "PDF : à faire avec l'outil convert_document (pdf-pro absent)."
    import subprocess
    try:
        r = subprocess.run([sys.executable, str(PDFPRO), "render", str(page), str(pdf)], capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as e:
        return f"PDF non fait ({e}) : fais-le avec l'outil convert_document."
    if r.returncode or not pdf.exists():
        return f"PDF non fait ({(r.stderr or r.stdout).strip()[-300:]}) : fais-le avec l'outil convert_document."
    pages = re.search(r"\((\d+) pages?\)", r.stdout)
    return (f"PDF : {pdf}" + (f" ({pages.group(1)} page(s))" if pages else "") + ". Regarde-le avec look_at ; si tu "
            f"modifies le .html, refais le PDF : python3 {PDFPRO} render \"{page}\" \"{pdf}\"")


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    cv, text, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    if cv.suffix.lower() == ".json":  # no CV page: the same pdf-pro head (name, contact, photo) made from these facts
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import json
        import cv_pro
        facts = cv_pro.tidy({**json.loads(cv.read_text()), "kicker": "Candidature"})
        model = cv_pro.MODEL.read_text(errors="replace")
        head = model[:re.search(r"<body\b[^>]*>", model, re.I).end()].replace("</head>", cv_pro.KEEP + "</head>", 1)
        source = f"{head}\n<main>\n{cv_pro.body({k: facts.get(k) for k in ('nom', 'titre', 'kicker', 'photo', 'contact')})}\n</main>\n</body>\n</html>\n"
    else:
        source = cv.read_text(errors="replace")
    top, header, card, badge, close = parts(source)
    header = re.sub(r"(class=\"kicker\"[^>]*>)\s*(curriculum vit\w*|cv)\s*(?=<)", r"\1Candidature", header, flags=re.I)  # not a CV
    body, words = letter_html(text.read_text(errors="replace"))
    style = ("<style>.lettre p{margin:0 0 11px;line-height:1.55}.lettre .l-date{text-align:right}"
             ".lettre .l-dest{margin-bottom:16px}.lettre .l-objet{margin:14px 0 16px}.lettre .l-sign{margin-top:22px;text-align:right}"
             "@page{size:A4}</style>\n")
    top = top.replace("</head>", style + "</head>", 1) if "</head>" in top else top
    title = f'<h2 class="{badge}">Lettre de motivation</h2>\n      ' if badge else ""
    page = (f"{top}\n  {header}\n  <section class=\"{card} lettre\">\n      {title}{body}\n  </section>\n{close}")
    dst.write_text(page)
    print(f"ok: {dst} ({words} mots{', trop long pour une page : vise 250-380 mots' if words > 400 else ''}). "
          f"Style et en-tête repris de {cv.name}, aucun contenu du CV dans la lettre.")
    print(to_pdf(dst))


if __name__ == "__main__":
    main()
