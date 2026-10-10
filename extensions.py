"""Naim extensions: MCP servers, skills, memory, project instructions (NAIM.md), web access,
undo checkpoints and git helpers. Shared by the agent (naimtools.py) and the UI server (server.py).

Naim's own home is ~/.naim (override with NAIM_HOME):
  mcp.json          MCP servers, standard format {"mcpServers": {name: {command, args, env} | {type: "http", url, headers}}}
  skills/<name>/    user skills (SKILL.md + optional files); projects may add .naim/skills/<name>/
  memory.md         long-term memory, one fact per line ("- ...")
  NAIM.md           global instructions applied to every project
App data (conversations, settings, undo checkpoints) stays in DATA (~/Library/Application Support/Naim).
"""
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(os.environ.get("NAIM_DATA", Path.home() / "Library/Application Support/Naim"))
HOME = Path(os.environ.get("NAIM_HOME", Path.home() / ".naim"))


def _migrate_home():
    """First run with ~/.naim: move skills / MCP config / memory from the old app-data folder."""
    HOME.mkdir(parents=True, exist_ok=True)
    for name in ("skills", "memory.md"):
        old, new = DATA / name, HOME / name
        if old.exists() and not new.exists():
            shutil.move(str(old), str(new))
    old = DATA / "mcp.json"
    if old.exists() and not (HOME / "mcp.json").exists():
        try:
            servers = json.loads(old.read_text()).get("servers", {})
        except ValueError:
            servers = {}
        (HOME / "mcp.json").write_text(json.dumps({"mcpServers": {
            k: {**{x: v[x] for x in ("command", "args", "env") if x in v}, **({"disabled": True} if v.get("enabled") is False else {})}
            for k, v in servers.items()}}, indent=2, ensure_ascii=False))
        old.unlink()


_migrate_home()


def global_instructions():
    f = HOME / "NAIM.md"
    if not f.exists():  # first launch: start from the generic template shipped with Naim
        tpl = Path(__file__).with_name("NAIM.default.md")
        if tpl.exists():
            HOME.mkdir(parents=True, exist_ok=True)
            f.write_text(tpl.read_text())
    return f.read_text(errors="replace")[:8000].strip() if f.is_file() else ""
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


# ============================================================================ MCP (stdio transport)
class MCPServer:
    """Minimal MCP client over stdio (newline-delimited JSON-RPC 2.0)."""

    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg
        self.proc, self.tools, self.error, self.log = None, [], None, []
        self._id, self._pending, self._lock = 0, {}, threading.Lock()

    def start(self, timeout=30):
        cmd = [self.cfg["command"], *self.cfg.get("args", [])]
        env = {**os.environ, **{k: str(v) for k, v in (self.cfg.get("env") or {}).items()}}
        # GUI apps get a minimal PATH: make Homebrew / npx / uvx reachable
        env["PATH"] = ":".join(dict.fromkeys(env.get("PATH", "").split(":") + ["/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local/bin")]))
        try:
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True, bufsize=1, env=env, cwd=self.cfg.get("cwd") or str(Path.home()),
                                         start_new_session=True)
        except OSError as e:
            self.error = f"impossible de lancer {cmd[0]} : {e}"
            raise RuntimeError(self.error)
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "naim", "version": "1.0"}}, timeout)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools, cursor = [], None
        while True:
            res = self.request("tools/list", {"cursor": cursor} if cursor else {}, timeout)
            tools += res.get("tools", [])
            cursor = res.get("nextCursor")
            if not cursor:
                break
        self.tools, self.error = tools, None
        return self

    def _send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def _read(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "id" in msg and ("result" in msg or "error" in msg):
                slot = self._pending.get(msg["id"])
                if slot:
                    slot["msg"] = msg
                    slot["event"].set()
            elif msg.get("method") and "id" in msg:  # server->client request (e.g. ping): answer politely
                try:
                    self._send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
                except OSError:
                    pass
        for slot in list(self._pending.values()):  # process died: wake up waiters
            slot["event"].set()

    def _read_err(self):
        for line in self.proc.stderr:
            self.log.append(line)
            del self.log[:-200]

    def request(self, method, params, timeout=120):
        with self._lock:
            self._id += 1
            rid = self._id
        slot = self._pending[rid] = {"event": threading.Event(), "msg": None}
        try:
            self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
            if not slot["event"].wait(timeout):
                raise RuntimeError(f"MCP {self.name}: pas de réponse à {method} après {timeout} s")
        finally:
            self._pending.pop(rid, None)
        msg = slot["msg"]
        if msg is None:
            raise RuntimeError(f"MCP {self.name} s'est arrêté. {''.join(self.log[-5:]).strip()}")
        if "error" in msg:
            raise RuntimeError(f"MCP {self.name}: {msg['error'].get('message', msg['error'])}")
        return msg["result"]

    def call(self, tool, arguments, timeout=180):
        res = self.request("tools/call", {"name": tool, "arguments": arguments or {}}, timeout)
        parts = []
        for c in res.get("content", []):
            if c.get("type") == "text":
                parts.append(c["text"])
            elif c.get("type") == "resource":
                parts.append(c.get("resource", {}).get("text", "[ressource]"))
            else:
                parts.append(f"[{c.get('type')}]")
        text = "\n".join(parts) or json.dumps(res.get("structuredContent", {}), ensure_ascii=False)
        return ("error: " if res.get("isError") else "") + text

    @property
    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.alive:
            try:
                os.killpg(self.proc.pid, 15)
            except ProcessLookupError:
                pass


class MCPHttpServer(MCPServer):
    """Remote MCP server over Streamable HTTP (JSON or SSE responses)."""

    def start(self, timeout=30):
        self.session, self._alive = None, True
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "naim", "version": "1.0"}}, timeout)
        try:
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout)
        except Exception:
            pass
        tools, cursor = [], None
        while True:
            res = self.request("tools/list", {"cursor": cursor} if cursor else {}, timeout)
            tools += res.get("tools", [])
            cursor = res.get("nextCursor")
            if not cursor:
                break
        self.tools, self.error = tools, None
        return self

    def _post(self, msg, timeout):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   **{k: str(v) for k, v in (self.cfg.get("headers") or {}).items()}}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.cfg["url"], data=json.dumps(msg).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            self.session = r.headers.get("Mcp-Session-Id") or self.session
            body = r.read().decode("utf-8", errors="replace")
            ctype = r.headers.get("Content-Type", "")
        if "event-stream" in ctype:
            msgs = [json.loads(l[5:].strip()) for l in body.splitlines() if l.startswith("data:") and l[5:].strip()]
        else:
            msgs = [json.loads(body)] if body.strip() else []
        return msgs

    def request(self, method, params, timeout=120):
        with self._lock:
            self._id += 1
            rid = self._id
        try:
            msgs = self._post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}, timeout)
        except Exception as e:
            self._alive = False
            raise RuntimeError(f"MCP {self.name}: {e}")
        for m in msgs:
            if m.get("id") == rid:
                if "error" in m:
                    raise RuntimeError(f"MCP {self.name}: {m['error'].get('message', m['error'])}")
                return m.get("result", {})
        raise RuntimeError(f"MCP {self.name}: réponse vide à {method}")

    @property
    def alive(self):
        return getattr(self, "_alive", False)

    def stop(self):
        self._alive = False


def _tool_id(server, tool):
    return re.sub(r"[^A-Za-z0-9_-]", "_", f"mcp__{server}__{tool}")[:64]


class MCPManager:
    def __init__(self):
        self.servers, self.lock = {}, threading.Lock()

    @property
    def path(self):
        return HOME / "mcp.json"

    def config(self):
        """{name: cfg} with cfg["enabled"] derived from the standard "disabled" flag."""
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        servers = raw.get("mcpServers", raw.get("servers", {}))
        return {k: {**v, "enabled": not v.get("disabled", False) and v.get("enabled", True) is not False}
                for k, v in servers.items() if isinstance(v, dict)}

    def raw_json(self):
        try:
            return self.path.read_text()
        except OSError:
            return '{\n  "mcpServers": {}\n}\n'

    def save_config(self, servers):
        HOME.mkdir(parents=True, exist_ok=True)
        clean = {}
        for k, v in servers.items():
            c = {x: v[x] for x in ("type", "url", "headers", "command", "args", "env", "cwd", "always") if v.get(x) not in (None, "", [], {}, False)}
            if v.get("enabled") is False or v.get("disabled"):
                c["disabled"] = True
            clean[k] = c
        self.path.write_text(json.dumps({"mcpServers": clean}, indent=2, ensure_ascii=False))
        for name in list(self.servers):  # restart changed / removed servers lazily
            if name not in servers or servers[name] != self.servers[name].cfg:
                self.servers.pop(name).stop()

    def get(self, name, on_demand=False):
        """Running server `name`. A disabled server is started only on demand (Naim's use_mcp tool)."""
        cfg = self.config().get(name)
        if not cfg or (cfg.get("enabled") is False and not on_demand):
            return None
        with self.lock:
            srv = self.servers.get(name)
            if srv and srv.alive and srv.cfg == cfg:
                return srv
            if srv:
                srv.stop()
            remote = cfg.get("url") and cfg.get("type", "http") in ("http", "streamable-http", "sse")
            srv = self.servers[name] = (MCPHttpServer if remote else MCPServer)(name, cfg)
        try:
            return srv.start()
        except Exception as e:  # keep the error for the UI
            srv.error = str(e)
            return srv

    def status(self):
        out = []
        for name, cfg in self.config().items():
            srv = self.servers.get(name)
            out.append({"name": name, "type": "http" if cfg.get("url") else "stdio", "url": cfg.get("url", ""),
                        "headers": cfg.get("headers", {}), "command": cfg.get("command", ""), "args": cfg.get("args", []),
                        "env": cfg.get("env", {}), "enabled": cfg.get("enabled", True) is not False, "always": bool(cfg.get("always")),
                        "running": bool(srv and srv.alive), "error": srv.error if srv else None,
                        "tools": [{"name": t["name"], "description": t.get("description", "")} for t in (srv.tools if srv else [])],
                        "log": "".join(srv.log[-20:]) if srv else ""})
        return out

    def agent_tools(self):
        """Tool definitions of the servers marked « toujours prêt » (read with every request), plus a lookup table
        for the tools of every enabled server (the others are described on demand, see deferred / describe)."""
        defs, lookup = [], {}
        for name, cfg in self.config().items():
            if cfg.get("enabled") is False:
                continue
            srv = self.get(name)
            if not srv or srv.error:
                continue
            for t in srv.tools:
                tid = _tool_id(name, t["name"])
                lookup[tid] = (name, t["name"])
                if cfg.get("always"):
                    schema = t.get("inputSchema") or {"type": "object", "properties": {}}
                    defs.append({"type": "function", "function": {
                        "name": tid, "description": f"[MCP {name}] {t.get('description', '')}"[:1000], "parameters": schema}})
        return defs, lookup

    def deferred(self):
        """Enabled servers whose tools are NOT read with every request: one line each (what it does, its tools).
        Their details come only when a task asks for them (use_mcp), the tool list never changes."""
        try:
            import mcp_catalog
            known = {k: v[1] for k, v in mcp_catalog.CATALOG.items()}
        except ImportError:
            known = {}
        out = []
        for name, cfg in self.config().items():
            if cfg.get("enabled") is False or cfg.get("always"):
                continue
            srv = self.get(name)
            if not srv or srv.error:
                continue
            first = (srv.tools[0].get("description", "") if srv.tools else "").split(". ")[0]
            what = known.get(name) or cfg.get("description") or (first[:140] + ("…" if len(first) > 140 else ""))
            out.append({"name": name, "description": what, "tools": [t["name"] for t in srv.tools]})
        return out

    def describe(self, name):
        """The tools of one server with their parameters, as text (nothing is added to the tool list)."""
        srv = self.get(name, on_demand=True)
        if srv is None:
            raise ValueError(f"serveur MCP inconnu : {name}")
        if srv.error:
            raise ValueError(f"le serveur MCP {name} ne démarre pas : {srv.error}")
        lines, lookup = [], {}
        for t in srv.tools:
            lookup[_tool_id(name, t["name"])] = (name, t["name"])
            sch = t.get("inputSchema") or {}
            req = set(sch.get("required") or [])
            props = ", ".join(f"{k}{'' if k in req else '?'}: {(v or {}).get('type', 'any')}"
                              + (f" ({str((v or {}).get('description'))[:60]})" if (v or {}).get("description") else "")
                              for k, v in (sch.get("properties") or {}).items())
            lines.append(f"- {t['name']}: {t.get('description', '')[:200]}\n  arguments: {{{props}}}")
        return "\n".join(lines), lookup

    def on_demand(self):
        """Disabled servers Naim may load itself when a task needs them: [{name, description}]."""
        try:
            import mcp_catalog
            known = {k: v[1] for k, v in mcp_catalog.CATALOG.items()}
        except ImportError:
            known = {}
        out = []
        conf = self.config()
        for name, cfg in conf.items():
            if cfg.get("enabled") is False:
                what = known.get(name) or cfg.get("description") or (cfg.get("url") or " ".join([cfg.get("command", "")] + cfg.get("args", [])))[:120]
                out.append({"name": name, "description": what})
        # catalogue servers not added yet, that need no key and whose runtime is installed: Naim can add one itself
        # when a task needs it (the user confirms), like an assistant that goes and gets the tool it lacks
        try:
            for c in mcp_catalog.catalog(installed=set(conf)):
                if not c["installed"] and not c["env"] and c["ready"] and c["name"] not in mcp_catalog.NOT_ON_DEMAND:
                    out.append({"name": c["name"], "description": c["description"] + " (à ajouter : confirmation demandée)",
                                "catalog": True})
        except Exception:
            pass
        return out

    def tools_of(self, name):
        """Load one server on demand; returns (tool definitions, lookup) or raises with the error."""
        srv = self.get(name, on_demand=True)
        if srv is None:
            raise ValueError(f"serveur MCP inconnu : {name}")
        if srv.error:
            raise ValueError(f"le serveur MCP {name} ne démarre pas : {srv.error}")
        defs, lookup = [], {}
        for t in srv.tools:
            tid = _tool_id(name, t["name"])
            lookup[tid] = (name, t["name"])
            schema = t.get("inputSchema") or {"type": "object", "properties": {}}
            defs.append({"type": "function", "function": {
                "name": tid, "description": f"[MCP {name}] {t.get('description', '')}"[:1000], "parameters": schema}})
        return defs, lookup

    def call(self, server, tool, args):
        srv = self.get(server, on_demand=True)
        if not srv or srv.error:
            return f"error: serveur MCP {server} indisponible ({srv.error if srv else 'désactivé'})"
        try:
            return srv.call(tool, args)
        except Exception as e:
            return f"error: {e}"

    def stop_all(self):
        for srv in self.servers.values():
            srv.stop()


MCP = MCPManager()


# ============================================================================ skills
BUILTIN_SKILLS = {
    "git-commit": ("Rédiger et faire un commit Git propre (messages conventionnels).", """# Commit Git propre

1. `git status` et `git diff` pour voir exactement ce qui a changé.
2. Regrouper les changements par intention ; un commit = une intention.
3. Message au format conventionnel : `type(portée): résumé à l'impératif` (feat, fix, refactor, docs, test, chore),
   72 caractères max, puis une ligne vide et le *pourquoi* si utile.
4. `git add` seulement les fichiers concernés, puis `git commit -m "..."`.
5. Ne jamais pousser (`git push`) sans que l'utilisateur le demande. Jamais de ligne « Co-Authored-By » ni de mention d'un assistant.
"""),
    "debug": ("Méthode pour trouver et corriger un bug de façon systématique.", """# Débogage systématique

1. Reproduire : exécuter le programme ou le test qui échoue et lire l'erreur complète.
2. Localiser : suivre la pile d'appels, lire le code concerné, chercher (search) les usages.
3. Hypothèse : formuler UNE cause probable et la vérifier (print, test ciblé).
4. Corriger au plus petit endroit possible, avec edit_file.
5. Vérifier : relancer le test / programme ; ajouter un test qui aurait attrapé le bug.
6. Résumer la cause racine et le correctif.
"""),
    "readme": ("Écrire ou mettre à jour le README d'un projet.", """# README

1. Explorer le projet (list_files, lire package.json / pyproject / pom.xml…).
2. Sections : titre + une phrase, fonctionnalités, prérequis, installation, lancement, configuration, structure, licence.
3. Commandes exactes et testées (exécuter les commandes d'installation/lancement si possible).
4. Écrire README.md avec write_file, en français si le projet est en français.
"""),
    "application-web": ("Créer une application web minimale qui marche (Flask, 3-6 petits fichiers), la lancer et la vérifier.", """# Application web (version minimale d'abord)

Objectif : une première version qui MARCHE, petite et rapide à écrire. Pas de pages ni de fonctions non demandées.

1. Pile : Python → Flask. Respecter l'existant s'il y a déjà une app.
2. Structure minimale (chaque fichier < 120 lignes, pas de commentaires inutiles) :
   - `app.py` : création de l'app + routes (liste, création, détail) + port 5050
   - `models.py` : données (SQLite via `sqlite3`, tables créées au démarrage)
   - `templates/base.html` + 2 à 3 pages maximum (ex. liste.html, form.html, detail.html)
   - `requirements.txt`
   CSS : quelques lignes dans base.html (pas de fichier séparé au début).
3. Créer les fichiers UN PAR UN avec write_file.
4. Environnement : `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
5. Lancer avec start_process (keep=true) : `.venv/bin/python app.py` sur le port 5050 (jamais 5000, pris par AirPlay).
6. Vérifier chaque page avec `curl` (200) et corriger les erreurs.
7. Résumer : fichiers, URL, et proposer 2-3 améliorations possibles (sans les faire).
"""),
    "api-rest": ("Créer une API REST propre (routes CRUD, validation, erreurs JSON, tests).", """# API REST

1. Ressources et routes : GET /items, GET /items/<id>, POST /items, PUT /items/<id>, DELETE /items/<id>.
2. Validation des entrées, codes HTTP corrects (200/201/204/400/404), erreurs en JSON `{"error": "..."}`.
3. Découper : `app.py` (routes), `models.py`, `storage.py` (SQLite), `tests/test_api.py`.
4. Lancer le serveur avec start_process, tester chaque route avec `curl`, puis écrire les tests et les lancer.
5. Documenter les routes dans README.md avec un exemple curl par route.
"""),
    "tests-unitaires": ("Ajouter des tests unitaires au projet et les faire passer.", """# Tests unitaires

1. Détecter le langage et le framework de test existant (pytest, jest/vitest, JUnit, XCTest, PHPUnit…) ; sinon choisir le standard.
2. Lister les fonctions publiques importantes ; pour chacune : cas nominal, cas limites, cas d'erreur.
3. Écrire les tests dans le dossier habituel du projet.
4. Lancer la suite avec run_command, corriger jusqu'à ce que tout passe.
5. Donner la commande pour relancer les tests.
"""),
}


try:  # extended built-in library (documents, data, stacks, quality)
    from skills_library import LIBRARY as _LIB
    BUILTIN_SKILLS.update(_LIB)
except ImportError:
    pass
try:  # detailed, field-tested versions (override the short ones)
    from skills_pro import PRO as _PRO
    BUILTIN_SKILLS.update(_PRO)
except ImportError:
    pass
# built-in skills rewritten in skills_pro: an older unedited copy is upgraded once (backed up in skills/.anciens)
UPGRADED = {"react-app", "ci-cd", "projet-existant", "debug", "application-web", "api-rest", "ios-swiftui",
            "veille-email", "controle-ecran", "tri-emails", "node-typescript", "pdf", "word", "excel", "presentation", "analyse-donnees"}


def skill_dirs(root=None):
    dirs = [("utilisateur", HOME / "skills")]
    if root:
        dirs.append(("projet", Path(root) / ".naim" / "skills"))
    return dirs


def ensure_builtin_skills():
    """Install built-in skills, and keep them up to date while the user has not edited them.

    .builtin.json remembers the hash of what Naim wrote for each skill: if the file still has that hash, a newer
    built-in version replaces it; if the user edited it, it is left alone. A skill the user deleted is not re-created.
    """
    base = HOME / "skills"
    base.mkdir(parents=True, exist_ok=True)
    marker, record_f = base / ".seeded", base / ".builtin.json"
    seeded = set(marker.read_text().split()) if marker.exists() else set()
    if seeded == {"1"}:  # marker from the first version
        seeded = {"git-commit", "debug", "readme", "tests-unitaires"}
    try:
        record = json.loads(record_f.read_text())
    except (OSError, ValueError):
        record = {}
    changed = False
    for name, (desc, body) in BUILTIN_SKILLS.items():
        d, content = base / name, f"---\nname: {name}\ndescription: {desc}\n---\n\n{body}"
        new_hash = hashlib.md5(content.encode()).hexdigest()
        f = d / "SKILL.md"
        if not d.exists():
            if name in seeded:
                continue  # deleted by the user
            d.mkdir(parents=True)
            f.write_text(content)
            record[name], changed = new_hash, True
        elif f.is_file() and record.get(name) != new_hash:
            cur = hashlib.md5(f.read_bytes()).hexdigest()
            untouched = cur == record.get(name)
            if untouched or (name not in record and name in UPGRADED):
                if not untouched:  # first upgrade of an old built-in copy: keep it just in case
                    backup = base / ".anciens" / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}"
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(d, backup)
                f.write_text(content)
                record[name], changed = new_hash, True
        seeded.add(name)
    marker.write_text("\n".join(sorted(seeded)))
    if changed or not record_f.exists():
        record_f.write_text(json.dumps(record, indent=1))


def parse_frontmatter(text):
    """(meta, body) of a SKILL.md; handles YAML folded/literal values (`key: >` followed by indented lines)."""
    meta, body = {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if m:
        body, key = m.group(2), None
        for line in m.group(1).splitlines():
            if line[:1] in (" ", "\t") and key:
                meta[key] = (meta[key] + " " + line.strip()).strip()
            elif ":" in line:
                k, v = line.split(":", 1)
                key, v = k.strip(), v.strip()
                meta[key] = "" if v in (">", "|", ">-", "|-", ">+", "|+") else v.strip('"').strip("'")
    return meta, body


def parse_skill(path):
    return parse_frontmatter(path.read_text(errors="replace"))


def list_skills(root=None, disabled=()):
    ensure_builtin_skills()
    out = []
    for scope, base in skill_dirs(root):
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            f = d / "SKILL.md"
            if d.is_dir() and f.is_file():
                meta, body = parse_skill(f)
                name = meta.get("name") or d.name
                out.append({"name": name, "dir": d.name, "description": meta.get("description", body.strip().split("\n")[0][:150]),
                            "scope": scope, "path": str(f), "enabled": name not in disabled,
                            "files": sorted(p.name for p in d.iterdir() if p.name != "SKILL.md" and not p.name.startswith("."))})
    return out


def find_skill(name, root=None):
    for s in list_skills(root):
        if s["name"] == name or s["dir"] == name:
            return s
    return None


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")
    return s[:48] or "skill"


def write_skill(name, description, instructions, root=None, scope="utilisateur"):
    base = (Path(root) / ".naim" / "skills") if scope == "projet" and root else HOME / "skills"
    d = base / slugify(name)
    d.mkdir(parents=True, exist_ok=True)
    desc = " ".join(description.split())
    (d / "SKILL.md").write_text(f"---\nname: {slugify(name)}\ndescription: {desc}\n---\n\n{instructions.strip()}\n")
    return d / "SKILL.md"


def delete_skill(path):
    p = Path(path)
    if p.name == "SKILL.md" and p.parent.parent.name == "skills":
        shutil.rmtree(p.parent)
        return True
    return False


# ============================================================================ memory (see memory.py)
MEMORY = HOME / "memory.md"


def read_memory():
    import memory
    return [f["text"] for f in memory.load() if f.get("active", True)]


def write_memory(facts):
    """Replace the memory with plain texts (old API): keeps existing facts' metadata when the text is unchanged."""
    import memory
    old = {f["text"]: f for f in memory.load()}
    memory.save([old.get(t) or memory._fact(t) for t in (" ".join(x.split()) for x in facts) if t])


def add_memory(fact, cat="autre"):
    import memory
    memory.add(fact, cat, "Naim")
    return read_memory()


def forget_memory(text):
    import memory
    return memory.forget(text)


def memory_prompt():
    import memory
    return memory.prompt(memory.LIMIT)


# ============================================================================ project instructions
PROJECT_FILES = ("NAIM.md", ".naim/NAIM.md", "AGENTS.md")


def project_instructions(root):
    for name in PROJECT_FILES:
        f = Path(root) / name
        if f.is_file():
            text = f.read_text(errors="replace")
            return name, text[:10000] + ("\n...(tronqué)" if len(text) > 10000 else "")
    return None, ""


# ============================================================================ web
def _get(url, timeout=20, limit=3_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        data = r.read(limit)
        charset = re.search(r"charset=([\w-]+)", ctype)
        return data.decode(charset.group(1) if charset else "utf-8", errors="replace"), ctype, r.geturl()


def html_to_text(src):
    src = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)[^>]*>.*?</\1>", " ", src)
    src = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|section|article|pre)>", "\n", src)
    src = re.sub(r"(?i)<li[^>]*>", "\n- ", src)
    src = re.sub(r"(?s)<[^>]+>", " ", src)
    src = html.unescape(src)
    src = re.sub(r"[ \t\r\f\v]+", " ", src)
    return re.sub(r"\n\s*\n+", "\n\n", src).strip()


def web_search(query, limit=6):
    page, _, _ = _get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query))
    results = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|$)', page, re.S):
        href, title, rest = m.groups()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(html.unescape(href)).query)
        url = q.get("uddg", [html.unescape(href)])[0]
        if "duckduckgo.com/y.js" in url:  # ads
            continue
        snip = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.S)
        results.append({"title": html_to_text(title), "url": url, "snippet": html_to_text(snip.group(1)) if snip else ""})
        if len(results) >= limit:
            break
    return results


def web_fetch(url, max_chars=12000):
    if not re.match(r"^https?://", url):
        return "error: URL invalide (http:// ou https:// attendu)"
    try:
        body, ctype, final = _get(url)
    except Exception as e:
        return f"error: {e}"
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    text = html_to_text(body) if "html" in ctype or body.lstrip().startswith("<") else body
    head = f"{html_to_text(title.group(1)) if title else final}\n{final}\n\n"
    return head + (text[:max_chars] + "\n...(tronqué)" if len(text) > max_chars else text)


# ============================================================================ undo checkpoints
CKPT = DATA / "checkpoints"


class Checkpoint:
    """Backs up each file the first time an agent run modifies it, so the whole run can be undone."""

    def __init__(self, run_id, root):
        self.run_id, self.root = run_id, Path(root)
        self.dir = CKPT / run_id
        self.manifest = {"root": str(self.root), "created": time.time(), "files": {}}
        self.lock = threading.Lock()

    def save(self, path):
        rel = str(Path(path).resolve().relative_to(self.root))
        with self.lock:
            if rel in self.manifest["files"]:
                return
            self.dir.mkdir(parents=True, exist_ok=True)
            entry = {"existed": Path(path).exists()}
            if entry["existed"]:
                entry["backup"] = f"{len(self.manifest['files'])}.bak"
                shutil.copy2(path, self.dir / entry["backup"])
            self.manifest["files"][rel] = entry
            (self.dir / "manifest.json").write_text(json.dumps(self.manifest, indent=1))


def checkpoint_info(run_id):
    f = CKPT / run_id / "manifest.json"
    if not re.match(r"^[A-Za-z0-9_-]+$", run_id or "") or not f.exists():
        return None
    m = json.loads(f.read_text())
    return {"run_id": run_id, "root": m["root"], "files": [{"path": k, "created": not v["existed"]} for k, v in m["files"].items()],
            "restored": m.get("restored", False)}


def restore_checkpoint(run_id):
    info = checkpoint_info(run_id)
    if not info:
        return None
    d = CKPT / run_id
    m = json.loads((d / "manifest.json").read_text())
    root = Path(m["root"])
    restored = []
    for rel, e in m["files"].items():
        target = root / rel
        if e["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(d / e["backup"], target)
        elif target.exists():
            target.unlink()
        restored.append(rel)
    m["restored"] = True
    (d / "manifest.json").write_text(json.dumps(m, indent=1))
    return restored


def checkpoint_changes(run_id):
    """Files changed by one run: path, created / deleted / reverted, +/- line counts and unified diff."""
    import difflib
    info = checkpoint_info(run_id)
    if not info:
        return []
    d = CKPT / run_id
    m = json.loads((d / "manifest.json").read_text())
    root, out = Path(m["root"]), []
    for rel, e in m["files"].items():
        target = root / rel
        try:
            before = (d / e["backup"]).read_text(errors="replace") if e["existed"] else ""
            after = target.read_text(errors="replace") if target.exists() else ""
        except OSError:
            continue
        if "\0" in before[:4000] or "\0" in after[:4000]:
            diff, add, rem = "(fichier binaire)", 0, 0
        else:
            lines = list(difflib.unified_diff(before.splitlines(True), after.splitlines(True), f"a/{rel}", f"b/{rel}"))
            diff = "".join(lines)[:60000]
            add = sum(1 for x in lines if x.startswith("+") and not x.startswith("+++"))
            rem = sum(1 for x in lines if x.startswith("-") and not x.startswith("---"))
        if e["existed"] and before == after and target.exists() and not e.get("reverted"):
            continue  # changed then put back: nothing left to show
        out.append({"run_id": run_id, "root": str(root), "path": rel, "created": not e["existed"],
                    "deleted": e["existed"] and not target.exists(), "reverted": bool(e.get("reverted")),
                    "added": add, "removed": rem, "diff": diff})
    return out


def revert_checkpoint_file(run_id, rel):
    """Put back one file as it was before the run (or delete it if the run created it)."""
    info = checkpoint_info(run_id)
    if not info:
        return False
    d = CKPT / run_id
    m = json.loads((d / "manifest.json").read_text())
    e = m["files"].get(rel)
    if not e:
        return False
    target = Path(m["root"]) / rel
    if e["existed"]:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(d / e["backup"], target)
    elif target.exists():
        target.unlink()
    e["reverted"] = True
    (d / "manifest.json").write_text(json.dumps(m, indent=1))
    return True


def prune_checkpoints(max_age_days=30):
    if not CKPT.is_dir():
        return
    limit = time.time() - max_age_days * 86400
    for d in CKPT.iterdir():
        if d.is_dir() and d.stat().st_mtime < limit:
            shutil.rmtree(d, ignore_errors=True)


# ============================================================================ git
def git(root, *args, timeout=30):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def git_status(root):
    code, _ = git(root, "rev-parse", "--is-inside-work-tree")
    if code != 0:
        return {"repo": False}
    _, branch = git(root, "branch", "--show-current")
    _, branches = git(root, "branch", "--format=%(refname:short)")
    _, porcelain = git(root, "status", "--porcelain=v1", "-uall")
    files = []
    for line in porcelain.splitlines():
        if len(line) > 3:
            files.append({"status": line[:2], "path": line[3:].split(" -> ")[-1].strip('"')})
    code, log = git(root, "log", "-8", "--pretty=format:%h\t%s\t%ar")
    log = log if code == 0 else ""  # a fresh repo has no commit yet
    return {"repo": True, "branch": branch, "branches": [b for b in branches.splitlines() if b],
            "files": files, "log": [dict(zip(("hash", "subject", "when"), l.split("\t"))) for l in log.splitlines() if l]}


def git_diff(root, path=None):
    args = ["diff", "HEAD", "--"] + ([path] if path else [])
    code, out = git(root, *args)
    if code != 0 or not out:  # new repo without HEAD, or untracked file
        if path and (Path(root) / path).is_file():
            code2, out2 = git(root, "diff", "--no-index", "/dev/null", path)
            return out2
        _, out = git(root, "diff", "--", *( [path] if path else []))
    return out


# ============================================================================ web app verification
ROUTE_PATTERNS = [
    # Flask: @app.route("/x") / @bp.route('/x', methods=[...]) / @app.get("/x")
    re.compile(r"""@\w+\.route\(\s*['"]([^'"]+)['"]([^)]*)\)"""),
    re.compile(r"""@\w+\.get\(\s*['"]([^'"]+)['"]()"""),
    # Express / Koa style: app.get('/x', ...) / router.get("/x", ...)
    re.compile(r"""\b(?:app|router|server)\.get\(\s*['"`]([^'"`]+)['"`]()"""),
]
SKIP_ROUTE_DIRS = {".venv", "venv", "node_modules", "__pycache__", ".git", "dist", "build"}


def discover_routes(root):
    """GET routes without parameters declared in the project's source (Flask, FastAPI, Express)."""
    routes = []
    root = Path(root)
    walk = [(str(root.parent), [], [root.name])] if root.is_file() else os.walk(root)
    for dirpath, dirnames, filenames in walk:
        dirnames[:] = [d for d in dirnames if d not in SKIP_ROUTE_DIRS]
        for name in filenames:
            if not name.endswith((".py", ".js", ".mjs", ".ts")):
                continue
            try:
                text = (Path(dirpath) / name).read_text(errors="replace")
            except OSError:
                continue
            for rx in ROUTE_PATTERNS:
                for path, extra in rx.findall(text):
                    if "methods" in extra and "GET" not in extra:
                        continue
                    if re.search(r"[<{:*]", path) or not path.startswith("/"):
                        continue
                    if path not in routes:
                        routes.append(path)
    return sorted(routes, key=lambda r: (r != "/", r)) or ["/"]


def http_status(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Naim-verify"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def last_traceback(text, max_lines=12):
    """The useful part of the last Python traceback: frames from the project (not libraries) + the error."""
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if l.startswith("Traceback")]
    if not starts:
        errs = [l for l in lines if re.search(r"\b(Error|Exception)\b", l)]
        return "\n".join(errs[-3:])
    block = lines[starts[-1]:]
    keep = []
    for i, l in enumerate(block):
        frame = l.strip().startswith("File ")
        if frame and not re.search(r"site-packages|/lib/python\d|<frozen", l):
            keep.append(l)
            if i + 1 < len(block) and not block[i + 1].strip().startswith("File "):
                keep.append(block[i + 1])
    tail = [l for l in block if l and not l.startswith(" ")][-2:]  # "SomeError: message"
    keep += [l for l in tail if l not in keep]
    # template errors: show the offending template line (jinja prints it as a frame)
    for i, l in enumerate(block):
        if re.search(r'File ".*\.(html|jinja2?|j2)"', l) and l not in keep:
            keep[-1:-1] = [l] + ([block[i + 1]] if i + 1 < len(block) else [])
    return "\n".join(keep[-max_lines:])


# ============================================================================ automatic skill choice
SKILL_TRIGGERS = {
    # making a web app (« ouvre le site de la CAF », « imprime la page 2 » are not)
    "application-web": r"\b(cr[ée]\w*|fai[st]|faire|d[ée]velopp\w*|code[rz]?|construi\w*|programme[rz]?)\b[^.?!]{0,50}\b(appli(cation)?s?|app|site|page web|"
                       r"logiciel)\b|\b(flask|fastapi|django)\b",
    "api-rest": r"\b(api|rest|endpoint|crud)\b",
    "tests-unitaires": r"\b(tests?|unitaires?|pytest|jest|junit)\b",
    # code that fails (« corrige les fautes de ce texte » is proofreading, not debugging)
    "debug": r"\b(bugs?|error|plante|crash|debug|traceback|exception)\b|\b(erreur|marche pas|fonctionne pas)\b[^.?!]{0,40}\b(code|script|programme|appli\w*|site|commande|fichier \w+\.\w+)\b|"
             r"\bcorrige\b[^.?!]{0,30}\b(code|script|programme|bug|erreur|appli\w*|fonction|\w+\.(py|js|ts|html|css|php|swift|java))\b",
    "git-commit": r"\bcommit\b",
    "readme": r"\b(readme)\b",
    "pdf": r"\bpdf\b",
    "excel": r"\b(excel|xlsx|tableur)\b",
    "word": r"\b(word|docx)\b",
    # slides; « la page de présentation d'un café » is a web page, not slides
    "presentation": r"\b(powerpoint|pptx|diapo|keynote|slides?\b)|(?<!page de )(?<!site de )(?<!page d'accueil et de )\bpr[ée]sentation\b(?! (?:d'une? |du |de la )?(?:site|page|web))",
    "analyse-donnees": r"\b(csv|analyse[rz]? (les |des )?donn[ée]es|pandas|graphiques?|statistiques)\b",
    "scraping": r"\b(scrap\w*|extraire .* site)\b",
    "react-native": r"\breact[- ]?nati\w*|\bexpo\b|\bapp(lication)? mobile (en |avec )?(js|javascript|react)",
    "react-app": r"\breact\b(?![- ]?nati)",
    "ios-swiftui": r"\b(ios|swiftui|iphone|xcode)\b",
    "api-php": r"\bphp\b",
    "docker": r"\b(docker|conteneur|container)\w*",
    "deploiement-vps": r"\b(d[ée]ploi\w*|vps|nginx|serveur linux)\b",
    "base-de-donnees": r"\b(sql|schéma|migration|base de donn[ée]es)\b",
    "script-bash": r"\b(bash|shell|script sh)\b",
    "securite": r"\b(s[ée]curit[ée]|faille|vuln[ée]rab\w*|audit)\b",
    "performance": r"\b(lent|lenteur|performance|optimis\w*|acc[ée]l[ée]r\w*)\b",
    "refactoring": r"\b(refacto\w*|nettoie[rz]? le code|restructur\w*)\b",
    "doc-api": r"\b(document\w* (l')?api|openapi|swagger)\b",
    # the look of an interface (a site, an app, a screen), not of a text document
    "frontend-design": r"\b(design|interface|landing|ui|ux|maquette)\b|\b(belle|beau|joli\w*|esth[ée]tique|couleurs?|th[èe]mes?|look|style|moche)\b[^.?!]{0,40}\b(site|page web|appli\w*|app|interface|[ée]cran)\b|"
                       r"\b(site|page web|appli\w*|app|interface|[ée]cran)\b[^.?!]{0,40}\b(belle|beau|joli\w*|esth[ée]tique|couleurs?|th[èe]mes?|look|style|moche)\b",
    "veille-email": r"(nouvelles|nouveaut|actualit|veille|newsletter).*\b(e-?mail|mail)\b|\b(e-?mail|mail)\b.*(nouvelles|nouveaut|actualit|veille)",
    "tri-emails": r"\b(r[ée]pond\w* (aux?|à mes) (e-?mails?|mails?)|tri\w* (mes |les )?(e-?mails|mails)|traite\w* (mes |les )?(nouveaux )?(e-?mails|mails)|spams?|bo[iî]te (mail|de r[ée]ception))\b",
    "controle-ecran": r"\b(clique\w*|[ée]cran|calculatrice|ouvre l'app\w*|application (mac|du mac)|r[ée]glages syst[eè]me)\b",
    "node-typescript": r"\b(node(\.js)?|typescript|npm|express|tsx?)\b",
    # changing an existing code project (« ajoute une conclusion à mon texte » is not)
    "projet-existant": r"\b(ajoute|modifie|am[ée]liore|change|mets? [àa] jour|int[eè]gre)\b[^.?!]{0,50}\b(code|projet|appli\w*|programme|script|fonction|"
                       r"site|api|module|classe|fichier \w+\.(py|js|ts|php|swift|java))\b",
    # a house or flat plan: drawn to scale by the plan-maison skill tools, not as a Mermaid diagram
    "plan-maison": r"\bplans? (d['’]|c['’])?archit|\b(plans?|sch[ée]mas?|croquis|dessin)\b[^.?!]{0,40}\b(maisons?|appartements?|villas?|pavillons?|logements?|duplex|plain[- ]pied)\b|\b(fai\w*|cr[ée]\w*|con[cç]\w*|imagin\w*|dessin\w*)\b[^.?!]{0,30}\b(maisons?|appartements?|villas?)\b[^.?!]{0,20}\bt[1-7]\b"
                   r"|\b(plans?|sch[ée]mas?|croquis|dessine\w*)\b[^.?!]{0,30}\b[tf][1-7]\b|\b[tf][1-7]\b[^.?!]{0,15}\d+ ?(m²|m2\b|m[eè]tres? carr)",
    "schemas": r"\b(sch[ée]mas?|diagrammes?|organigrammes?|flowchart|mermaid|uml|mcd|erd|logigrammes?|carte mentale|mind ?map|gantt)\b",
    "rapport": r"\b(rapport(?! de bug| d'erreur)|dossier technique|cahier des charges|compte[- ]rendu|livre blanc|note de synth[eè]se)\b",
    "visuels": r"\b(logo|banni[eè]re|ic[oô]ne d'app|flyer|infographie|carte de visite)\b|\b(une|cette|mon|ma|ton|des|l['’]|d['’])\s?affiches?\b",  # « affiche-moi les photos » is not a poster
    "recherche-approfondie": r"\b(recherche approfondie|enqu[eê]te sur|[ée]tat de l'art|[ée]tude de march[ée]|analyse concurrentielle|recoupe|compare les sources|veille approfondie|deep research)\b",
    "github": r"\b(pull[- ]?requests?|github|gh pr|branches?|merge|fusionne\w*|git push|pousse\w* (le code|sur|la branche))\b",
    # a Mac application in SwiftUI (built without an Xcode project); an iPhone app stays ios-swiftui
    "app-macos": r"\b(swift ?ui|swift|uiswuift|ui ?swift)\b(?![^.?!]*\b(ios|iphone|ipad|simulateur)\b)"
                 r"|\bapp(lication)?s?\b[^.?!]{0,30}\b(mac|macos|pour le bureau)\b|\.app\b|dans (mes |le dossier )?applications",
    # looking for something to buy (a product, a good): photos, prices and advice
    "recherche-produits": r"\b(ach[eè]te\w*|acheter|prix d[eu']|combien co[uû]te|meilleure? (prix|offre|rapport)|compar\w* (les )?(prix|offres|mod[eè]les|produits)|"
                          r"o[uù] (trouver|acheter)|bons? plans?|promos?|soldes|pas cher|moins cher|recherche\w* (des |de )?biens?|cherche[rz]? (un |une |des |le |la |les )?"
                          r"(t[ée]l[ée]phone|smartphone|ordinateur|pc|casque|t[ée]l[ée]vis\w*|tv|voiture|v[ée]lo|chaussures?|montre|frigo|"
                          r"lave-linge|canap[ée]|appartement|maison [àa] (vendre|louer)))\b"
                          r"|\b(maisons?|appartements?|studios?|terrains?|villas?|biens?)\b[^.?!]{0,30}\b([àa] (vendre|louer)|en vente|immobili\w*)\b"
                          r"|\b(annonces? immobili\w*|immobilier [àa]|encore (plus )?de photos|d'autres photos|plus de photos)\b"
                          r"|\b(cherch\w*|trouv\w*|recherch\w*)\b[^.?!]{0,40}\b(maisons?|appartements?|studios?|villas?|lofts?|terrains?|[tf][1-6])\b"
                          r"|\b(maisons?|appartements?|studios?|villas?|terrains?|voitures?|[tf][1-6])\b[^.?!]{0,60}(\d[\d .]*\s*(k?€|euros?|k\b)|budget|pas plus de|moins de)"
                          r"|\b(cherch\w*|trouv\w*|recherch\w*)\b[^.?!]{0,80}\bavec (des |les |de )?photos?\b",
    # acting on the Mac itself (last of the specialised ones: « crée une application de rappels » is an app)
    "mac": r"\b(sms|texto|imessage|envoie[rz]? (un |le |ce )?(message|texto)|appell?e[rz]?|t[ée]l[ée]phone[rz]? (à|a)|facetime|"
           r"agenda|calendrier|rendez-vous|rdv|rappelle-moi|(un |des |mes )rappels?|ajoute (une |la )?note|dans (mes )?notes|"
           r"musique|mets? (de la |la )?musique|volume|wi-?fi|bluetooth|mets? (le mac |l'[ée]cran )?en veille|batterie|notification|imprim\w*)\b",
    # « ci » alone is French (« celle-ci », « ci-dessous »): only the real terms
    "ci-cd": r"\b(ci ?/ ?cd|ci-cd|cicd|int[ée]gration continue|d[ée]ploiement continu|github actions?|gitlab[- ]ci|jenkins|"
             r"pipelines? (ci|de d[ée]ploiement|d'int[ée]gration))\b",
}


def match_skill(task, root=None, disabled=()):
    """Pick the enabled skill that best fits the task (keyword triggers, then description overlap)."""
    if re.search(r"(Document|Fichier) joint « ", task or ""):
        # attached files come first, the user's own words last: only their words choose the skill (a Word file
        # about health that says « celle-ci » is not a CI/CD request)
        task = task.rsplit("\n\n", 1)[-1]
    text = task.lower()
    skills = [s for s in list_skills(root, disabled) if s["enabled"]]
    by_name = {s["name"]: s for s in skills}
    generic = ("debug", "application-web", "api-rest", "projet-existant")  # broad: only if nothing specialised matches
    first = ("plan-maison", "app-macos", "recherche-produits", "react-native", "ci-cd", "veille-email", "tri-emails", "recherche-approfondie", "rapport", "schemas", "visuels", "github")  # "déploiement continu" is CI/CD, not a manual VPS deployment
    ordered = list(first) + [n for n in SKILL_TRIGGERS if n not in generic and n not in first] + list(generic)
    for name in ordered:
        if name in by_name and re.search(SKILL_TRIGGERS[name], text):
            return by_name[name]
    words = {w for w in re.findall(r"[a-zà-ÿ]{5,}", text)}
    best, score = None, 1
    for s in skills:
        if s["name"] in SKILL_TRIGGERS:
            continue
        overlap = len(words & set(re.findall(r"[a-zà-ÿ]{5,}", (s["description"] + " " + s["name"]).lower())))
        if overlap > score:
            best, score = s, overlap
    return best
