"""naim-mem MCP server (stdio, JSON-RPC): the tools Naim calls to search what it did in past sessions."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import memoire  # noqa: E402

TOOLS = [
    {"name": "chercher", "description": "Search past sessions (requests, actions, final answers) by words: what was done, "
     "fixed, decided before. Returns entries #id · date · type · project · title, with an excerpt.",
     "inputSchema": {"type": "object", "properties": {"requete": {"type": "string"}, "limite": {"type": "integer"}},
                     "required": ["requete"]}},
    {"name": "chronologie", "description": "The recent requests and answers (not every action), newest first; optionally "
     "for one project (a word of its folder name) and over N days (default 7).",
     "inputSchema": {"type": "object", "properties": {"projet": {"type": "string"}, "jours": {"type": "number"}}}},
    {"name": "detail", "description": "The full text of one entry by its #id (from chercher or chronologie).",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}},
]


def call(name, a):
    if name == "chercher":
        rows = memoire.search(a.get("requete", ""), a.get("limite") or 10)
        return "\n\n".join(rows) if rows else "Rien trouvé dans la mémoire des sessions pour ces mots."
    if name == "chronologie":
        rows = memoire.timeline(a.get("projet") or "", a.get("jours") or 7)
        return "\n".join(rows) if rows else "Rien sur cette période."
    if name == "detail":
        return memoire.detail(a.get("id", 0)) or "Entrée inconnue."
    raise ValueError(f"outil inconnu : {name}")


def reply(id_, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    msg.update({"error": {"code": -32000, "message": error}} if error else {"result": result})
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    try:
        req = json.loads(line)
    except ValueError:
        continue
    method, id_ = req.get("method"), req.get("id")
    if id_ is None:  # a notification (« initialized »…): no answer
        continue
    try:
        if method == "initialize":
            reply(id_, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                        "serverInfo": {"name": "naim-mem", "version": "1.0"}})
        elif method == "tools/list":
            reply(id_, {"tools": TOOLS})
        elif method == "tools/call":
            p = req.get("params") or {}
            reply(id_, {"content": [{"type": "text", "text": call(p.get("name"), p.get("arguments") or {})}]})
        elif method == "ping":
            reply(id_, {})
        else:
            reply(id_, error=f"méthode inconnue : {method}")
    except Exception as e:  # noqa: BLE001
        reply(id_, error=str(e))
