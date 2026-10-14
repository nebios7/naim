"""The skills library: as many skills as wanted (even thousands), kept apart, NOT listed in Naim's instructions.

Naim's active skills (~/.naim/skills) are listed in every prompt, so they must stay few. The library
(~/.naim/skills-bibliotheque/<skill>/SKILL.md + its files) costs nothing until a task needs one: Naim calls
chercher_skill with a few words, then use_skill loads the one it picked. The index (name, description, first lines)
is rebuilt only when the folder changes.
"""
import json
import re
import unicodedata
from pathlib import Path

import extensions as ext

LIB = ext.HOME / "skills-bibliotheque"
INDEX = LIB / ".index.json"
SCRIPT_EXTS = {".py", ".sh", ".js", ".mjs", ".ts", ".rb", ".pl", ".swift", ".applescript", ".bash", ".zsh", ".command"}
STOP = set("""le la les un une des de du d l et ou en au aux pour par sur dans avec sans mon ma mes ton ta tes son sa ses
ce cette ces qui que quoi comment faire fais fait je tu il on nous vous moi a the of to and or for with in on an is be
how make create use using""".split())


def _plain(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()


def _words(s):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9+#.-]{1,}", _plain(s)) if w not in STOP and len(w) > 1]


def _stamp():
    """Changes when a skill is added, removed or edited (only the folders' times: cheap even for thousands)."""
    if not LIB.is_dir():
        return ""
    dirs = [d for d in LIB.iterdir() if d.is_dir() and not d.name.startswith(".")]  # never its own index file
    return f"{len(dirs)}:{sum(int(d.stat().st_mtime_ns // 1000) for d in dirs)}"


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
    for d in sorted(LIB.iterdir()) if LIB.is_dir() else []:
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
    if LIB.is_dir():
        INDEX.write_text(json.dumps({"stamp": stamp, "skills": out}, ensure_ascii=False))
    return out


def count():
    return len(index())


def search(query, n=8):
    """The library's skills that best match the words of the task: name ×4, description ×2, beginning of the text ×1."""
    words = _words(query)
    if not words:
        return []
    scored = []
    for s in index():
        name, desc, head = _plain(s["name"] + " " + s["dir"]), _plain(s["description"]), _plain(s["head"])
        score = 0
        for w in words:
            stem = w[:6] if len(w) > 6 else w
            score += 4 * (stem in name) + 2 * (stem in desc) + 1 * (stem in head)
        if score:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:n]]


def find(name):
    """A library skill by its name or folder, in the shape of extensions.list_skills()."""
    for s in index():
        if s["name"] == name or s["dir"] == name:
            d = Path(s["path"]).parent
            return {"name": s["name"], "dir": s["dir"], "description": s["description"], "scope": "bibliothèque",
                    "path": s["path"], "enabled": True,
                    "files": sorted(p.name for p in d.iterdir() if p.name != "SKILL.md" and not p.name.startswith("."))}
    return None
