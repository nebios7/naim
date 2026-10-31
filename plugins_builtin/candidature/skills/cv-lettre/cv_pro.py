"""The CV in the pdf-pro style, built from its facts: as many jobs, diplomas and sections as the person has (the model
has two jobs and one diploma: filling it would drop the rest), then the PDF in the same step.

    python3 cv_pro.py cv.json "<dossier>/CV_<Nom>.html"

cv.json (only what the source gives; a missing key is simply not shown):
{
  "nom": "Prénom NOM", "titre": "Poste visé", "kicker": "Curriculum vitæ", "photo": "/chemin/de/la/photo.jpg",
  "contact": [["Tél.", "06 …"], ["E-mail", "…"], ["Ville", "…"], ["En ligne", "GitHub", "https://github.com/…"]],
  "profil": "Deux ou trois phrases.",
  "experiences": [{"quand": "2023 — 2025", "poste": "…", "ou": "Entreprise · Ville", "points": ["…", "…"]}],
  "formations": [{"quand": "2024", "diplome": "…", "ou": "École · Ville", "points": []}],
  "sections": [{"titre": "Projets", "items": [{"quand": "", "titre": "…", "ou": "…", "points": ["…"]}]},
               {"titre": "Centres d'intérêt", "texte": "…"}, {"titre": "Certifications", "liste": ["…"]}],
  "competences": {"fortes": ["Python", "…"], "autres": ["Git", "…"]},
  "langues": [["Français", "Langue maternelle"], ["Anglais", "B2"]],
  "ordre": ["profil", "competences", "experiences", "Projets", "formations"]
}
"photo" (facultatif) : la photo de l'utilisateur, ronde, en haut à droite : le chemin de l'image, ou du CV Word joint
(sa photo est prise dedans). Elle est mise DANS la page : rien à copier ni à extraire.
"ordre" (facultatif) : l'ordre des rubriques du CV source (les clés, ou le titre d'une section) ; sinon profil,
expériences, formations, puis les sections.
"""
import html
import json
import re
import sys
from pathlib import Path

MODEL = Path.home() / ".naim/plugins/pdf-pro/skills/pdf-pro/exemples/cv.html"
PDFPRO = Path.home() / ".naim/plugins/pdf-pro/skills/pdf-pro/pdfpro.py"
# a rubric title stays with what follows it, a job or a diploma is never cut in two, skills and languages stay together
KEEP = ("<style>.rubrique{break-after:avoid;page-break-after:avoid}.poste,.deux,.tags,.niveaux{break-inside:avoid;"
        "page-break-inside:avoid}.carte>.rubrique+*{break-before:avoid}"
        "header:has(.photo){padding-right:33mm}header .photo{position:absolute;right:0;top:0;width:27mm;height:27mm;"
        "border-radius:50%;object-fit:cover;border:1px solid var(--line)}</style>\n")


def esc(t):
    return html.escape(str(t or "").strip())


def photo(path):
    """The person's photo, round, top right, inside the page itself (a data URI: the PDF needs no other file)."""
    if not path:
        return ""
    import base64
    import mimetypes
    f = Path(str(path)).expanduser()
    if not f.is_file():
        sys.exit(f"error: photo introuvable : {f} (donne le chemin exact de l'image jointe).")
    if f.suffix.lower() == ".docx":  # the photo inside the Word CV given: its largest picture
        import zipfile
        with zipfile.ZipFile(f) as z:
            pics = sorted((i for i in z.infolist() if i.filename.startswith("word/media/")
                           and Path(i.filename).suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp")), key=lambda i: -i.file_size)
            if not pics:
                sys.exit(f"error: pas d'image dans {f.name} : demande la photo à l'utilisateur.")
            data, name = z.read(pics[0]), pics[0].filename
    else:
        data, name = f.read_bytes(), f.name
    mime = mimetypes.guess_type(name)[0] or "image/jpeg"
    return f'<img class="photo" alt="" src="data:{mime};base64,{base64.b64encode(data).decode()}">'


def block(when, title, where, points):
    pts = "".join(f"<li>{esc(p)}</li>" for p in points or [] if str(p).strip())
    return (f'  <div class="poste">\n    <div class="quand">{esc(when)}</div>\n'
            f'    <div><h3>{esc(title)}</h3>' + (f'<div class="ou">{esc(where)}</div>' if str(where or "").strip() else "")
            + (f"\n      <ul>{pts}</ul>" if pts else "") + "</div>\n  </div>")


def card(title, inner):
    return f'<section class="carte">\n  <h2 class="rubrique">{esc(title)}</h2>\n{inner}\n</section>'


def body(cv):
    contact = []
    for c in cv.get("contact") or []:
        label, value, link = (list(c) + ["", ""])[:3]
        shown = f'<a href="{esc(link)}">{esc(value)}</a>' if link else esc(value)
        contact.append(f"<span><b>{esc(label)}</b>{shown}</span>")
    out = ["<header>" + photo(cv.get("photo")), f'  <div class="kicker">{esc(cv.get("kicker") or "Curriculum vitæ")}</div>', f'  <h1>{esc(cv.get("nom"))}</h1>']
    if cv.get("titre"):
        out.append(f'  <div class="titre">{esc(cv["titre"])}</div>')
    out += ['  <div class="band"></div>', '  <div class="contact">\n    ' + "\n    ".join(contact) + "\n  </div>", "</header>", ""]
    parts = {}
    if cv.get("profil"):
        parts["profil"] = card("Profil", f'  <p class="profil">{esc(cv["profil"])}</p>')
    if cv.get("experiences"):
        parts["experiences"] = card("Expérience", "\n".join(block(e.get("quand"), e.get("poste") or e.get("titre"), e.get("ou"), e.get("points"))
                                                          for e in cv["experiences"]))
    if cv.get("formations"):
        parts["formations"] = card("Formation", "\n".join(block(f.get("quand"), f.get("diplome") or f.get("titre"), f.get("ou"), f.get("points"))
                                                         for f in cv["formations"]))
    for s in cv.get("sections") or []:
        if s.get("items"):
            inner = "\n".join(block(i.get("quand"), i.get("titre"), i.get("ou"), i.get("points")) for i in s["items"])
        elif s.get("liste"):
            inner = '  <ul class="niveaux">' + "".join(f"<li><span>{esc(x)}</span><span></span></li>" for x in s["liste"]) + "</ul>"
        else:
            inner = f'  <p class="profil">{esc(s.get("texte"))}</p>'
        parts[s.get("titre") or f"section{len(parts)}"] = card(s.get("titre") or "", inner)
    comp, langs = cv.get("competences") or {}, cv.get("langues") or []
    if isinstance(comp, list):
        comp = {"fortes": [], "autres": comp}
    tags = "".join(f'<span class="tag fort">{esc(t)}</span>' for t in comp.get("fortes") or []) + \
        "".join(f'<span class="tag">{esc(t)}</span>' for t in comp.get("autres") or [])
    side = []
    if tags:
        side.append(card("Compétences", f'  <div class="tags">{tags}</div>'))
    if langs:
        side.append(card("Langues", '  <ul class="niveaux">' + "".join(
            f"<li><span>{esc(l[0])}</span><span>{esc(l[1] if len(l) > 1 else '')}</span></li>" for l in langs) + "</ul>"))
    if side:  # « competences » in "ordre": skills and languages side by side, where the source puts them
        parts["competences"] = '<div class="deux">\n' + "\n".join(side) + "\n</div>" if len(side) == 2 else side[0]
    order = [k for k in cv.get("ordre") or [] if k in parts]
    out += [parts[k] for k in order + [k for k in parts if k not in order]]
    return "\n\n".join(out)


def to_pdf(page):
    """The PDF next to the page (pdf-pro); if it fails the page is still there and convert_document does it."""
    import subprocess
    page = page.resolve()
    pdf = page.with_suffix(".pdf")
    if not PDFPRO.exists():
        return "PDF : à faire avec l'outil convert_document (pdf-pro absent)."
    try:
        r = subprocess.run([sys.executable, str(PDFPRO), "render", str(page), str(pdf)], capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as e:
        return f"PDF non fait ({e}) : fais-le avec l'outil convert_document."
    if r.returncode or not pdf.exists():
        return f"PDF non fait ({(r.stderr or r.stdout).strip()[-300:]}) : fais-le avec l'outil convert_document."
    pages = re.search(r"\((\d+) pages?\)", r.stdout)
    return (f"PDF : {pdf}" + (f" ({pages.group(1)} page(s))" if pages else "") + ". Regarde-le avec look_at ; pour changer "
            f"quelque chose, corrige cv.json et relance la même commande.")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    try:
        cv = json.loads(src.read_text())
    except ValueError as e:
        sys.exit(f"error: {src.name} n'est pas un JSON valide ({e}) : corrige-le et relance.")
    if not cv.get("nom"):
        sys.exit("error: « nom » manque dans cv.json.")
    model = MODEL.read_text(errors="replace")
    head = model[:re.search(r"<body\b[^>]*>", model, re.I).end()].replace("</head>", KEEP + "</head>", 1)
    dst.write_text(f"{head}\n<main>\n{body(cv)}\n</main>\n</body>\n</html>\n")
    comp = cv.get("competences") or {}
    n_comp = len(comp) if isinstance(comp, list) else len(comp.get("fortes") or []) + len(comp.get("autres") or [])
    print(f"ok: {dst} — {len(cv.get('experiences') or [])} expérience(s), {len(cv.get('formations') or [])} formation(s), "
          f"{n_comp} compétence(s), {len(cv.get('langues') or [])} langue(s), {len(cv.get('sections') or [])} autre(s) "
          f"rubrique(s). Compare ces nombres avec le CV source : il doit en avoir autant.")
    print(to_pdf(dst))


if __name__ == "__main__":
    main()
