"""The MCP library: as many MCP servers as wanted, kept apart from mcp.json, NOT listed in Naim's instructions.

Like the skills library: a server added here costs nothing until a task needs it. Naim calls chercher_mcp with a few
words, then use_mcp(name) starts it on demand. ~/.naim/mcp.json (the user's servers) is never changed by it.
File: ~/.naim/mcp-bibliotheque.json  {"mcpServers": {name: {command, args, env | type, url, headers, description, source}}}
"""
import json
import re
import unicodedata

import extensions as ext

FILE = ext.HOME / "mcp-bibliotheque.json"
STOP = set("""le la les un une des de du d l et ou en au aux pour par sur dans avec sans mon ma mes qui que faire
a the of to and or for with in on an is mcp server serveur""".split())


def _plain(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()


def servers():
    try:
        raw = json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in (raw.get("mcpServers") or {}).items() if isinstance(v, dict)}


def _save(all_):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps({"mcpServers": all_}, indent=2, ensure_ascii=False))


def count():
    return len(servers())


def add(name, cfg, description="", source=""):
    all_ = servers()
    all_[name] = {**{k: v for k, v in cfg.items() if k not in ("enabled", "disabled")},
                  "description": str(description or "")[:400], "source": source}
    _save(all_)
    return name


def remove(name):
    all_ = servers()
    if all_.pop(name, None) is not None:
        _save(all_)
        return True
    return False


def config(name):
    """The server's launch config (for MCPManager), or None."""
    cfg = servers().get(name)
    return {k: v for k, v in cfg.items() if k not in ("description", "source")} if cfg else None


def search(query, n=8, min_score=1):
    """The library's servers that best match the words of the task: name ×4, description ×2; whole words, and each
    French word also looks for its English twin (the same dictionary as the skills library)."""
    import skills_bibliotheque as sk
    base = [w for w in re.findall(r"[a-z0-9][a-z0-9+#.-]{1,}", _plain(query)) if w not in STOP and w not in sk.STOP]
    if not base:
        return []
    words = list(dict.fromkeys(base + [t for w in base for t in (sk.FR_EN.get(w, "").split() + [sk.EN_FR.get(w, "")]) if t]))
    bag = lambda t: frozenset(re.findall(r"[a-z0-9]+", _plain(t)))  # noqa: E731
    scored = []
    for name, cfg in servers().items():
        nm, desc = bag(name), bag(cfg.get("description", "") + " " + cfg.get("source", ""))
        score = sum(4 * sk._hit(w, nm) + 2 * sk._hit(w, desc) for w in words)
        if score >= min_score:
            scored.append((score, name, cfg))
    scored.sort(key=lambda x: -x[0])
    return [{"name": nm, "description": c.get("description", ""), "remote": bool(c.get("url"))} for _, nm, c in scored[:n]]


def suggestion(task):
    """The note joined to a task: the 2 closest servers of the MCP library (empty if none really matches)."""
    try:
        found = search(task, 2, min_score=4) if count() else []
    except Exception:  # noqa: BLE001
        return ""
    if not found:
        return ""
    return ("[Bibliothèque MCP : ces serveurs pourraient servir à cette demande. Si l'un convient, use_mcp(server=nom) "
            "pour voir ses outils ; sinon ignore-les.]\n" + "\n".join(f"- {s['name']} : {s['description'][:160]}" for s in found))
