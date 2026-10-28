"""Naim's plugins: one folder that brings skills, MCP servers, « / » commands and the tools they need, on or off in one click.

A plugin lives in ~/.naim/plugins/<name>/ with a plugin.json:
    {"name": "electronique", "version": "1.0", "description": "...",
     "skills": "skills",                                   folder of skills (each <skill>/SKILL.md, plus its files)
     "triggers": {"arduino": "\\b(arduino|esp32)\\b"},      words that pick a skill of the plugin (regex, lowercase text)
     "mcp": {"serveur": {"command": "...", "args": []}},   MCP servers (${PLUGIN_DIR} = the plugin's folder)
     "commands": [{"cmd": "/televerser", "description": "...", "prompt": "..."}],
     "tools": [{"cmd": "arduino-cli", "brew": "arduino-cli", "why": "compiler et téléverser"}],
     "hooks": {"PostToolUse": [{"matcher": "write_file|edit_file", "hooks": [{"type": "command", "command": "${PLUGIN_DIR}/verifier.sh"}]}]}}
     (hooks: the same format as ~/.naim/hooks.json, see hooks.py)
     "library": "skills",                                  instead of "skills": a big set of skills, found on demand in
                                                           the skills library (chercher_skill), never listed in the prompt
     "hooks_off": true                                     hooks brought but not run until the user turns them on
     "hooks_env": {"NOM": "valeur"}                        settings given to its hooks (e.g. a check they can turn off)
Plugins made for other coding agents (a .<agent>-plugin/ folder with plugin.json, a marketplace.json) are translated at
install: see the end.
Plugins shipped with Naim (plugins_builtin/) are copied once; ~/.naim/plugins.json keeps which are on, and which the
user removed (never re-installed). Removing a plugin moves it to the Trash.
"""
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import extensions as ext

PLUGINS = ext.HOME / "plugins"
STATE = ext.HOME / "plugins.json"
BUILTIN = Path(__file__).with_name("plugins_builtin")
BREW = next((b for b in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew") if Path(b).exists()), shutil.which("brew"))


class PluginError(Exception):
    pass


def _state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {"enabled": {}, "removed": [], "versions": {}}


def _save(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1, ensure_ascii=False))


def _manifest(d):
    try:
        m = json.loads((d / "plugin.json").read_text())
    except (OSError, ValueError):
        return None
    return m if isinstance(m, dict) and m.get("name") else None


def _ver(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0"))[:4])


def ensure_builtin():
    """Plugins shipped with Naim: installed once (on), updated to a newer version while the user has not removed them."""
    if not BUILTIN.is_dir():
        return
    st, changed = _state(), False
    PLUGINS.mkdir(parents=True, exist_ok=True)
    for src in sorted(BUILTIN.iterdir()):
        m = _manifest(src)
        if not m or m["name"] in st.get("removed", []):
            continue
        dst = PLUGINS / m["name"]
        cur = _manifest(dst) if dst.is_dir() else None
        if cur and _ver(cur.get("version")) >= _ver(m.get("version")):
            continue
        if dst.exists():  # an older copy: kept aside, never lost
            back = ext.HOME / "plugins.anciens" / f"{m['name']}-{time.strftime('%Y%m%d-%H%M%S')}"
            back.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(back))
        shutil.copytree(src, dst)
        st.setdefault("enabled", {}).setdefault(m["name"], True)
        changed = True
    if changed:
        _save(st)


def _which(cmd):
    return shutil.which(cmd) or next((str(p) for p in (Path("/opt/homebrew/bin") / cmd, Path("/usr/local/bin") / cmd) if p.exists()), None)


def all_plugins():
    ensure_builtin()
    st, out = _state(), []
    for d in sorted(PLUGINS.glob("*")) if PLUGINS.is_dir() else []:
        m = _manifest(d)
        if not m:
            continue
        sk = d / (m.get("library") or m.get("skills") or "skills")
        tools = [{**t, "ok": bool(_which(t.get("cmd", "")))} for t in m.get("tools") or [] if isinstance(t, dict)]
        out.append({"name": m["name"], "version": m.get("version", ""), "description": m.get("description", ""),
                    "enabled": st.get("enabled", {}).get(m["name"], True), "path": str(d),
                    "builtin": (BUILTIN / d.name).is_dir(),
                    "skills": [] if m.get("library") else sorted(x.name for x in sk.iterdir() if (x / "SKILL.md").is_file()) if sk.is_dir() else [],
                    "library_skills": sum(1 for x in sk.iterdir() if (x / "SKILL.md").is_file()) if m.get("library") and sk.is_dir() else 0,
                    "hooks_off": bool(m.get("hooks_off")), "origin": m.get("origin", ""),
                    "mcp": sorted((m.get("mcp") or {}).keys()), "commands": m.get("commands") or [], "tools": tools,
                    "hooks": sorted((m.get("hooks") or {}).keys()) if isinstance(m.get("hooks"), dict) else []})
    return out


def _enabled():
    return [p for p in all_plugins() if p["enabled"]]


def skill_dirs():
    """(scope, folder) of the skills of the plugins that are on."""
    out = []
    for p in _enabled():
        m = _manifest(Path(p["path"])) or {}
        if not m.get("library"):  # a library plugin's skills are found on demand, not listed
            out.append((f"plugin:{p['name']}", Path(p["path"]) / (m.get("skills") or "skills")))
    return out


def library_dirs():
    """Folders of skills that join the skills library (big plugins: hundreds of skills found on demand)."""
    return [Path(p["path"]) / m["library"] for p in _enabled() if (m := _manifest(Path(p["path"])) or {}).get("library")]


def long_skills():
    """Skills of the plugins marked « long » in their plugin.json (a whole book to translate…): their work takes hundreds
    of steps, so the Chat gives them as many as the Agent."""
    return {k for p in _enabled() for m in [(_manifest(Path(p["path"])) or {})] if m.get("long")
            for k in (m.get("triggers") or {})}


def priority_skills():
    """Skills of the plugins marked « priority » in their plugin.json: their words are checked before Naim's own."""
    return [k for p in _enabled() if (_manifest(Path(p["path"])) or {}).get("priority")
            for k in ((_manifest(Path(p["path"])) or {}).get("triggers") or {})]


def triggers():
    """{skill name: regex} of the plugins that are on."""
    out = {}
    for p in _enabled():
        for k, v in ((_manifest(Path(p["path"])) or {}).get("triggers") or {}).items():
            try:
                re.compile(v)
                out[k] = v
            except re.error:
                pass
    return out


def mcp_servers():
    """MCP servers of the plugins that are on: {« plugin-server »: cfg} (not written to mcp.json)."""
    out = {}
    for p in _enabled():
        d = Path(p["path"])
        for name, cfg in ((_manifest(d) or {}).get("mcp") or {}).items():
            if isinstance(cfg, dict):
                cfg = json.loads(json.dumps(cfg).replace("${PLUGIN_DIR}", str(d).replace("\\", "\\\\")))
                out[f"{p['name']}-{name}"] = {**cfg, "plugin": p["name"]}
    return out


def hook_sets():
    """[(source, {"hooks": …})] of the plugins that are on, ${PLUGIN_DIR} replaced by the plugin's folder."""
    out = []
    for p in _enabled():
        d = Path(p["path"])
        m = _manifest(d) or {}
        if m.get("hooks_off"):
            continue
        h = m.get("hooks")
        if not isinstance(h, dict):  # a plugin made for another agent: its hooks file (hooks/hooks.json by default)
            for f in ([h] if isinstance(h, str) else []) + ["hooks/hooks.json"]:
                try:
                    h = json.loads((d / f).read_text()).get("hooks")
                    break
                except (OSError, ValueError, AttributeError):
                    h = None
        if isinstance(h, dict) and h:
            data = json.loads(json.dumps({"hooks": h}).replace("${PLUGIN_DIR}", str(d).replace("\\", "\\\\")))
            foreign = any(x.name.startswith(".") and x.name.endswith("-plugin") for x in d.iterdir())
            env = {str(k): str(v) for k, v in (m.get("hooks_env") or {}).items()} if isinstance(m.get("hooks_env"), dict) else {}
            out.append((f"plugin {p['name']}", {**data, "root": str(d), "foreign": foreign, "env": env}))
    return out


def commands():
    return [{**c, "plugin": p["name"]} for p in _enabled() for c in p["commands"]
            if isinstance(c, dict) and re.fullmatch(r"/[\w-]{2,30}(:[\w-]{1,40})?", str(c.get("cmd", ""))) and c.get("prompt")]


def set_enabled(name, on):
    st = _state()
    st.setdefault("enabled", {})[name] = bool(on)
    _save(st)


def install_tools(name):
    """brew install the plugin's missing tools (the user clicked « Installer les outils »). Returns what happened."""
    p = next((x for x in all_plugins() if x["name"] == name), None)
    if not p:
        raise PluginError("plugin inconnu")
    missing = [t["brew"] for t in p["tools"] if not t["ok"] and re.fullmatch(r"[\w@./+-]+", str(t.get("brew", "")))]
    if not missing:
        return {"ok": True, "installed": [], "log": "tout est déjà installé"}
    if not BREW:
        raise PluginError("Homebrew n'est pas installé (https://brew.sh)")
    r = subprocess.run([BREW, "install", *missing], capture_output=True, text=True, timeout=1800)
    return {"ok": r.returncode == 0, "installed": missing, "log": (r.stdout + r.stderr)[-3000:]}


def add(source):
    """A plugin from a GitHub link (cloned, nothing executed) or a folder on this Mac (copied)."""
    source = str(source or "").strip()
    PLUGINS.mkdir(parents=True, exist_ok=True)
    tmp = PLUGINS / f".ajout-{int(time.time())}"
    try:
        if re.match(r"https?://", source):
            if not re.match(r"https://(github\.com|gitlab\.com|codeberg\.org)/[\w.-]+/[\w.-]+", source):
                raise PluginError("lien GitHub, GitLab ou Codeberg attendu")
            r = subprocess.run(["git", "clone", "--depth", "1", source, str(tmp)], capture_output=True, text=True, timeout=180)
            if r.returncode:
                raise PluginError("clonage impossible : " + (r.stderr or "")[-300:])
        else:
            src = Path(source).expanduser()
            if not (src / "plugin.json").is_file():
                raise PluginError("ce dossier n'a pas de plugin.json")
            shutil.copytree(src, tmp)
        m = _manifest(tmp)
        if not m or not re.fullmatch(r"[\w-]{2,40}", m["name"]):
            raise PluginError("plugin.json invalide (il faut au moins un « name » simple)")
        dst = PLUGINS / m["name"]
        if dst.exists():
            raise PluginError(f"un plugin « {m['name']} » est déjà installé : retire-le d'abord")
        shutil.move(str(tmp), str(dst))
        st = _state()
        st.setdefault("enabled", {})[m["name"]] = True
        st["removed"] = [x for x in st.get("removed", []) if x != m["name"]]
        _save(st)
        return next(p for p in all_plugins() if p["name"] == m["name"])
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)  # only the temporary clone made here


def remove(name):
    """The plugin goes to the macOS Trash (it can be put back); a shipped one is not re-installed."""
    d = PLUGINS / name
    if not re.fullmatch(r"[\w-]{2,40}", name) or not d.is_dir():
        raise PluginError("plugin inconnu")
    for where in (Path.home() / ".Trash", ext.HOME / "plugins.supprimes"):
        try:
            where.mkdir(parents=True, exist_ok=True)
            shutil.move(str(d), str(where / f"Plugin Naim {name} {time.strftime('%Y-%m-%d %H.%M.%S')}"))
            break
        except OSError:
            continue
    st = _state()
    st.setdefault("removed", []).append(name)
    st.get("enabled", {}).pop(name, None)
    _save(st)
    return {"ok": True}


# ---- « /plugin marketplace add <link> » then « /plugin install <name> », as in other coding agents: a marketplace is a
# git repository with .<agent>-plugin/marketplace.json (or a single plugin); its plugins are translated into Naim's format
# at install (nothing is run): skills (in the library when there are many), agents as skills, commands as « / »
# commands (/plugin:command), MCP servers, and hooks (brought turned off: they were written for another harness)
MARKETS = ext.HOME / "marketplaces"
GIT_RE = re.compile(r"^(https://(github\.com|gitlab\.com|codeberg\.org)/[\w.-]+/[\w.-]+?)(\.git)?/?$")
MANY_SKILLS = 12  # above this, a plugin's skills go to the library (found on demand) instead of the instructions


def _clone(url, dst):
    m = GIT_RE.match(url.strip()) or (re.fullmatch(r"[\w.-]+/[\w.-]+", url.strip()) and GIT_RE.match(f"https://github.com/{url.strip()}"))
    if not m:
        raise PluginError("lien GitHub, GitLab ou Codeberg attendu (ou owner/repo)")
    r = subprocess.run(["git", "clone", "--depth", "1", m.group(1), str(dst)], capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise PluginError("clonage impossible : " + (r.stderr or "")[-300:])


def _plugin_meta(d, name):
    """d/.<agent>-plugin/<name> (marketplace.json or plugin.json): the folder that also has a marketplace.json first."""
    dirs = sorted(x for x in d.glob(".*-plugin") if x.is_dir())
    dirs.sort(key=lambda x: not (x / "marketplace.json").is_file())
    return next((x / name for x in dirs if (x / name).is_file()), None)


ROOT_VAR = re.compile(r"\$\{[A-Z]+_PLUGIN_ROOT\}")  # the plugin's folder, as other agents name it in hooks and MCP


def _json(f):
    try:
        return json.loads(Path(f).read_text())
    except (OSError, ValueError):
        return None


def _market_plugins(d):
    """[{name, description, version, source}] of a cloned marketplace (or the single plugin it is)."""
    f = _plugin_meta(d, "marketplace.json")
    mk = _json(f) if f else None
    if isinstance(mk, dict) and isinstance(mk.get("plugins"), list):
        return [x for x in mk["plugins"] if isinstance(x, dict) and x.get("name")]
    f = _plugin_meta(d, "plugin.json")
    one = (_json(f) if f else None) or _manifest(d)
    return [{**one, "source": "./"}] if one else []


def marketplace_add(url):
    MARKETS.mkdir(parents=True, exist_ok=True)
    tmp = MARKETS / f".ajout-{int(time.time())}"
    try:
        _clone(url, tmp)
        f = _plugin_meta(tmp, "marketplace.json")
        mk = (_json(f) if f else None) or {}
        name = re.sub(r"[^\w-]+", "-", str(mk.get("name") or url.rstrip("/").split("/")[-1].removesuffix(".git"))).strip("-")[:40]
        plugs = _market_plugins(tmp)
        if not plugs:
            raise PluginError("ce dépôt n'a ni marketplace.json (dans un dossier .<agent>-plugin) ni plugin")
        dst = MARKETS / name
        if dst.exists():  # the former copy of this marketplace: kept aside, never lost
            back = ext.HOME / "marketplaces.anciens" / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}"
            back.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(back))
        shutil.move(str(tmp), str(dst))
        (dst / ".naim-source").write_text(url.strip())
        return {"name": name, "plugins": [{"name": x["name"], "description": str(x.get("description", ""))[:300],
                                           "version": x.get("version", "")} for x in plugs]}
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)  # only the temporary clone made here


def marketplaces():
    out = []
    for d in sorted(MARKETS.glob("*")) if MARKETS.is_dir() else []:
        if d.is_dir() and not d.name.startswith("."):
            out.append({"name": d.name, "plugins": [{"name": x["name"], "description": str(x.get("description", ""))[:300],
                                                       "version": x.get("version", "")} for x in _market_plugins(d)]})
    return out


def _md_parts(f):
    meta, body = ext.parse_frontmatter(Path(f).read_text(errors="replace"))
    return (meta if isinstance(meta, dict) else {}), body


def _paths(root, value, default):
    """A manifest entry (« ./skills/ », a list of them, or nothing) → existing folders or files inside the plugin."""
    vals = value if isinstance(value, list) else [value] if isinstance(value, str) else [default]
    out = []
    for v in vals:
        q = (root / str(v)).resolve()
        if (q == root.resolve() or root.resolve() in q.parents) and q.exists():
            out.append(q)
    return out


def _translate(src, entry, origin):
    """A plugin folder made for another agent → the plugin.json Naim reads (written in the installed copy)."""
    f = _plugin_meta(src, "plugin.json")
    man = {**entry, **((_json(f) if f else None) or {})}
    name = re.sub(r"[^\w-]+", "-", str(man.get("name") or src.name)).strip("-")[:40]
    if not re.fullmatch(r"[\w-]{2,40}", name):
        raise PluginError("nom de plugin invalide")
    skill_roots = _paths(src, man.get("skills"), "skills")
    skill_root = skill_roots[0] if skill_roots else src / "skills"
    skill_root.mkdir(exist_ok=True)
    for extra in skill_roots[1:]:  # several skill folders: gathered into the first one
        for d in extra.iterdir():
            if (d / "SKILL.md").is_file() and not (skill_root / d.name).exists():
                shutil.copytree(d, skill_root / d.name)
    agents = 0
    for folder in _paths(src, man.get("agents"), "agents"):
        for f in sorted(folder.glob("*.md")) if folder.is_dir() else [folder]:
            meta, body = _md_parts(f)
            n = ext.slugify(str(meta.get("name") or f.stem))
            dst = skill_root / f"agent-{n}"
            if dst.exists():
                continue
            dst.mkdir()
            desc = str(meta.get("description") or body.strip().split("\n")[0])[:400].replace("\n", " ")
            (dst / "SKILL.md").write_text(f"---\nname: agent-{n}\ndescription: {json.dumps(desc, ensure_ascii=False)}\n---\n\n"
                                          f"Rôle à adopter (agent « {n} » du plugin {name}) :\n\n{body.strip()}\n")
            agents += 1
    commands = []
    for folder in _paths(src, man.get("commands"), "commands"):
        for f in sorted(folder.rglob("*.md")) if folder.is_dir() else [folder]:
            meta, body = _md_parts(f)
            stem = re.sub(r"[^\w-]+", "-", f.stem).strip("-")[:40]
            if not stem or not body.strip():
                continue
            commands.append({"cmd": f"/{name}:{stem}", "arg": str(meta.get("argument-hint") or "")[:60],
                             "description": str(meta.get("description") or body.strip().split("\n")[0])[:200],
                             "prompt": ROOT_VAR.sub(str(PLUGINS / name), body.strip()), "mode": "agent"})  # its scripts' real place
    def plugin_dir(text):
        return json.loads(ROOT_VAR.sub("${PLUGIN_DIR}", json.dumps(text)))
    if "mcpServers" in man:  # the plugin says which servers it brings (maybe none)
        mcp = man["mcpServers"] if isinstance(man["mcpServers"], dict) else (_json(src / str(man["mcpServers"])) or {}).get("mcpServers", {})
    else:
        mcp = (_json(src / ".mcp.json") or {}).get("mcpServers", {})
    hooks = {}
    for f in _paths(src, man.get("hooks") if isinstance(man.get("hooks"), (str, list)) else None, "hooks/hooks.json"):
        data = _json(f) if f.is_file() else None
        for ev, groups in ((data or {}).get("hooks", data or {}) or {}).items():
            if isinstance(groups, list):
                hooks.setdefault(ev, []).extend(groups)
    if isinstance(man.get("hooks"), dict):
        for ev, groups in (man["hooks"].get("hooks", man["hooks"]) or {}).items():
            if isinstance(groups, list):
                hooks.setdefault(ev, []).extend(groups)
    count = sum(1 for d in skill_root.iterdir() if (d / "SKILL.md").is_file())
    rel = skill_root.resolve().relative_to(src.resolve()).as_posix() or "."  # /var is /private/var on macOS
    out = {"name": name, "version": str(man.get("version") or ""), "description": str(man.get("description") or "")[:600],
           "origin": origin, "commands": commands, "mcp": plugin_dir(mcp) if isinstance(mcp, dict) else {},
           "hooks": plugin_dir(hooks), "hooks_off": bool(hooks)}
    out["library" if count > MANY_SKILLS else "skills"] = rel
    (src / "plugin.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return {"name": name, "skills": count - agents, "agents": agents, "commands": len(commands), "mcp": len(out["mcp"]),
            "hooks": sum(len(g) for g in hooks.values()), "library": count > MANY_SKILLS}


def install_from_market(spec):
    """« name » or « name@marketplace »: the plugin copied from its marketplace (or cloned from its own repository),
    translated, then turned on. Returns what it brings."""
    want, _, market = str(spec or "").strip().partition("@")
    found = [(m["name"], x) for m in marketplaces() if not market or m["name"] == market
             for x in _market_plugins(MARKETS / m["name"]) if x["name"] == want]
    if not found:
        raise PluginError(f"plugin « {want} » introuvable : ajoute d'abord sa marketplace (/plugin marketplace add <lien>)")
    mname, entry = found[0]
    PLUGINS.mkdir(parents=True, exist_ok=True)
    tmp = PLUGINS / f".ajout-{int(time.time())}"
    try:
        s = entry.get("source", "./")
        if isinstance(s, dict):  # {"source": "github", "repo": "o/r"} or {"source": "url", "url": "…"}
            _clone(s.get("url") or s.get("repo") or "", tmp)
        else:
            base = (MARKETS / mname).resolve()
            q = (base / str(s)).resolve()
            if not (q == base or base in q.parents) or not q.is_dir():
                raise PluginError("source du plugin invalide dans la marketplace")
            # its files without git and other tools' folders (.codex, .cursor…): only what Naim can use
            shutil.copytree(q, tmp, ignore=lambda d, names: [n for n in names if n == ".git" or (
                Path(d).resolve() == q and n.startswith(".") and not n.endswith("-plugin") and n != ".mcp.json")])
        info = _translate(tmp, entry, f"{want}@{mname}")
        dst = PLUGINS / info["name"]
        if dst.exists():  # an older version: kept aside, never lost
            back = ext.HOME / "plugins.anciens" / f"{info['name']}-{time.strftime('%Y%m%d-%H%M%S')}"
            back.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(back))
        shutil.move(str(tmp), str(dst))
        st = _state()
        st.setdefault("enabled", {})[info["name"]] = True
        st["removed"] = [x for x in st.get("removed", []) if x != info["name"]]
        _save(st)
        return {**info, "marketplace": mname}
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)  # only the temporary copy made here


def set_hooks(name, on):
    d = PLUGINS / str(name)
    m = _manifest(d) if re.fullmatch(r"[\w-]{2,40}", str(name)) and d.is_dir() else None
    if not m:
        raise PluginError("plugin inconnu")
    if not m.get("hooks"):
        raise PluginError(f"le plugin « {name} » n'a pas de hooks")
    m["hooks_off"] = not on
    (d / "plugin.json").write_text(json.dumps(m, ensure_ascii=False, indent=1))
    return {"ok": True, "hooks": sum(len(g) for g in m["hooks"].values()), "on": on}
