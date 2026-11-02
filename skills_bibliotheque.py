"""The skills library: as many skills as wanted (even thousands), kept apart, NOT listed in Naim's instructions.

Naim's active skills (~/.naim/skills) are listed in every prompt, so they must stay few. The library
(~/.naim/skills-bibliotheque/<skill>/SKILL.md + its files) costs nothing until a task needs one: Naim calls
chercher_skill with a few words, then use_skill loads the one it picked. The index (name, description, first lines)
is rebuilt only when the folder changes.
"""
import json
import math
import re
import unicodedata
from pathlib import Path

import extensions as ext

LIB = ext.HOME / "skills-bibliotheque"
INDEX = LIB / ".index.json"
SCRIPT_EXTS = {".py", ".sh", ".js", ".mjs", ".ts", ".rb", ".pl", ".swift", ".applescript", ".bash", ".zsh", ".command"}
STOP = set("""le la les un une des de du d l et ou en au aux pour par sur dans avec sans mon ma mes ton ta tes son sa ses
ce cette ces qui que quoi comment faire fais fait je tu il on nous vous moi a the of to and or for with in on an is be
how make create use using
bonjour salut merci stp svp aider aide peux peut veux voudrais pourrais besoin please help hello hi thanks""".split())


# the usual words of a French request and their English twins (most skills are written in English), both ways
FR_EN = {
    "facture": "invoice", "devis": "quote estimate", "graphique": "chart graph", "diagramme": "diagram chart",
    "schema": "diagram schema", "tableur": "spreadsheet excel", "tableau": "table spreadsheet", "presentation": "slides presentation powerpoint",
    "diapo": "slides", "diapositive": "slide", "rapport": "report", "lettre": "letter", "courriel": "email", "mail": "email",
    "image": "image picture", "photo": "photo image", "video": "video", "son": "audio sound", "musique": "music audio",
    "traduction": "translation translate", "traduire": "translate", "resume": "summary summarize", "resumer": "summarize",
    "recherche": "research search", "chercher": "search find", "site": "website web", "application": "app application",
    "jeu": "game", "base": "database", "donnees": "data", "securite": "security", "test": "test testing", "tests": "testing",
    "deploiement": "deploy deployment", "serveur": "server", "contrat": "contract legal", "juridique": "legal",
    "comptabilite": "accounting finance", "banque": "bank finance", "marketing": "marketing", "vente": "sales",
    "cv": "resume cv", "candidature": "application job", "emploi": "job", "recrutement": "hiring recruiting",
    "medical": "medical health", "sante": "health", "infirmier": "nurse nursing", "cours": "course lesson", "eleve": "student",
    "apprendre": "learn learning", "planning": "schedule planning", "calendrier": "calendar", "reunion": "meeting",
    "note": "notes", "memo": "memo notes", "conception": "design", "dessin": "drawing design", "logo": "logo brand",
    "couleur": "color", "police": "font typography", "carte": "map card", "mobile": "mobile ios android",
    "telephone": "phone mobile", "fichier": "file", "dossier": "folder", "pdf": "pdf", "word": "docx word",
    "nettoyer": "clean", "analyse": "analysis analyze", "statistiques": "statistics stats", "prevision": "forecast",
    "previsionnel": "forecast budget", "depenses": "expenses budget", "referencement": "seo", "prix": "price pricing",
    "recuperer": "scrape extract", "recupere": "scrape extract", "extraire": "extract", "aspirer": "scrape crawl",
    "automatiquement": "automation automate", "automatiser": "automation automate", "securiser": "security secure",
    "securite": "security", "agenda": "calendar schedule", "rendez": "appointment calendar", "conteneur": "container docker",
    "conteneuriser": "docker container", "requete": "query request", "lente": "slow performance", "optimiser": "optimize performance",
    "prospection": "outreach cold prospecting", "client": "customer client", "clients": "customers", "transcrire": "transcribe transcription",
    "transcription": "transcription transcribe", "schema": "diagram", "architecture": "architecture", "unitaires": "unit",
    "composants": "components", "composant": "component", "reutilisables": "reusable", "accueil": "landing home",
    "jolie": "design beautiful", "joli": "design beautiful", "explicative": "explainer", "animee": "animated animation",
    "animation": "animation", "convertir": "convert", "texte": "text", "anglais": "english", "francais": "french",
    "propre": "clean", "envoyer": "send", "ecrire": "write", "redaction": "writing", "rediger": "write", "corriger": "fix review",
    "erreur": "error bug", "bogue": "bug", "deboguer": "debug", "ameliorer": "improve", "performance": "performance",
    "connexion": "login auth", "authentification": "authentication auth", "paiement": "payment", "boutique": "shop ecommerce",
    "commande": "order command", "stock": "inventory stock", "livre": "book", "article": "article blog", "blog": "blog",
    "reseaux": "social", "sociaux": "social", "publicite": "ads advertising", "electronique": "electronics hardware",
    "capteur": "sensor", "carte": "board card map", "microcontroleur": "microcontroller", "mainframe": "mainframe",
    "cours": "course lesson tutorial", "exercice": "exercise", "examen": "exam quiz", "quiz": "quiz",
}
EN_FR = {}
for _fr, _en in FR_EN.items():
    for _w in _en.split():
        EN_FR.setdefault(_w, _fr)


def _plain(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()


def _words(s):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9+#.-]{1,}", _plain(s)) if w not in STOP and len(w) > 1]


def _roots():
    """The library itself, then the skill folders of the big plugins that are on (hundreds of skills, found on demand)."""
    try:
        import plugins
        extra = [d for d in plugins.library_dirs() if d.is_dir()]
    except Exception:  # noqa: BLE001 — a broken plugin never hides the library
        extra = []
    return ([LIB] if LIB.is_dir() else []) + extra


def _stamp():
    """Changes when a skill is added, removed or edited (only the folders' times: cheap even for thousands)."""
    dirs = [d for r in _roots() for d in r.iterdir() if d.is_dir() and not d.name.startswith(".")]  # never its own index
    return f"{len(_roots())}:{len(dirs)}:{sum(int(d.stat().st_mtime_ns // 1000) for d in dirs)}" if dirs else ""


def index():
    """[{name, dir, description, head, scripts, path}] of every skill in the library (cached)."""
    stamp = _stamp()
    try:
        cached = json.loads(INDEX.read_text())
        if cached.get("stamp") == stamp:
            return cached["skills"]
    except (OSError, ValueError):
        pass
    out = []
    for d in [d for r in _roots() for d in sorted(r.iterdir())]:
        f = d / "SKILL.md"
        if not (d.is_dir() and f.is_file()):
            continue
        try:
            meta, body = ext.parse_skill(f)
        except Exception:  # noqa: BLE001 — an unreadable skill is skipped, never blocks the others
            continue
        files = [p for p in d.rglob("*") if p.is_file() and p.name != "SKILL.md"]
        out.append({"name": meta.get("name") or d.name, "dir": d.name, "path": str(f),
                    "description": str(meta.get("description") or body.strip().split("\n")[0])[:400],
                    "head": re.sub(r"\s+", " ", body)[:1200],
                    "scripts": sorted({p.suffix for p in files if p.suffix.lower() in SCRIPT_EXTS}),
                    "files": len(files)})
    LIB.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps({"stamp": stamp, "skills": out}, ensure_ascii=False))
    return out


def count():
    return len(index())


SUFFIXES = ("", "s", "es", "e", "ed", "er", "ers", "ing", "ion", "ions", "ent", "ant", "al", "ale", "aux", "ique", "iques", "ic", "ics")
_TOK = {"stamp": None, "data": []}
_DF = {}  # in how many skills each word is, for the current library


def _tokens():
    """Each skill with the whole words of its name, description and beginning (kept until the library changes)."""
    stamp = _stamp()
    if _TOK["stamp"] != stamp:
        bag = lambda t: frozenset(re.findall(r"[a-z0-9]+", _plain(t)))  # noqa: E731
        _TOK["data"] = [(s, (bag(s["name"] + " " + s["dir"]), bag(s["description"]), bag(s["head"]))) for s in index()]
        _TOK["stamp"] = stamp
    return _TOK["data"]


def _hit(w, bag):
    """The word itself, or a real variant of it (plural, conjugation): « chart » finds « charts », « graph » is not « graphql »."""
    if w in bag:
        return True
    root = w[:-1] if len(w) > 5 and w.endswith(("e", "s")) else w
    return len(root) >= 4 and any(root + suf in bag for suf in SUFFIXES)


def _rarity(words, data):
    """How rare each word is in the library (« arduino » in 3 skills weighs far more than « data » in 900): 1 for a
    word found in about a third of the skills, up to ~4 for a word found in a handful."""
    n = max(len(data), 1)
    out, seen = {}, _DF.setdefault(_TOK["stamp"], {})
    if len(_DF) > 1:  # the library changed: the counts of the former one go
        for k in [k for k in _DF if k != _TOK["stamp"]]:
            del _DF[k]
    for w in words:
        if w not in seen:
            seen[w] = sum(1 for _, (name, desc, head) in data if _hit(w, name) or _hit(w, desc) or _hit(w, head))
        df = seen[w]
        out[w] = math.log(1 + n / (1 + df)) / math.log(4)
        if len(w) < 3 and w not in ACRONYMS and w not in FR_EN:
            out[w] *= 0.2  # « ça va », « je », « va »: rare in skills, yet they say nothing about the task
    return out


ACRONYMS = set("cv ia ai ui ux js ts go db qa ci cd ml 3d 2d os ip vm pr io ar vr bi hr rh tv".split())


def search(query, n=8, min_score=1):
    """The library's skills that best match the words of the task: name ×4, description ×2, beginning of the text ×1,
    each word weighed by its rarity (each French word also looks for its English twin, and the other way round). The
    same skill met twice (two plugins ship « pdf ») is given once."""
    base = _words(query)
    if not base:
        return []
    words = list(dict.fromkeys(base + [t for w in base for t in (FR_EN.get(w, "").split() + [EN_FR.get(w, "")]) if t]))
    data = _tokens()
    weight = _rarity(words, data)
    scored = []
    for s, (name, desc, head) in data:
        score = 0
        for w in words:
            score += weight[w] * (4 * _hit(w, name) + 2 * _hit(w, desc) + 1 * _hit(w, head))
        if score >= min_score:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for _, s in scored:
        key = (s["name"].lower(), s["description"][:80].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= n:
            break
    return out


def suggestion(task):
    """The note joined to a task when no active skill fits it: the 3 closest skills of the library (empty if none really
    matches). Costs ~15 ms and a few lines; the instructions themselves never grow."""
    try:
        found = search(task, 3, min_score=4) if count() else []
    except Exception:  # noqa: BLE001
        return ""
    if not found:
        return ""
    return ("[Bibliothèque de skills : ces méthodes pourraient servir à cette demande. Si l'une la couvre, charge-la avec "
            "use_skill(nom) avant de commencer ; sinon ignore-les.]\n"
            + "\n".join(f"- {s['name']} : {s['description'][:160]}" for s in found))


def find(name):
    """A library skill by its name or folder, in the shape of extensions.list_skills()."""
    for s in index():
        if s["name"] == name or s["dir"] == name:
            d = Path(s["path"]).parent
            return {"name": s["name"], "dir": s["dir"], "description": s["description"], "scope": "bibliothèque",
                    "path": s["path"], "enabled": True,
                    "files": sorted(p.name for p in d.iterdir() if p.name != "SKILL.md" and not p.name.startswith("."))}
    return None
