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
import re
import shutil
import tarfile
import time
import urllib.request
from pathlib import Path

import extensions as ext

MAX_ARCHIVE = 60 * 1024 * 1024   # download limit
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


class SkillError(Exception):
    pass


def parse_url(url):
    """(owner, repo, ref, subpath) for a GitHub link, or ("raw", url) for a direct SKILL.md link."""
    u = url.strip().rstrip("/")
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


def _download(owner, repo, ref):
    key = (owner, repo, ref)
    if key in _cache and time.time() - _cache[key][0] < 600:
        return _cache[key][1]
    url = f"https://github.com/{owner}/{repo}/archive/{ref}.tar.gz"
    req = urllib.request.Request(url, headers={"User-Agent": ext.UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read(MAX_ARCHIVE + 1)
    except Exception as e:
        raise SkillError(f"téléchargement impossible de {owner}/{repo} : {e}")
    if len(data) > MAX_ARCHIVE:
        raise SkillError("dépôt trop gros (plus de 60 Mo)")
    _cache[key] = (time.time(), data)
    return data


def _members(data):
    """{relative path inside the repo: TarInfo} for regular files, plus the open archive."""
    tar = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
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


def install(url, names=None, root=None, scope="utilisateur"):
    """Install the skills found at `url` (only `names` if given). Returns the list of installed skill names."""
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
    tar, files = _members(_download(owner, repo, ref))
    for s in available:
        if names and s["name"] not in names and s["folder"] not in names:
            continue
        if s["size"] > MAX_SKILL:
            raise SkillError(f"le skill {s['name']} est trop gros ({s['size'] // 1_000_000} Mo)")
        name = ext.slugify(s["name"])
        folder = s["folder"]

        def write(dest, folder=folder):
            for path, m in files.items():
                if folder and not path.startswith(folder + "/"):
                    continue
                rel = path[len(folder) + 1:] if folder else path
                if rel.startswith((".github/", ".git/")):
                    continue
                target = (dest / rel).resolve()
                if dest.resolve() not in target.parents:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(m).read())
                if m.mode & 0o111:
                    target.chmod(0o755)
            (dest / ".source").write_text(f"{url}\n{owner}/{repo}@{ref}/{folder}\n")

        _replace(base / name, write)
        installed.append(name)
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
