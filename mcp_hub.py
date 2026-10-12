"""Install MCP servers from a GitHub repository (Personnaliser → MCP → « Depuis un dépôt GitHub »).

Same links as the skills (owner/repo, https://github.com/owner/repo[/tree/<branch>/<path>]). The repository is
downloaded as an archive and only READ, never executed:
  1. the configurations its README gives ("mcpServers": {...} blocks, the format every MCP client uses);
  2. otherwise a published Node package (package.json using the MCP SDK)  → npx -y <package>;
  3. otherwise a Python package (pyproject.toml using mcp / fastmcp)      → uvx <package>.
Installing writes the chosen config in ~/.naim/mcp.json and starts the server (npx / uvx download it then).
"""
import json
import re

import extensions as ext
import mcp_catalog
import skill_hub

PLACEHOLDER = re.compile(r"^(.*<[^>]*>.*|.*\$\{.*\}.*|.*\byour[-_ ]?.*|.*(?:here|xxx+|\.\.\.)|)$", re.I)


class McpError(Exception):
    pass


def _loose_json(text):
    """JSON as written in READMEs: // comments and trailing commas allowed."""
    text = re.sub(r"(?m)^\s*//.*$", "", text)
    text = re.sub(r"(?<![:\"])//[^\n\"]*$", "", text, flags=re.M)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def _configs_in(md):
    """{name: config} from the ```json blocks of a README that contain "mcpServers" (or a bare server map)."""
    out = {}
    for block in re.findall(r"```[ \t]*(?:json[c5]?|javascript|js)?[ \t]*\n(.*?)```", md, re.S):
        if '"command"' not in block and '"url"' not in block:
            continue
        data = None
        for text in (block, "{" + block + "}"):  # « "github": {...} » alone, without the outer braces
            try:
                data = _loose_json(text)
                break
            except Exception:
                pass
        if data is None:
            continue
        servers = None
        if isinstance(data, dict):
            for key in ("mcpServers", "servers"):
                if isinstance(data.get(key), dict):
                    servers = data[key]
            if servers is None and isinstance(data.get("mcp"), dict) and isinstance(data["mcp"].get("servers"), dict):
                servers = data["mcp"]["servers"]  # VS Code format
            if servers is None:
                servers = {k: v for k, v in data.items() if isinstance(v, dict) and ("command" in v or "url" in v)}
        for name, cfg in (servers or {}).items():
            if isinstance(cfg, dict) and (isinstance(cfg.get("command"), str) or isinstance(cfg.get("url"), str)) and name not in out:
                out[name] = cfg
    return out


def _entry(name, cfg, source, description):
    env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
    headers = cfg.get("headers") if isinstance(cfg.get("headers"), dict) else {}
    args = [str(a) for a in cfg.get("args") or [] if isinstance(a, (str, int, float))]
    cmd, url = cfg.get("command") or "", cfg.get("url") or ""
    hole = lambda v: bool(PLACEHOLDER.match(str(v).strip()))
    # a key written in the command itself (« --api-key YOUR_API_KEY »): an optional field, the pair is dropped if empty
    opt = [a for a in args if hole(a) and a.strip()]
    return {"name": re.sub(r"[^\w.-]+", "-", name).strip("-").lower() or "serveur", "command": cmd, "args": args,
            "optional": opt,
            "url": url, "type": cfg.get("type", "http") if url else "stdio",
            # the keys to fill in (tokens, API keys…): the README only shows placeholders for them
            "env": [k for k, v in env.items() if hole(v)] + [k for k, v in headers.items() if hole(v)],
            "env_defaults": {k: str(v) for k, v in env.items() if not hole(v)},
            "headers": {k: str(v) for k, v in headers.items()},
            "ready": bool(url) or mcp_catalog._which(cmd) is not None, "source": source, "description": description,
            "docker": cmd == "docker"}


def _description(readme, repo):
    for line in readme.splitlines():
        t = line.strip()
        if t and not t.startswith(("#", "[", "!", "<", "|", "```", "---", ">")) and len(t) > 30:
            return re.sub(r"[*_`]", "", t)[:240]
    return f"Serveur MCP du dépôt {repo}"


def browse(url):
    """The MCP servers a repository describes: [{name, command, args, env, ready, source, description}]."""
    u = url.strip()
    if re.match(r"https?://", u) and "github.com" not in u:
        # the address of a remote MCP server itself (https://…/mcp or …/sse): nothing to download
        host = re.sub(r"^https?://(www\.|mcp\.)?", "", u).split("/")[0].split(".")[0]
        return [_entry(host or "distant", {"url": u, "type": "sse" if u.rstrip("/").endswith("/sse") else "http"},
                       "adresse directe", f"Serveur MCP distant : {u}")]
    try:
        p = skill_hub.parse_url(u)
    except skill_hub.SkillError:
        raise McpError("lien non reconnu : donne un lien GitHub (owner/repo ou https://github.com/…) "
                       "ou l'adresse d'un serveur MCP distant (https://…/mcp)")
    if p[0] != "github":
        raise McpError("donne le lien du dépôt GitHub du serveur MCP")
    _, owner, repo, ref, sub = p
    try:
        tar, files = skill_hub._members(skill_hub._download(owner, repo, ref))
    except skill_hub.SkillError as e:
        raise McpError(str(e))

    def read(path):
        m = files.get(path)
        return tar.extractfile(m).read(400_000).decode("utf-8", errors="replace") if m else ""

    base = f"{sub}/" if sub else ""
    readmes = [f for f in files if f.lower().startswith(base.lower()) and re.search(r"(^|/)readme(\.[a-z-]+)?\.md$", f, re.I)]
    readmes.sort(key=lambda f: (f.count("/"), "fr" not in f.lower(), f))  # the top README first
    top = read(readmes[0]) if readmes else ""
    desc = _description(top, repo)
    # the READMEs first (top one first, translations last), then the docs that show a configuration
    readmes = [f for f in readmes if "/i18n/" not in "/" + f] + [f for f in readmes if "/i18n/" in "/" + f]
    docs = [f for f in files if f.startswith(base) and f.endswith((".md", ".mdx")) and f not in readmes
            and "node_modules/" not in f and files[f].size < 400_000]
    docs = [f for f in docs if b"mcpServers" in tar.extractfile(files[f]).read()][:40]
    out, seen = [], set()
    for f in readmes[:12] + docs:
        for name, cfg in _configs_in(read(f)).items():
            key = cfg.get("url") or (cfg.get("command"), tuple(map(str, cfg.get("args") or [])))
            if key not in seen:
                seen.add(key)
                out.append(_entry(name, cfg, f, desc))
    # a published Node package using the MCP SDK (also in a monorepo: packages/*/package.json)
    have = {(e["command"], tuple(e["args"][-1:])) for e in out}
    for f in sorted((f for f in files if f.startswith(base) and f.endswith("package.json") and "node_modules/" not in f
                     and f.count("/") <= base.count("/") + 3), key=lambda f: f.count("/")):
        try:
            j = json.loads(read(f))
        except Exception:
            continue
        deps = {**j.get("dependencies", {}), **j.get("devDependencies", {})}
        if j.get("name") and not j.get("private") and any("modelcontextprotocol" in d or d == "fastmcp" for d in deps) \
                and not any(j["name"] in " ".join(e["args"]) for e in out):
            out.append(_entry(j["name"].split("/")[-1], {"command": "npx", "args": ["-y", j["name"]]},
                              f"{f} (paquet npm)", j.get("description") or desc))
    # the simplest first: npx / uvx on this Mac, then remote servers, then docker
    out.sort(key=lambda e: (e["docker"], not e["ready"], bool(e["url"]), e["command"] not in ("npx", "uvx")))
    out = out[:10]
    if not out:
        py = read(base + "pyproject.toml")
        m = re.search(r'(?m)^name\s*=\s*"([^"]+)"', py)
        if m and re.search(r'["\'](mcp|fastmcp)\b', py):
            out.append(_entry(m.group(1), {"command": "uvx", "args": [m.group(1)]}, "pyproject.toml (paquet Python)", desc))
    if not out:
        raise McpError("aucun serveur MCP trouvé dans ce dépôt (ni configuration « mcpServers » dans le README, "
                       "ni paquet npm / Python MCP)")
    return out


def install(url, name, env_values=None, project=""):
    """Install one server found by browse(): its config goes into mcp.json, then it is started."""
    found = next((s for s in browse(url) if s["name"] == name), None)
    if not found:
        raise McpError(f"serveur {name} introuvable dans ce dépôt")
    env_values = {k: str(v).strip() for k, v in (env_values or {}).items()}
    missing = [k for k in found["env"] if not env_values.get(k)]
    if missing:
        raise McpError("à renseigner d'abord : " + ", ".join(missing))
    home = str(__import__("pathlib").Path.home())
    args = []
    for a in found["args"]:
        if a in found["optional"]:
            if env_values.get(a):
                args.append(env_values[a])
            elif args and args[-1].startswith("-"):
                args.pop()  # « --api-key » without its value: dropped too
            continue
        args.append(a.replace("${workspaceFolder}", project or home).replace("/path/to/allowed/files", project or home))
    if found["url"]:
        headers = {k: (env_values[k] if k in found["env"] else v) for k, v in found["headers"].items()}
        cfg = {"type": found["type"], "url": found["url"], "headers": headers, "enabled": True}
    else:
        cfg = {"command": mcp_catalog._which(found["command"]) or found["command"], "args": args,
               "env": {**found["env_defaults"], **{k: env_values[k] for k in found["env"] if k not in found["headers"]}},
               "enabled": True}
    servers = dict(ext.MCP.config())
    servers[found["name"]] = cfg
    ext.MCP.save_config(servers)
    srv = ext.MCP.get(found["name"])  # start it now so errors show up immediately
    return {"name": found["name"], "error": srv.error if srv else None}
