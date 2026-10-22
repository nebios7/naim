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
        sk = d / (m.get("skills") or "skills")
        tools = [{**t, "ok": bool(_which(t.get("cmd", "")))} for t in m.get("tools") or [] if isinstance(t, dict)]
        out.append({"name": m["name"], "version": m.get("version", ""), "description": m.get("description", ""),
                    "enabled": st.get("enabled", {}).get(m["name"], True), "path": str(d),
                    "builtin": (BUILTIN / d.name).is_dir(),
                    "skills": sorted(x.name for x in sk.iterdir() if (x / "SKILL.md").is_file()) if sk.is_dir() else [],
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
        out.append((f"plugin:{p['name']}", Path(p["path"]) / (m.get("skills") or "skills")))
    return out


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
        h = (_manifest(d) or {}).get("hooks")
        if isinstance(h, dict) and h:
            out.append((f"plugin {p['name']}", json.loads(json.dumps({"hooks": h}).replace("${PLUGIN_DIR}", str(d).replace("\\", "\\\\")))))
    return out


def commands():
    return [{**c, "plugin": p["name"]} for p in _enabled() for c in p["commands"]
            if isinstance(c, dict) and re.fullmatch(r"/[\w-]{2,30}", str(c.get("cmd", ""))) and c.get("prompt")]


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
