"""Catalogue of ready-to-install MCP servers for Naim (one click in Personnaliser → MCP)."""
import shutil

# name: (category, description, config, required env vars, runtime)
CATALOG = {
    "docs-librairies": ("Code", "Documentation à jour de n'importe quelle librairie ou framework (React, Flask, Expo, SwiftUI…), avec exemples.",
                        {"command": "npx", "args": ["-y", "@upstash/context7-mcp"]}, [], "node"),
    "code-semantique": ("Code", "Comprendre un gros projet : symboles, définitions, références, modifications précises (Serena).",
                        {"command": "uvx", "args": ["--from", "serena-agent", "serena", "start-mcp-server", "--context", "ide-assistant",
                                                    "--project", "{PROJECT}"]}, [], "uv"),
    "recherche-web": ("Web", "Recherche web DuckDuckGo et lecture de pages, sans clé.",
                      {"command": "uvx", "args": ["duckduckgo-mcp-server"]}, [], "uv"),
    "wikipedia": ("Savoir", "Articles Wikipédia : recherche, résumés, sections, liens, dans plusieurs langues.",
                  {"command": "uvx", "args": ["wikipedia-mcp"]}, [], "uv"),
    "excel": ("Documents", "Créer, lire et modifier des classeurs Excel : feuilles, formules, mise en forme, graphiques, tableaux croisés.",
              {"command": "uvx", "args": ["excel-mcp-server", "stdio"]}, [], "uv"),
    "markitdown": ("Documents", "Convertir PDF, Word, Excel, PowerPoint, HTML, images en Markdown (Microsoft MarkItDown).",
                   {"command": "uvx", "args": ["markitdown-mcp"]}, [], "uv"),
    "fichiers": ("Fichiers", "Lire, écrire et chercher dans un dossier autorisé.",
                 {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "{PROJECT}"]}, [], "node"),
    "web-fetch": ("Web", "Télécharger une page web et la convertir en texte lisible.",
                  {"command": "uvx", "args": ["mcp-server-fetch"]}, [], "uv"),
    "navigateur": ("Web", "Piloter un vrai navigateur (Playwright) : cliquer, remplir, capturer.",
                   {"command": "npx", "args": ["-y", "@playwright/mcp@latest"]}, [], "node"),
    "brave-search": ("Web", "Recherche web via l'API Brave Search.",
                     {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-brave-search"]}, ["BRAVE_API_KEY"], "node"),
    "git": ("Code", "Historique, diff, branches et commits d'un dépôt Git.",
            {"command": "uvx", "args": ["mcp-server-git", "--repository", "{PROJECT}"]}, [], "uv"),
    "github": ("Code", "Issues, pull requests, fichiers et recherche sur GitHub.",
               {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]}, ["GITHUB_PERSONAL_ACCESS_TOKEN"], "node"),
    "gitlab": ("Code", "Projets, merge requests et issues GitLab.",
               {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-gitlab"]}, ["GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_API_URL"], "node"),
    "sentry": ("Code", "Lire les erreurs et incidents remontés par Sentry.",
               {"command": "uvx", "args": ["mcp-server-sentry"]}, ["SENTRY_AUTH_TOKEN"], "uv"),
    "sqlite": ("Données", "Interroger et modifier une base SQLite.",
               {"command": "uvx", "args": ["--with", "mcp==1.1.2", "mcp-server-sqlite", "--db-path", "{PROJECT}/data.db"]}, [], "uv"),
    "postgres": ("Données", "Interroger une base PostgreSQL (lecture seule).",
                 {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-postgres", "{DATABASE_URL}"]}, ["DATABASE_URL"], "node"),
    "memoire-graphe": ("Mémoire", "Mémoire à long terme sous forme de graphe d'entités.",
                       {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"]}, [], "node"),
    "reflexion": ("Raisonnement", "Réflexion pas à pas structurée pour les problèmes complexes.",
                  {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]}, [], "node"),
    "heure": ("Utilitaires", "Heure actuelle et conversions de fuseaux horaires.",
              {"command": "uvx", "args": ["mcp-server-time"]}, [], "uv"),
    "slack": ("Communication", "Lire et envoyer des messages Slack.",
              {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-slack"]}, ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"], "node"),
    "notion": ("Productivité", "Lire et modifier des pages et bases Notion.",
               {"command": "npx", "args": ["-y", "@notionhq/notion-mcp-server"]}, ["NOTION_TOKEN"], "node"),
    "google-maps": ("Utilitaires", "Adresses, itinéraires et lieux via Google Maps.",
                    {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-google-maps"]}, ["GOOGLE_MAPS_API_KEY"], "node"),
    "docker": ("DevOps", "Gérer conteneurs, images et volumes Docker.",
               {"command": "uvx", "args": ["mcp-server-docker"]}, [], "uv"),
    "kubernetes": ("DevOps", "Inspecter et gérer un cluster Kubernetes (kubectl).",
                   {"command": "npx", "args": ["-y", "mcp-server-kubernetes"]}, [], "node"),
    "tout-test": ("Développement", "Serveur de démonstration qui expose tous les types d'outils MCP (pour tester).",
                  {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}, [], "node"),
}

RUNTIMES = {
    "node": ("npx", "Node.js : brew install node"),
    "uv": ("uvx", "uv (Python) : brew install uv"),
}


# not offered to Naim on demand: its own tools already do it (files, web pages, time) or test-only servers
NOT_ON_DEMAND = {"fichiers", "web-fetch", "heure", "tout-test", "markitdown"}


def _which(cmd):
    return shutil.which(cmd) or next((p for p in (f"/opt/homebrew/bin/{cmd}", f"/usr/local/bin/{cmd}") if __import__("os").path.exists(p)), None)


def catalog(installed=()):
    out = []
    for name, (cat, desc, cfg, env, runtime) in CATALOG.items():
        exe, hint = RUNTIMES[runtime]
        out.append({"name": name, "category": cat, "description": desc, "env": env, "runtime": runtime,
                    "ready": _which(exe) is not None, "install_hint": hint, "installed": name in installed,
                    "command": cfg["command"], "args": cfg["args"]})
    return out


def build_config(name, project="", env_values=None):
    """Concrete server config for the catalogue entry (placeholders filled, absolute npx/uvx path)."""
    cat, desc, cfg, env, runtime = CATALOG[name]
    env_values = env_values or {}
    home = str(__import__("pathlib").Path.home())
    subst = {"{PROJECT}": project or home, **{"{%s}" % k: env_values.get(k, "") for k in env}}
    args = []
    for a in cfg["args"]:
        for k, v in subst.items():
            a = a.replace(k, v)
        args.append(a)
    return {"command": _which(cfg["command"]) or cfg["command"], "args": args,
            "env": {k: env_values.get(k, "") for k in env}, "enabled": True}
