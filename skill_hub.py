"""Install skills from the internet (GitHub repositories or a direct SKILL.md link) into ~/.naim/skills.

Accepted links:
  owner/repo                                   every skill of the repository
  https://github.com/owner/repo                idem
  https://github.com/owner/repo/tree/<branch>/<path>   the skill(s) under that folder
  https://github.com/owner/repo/blob/<branch>/<path>/SKILL.md
  https://…/SKILL.md                           a single-file skill (raw link)

The repository is downloaded once as a tar.gz archive (no git, no API rate limit), then every folder that contains
a SKILL.md is copied with its scripts and resources. Files are only copied, never executed.
"""
import io
import os
import re
import shutil
import tarfile
import threading
import time
import urllib.request
from pathlib import Path

import extensions as ext

MAX_ARCHIVE = 1024 * 1024 * 1024  # download limit (1 Go): the archive goes to disk, never whole in memory
CACHE_DIR = ext.HOME / "cache" / "depots-skills"  # downloaded archives, kept 10 min (browse then install)
MAX_SKILL = 25 * 1024 * 1024     # size limit of one installed skill
POPULAR = [
    {"url": "anthropics/skills", "title": "Skills officiels (documents, PDF, Excel…)",
     "description": "Documents (PDF, Word, Excel, PowerPoint), design, tests d'apps web, création de skills…"},
    {"url": "SimoneAvogadro/android-reverse-engineering-skill", "title": "Rétro-ingénierie Android",
     "description": "Décompiler un APK (jadx) et retrouver les appels d'API, le flux de l'app."},
    {"url": "P4nda0s/reverse-skills", "title": "Reverse skills (binaires)",
     "description": "Frida, IDAPython, reconstruction de structures et de symboles, Unicorn, IL2CPP."},
]
_cache = {}

# The skills library a new Naim can fetch (welcome screen, Personnaliser): each pack is downloaded from its authors'
# own repositories, under their license, into the library (found by chercher_skill, never listed in the prompt).
# « also »: the same repository under an older name (a library filled before it moved still counts as installed)
PACKS = [
    {"id": "general", "title": "Bibliothèque générale", "count": 2900, "size": "100 Mo", "license": "MIT", "on": True,
     "description": "Développement, données, marketing, documents, sécurité, IA… pour presque toute demande.",
     "sources": ["sickn33/agentic-awesome-skills"], "also": ["sickn33/antigravity-awesome-skills"]},
    {"id": "ecc", "title": "Développement et vidéo (ECC)", "count": 317, "size": "3 Mo", "license": "MIT", "on": True,
     "description": "Tests, revue de code, architecture, vidéo (Remotion, Manim), motion design, interfaces animées.",
     "sources": ["affaan-m/ECC"]},
    {"id": "officiels", "title": "Skills officiels", "count": 20, "size": "18 Mo", "license": "selon le skill", "on": True,
     "description": "Word, Excel, PowerPoint, PDF, affiches, thèmes, pages web : les skills publiés par Anthropic.",
     "sources": ["anthropics/skills"]},
    {"id": "design", "title": "Design d'interfaces", "count": 28, "size": "2 Mo", "license": "MIT, Apache-2.0",
     "on": True,
     "description": "Règles d'Apple, critique et accessibilité d'un design, design system, React et Next.js, "
                    "décortiquer une app pour la refaire.",
     "sources": ["dickwu/apple-design-skill", "https://github.com/anthropics/knowledge-work-plugins/tree/main/design",
                 "vercel-labs/agent-skills", "Jakeschincariol/replica-skill"]},
    {"id": "applications", "title": "Automatiser des applications", "count": 840, "size": "2 Mo",
     "license": "voir le dépôt", "on": False,
     "description": "Gmail, Slack, Notion, Trello, HubSpot… (plus de 800 services) par Composio : un compte Composio "
                    "est nécessaire.",
     "sources": ["github:1078079172"]},
    {"id": "retro", "title": "Rétro-ingénierie", "count": 9, "size": "1 Mo", "license": "Apache-2.0, Unlicense…",
     "on": False,
     "description": "Analyser une app Android ou iOS, un binaire (Frida, Ghidra) : pour la sécurité de tes propres "
                    "logiciels.",
     "sources": ["P4nda0s/reverse-skills", "SimoneAvogadro/android-reverse-engineering-skill",
                 "github:1194491216"]},
]


def _repo_key(url):
    try:
        p = parse_url(url)  # a repository given by its number is looked up once (installed under its real name)
    except SkillError:
        return url.lower()
    return f"{p[1]}/{p[2]}".lower() if p[0] == "github" else url.lower()


def packs_status():
    """The packs, each with how many of its skills the library already holds."""
    import skills_bibliotheque
    held = {}
    if skills_bibliotheque.LIB.is_dir():
        for src in skills_bibliotheque.LIB.glob("*/.source"):
            try:
                key = _repo_key(src.read_text().split("\n", 1)[0].strip())
            except OSError:
                continue
            held[key] = held.get(key, 0) + 1
    out = []
    for pk in PACKS:
        n = sum(held.get(_repo_key(u), 0) for u in pk["sources"] + pk.get("also", []))
        out.append({k: v for k, v in pk.items() if k != "also"} | {"installed": n})
    return out


def install_pack(pid, progress=None):
    """Every skill of a pack's repositories into the library; a source that fails does not stop the others.
    Returns (installed names, errors)."""
    pack = next((pk for pk in PACKS if pk["id"] == pid), None)
    if not pack:
        raise SkillError(f"pack inconnu : {pid}")
    got, errors = [], []
    for url in pack["sources"]:
        try:
            names = [s["name"] for s in browse(url)]
            got += install(url, names, scope="bibliotheque",
                           progress=(lambda d, t, u=url: progress(u, d, t)) if progress else None)
        except Exception as e:  # noqa: BLE001 — one repository moved or offline: the others are still installed
            errors.append(f"{url} : {e}")
    return got, errors


class SkillError(Exception):
    pass


_ids = {}  # GitHub repository number -> "owner/repo" (looked up once)


def _by_id(num):
    """A repository by its GitHub number: still found after it is renamed or moved to another owner."""
    if num not in _ids:
        import json
        try:
            text, _, _ = ext._get(f"https://api.github.com/repositories/{num}", limit=200_000)
            _ids[num] = json.loads(text)["full_name"]
        except Exception as e:  # noqa: BLE001
            raise SkillError(f"dépôt GitHub n° {num} introuvable ({e})")
    return _ids[num]


def parse_url(url):
    """(owner, repo, ref, subpath) for a GitHub link, or ("raw", url) for a direct SKILL.md link.
    Also « github:<number>[/path] »: a repository by its GitHub number (it survives a rename)."""
    u = url.strip().rstrip("/")
    m = re.fullmatch(r"github:(\d+)(?:/(.*))?", u)
    if m:
        return ("github", *_by_id(m.group(1)).split("/", 1), "HEAD", m.group(2) or "")
    if re.fullmatch(r"[\w.-]+/[\w.-]+", u):
        return ("github", *u.split("/"), "HEAD", "")
    m = re.match(r"https?://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/(?:tree|blob)/([^/]+)(?:/(.*))?)?$", u)
    if m:
        owner, repo, ref, sub = m.groups()
        sub = sub or ""
        if sub.endswith("SKILL.md"):
            sub = sub[: -len("SKILL.md")].rstrip("/")
        return ("github", owner, repo, ref or "HEAD", sub)
    m = re.match(r"https?://raw\.githubusercontent\.com/([\w.-]+)/([\w.-]+)/([^/]+)/(.*)$", u)
    if m and m.group(4).endswith("SKILL.md"):
        owner, repo, ref, path = m.groups()
        return ("github", owner, repo, ref, path[: -len("SKILL.md")].rstrip("/"))
    if u.startswith(("http://", "https://")) and u.endswith(".md"):
        return ("raw", u)
    raise SkillError("lien non reconnu : donne un lien GitHub (owner/repo ou https://github.com/…) ou un lien vers un SKILL.md")


_dl_locks, _dl_guard = {}, threading.Lock()


def _download(owner, repo, ref):
    """The repository's archive, written to disk as it arrives (up to 1 Go); its path. One download at a time per
    repository (a double click on « Parcourir », or browse and install together, waits for it and shares it)."""
    key = (owner, repo, ref)
    with _dl_guard:
        lock = _dl_locks.setdefault(key, threading.Lock())
    with lock:
        return _download_locked(owner, repo, ref, key)


def _download_locked(owner, repo, ref, key):
    if key in _cache and time.time() - _cache[key][0] < 600 and _cache[key][1].exists():
        return _cache[key][1]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for old in [*CACHE_DIR.glob("*.tar.gz"), *CACHE_DIR.glob("*.part")]:  # older than 10 minutes: not needed any more
        if time.time() - old.stat().st_mtime > 600:
            old.unlink(missing_ok=True)
    dst = CACHE_DIR / re.sub(r"[^\w.-]", "_", f"{owner}-{repo}-{ref}.tar.gz")
    tmp = dst.parent / f"{dst.name}.{os.getpid()}.{threading.get_ident()}.part"  # its own temporary file
    url = f"https://github.com/{owner}/{repo}/archive/{ref}.tar.gz"
    req = urllib.request.Request(url, headers={"User-Agent": ext.UA})
    size = 0
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                size += len(chunk)
                if size > MAX_ARCHIVE:
                    raise SkillError("dépôt trop gros (plus de 1 Go)")
                f.write(chunk)
    except SkillError:
        tmp.unlink(missing_ok=True)
        raise
    except Exception as e:
        tmp.unlink(missing_ok=True)
        raise SkillError(f"téléchargement impossible de {owner}/{repo} : {e}")
    tmp.replace(dst)
    _cache[key] = (time.time(), dst)
    return dst


def _members(archive):
    """{relative path inside the repo: TarInfo} for regular files, plus the open archive (read from disk)."""
    tar = tarfile.open(archive, mode="r:gz") if isinstance(archive, Path) else tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz")
    files = {}
    for m in tar.getmembers():
        if not m.isfile():
            continue  # skip links, devices, folders
        parts = m.name.split("/", 1)
        if len(parts) == 2 and ".." not in Path(parts[1]).parts and not parts[1].startswith("/"):
            files[parts[1]] = m
    return tar, files


def _meta(text):
    return ext.parse_frontmatter(text)


def browse(url):
    """List the skills available at a link: [{name, description, folder, files, size}]."""
    p = parse_url(url)
    if p[0] == "raw":
        text, _, _ = ext._get(p[1], limit=500_000)
        meta, body = _meta(text)
        return [{"name": meta.get("name") or Path(p[1]).parent.name or "skill", "folder": "",
                 "description": meta.get("description", body.strip().split("\n")[0][:200]), "files": 1, "size": len(text)}]
    _, owner, repo, ref, sub = p
    tar, files = _members(_download(owner, repo, ref))
    out = []
    for path, m in sorted(files.items()):
        if not path.endswith("SKILL.md") or (sub and not (path == f"{sub}/SKILL.md" or path.startswith(sub + "/"))):
            continue
        folder = path[: -len("SKILL.md")].rstrip("/")
        meta, body = _meta(tar.extractfile(m).read().decode("utf-8", errors="replace"))
        inside = [f for f in files if folder == "" or f.startswith(folder + "/")]
        out.append({"name": meta.get("name") or Path(folder).name or repo, "folder": folder,
                    "description": meta.get("description", body.strip().split("\n")[0][:200])[:300],
                    "license": meta.get("license", ""), "files": len(inside),
                    "size": sum(files[f].size for f in inside)})
    if not out:
        raise SkillError("aucun SKILL.md trouvé à cette adresse")
    return out


def install(url, names=None, root=None, scope="utilisateur", progress=None):
    """Install the skills found at `url` (only `names` if given). Returns the list of installed skill names."""
    if scope == "bibliotheque":  # the library: as many as wanted, found by chercher_skill, not listed in the prompt
        import skills_bibliotheque
        base = skills_bibliotheque.LIB
    else:
        base = (Path(root) / ".naim" / "skills") if scope == "projet" and root else ext.HOME / "skills"
    base.mkdir(parents=True, exist_ok=True)
    p = parse_url(url)
    installed = []
    if p[0] == "raw":
        text, _, _ = ext._get(p[1], limit=500_000)
        meta, _ = _meta(text)
        name = ext.slugify(meta.get("name") or Path(p[1]).parent.name or "skill")
        _replace(base / name, lambda d: (d / "SKILL.md").write_text(text))
        return [name]
    _, owner, repo, ref, sub = p
    available = browse(url)
    archive = _download(owner, repo, ref)
    wanted = set(names or [])
    chosen = {}  # skill folder in the repo → its folder in Naim
    for s in available:
        if wanted and s["name"] not in wanted and s["folder"] not in wanted:
            continue
        if s["size"] > MAX_SKILL:
            if wanted and len(wanted) > 1:
                continue  # « Tout installer »: one skill too big is skipped, the others are installed
            raise SkillError(f"le skill {s['name']} est trop gros ({s['size'] // 1_000_000} Mo)")
        name = ext.slugify(s["name"])
        if name in (d.name for d in chosen.values()):  # two skills with the same name in one repository: the first
            continue
        chosen[s["folder"]] = base / name
    if not chosen:
        raise SkillError("aucun skill correspondant à installer")
    for dest in chosen.values():  # an existing skill with the same name is kept in .anciens/ first
        if dest.exists():
            src = dest / ".source"
            if src.is_file() and src.read_text().split("\n", 1)[0].strip() == url:
                shutil.rmtree(dest)  # the same repository installed again: replaced, no thousand useless copies
            else:
                backup = dest.parent / ".anciens" / f"{dest.name}-{time.strftime('%Y%m%d-%H%M%S')}"
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(backup))
        dest.mkdir(parents=True)
    # ONE pass through the archive (a big repository has thousands of skills: reading it again for each one, or
    # looking through all its files for each skill, took minutes); each file goes to the skill folder that holds it
    folders = sorted(chosen, key=len, reverse=True)
    roots = {f for f in folders}
    done, total = 0, len(chosen)
    seen_skill = set()
    with tarfile.open(archive, mode="r|gz") if isinstance(archive, Path) else tarfile.open(fileobj=io.BytesIO(archive), mode="r|gz") as tar:
        for m in tar:
            if not m.isfile():
                continue
            parts = m.name.split("/", 1)
            if len(parts) != 2 or ".." in Path(parts[1]).parts or parts[1].startswith("/"):
                continue
            path = parts[1]
            folder = "" if "" in roots else None
            pp = path.split("/")
            for k in range(len(pp) - 1, 0, -1):  # the deepest skill folder that holds this file
                cand = "/".join(pp[:k])
                if cand in roots:
                    folder = cand
                    break
            if folder is None:
                continue
            rel = path[len(folder) + 1:] if folder else path
            if rel.startswith((".github/", ".git/")):
                continue
            dest = chosen[folder]
            target = (dest / rel).resolve()
            if dest.resolve() not in target.parents:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            fobj = tar.extractfile(m)
            if fobj is None:
                continue
            target.write_bytes(fobj.read())
            if m.mode & 0o111:
                target.chmod(0o755)
            if folder not in seen_skill:
                seen_skill.add(folder)
                done += 1
                if progress and done % 50 == 0:
                    progress(done, total)
    installed = []
    for folder, dest in chosen.items():
        if any(dest.iterdir()):
            (dest / ".source").write_text(f"{url}\n{owner}/{repo}@{ref}/{folder}\n")
            installed.append(dest.name)
        else:
            dest.rmdir()
    if progress:
        progress(total, total)
    if not installed:
        raise SkillError("aucun skill correspondant à installer")
    return installed


def _replace(dest, write):
    """Write a skill folder; an existing skill with the same name is kept in skills/.anciens/ first."""
    if dest.exists():
        backup = dest.parent / ".anciens" / f"{dest.name}-{time.strftime('%Y%m%d-%H%M%S')}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dest), str(backup))
    dest.mkdir(parents=True)
    try:
        write(dest)
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise


def install_file(data, filename, root=None, scope="utilisateur"):
    """A skill from this Mac: a `.skill` or `.zip` archive (a folder with its SKILL.md and files) or a SKILL.md alone.
    Only copied, never executed; nothing outside the skill's folder is written. Returns [name]."""
    import zipfile
    if scope == "bibliotheque":
        import skills_bibliotheque
        base = skills_bibliotheque.LIB
    else:
        base = (Path(root) / ".naim" / "skills") if scope == "projet" and root else ext.HOME / "skills"
    base.mkdir(parents=True, exist_ok=True)
    if len(data) > MAX_SKILL:
        raise SkillError(f"fichier trop gros ({len(data) // 1_000_000} Mo, au plus {MAX_SKILL // 1_000_000} Mo)")
    if not data[:4] == b"PK\x03\x04":  # not an archive: a SKILL.md alone
        text = data.decode("utf-8", errors="replace")
        meta, body = _meta(text)
        if not body.strip() or not (meta.get("name") or meta.get("description")):
            raise SkillError("ce fichier n'est ni une archive .skill / .zip ni un SKILL.md (avec son en-tête name / description)")
        name = ext.slugify(meta.get("name") or Path(filename).stem or "skill")
        _replace(base / name, lambda d: (d / "SKILL.md").write_text(text))
        return [name]
    zf = zipfile.ZipFile(io.BytesIO(data))
    files = [i for i in zf.infolist() if not i.is_dir() and "__MACOSX" not in i.filename and not Path(i.filename).name.startswith("._")]
    skills = sorted((i for i in files if Path(i.filename).name == "SKILL.md"), key=lambda i: i.filename.count("/"))
    if not skills:
        raise SkillError("aucun SKILL.md dans cette archive")
    if sum(i.file_size for i in files) > MAX_SKILL:
        raise SkillError(f"skill trop gros une fois décompressé (au plus {MAX_SKILL // 1_000_000} Mo)")
    parent = str(Path(skills[0].filename).parent)
    top = "" if parent == "." else parent  # the folder holding the SKILL.md (« retro-editorial-fonts/ »), or the root
    meta, _ = _meta(zf.read(skills[0]).decode("utf-8", errors="replace"))
    name = ext.slugify(meta.get("name") or (Path(top).name if top else Path(filename).stem) or "skill")

    def write(dest):
        for i in files:
            rel = i.filename[len(top) + 1:] if top else i.filename
            if not rel or (top and not i.filename.startswith(top + "/")):
                continue  # outside the skill's folder
            out = (dest / rel).resolve()
            if dest.resolve() not in out.parents:
                raise SkillError(f"chemin refusé dans l'archive : {i.filename}")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(zf.read(i))
    _replace(base / name, write)
    return [name]
