"""A page made from a model page: the model is copied as it is (HTML, CSS, fonts) and only the texts are replaced.

    python3 remplir_modele.py modele.html textes.json sortie.html

textes.json: a list of [old text, new text] pairs, old text as it is READ on the page (spaces and line breaks do not
need to match, tags inside it neither: « Développeur <b>COBOL</b> » is found with « Développeur COBOL »):
    [["Programmeur — candidat Professeur contractuel de Technologie", "Développeur Python — candidat …"],
     ["Bordeaux", "Paris"]]
Each pair is reported: replaced, or not found (then nothing is changed for it and the closest texts are shown).
"""
import difflib
import html
import json
import re
import sys
from pathlib import Path

TAG = re.compile(r"<[^>]+>")


def text_nodes(page):
    """[(start, end, text)] of the visible texts between tags (not inside <style>, <script> or <head>)."""
    body = re.search(r"<body\b[^>]*>", page, re.I)
    start = body.end() if body else 0
    out = []
    for m in re.finditer(r">([^<]+)<", page[start - 1:]):
        t = m.group(1)
        if t.strip():
            out.append((start - 1 + m.start(1), start - 1 + m.end(1), t))
    return [n for n in out if not re.search(r"<(style|script)\b[^>]*>[^<]*$", page[:n[0]], re.I)]


def flat(s):
    return " ".join(html.unescape(TAG.sub(" ", s)).split())


def replace(page, old, new):
    """The text found exactly (whitespace aside) in ONE text node, or across a run of nodes (inline tags)."""
    want = flat(old)
    nodes = text_nodes(page)
    for i in range(len(nodes)):
        joined = ""
        for j in range(i, min(i + 12, len(nodes))):
            joined = (joined + " " + flat(nodes[j][2])).strip()
            if want not in joined:
                if len(joined) > len(want) + 200:
                    break
                continue
            if i == j:  # inside one text: only that part changes, the rest of the text stays
                s, e, t = nodes[i]
                pattern = r"\s+".join(map(re.escape, html.escape(want, quote=False).split()))
                plain = r"\s+".join(map(re.escape, want.split()))
                for p in (plain, pattern):
                    if re.search(p, t):
                        return page[:s] + re.sub(p, lambda _: html.escape(new, quote=False), t, count=1) + page[e:], True
            if want in " ".join(flat(n[2]) for n in nodes[i + 1:j + 1]) or not want.startswith(flat(nodes[i][2])[:20]):
                break  # it starts in a later text: found from there
            # across inline tags: the first node gets the new text, the others are emptied (the tags stay)
            s0 = nodes[i][0]
            pieces, last = [], s0
            for k in range(i, j + 1):
                s, e, t = nodes[k]
                pieces.append(page[last:s])
                pieces.append(html.escape(new, quote=False) if k == i else "")
                last = e
            return page[:s0] + "".join(pieces) + page[last:], True
    return page, False


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
    src, pairs_f, dst = map(Path, sys.argv[1:])
    page = src.read_text(errors="replace")
    pairs = json.loads(pairs_f.read_text())
    done, missing = 0, []
    for pair in pairs:
        if not (isinstance(pair, list) and len(pair) == 2 and all(isinstance(x, str) for x in pair)):
            missing.append(f"  - {json.dumps(pair, ensure_ascii=False)[:90]} ignoré : chaque ligne est [\"texte du modèle\", \"nouveau texte\"]")
            continue
        old, new = pair
        page, ok = replace(page, old, new)
        if ok:
            done += 1
        else:
            texts = [flat(t) for _, _, t in text_nodes(page)]
            close = difflib.get_close_matches(flat(old), texts, n=2, cutoff=0.4)
            missing.append(f"  - « {old[:70]} » introuvable" + (f" ; textes proches : {' | '.join(c[:70] for c in close)}" if close else ""))
    dst.write_text(page)
    print(f"ok: {dst} — {done} texte(s) remplacé(s) sur {len(pairs)}, style du modèle intact.")
    if missing:
        print("Non trouvés (rien changé pour eux) : copie le texte tel qu'il est sur la page :\n" + "\n".join(missing))
    print(to_pdf(dst))


if __name__ == "__main__":
    main()
