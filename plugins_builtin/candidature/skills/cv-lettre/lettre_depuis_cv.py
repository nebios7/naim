"""A cover letter in the exact style of a CV page: same <head> (fonts, colours, CSS), same header (name, contact
details), and in place of the CV's sections, one card with the letter. Nothing of the CV's content is kept.

    python3 lettre_depuis_cv.py CV.html lettre.txt Lettre.html

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


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    cv, text, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    top, header, card, badge, close = parts(cv.read_text(errors="replace"))
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


if __name__ == "__main__":
    main()
