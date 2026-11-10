"""The CV in the pdf-pro style, built from its facts: as many jobs, diplomas and sections as the person has (the model
has two jobs and one diploma: filling it would drop the rest), then the PDF in the same step.

    python3 cv_pro.py cv.json "<dossier>/CV_<Nom>.html"

cv.json (only what the source gives; a missing key is simply not shown):
{
  "nom": "Prénom NOM", "titre": "Poste visé", "kicker": "Curriculum vitæ", "photo": "/chemin/de/la/photo.jpg",
  "couleur": "gris",   (facultatif : gris, bleu, vert, rouge, noir, marine… ou #rrggbb ; orange sinon)
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

# a CV longer than two pages is tightened, step by step, then made again (same content, smaller spacing)
TIGHT = ["",
         "<style>body{font-size:9.4pt;line-height:1.4}header{padding-bottom:4mm;margin-bottom:4.5mm}header h1{font-size:24pt}"
         "header .band{margin:3mm 0}section.carte{margin-bottom:4mm}.poste{margin-bottom:2.6mm}.poste li{margin:.2mm 0}"
         "p.profil{font-size:9.8pt;line-height:1.45}.niveaux li{padding:.7mm 0}h2.rubrique{margin-bottom:2mm}</style>\n",
         "<style>@page{margin:12mm 14mm}body{font-size:8.9pt;line-height:1.35}header h1{font-size:21pt}.poste{grid-template-columns:"
         "25mm 1fr;margin-bottom:2mm}.poste h3{font-size:10.3pt}.poste .ou{margin:0 0 .8mm}section.carte{margin-bottom:3mm}"
         "p.profil{font-size:9.2pt}</style>\n"]


def accent(name):
    """The accent the user asked for (« gris », « bleu », #rrggbb), from pdf-pro: "" for its orange."""
    if not name or not PDFPRO.exists():
        return ""
    import importlib.util
    spec = importlib.util.spec_from_file_location("naim_pdfpro", PDFPRO)
    pro = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pro)
    return pro.accent_css(name)


def text_of(x):
    """Any value of cv.json as words: a dict ({"langue": "Anglais", "niveau": "B2"}) or a list is never shown with its
    braces and quotes — its values are joined (« Anglais — B2 »), a list with commas."""
    if isinstance(x, dict):
        return " — ".join(t for t in (text_of(v) for v in x.values()) if t)
    if isinstance(x, (list, tuple)):
        return ", ".join(t for t in (text_of(v) for v in x) if t)
    return str(x if x is not None else "").strip()


def esc(t):
    return html.escape(text_of(t))


NAME_KEYS = ("langue", "language", "nom", "name", "intitule", "titre", "label")
LEVEL_KEYS = ("niveau", "level", "maitrise", "degre", "note", "certification")


def lang_pair(l):
    """One language as [name, level], whatever cv.json gives: ["Anglais", "B2"], {"langue": …, "niveau": …},
    {"Anglais": "B2"}, or « Anglais (B2) » / « Anglais : B2 »."""
    if isinstance(l, (list, tuple)):
        return [text_of(l[0]).capitalize() if l else "", text_of(list(l[1:]))]
    if isinstance(l, dict):
        low = {slug(k): v for k, v in l.items()}
        name = next((low[k] for k in NAME_KEYS if str(low.get(k) or "").strip()), "")
        level = next((low[k] for k in LEVEL_KEYS if str(low.get(k) or "").strip()), "")
        if not name and len(l) == 1:  # {"Anglais": "B2"}
            name, level = next(iter(l.items()))
        if not name:
            vals = [v for v in l.values() if str(v or "").strip()]
            name, level = (vals[0] if vals else ""), vals[1:]
        return [text_of(name).capitalize(), text_of(level)]
    m = re.match(r"(.+?)\s*[(:—-]\s*([^)]*)\)?$", str(l))
    return [m.group(1).strip().capitalize(), m.group(2)] if m else [str(l).capitalize(), ""]


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


def pick(d, *keys):
    for k in keys:
        if str(d.get(k) or "").strip():
            return d[k]
    return ""


def entry(d, *title_keys):
    """One job, diploma or project, whatever names cv.json gives its fields (periode, entreprise, missions…)."""
    if not isinstance(d, dict):
        return {"quand": "", "titre": str(d), "ou": "", "points": []}
    where = pick(d, "ou") or " · ".join(str(d[k]) for k in ("entreprise", "societe", "employeur", "etablissement", "ecole",
                                                               "organisme", "lieu", "ville") if str(d.get(k) or "").strip())
    points = pick(d, "points", "missions", "taches", "realisations", "details", "description")
    if isinstance(points, str):
        points = [points]
    return {"quand": pick(d, "quand", "periode", "dates", "date", "annee", "duree"),
            "titre": pick(d, *title_keys, "titre", "intitule", "nom", "role"), "ou": where, "points": points}


LABELS = {"telephone": "Tél.", "tel": "Tél.", "email": "E-mail", "mail": "E-mail", "ville": "Ville", "adresse": "Adresse"}
TITLES = {"projets": "Projets", "publications": "Publications", "certifications": "Certifications", "benevolat": "Bénévolat",
          "centres_interet": "Centres d'intérêt", "interets": "Centres d'intérêt", "loisirs": "Loisirs", "references": "Références"}
GROUPS = {"basesdedonnees": "Bases de données", "systemes": "Systèmes", "methodes": "Méthodes", "reseaux": "Réseaux",
          "securite": "Sécurité", "logiciels": "Logiciels", "electronique": "Électronique"}
KNOWN = {"nom", "titre", "kicker", "photo", "couleur", "contact", "profil", "experiences", "formations", "sections", "competences",
         "langues", "ordre"}


def slug(t):
    import unicodedata
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFD", str(t)).encode("ascii", "ignore").decode().lower())


def tidy(cv):
    """cv.json as Naim wrote it -> the keys this script draws. Nothing of the source is dropped: a key with another
    name (projets, publications, entreprise, missions, skill groups, a contact dict) still reaches the page."""
    cv = dict(cv)
    if isinstance(cv.get("contact"), dict):
        cv["contact"] = [[LABELS.get(slug(k), k.replace("_", " ").capitalize()), v] + ([v] if re.match(r"https?://", str(v)) else [])
                         for k, v in cv["contact"].items() if str(v or "").strip()]
    cv["experiences"] = [entry(e, "poste") for e in cv.get("experiences") or []]
    cv["formations"] = [entry(f, "diplome") for f in cv.get("formations") or []]
    L = cv.get("langues") or []
    langs, groups = ([[k, v] for k, v in L.items()] if isinstance(L, dict) else list(L)), []  # {"Anglais": "B2"} too
    comp = cv.get("competences") or {}
    if isinstance(comp, dict):
        for k, v in list(comp.items()):
            if k in ("fortes", "autres"):
                continue
            if slug(k).startswith("langue"):
                langs += v if isinstance(v, list) else [v]
            else:
                groups.append([GROUPS.get(slug(k), k.replace("_", " ").capitalize()), text_of(v)])
            del comp[k]
    cv["competences"], cv["groupes"] = comp, groups
    cv["langues"] = [lang_pair(l) for l in langs]
    sections = list(cv.get("sections") or [])
    for k in [k for k in cv if k not in KNOWN and k != "groupes"]:
        v, title = cv.pop(k), TITLES.get(slug(k), k.replace("_", " ").capitalize())
        if isinstance(v, list) and v and all(isinstance(i, dict) for i in v):
            sections.append({"titre": title, "items": v})
        elif isinstance(v, list):
            sections.append({"titre": title, "liste": v})
        elif str(v or "").strip():
            sections.append({"titre": title, "texte": v})
    cv["sections"] = [dict(s, items=[entry(i) for i in s["items"]]) if s.get("items") else s for s in sections]
    return cv


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
        parts["experiences"] = card("Expérience", "\n".join(block(e["quand"], e["titre"], e["ou"], e["points"])
                                                          for e in cv["experiences"]))
    if cv.get("formations"):
        parts["formations"] = card("Formation", "\n".join(block(f["quand"], f["titre"], f["ou"], f["points"])
                                                         for f in cv["formations"]))
    for s in cv.get("sections") or []:
        if s.get("items"):
            inner = "\n".join(block(i["quand"], i["titre"], i["ou"], i["points"]) for i in s["items"])
        elif s.get("liste"):
            inner = '  <ul class="niveaux">' + "".join(f"<li><span>{esc(x)}</span><span></span></li>" for x in s["liste"]) + "</ul>"
        else:
            inner = f'  <p class="profil">{esc(s.get("texte"))}</p>'
        parts[slug(s.get("titre")) or f"section{len(parts)}"] = card(s.get("titre") or "", inner)
    comp, langs = cv.get("competences") or {}, cv.get("langues") or []
    if isinstance(comp, list):
        comp = {"fortes": [], "autres": comp}
    tags = "".join(f'<span class="tag fort">{esc(t)}</span>' for t in comp.get("fortes") or []) + \
        "".join(f'<span class="tag">{esc(t)}</span>' for t in comp.get("autres") or [])
    rows = "".join(f"<li><span>{esc(g)}</span><span>{esc(v)}</span></li>" for g, v in cv.get("groupes") or [])
    side = []
    if tags or rows:  # the source's own groups (Programmation : …) as rows, else tags
        side.append(card("Compétences", (f'  <ul class="niveaux">{rows}</ul>' if rows else "") + (f'\n  <div class="tags">{tags}</div>' if tags else "")))
    if langs:
        side.append(card("Langues", '  <ul class="niveaux">' + "".join(
            f"<li><span>{esc(l[0])}</span><span>{esc(l[1] if len(l) > 1 else '')}</span></li>" for l in langs) + "</ul>"))
    if side:  # « competences » in "ordre": skills and languages side by side, where the source puts them
        parts["competences"] = '<div class="deux">\n' + "\n".join(side) + "\n</div>" if len(side) == 2 else side[0]
    order = [slug(k) for k in cv.get("ordre") or [] if slug(k) in parts]
    out += [parts[k] for k in order + [k for k in parts if k not in order]]
    return "\n\n".join(out)


def to_pdf(page, remake=None):
    """The PDF next to the page (pdf-pro); if it fails the page is still there and convert_document does it.
    remake(level) writes the page again tighter: used while the PDF has more than two pages."""
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
    level = getattr(remake, "level", 0)
    if remake and pages and int(pages.group(1)) > 2 and level + 1 < len(TIGHT):
        remake.level = level + 1
        remake(remake.level)
        return to_pdf(page, remake)
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
    if "photo" not in cv:  # the source Word CV beside cv.json holds a photo: a faithful CV keeps it ("photo": "" = none)
        import zipfile
        for w in sorted(src.resolve().parent.glob("*.docx")):
            try:
                with zipfile.ZipFile(w) as z:
                    if any(n.startswith("word/media/") for n in z.namelist()):
                        cv["photo"] = str(w)
                        print(f"photo : prise dans {w.name} (le CV Word source). Pas de photo voulue : \"photo\": \"\" dans cv.json.")
                        break
            except (OSError, zipfile.BadZipFile):
                pass
    cv = tidy(cv)
    model = MODEL.read_text(errors="replace")
    page = f"<main>\n{body(cv)}\n</main>\n</body>\n</html>\n"
    color = accent(cv.get("couleur"))  # « trait gris », « en bleu »: the lines and small titles in that colour

    def write(level=0):
        head = model[:re.search(r"<body\b[^>]*>", model, re.I).end()].replace("</head>", KEEP + TIGHT[level] + color + "</head>", 1)
        dst.write_text(f"{head}\n{page}")
    write()
    comp = cv.get("competences") or {}
    n_comp = (len(comp) if isinstance(comp, list) else len(comp.get("fortes") or []) + len(comp.get("autres") or [])) + \
        sum(len(v.split(",")) for _, v in cv.get("groupes") or [])
    other = ", ".join(f"{x.get('titre')} ({len(x.get('items') or x.get('liste') or [])})" if x.get("items") or x.get("liste")
                      else str(x.get("titre")) for x in cv["sections"]) or "aucune"
    print(f"ok: {dst} — {len(cv['experiences'])} expérience(s), {len(cv['formations'])} formation(s), "
          f"{n_comp} compétence(s), {len(cv['langues'])} langue(s), autres rubriques : {other}, "
          f"photo : {'oui' if cv.get('photo') else 'non'}. Compare chaque nombre avec le CV source (et sa photo) : "
          f"un 0 ou un manque = une rubrique du source absente du CV, corrige cv.json et relance.")
    print(to_pdf(dst, write))


if __name__ == "__main__":
    main()
