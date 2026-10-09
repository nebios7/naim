"""Local web server for the Naim UI (browser and desktop app).

Serves web/index.html and a small API on 127.0.0.1 only:
  GET  /api/status                      Ollama reachability + installed models
  POST /api/chat                        streams NDJSON events (chat tokens, or agent steps/approvals)
  POST /api/approve                     answer an agent approval request
  POST /api/answer                      answer a question the agent asked (ask_user)
  GET  /api/autotrain                   automatic training status; POST /api/autotrain/run, /api/autotrain/rollback
  GET  /api/voicetrain[/audio]          Naim's voices (owner); POST /api/voicetrain/{run,pause,source,clean,try,activate}
  POST /api/interject                   a message typed while the agent works (read at its next step)
  GET  /api/changes?runs=a,b            files changed by agent runs, with their diff; POST /api/changes/revert one file
  POST /api/stop                        stop a running chat/agent run
  GET  /api/conversations               list saved conversations (id, title, updated)
  GET|PUT|DELETE /api/conversations/ID  read / save / delete one conversation
  GET|PUT /api/settings                 user settings
  GET  /api/files?root=&path=           list one directory of a project
  GET  /api/file?root=&path=            read one project file (text, max 400 KB)
  GET  /api/pick-folder                 native macOS folder picker
  GET  /api/models                      installed + loaded Ollama models
  POST /api/models/pull | delete | unload   manage Ollama models (pull streams progress)
  POST /api/terminal                    run a shell command in a folder, streaming output
  POST /api/notify                      macOS notification
  POST /api/reveal                      show a folder in the Finder
  GET  /api/processes[?cwd=]            background processes (servers, apps...) started by the agent or the terminal
  GET  /api/processes/ID                one process: status + last output lines
  POST /api/processes/start | ID/stop | ID/remove
  GET|PUT /api/mcp, POST /api/mcp/NAME/restart   MCP servers
  GET /api/skills?root=, GET /api/skill?path=, POST /api/skills, PUT /api/skill, DELETE /api/skill?path=
  GET|PUT /api/memory                   long-term memory facts
  GET /api/project-info?root=           NAIM.md / AGENTS.md of a project
  GET /api/git/status|diff?root=, POST /api/git/commit|branch|init
  GET /api/checkpoints/RUN, POST /api/checkpoints/RUN/restore   undo an agent run
Conversations and settings live in ~/Library/Application Support/Naim, so the desktop app and the
browser share them.
"""
import json
import mimetypes
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import base64
import computer as cu
import docs
import extensions as ext
import feedback_share
import learning
import model_download
import memory
import llamacpp
import mcp_catalog
import scheduler
import skill_hub
from naimtools import (ANNOUNCE_RE, STOP_WORDS_RE, writing_text, CHAT_PROMPT, OLLAMA_HOST, PROCESSES, SKIP_DIRS, TOOL_GROUPS, WEB_TOOLS, Agent, now_note, ollama_chat,
                       raw_tool_calls, today_line)

# chat mode: the web tools are offered only when the message asks for something the model cannot know
WEB_NEED_RE = re.compile(r"\b(cherche|recherche|web|internet|en ligne|google|actualit|news|aujourd'hui|cette semaine|"
                         r"derni[eè]re? version|prix|m[ée]t[ée]o|qui est|c'est qui|si ki|search|latest|today)\b|https?://", re.I)
WEB_CHAT_NOTE = ("\n\nYou CAN access the internet in this conversation with the web_search and web_fetch tools. Use them to "
                 "answer; then answer in the user's language, cite the sources (links) you used, and say clearly when "
                 "nothing reliable was found. Never claim you have no internet access.")

WEB = Path(__file__).parent / "web"
# the user wants a file (Chat mode then gets the creer_fichier tool, see chatfiles.py)
FILE_NEED_RE = re.compile(r"\b(pdf|docx?|word|odt|rtf|zip|archive|excel|xlsx|csv|pptx|powerpoint|fichiers?|"
                          r"t[ée]l[ée]charg\w*|export\w*|en (png|svg|json|html|markdown|txt|image))\b|"
                          r"\b[\w-]+\.(pdf|docx|odt|rtf|xlsx|csv|zip|png|svg|json|html|md|txt|py|js|ts|sh|swift|yaml|xml)\b", re.I)
FILE_OFFER_RE = re.compile(r"\b(pdf|docx?|word|zip|excel|xlsx|csv|fichier|document|t[ée]l[ée]charg)", re.I)
FILE_CHAT_NOTE = ("\n\nYou CAN create real files in this conversation with the creer_fichier tool (PDF, Word, Excel, ZIP, images, "
                  "code, any extension). When the user wants a file, call creer_fichier with the COMPLETE content: never "
                  "write Python, shell or <tool_call> text to make it yourself. Then say in one sentence what you created.")


# a greeting, thanks or a short acknowledgement needs no reasoning: it would take minutes to answer « bonsoir »
TRIVIAL_RE = re.compile(r"\W*((salut|bonjour|bonsoir|coucou|hello|hey|hi|yo|re)\b|(merci|thanks?|thank you)\b|"
                        r"(ok|okay|d'accord|dac|super|g[ée]nial|parfait|top|cool|nickel|bien|tr[eè]s bien|bonne nuit|"
                        r"[àa] (demain|plus|bient[oô]t)|bye|ciao)\b)", re.I)


# tools kept for a plain question or a lesson in Chat: look things up, never change files
ANSWER_TOOLS = {"read_file", "list_files", "find_files", "search", "find_symbol", "find_references", "web_search", "web_fetch",
                "use_mcp", "use_tools", "look_at", "remember", "use_skill", "aller_dans_dossier", "chercher_contact",
                "mail_inbox", "planifier", "send_email", "http_request"}
# actions on the Mac itself (printer, apps, settings, music…): Naim does them with its tools, asking when it is sensitive
MAC_ACTION = (r"appelle|appeler|passe un appel|t[ée]l[ée]phone (à|a)\b|\bsms\b|texto|imessage|envoie (un |le |ce )?message|"
              r"imprim|impression|imprimante|\bscanne|ouvre|ferme|quitte|r[eè]gle|active|d[ée]sactive|[ée]teins|allume|"
              r"monte le son|baisse le son|volume|luminosit|wi-?fi|bluetooth|mets? en veille|red[ée]marre|joue|musique")
MAC_ACTION_RE = re.compile(MAC_ACTION, re.I)
# « n'imprime pas », « ne lance pas encore », « attends mon signal »: the user does NOT want the action now
NOT_NOW_RE = re.compile(r"\bn['’e]\s*(?:\w+\s+){0,2}?(?:pas|rien|plus|jamais)\b|\bpas encore\b|\battends?\b|\bstop\b|"
                        r"\bne (?:pas|rien) (?:lancer|imprimer|envoyer|appeler)", re.I)
# making something new (a skill's job), as opposed to acting on a file that already exists
MAKE_RE = re.compile(r"\b(cr[ée]e[rz]?|fais|faire|fait|g[ée]n[èe]re[rz]?|dessine[rz]?|[ée]cri[st]|[ée]crire|r[ée]dige[rz]?|"
                     r"pr[ée]pare[rz]?|construi\w*|con[çc]oi\w*|plans?|sch[ée]mas?|nouveau|nouvelle)\b", re.I)
# the user wants files made or changed (a document, their project), not only an answer
FILE_WORK_RE = re.compile(r"images?|logo|affiche|\bsvg\b|\bpng\b|infographie|fichiers?|documents?|\bpdf\b|word|docx|excel|xlsx|csv|\bzip\b|enregistr|sauvegard|"
                          r"\bcr[ée]e[rz]?\b|\bcr[ée]ation|g[ée]n[èe]re|modifi|corrige|ajoute|supprime|renomme|d[ée]place|"
                          r"installe|lance|ex[ée]cute|teste|" + MAC_ACTION, re.I)  # a file name alone (« un exemple chronometre.py ») is a question
TRIVIAL_WORDS = set("""salut bonjour bonsoir bonsoire coucou hello hey hi yo re merci thanks thank you beaucoup bien ok okay
d'accord dac super génial genial parfait top cool nickel très tres bonne nuit à a demain plus bientôt bientot bye ciao naim
mohamed et encore c'est cool ça ca marche""".split())


# small talk with a question mark: « ça va ? », « Salut Naim, comment vas-tu ? », « tu vas bien ? »
SOCIAL_RE = re.compile(r"^\W*(?:(?:salut|bonjour|bonsoir|coucou|hello|hey|yo)\W+)?(?:naim\W+)?(?:et toi\W+)?"
                       r"(?:ça va|ca va|comment (?:ça va|ca va|vas[- ]tu|tu vas|allez[- ]vous)|tu vas bien|vous allez bien)"
                       r"(?:\W+(?:naim|toi|aujourd'hui|ce soir))?\W*$", re.I)


# a request to DO something (create, fix, run, send…): the Agent acts, even if the message is also a question
ACTION_RE = re.compile(r"\b(?:cr[ée]{1,2}[sz]?|cr[ée]er|fai[st]|faire|fabrique|g[ée]n[èe]re|[ée]cri[st]|[ée]crire|r[ée]dige|d[ée]veloppe|"
                       r"construi[st]|corrige|r[ée]pare|modifie|remplace|ajoute|supprime|efface|renomme|d[ée]place|copie|"
                       r"installe|lance|ex[ée]cute|teste|d[ée]ploie|envoie|imprime|appelle|ouvre|ferme|convertis|"
                       r"t[ée]l[ée]charge|configure|optimise|nettoie|range|organise|planifie|mets|mettre|transforme|traduis|"
                       r"r[ée]sume|compile|build|push|commit|sauvegarde|enregistre)\w*", re.I)
QUESTION_RE = re.compile(r"\?\s*$|^\W*(?:c'est quoi|qu'est[- ]ce|pourquoi|comment|tu penses|que penses|quel(?:le)?s?\b|"
                         r"est[- ]ce que|explique|dis[- ]moi|parle[- ]moi|à quoi sert|quelle est la diff[ée]rence|c'est quoi la)", re.I)


def pure_question(text):
    """A question that asks for nothing to be done (no action verb): it gets an answer, not a task."""
    t = (text or "").strip()
    return bool(t) and len(t) < 400 and bool(QUESTION_RE.search(t)) and not ACTION_RE.search(t) and not MAC_ACTION_RE.search(t)


def trivial_message(text):
    """Only polite words (a greeting, thanks, « ok super »): no request inside."""
    t = (text or "").strip().lower()
    if not t or "?" in t or "`" in t or len(t.split()) > 6 or not TRIVIAL_RE.match(t):
        return False
    words = [w for w in re.findall(r"[\w'àâçéèêëîïôûùüÿœ]+", t)]
    return sum(w not in TRIVIAL_WORDS for w in words) == 0


def shown_part(text):
    """What may be displayed while streaming: never a « <tool_call> » block, nor the start of one being written."""
    cut = text.find("<tool_call")
    if cut >= 0:
        return text[:cut]
    lt = text.rfind("<")
    if lt >= 0 and "<tool_call".startswith(text[lt:]):  # « <too… » could become « <tool_call »: wait
        return text[:lt]
    return text


def with_first_request(message, history):
    """« Un programme de calcul » answering Naim's own question: the request it answers comes back with it, so that
    nothing asked first (« … et imprime-le ») is forgotten. Else the message unchanged."""
    msg = (message or "").strip()
    hist = [h for h in (history or []) if h.get("role") in ("user", "assistant")]
    # only a short answer (« Un programme de calcul », « en PDF ») — a sentence of its own is a new request
    if not msg or len(msg.split()) > 8 or len(hist) < 2 or hist[-1].get("role") != "assistant":
        return message
    if "?" not in str(hist[-1].get("content") or "")[-400:]:
        return message
    first = str(hist[-2].get("content") or "").strip() if hist[-2].get("role") == "user" else ""
    if (not first or trivial_message(first) or SOCIAL_RE.match(first) or first.lower() in msg.lower()
            or not (MAKE_RE.search(first) or MAC_ACTION_RE.search(first) or FILE_WORK_RE.search(first))):
        return message  # « Salut, comment vas-tu ? » is not a request to come back to
    return f"{first}\n\n(Réponse à ta question : {msg}. Fais maintenant TOUT ce que je demandais ci-dessus.)"


def chosen_option(message, history):
    """« 2 », « la 2 », « option 2 » after Naim offered numbered choices: the text of that choice, else ''."""
    m = re.fullmatch(r"\s*(?:(?:la|le|l'|option|choix|n°|num[ée]ro)\s*)?(\d{1,2})\s*[.)!]?\s*", message or "", re.I)
    last = next((x.get("content") or "" for x in reversed(history or []) if x.get("role") == "assistant"), "")
    if not m or not last:
        return ""
    line = re.search(rf"(?m)^\s*(?:\*\*)?{m.group(1)}[.)]\s*(?:\*\*)?\s*(.+)$", last[-3000:])
    return line.group(1).replace("**", "").strip(" *") if line else ""


EMAIL_NEED_RE = re.compile(r"\b(e-?mails?|mails?|courriels?|envoi[es]?|envoie[rz]?|envoy\w*|transf[èe]re\w*)\b", re.I)
EMAIL_CHAT_NOTE = ("\n\nYou CAN send emails in this conversation with send_email (attach files you created with their full path). "
                   "When the user names a person without an address, call chercher_contact first; never invent an address. "
                   "« une copie à moi » = also send to the user's own address (from your memory).")


# a request (not a mere mention: « merci, le lien dans le pdf n'est pas bon, pas grave » asks for nothing)
FILE_ASK_RE = re.compile(r"\b(fai[st]e?s?|cr[ée]{2}[rz]?|g[ée]n[èe]re[rz]?|refai[st]|recr[ée]{2}|transforme[rz]?|convertis|convertir|"
                         r"exporte[rz]?|mets?|donne[- ]moi|pr[ée]pare[rz]?|r[ée]dige[rz]?|[ée]cri[st]|[ée]crire|sauvegarde[rz]?|"
                         r"enregistre[rz]?|peux[- ]tu|pourrais[- ]tu|tu peux|je veux|je voudrais|j'aimerais|besoin d'|"
                         r"en (pdf|word|docx|excel|xlsx|zip|csv|png|image)|un (pdf|zip|fichier|document)|une (archive|image))\b", re.I)


def wants_file(message, history):
    """A file request, or a short answer (« 2 », « oui ») to Naim's last message when it offered a file."""
    msg = (message or "").strip()
    if FILE_NEED_RE.search(msg):
        return bool(FILE_ASK_RE.search(msg))
    last = next((m.get("content") or "" for m in reversed(history or []) if m.get("role") == "assistant"), "")
    if "@" in msg or re.search(r"\b(j'ai cr[ée]{2}|fichier cr[ée]{2}|cr[ée]{2} le fichier)", last, re.I):
        return False  # an address given, or the file is already made: not a new file request
    yes = re.fullmatch(r"\W*(oui|ouais|ok|okay|d'accord|dac|vas[- ]y|go|fais[- ]le|fais[- ]la|je veux bien|volontiers|yes|"
                       r"bien s[uû]r|carr[ée]ment|parfait,? vas[- ]y|ok vas[- ]y|oui vas[- ]y|oui stp|oui merci)\W*", msg, re.I)
    return bool(yes) and bool(FILE_OFFER_RE.search(last[-1500:]))


SCHEDULE_NEED_RE = re.compile(r"\b(planifi\w*|programme\w*|tous les (jours|matins|soirs|lundis|mardis|mercredis|jeudis|vendredis|samedis|dimanches)|"
                              r"chaque (jour|matin|soir|semaine|mois|heure|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)|"
                              r"toutes les \d+\s*(min|minutes|h|heures)|toutes les heures|demain à|rappelle[- ]moi|t[aâ]ches? planifi)", re.I)
DATA = Path(os.environ.get("NAIM_DATA", Path.home() / "Library/Application Support/Naim"))
CONVS = DATA / "conversations"
SETTINGS = DATA / "settings.json"
APPROVAL_TIMEOUT = 600  # seconds before an unanswered approval counts as "denied"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_pending = {}  # approval id -> {"event": threading.Event, "allow": bool}
_agents = {}  # run id -> running Agent (to pass it the messages typed while it works)
_runs = {}     # run id -> threading.Event (stop flag)
_lock = threading.Lock()


def ollama_models():
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST.rstrip('/')}/api/tags", timeout=3) as r:
            return [m["name"] for m in json.load(r)["models"]]
    except (urllib.error.URLError, OSError, ValueError):
        return None


def uses_llamacpp(body):
    """Naim runs on llama.cpp unless the user picked Ollama in the settings (or llama.cpp is unavailable)."""
    s = body.get("settings") or {}
    model = str(body.get("model", "naim")).split(":")[0]
    return model == "naim" and s.get("naim_backend", "llamacpp") in ("llamacpp", "mlx") and llamacpp.available()


def uses_mlx(body):
    """Naim on MLX: chosen in Moteur, and MLX + the MLX version of Naim are on this Mac."""
    s = body.get("settings") or {}
    if str(body.get("model", "naim")).split(":")[0] != "naim" or s.get("naim_backend") != "mlx":
        return False
    try:
        import mlxengine
        return mlxengine.available()
    except ImportError:
        return False


def _mlx_status():
    try:
        import mlxengine
        return mlxengine.SERVER.status()
    except ImportError:
        return {"available": False}


def model_options(body):
    s = body.get("settings") or {}
    if str(s.get("memory_limit", "")).isdigit():
        memory.LIMIT = max(5, min(int(s["memory_limit"]), 300))
    opts = {}
    for key, cast in (("temperature", float), ("top_p", float), ("top_k", int), ("repeat_penalty", float),
                      ("num_ctx", int), ("num_predict", int), ("seed", int)):
        v = s.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and (key != "num_predict" or v > 0) and (key != "seed" or v >= 0):
            opts[key] = cast(v)
    if s.get("keep_alive"):
        opts["keep_alive"] = str(s["keep_alive"])
    if uses_mlx(body):
        opts["backend"] = "mlx"
        opts.pop("keep_alive", None)
        opts["num_ctx"] = max(int(opts.get("num_ctx") or 0), 32768)
    elif uses_llamacpp(body):
        opts["backend"] = "llamacpp"
        for k, key in (("gpu_layers", "llama_gpu_layers"), ("threads", "llama_threads"), ("batch", "llama_batch"),
                       ("kv_type", "llama_kv_type"), ("checkpoints", "llama_checkpoints"), ("parallel", "llama_parallel")):
            if s.get(key) not in (None, ""):
                llamacpp.CONFIG[k] = s[key]
        opts.pop("keep_alive", None)
        opts["num_ctx"] = max(int(opts.get("num_ctx") or 0), 32768)
    system = (s.get("system_prompt") or "").strip()
    if s.get("user_name"):
        system = f"The user's name is {s['user_name']}.\n" + system
    return opts, system.strip()


_caps_cache = {}
VISION_PREFERENCE = ("naim", "gemma4", "gemma3", "llava-phi3", "llava", "moondream")  # Naim first


def model_caps(name):
    if name not in _caps_cache:
        try:
            with ollama_call("/api/show", {"model": name}) as r:
                _caps_cache[name] = set(json.load(r).get("capabilities", []))
        except (urllib.error.URLError, OSError, ValueError):
            return set()
    return _caps_cache[name]


def vision_model(preferred=""):
    names = ollama_models() or []
    candidates = ([preferred] if preferred else []) + [n for p in VISION_PREFERENCE for n in names if n.startswith(p)] + names
    for n in candidates:
        if n in names and "vision" in model_caps(n):
            return n
    return None


def describe_images(images, question, model):
    """Vision relay: a vision model describes the images so a text-only model (Naim) can use them."""
    prompt = ("Décris ces images de façon très détaillée et fidèle pour quelqu'un qui ne peut pas les voir : tout le texte "
              "visible (recopié exactement), le code, les erreurs, les éléments d'interface, les couleurs, la mise en page. "
              f"Question de l'utilisateur à propos des images : {question}")
    msg = ollama_chat(model, [{"role": "user", "content": prompt, "images": images}], options={"temperature": 0.2, "num_ctx": 16384})
    return (msg.get("content") or "").strip()


def with_vision(self, body):
    """If images are attached and the chosen model can't see, describe them with a vision model first."""
    images = body.get("images")
    model = body.get("model", "naim")
    if not images or "vision" in model_caps(model) or (uses_llamacpp(body) and llamacpp.model_files()[1]):
        return body
    vm = vision_model((body.get("settings") or {}).get("vision_model", ""))
    if not vm:
        self.event({"type": "note", "text": "⚠ Ce modèle ne voit pas les images : l'image est ignorée. Naim les voit avec son moteur llama.cpp (Personnaliser › Modèle › Moteur de Naim)."})
        return {**body, "images": None}
    self.event({"type": "status", "text": f"{vm} regarde l'image…"})
    desc = describe_images(images, body["message"], vm)
    self.event({"type": "vision", "model": vm, "text": desc})
    msg = f"[Description des {len(images)} image(s) jointe(s), faite par {vm}]\n{desc}\n\n[Message]\n{body['message']}"
    return {**body, "message": msg, "images": None}


def ollama_call(path, body=None, method="POST", timeout=30):
    req = urllib.request.Request(f"{OLLAMA_HOST.rstrip('/')}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


FENCE_RE = re.compile(r"```[ \t]*([\w+#.-]*)[^\n]*\n(.*?)```", re.S)


def collect_artifacts(limit=400):
    """Every code block (3+ lines) produced by Naim, newest conversations first."""
    out = []
    files = sorted(CONVS.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True) if CONVS.exists() else []
    for f in files:
        try:
            c = json.loads(f.read_text())
        except (ValueError, OSError):
            continue
        for i, m in enumerate(c.get("messages", [])):
            if m.get("role") != "assistant":
                continue
            for lang, code in FENCE_RE.findall(m.get("content", "")):
                if code.count("\n") >= 2:
                    out.append({"conv": c.get("id"), "title": c.get("title", ""), "updated": c.get("updated", 0),
                                "msg": i, "lang": lang.lower(), "code": code.rstrip("\n")})
                    if len(out) >= limit:
                        return out
    return out


def agent_settings(body):
    s = body.get("settings") or {}
    out = {"auto_writes": bool(s.get("auto_writes")), "auto_commands": bool(s.get("auto_commands")),
           "blocked": [b for b in str(s.get("blocked_commands") or "").splitlines() if b.strip()]}
    if isinstance(s.get("max_steps"), int) and 1 <= s["max_steps"] <= 200:
        out["max_steps"] = s["max_steps"]
    out["features"] = {k: s.get(f"enable_{k}", True) is not False for k in ("web", "memory", "skills", "mcp", "subagents", "computer", "simulator")}
    out["disabled_skills"] = s.get("disabled_skills") or []
    out["auto_mcp"] = bool(s.get("auto_mcp"))
    out["auto_computer"] = bool(s.get("auto_computer"))
    out["power"] = bool(s.get("computer_power"))  # red switch: everything without asking except sensitive actions
    out["screen_images"] = bool(s.get("screen_images"))
    out["email"] = s.get("enable_email", True) is not False
    out["learning"] = s.get("enable_learning", True) is not False
    out["review"] = s.get("enable_review", True) is not False
    if str(s.get("memory_limit", "")).isdigit():
        memory.LIMIT = max(5, min(int(s["memory_limit"]), 300))
    if str(s.get("max_subagents", "")).isdigit():
        out["max_subagents"] = int(s["max_subagents"])
    out["email_allowed"] = [str(s.get("email_allowed") or "")] + ([str(body.get("email_allow_extra"))] if body.get("email_allow_extra") else [])
    out["stop_temp_processes"] = s.get("stop_temp_processes", True) is not False
    out["keep_final_app"] = s.get("keep_final_app", True) is not False
    out["permissions"] = str(s.get("permissions") or "")
    out["hooks"] = str(s.get("hooks") or "")
    for k in ("auto_verify", "auto_skill", "minimal_mode"):
        out[k] = s.get(k, True) is not False
    for k, lo, hi in (("command_timeout", 10, 1800), ("loop_limit", 2, 20)):
        if isinstance(s.get(k), int) and lo <= s[k] <= hi:
            out[k] = s[k]
    return out


def project_path(root, path=""):
    base = Path(root).expanduser().resolve()
    p = (base / (path or ".")).resolve()
    if p != base and base not in p.parents:
        raise ValueError("path outside the project")
    return base, p


class Handler(BaseHTTPRequestHandler):
    server_version = "NaimServer/2.0"

    def log_message(self, *args):  # keep the terminal quiet
        pass

    # ------------------------------------------------------------ helpers
    def _owner_ok(self):
        """Owner routes: only Naim's own page (its address, and a header other web pages cannot send)."""
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost") and self.headers.get("X-Naim") == "1"

    def send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def event(self, ev):
        self.wfile.write((json.dumps(ev, ensure_ascii=False) + "\n").encode())
        self.wfile.flush()

    def route(self):
        u = urllib.parse.urlparse(self.path)
        return u.path, {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

    # ------------------------------------------------------------ GET
    def do_GET(self):
        path, q = self.route()
        if path in ("/", "/index.html"):
            data = (WEB / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/status":
            models = ollama_models()
            loaded = []
            if models is not None:
                try:
                    with ollama_call("/api/ps", method="GET", timeout=3) as r:
                        loaded = [m["name"] for m in json.load(r).get("models", [])]
                except (urllib.error.URLError, OSError, ValueError):
                    pass
            self.send_json({"ollama": models is not None, "models": models or [], "loaded": loaded, "home": str(Path.home()),
                            "llamacpp": llamacpp.SERVER.status(), "mlx": _mlx_status(),
                            "warm": {**WARM, "since": round(time.time() - WARM["t0"])}})
        elif path == "/api/settings":
            self.send_json(json.loads(SETTINGS.read_text()) if SETTINGS.exists() else {})
        elif path == "/api/conversations":
            items = []
            for f in CONVS.glob("*.json") if CONVS.exists() else []:
                try:
                    c = json.loads(f.read_text())
                    items.append({"id": c["id"], "title": c.get("title", ""), "updated": c.get("updated", 0),
                                  "mode": c.get("mode", "chat"), "pinned": bool(c.get("pinned")),
                                  "project": c.get("project", "") if c.get("mode") == "agent" else "",
                                  "scheduled": c.get("scheduled"), "folder": c.get("folder", ""),
                                  "tags": c.get("tags") or []})
                except (ValueError, KeyError, OSError):
                    continue
            self.send_json(sorted(items, key=lambda c: -c["updated"]))
        elif path == "/api/search":
            # full-text search in every conversation (messages, not only titles)
            needle = (q.get("q") or "").strip().lower()
            hits = []
            if len(needle) >= 2:
                for f in CONVS.glob("*.json") if CONVS.exists() else []:
                    try:
                        c = json.loads(f.read_text())
                    except (ValueError, OSError):
                        continue
                    for m in c.get("messages", []):
                        text = str(m.get("content") or "")
                        at = text.lower().find(needle)
                        if at >= 0:
                            a, b = max(0, at - 60), at + len(needle) + 80
                            hits.append({"id": c["id"], "title": c.get("title", ""), "mode": c.get("mode", "chat"),
                                         "updated": c.get("updated", 0), "role": m.get("role"),
                                         "snippet": ("…" if a else "") + " ".join(text[a:b].split()) + ("…" if b < len(text) else "")})
                            break
                hits.sort(key=lambda h: -h["updated"])
            self.send_json({"hits": hits[:40]})
        elif path == "/api/schedules/pending":
            self.send_json({"pending": scheduler.pending()})
        elif path == "/api/processes":
            self.send_json(PROCESSES.list(Path(q["cwd"]).expanduser().resolve() if q.get("cwd") else None))
        elif path.startswith("/api/processes/"):
            p = PROCESSES.get(path.rsplit("/", 1)[1])
            if not p:
                self.send_json({"error": "processus inconnu"}, 404)
                return
            self.send_json({**p.info(), "output": p.tail(400)})
        elif path == "/api/mcp":
            self.send_json({"servers": ext.MCP.status(), "path": str(ext.MCP.path), "json": ext.MCP.raw_json()})
        elif path == "/api/mcp/catalog":
            self.send_json(mcp_catalog.catalog(installed=set(ext.MCP.config())))
        elif path == "/api/share":
            s = _settings()
            shared = sum(1 for f in learning.TRACES.glob("*.json") if '"shared": "' in f.read_text(errors="ignore"))
            self.send_json({"enabled": bool(s.get("share_feedback")), "auto": bool(s.get("share_auto")),
                            "url": s.get("share_url") or feedback_share.DEFAULT_URL, "pending": len(feedback_share.pending()),
                            "shared": shared, "install": feedback_share.install_id(), **feedback_share.STATE})
        elif path == "/api/learning":
            self.send_json(learning.summary())
        elif path == "/api/storage":
            self.send_json(storage_info())
        elif path == "/api/backups":
            self.send_json(backup_list())
        elif path == "/api/tts":
            import naim_voice
            self.send_json({"available": naim_voice.available() or naim_voice.natural_available(),
                            "natural": naim_voice.natural_available(), "fast": naim_voice.available()})
        elif path == "/api/model/version":
            self.send_json(model_version())
        elif path == "/api/model/download":
            self.send_json({**model_download.STATE, "missing": [f for f, _ in model_download.missing()]})
        elif path == "/api/computer":
            self.send_json(cu.status())
        elif path == "/api/llama":
            self.send_json({**llamacpp.SERVER.status(), "log": llamacpp.SERVER.log_tail()})
        elif path == "/api/schedules":
            self.send_json({"tasks": scheduler.load(), "running": scheduler.running_ids(), "pending": scheduler.pending()})
        elif path == "/api/naim-home":
            self.send_json({"home": str(ext.HOME), "skills": str(ext.HOME / "skills"),
                            "instructions": ext.global_instructions()})
        elif path == "/api/skills":
            settings = json.loads(SETTINGS.read_text()) if SETTINGS.exists() else {}
            self.send_json(ext.list_skills(q.get("root") or None, set(settings.get("disabled_skills") or [])))
        elif path == "/api/skill":
            f = Path(q.get("path", ""))
            ok = f.name == "SKILL.md" and f.is_file()
            self.send_json({"content": f.read_text()} if ok else {"error": "skill introuvable"}, 200 if ok else 404)
        elif path == "/api/memory":
            self.send_json({"facts": memory.load(), "cats": memory.CATS, "limit": memory.LIMIT, "progress": memory.PROGRESS})
        elif path == "/api/project-info":
            root = q.get("root", "")
            name, text = ext.project_instructions(root) if root and Path(root).is_dir() else (None, "")
            self.send_json({"file": name, "content": text})
        elif path == "/api/git/status":
            try:
                self.send_json(ext.git_status(q["root"]))
            except (OSError, KeyError, subprocess.SubprocessError) as e:
                self.send_json({"repo": False, "error": str(e)})
        elif path == "/api/git/diff":
            self.send_json({"diff": ext.git_diff(q["root"], q.get("path") or None)})
        elif path.startswith("/api/checkpoints/"):
            info = ext.checkpoint_info(path.rsplit("/", 1)[1])
            self.send_json(info or {"error": "aucun point de restauration"}, 200 if info else 404)
        elif path == "/api/artifacts":
            self.send_json(collect_artifacts())
        elif path.startswith("/api/conversations/"):
            cid = path.rsplit("/", 1)[1]
            f = CONVS / f"{cid}.json"
            if ID_RE.match(cid) and f.exists():
                self.send_json(json.loads(f.read_text()))
            else:
                self.send_error(404)
        elif path == "/api/files" and q.get("all"):
            try:  # every file of the project (for @mentions), newest first
                base, _ = project_path(q.get("root", ""))
                found = []
                for dirpath, dirnames, filenames in os.walk(base):
                    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
                    for n in filenames:
                        if n.startswith(".") or n == ".DS_Store":
                            continue
                        f = Path(dirpath) / n
                        try:
                            found.append((f.stat().st_mtime, str(f.relative_to(base))))
                        except OSError:
                            pass
                    if len(found) > 4000:
                        break
                self.send_json({"files": [r for _, r in sorted(found, reverse=True)[:4000]]})
            except (ValueError, OSError) as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/files":
            try:
                base, p = project_path(q.get("root", ""), q.get("path", ""))
                entries = []
                for e in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                    if e.name in SKIP_DIRS or e.name == ".DS_Store":
                        continue
                    entries.append({"name": e.name, "path": str(e.relative_to(base)), "dir": e.is_dir()})
                self.send_json({"entries": entries})
            except (ValueError, OSError) as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/docinfo":
            # number of pages of a PDF / document (Spotlight metadata: instant, nothing to open)
            try:
                _, f = project_path(q.get("root", ""), q.get("path", ""))
                r = subprocess.run(["mdls", "-raw", "-name", "kMDItemNumberOfPages", str(f)], capture_output=True, text=True, timeout=10)
                n = r.stdout.strip()
                if not n.isdigit() and f.suffix.lower() == ".pdf":
                    import docs as _docs  # (a plain « import docs » here would shadow the module in the whole handler)
                    n = str(_docs.extract(f)[0].count("--- Page "))
                self.send_json({"pages": int(n) if n.isdigit() and int(n) > 0 else None})
            except (ValueError, OSError, subprocess.SubprocessError):
                self.send_json({"pages": None})
        elif path in ("/api/thumb", "/api/raw") or path == "/vendor/mermaid.min.js":
            try:
                if path == "/vendor/mermaid.min.js":
                    import diagrams
                    f, ctype = diagrams.mermaid_js(), "text/javascript"
                else:
                    _, f = project_path(q.get("root", ""), q.get("path", ""))
                    if path == "/api/thumb":
                        f, _note = docs.preview_png(f, int(q.get("page") or 1), int(q.get("w") or 640))
                    ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                data = f.read_bytes()
            except Exception as e:  # noqa: BLE001 — any failure is just "no preview"
                self.send_json({"error": str(e)}, 404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=86400" if path.startswith("/vendor") else "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/owner":
            mod = _private("owner_admin") if self._owner_ok() else None
            self.send_json(mod.payload() if mod and mod.available() else {"available": False})
        elif path == "/api/autotrain":
            at = _private("autotrain")
            self.send_json(at.status(_settings()) if at else {"available": False})
        elif path == "/api/voicetrain":
            vt = _private("voicetrain")
            self.send_json(vt.status() if vt else {"available": False})
        elif path == "/api/voicetrain/audio":
            vt = _private("voicetrain") if (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost") else None
            f = vt.audio(q.get("voix", ""), q.get("f", "")) if vt and re.fullmatch(r"[a-z0-9-]+", q.get("voix", "")) else None
            if not f or not f.exists():
                self.send_json({"error": "introuvable"}, 404)
            else:
                data = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/mp4" if f.suffix in (".m4a", ".mp4") else "audio/mpeg" if f.suffix == ".mp3" else "audio/wav")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
        elif path == "/api/background":  # long jobs started « in the background »: running, and finished not reported
            import naimtools as _nt
            self.send_json(_nt.background_state())
        elif path == "/api/notify/last":
            self.send_json(dict(cu.LAST_NOTIF))
        elif path == "/api/changes":
            out = []
            for rid in [r for r in (q.get("runs") or "").split(",") if r][-20:]:
                out += ext.checkpoint_changes(rid)
            self.send_json({"changes": out})
        elif path == "/api/file":
            try:
                _, p = project_path(q.get("root", ""), q.get("path", ""))
                if p.stat().st_size > 400_000:
                    self.send_json({"error": "fichier trop volumineux"}, 400)
                    return
                self.send_json({"content": p.read_text(errors="replace")})
            except (ValueError, OSError) as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/models":
            try:
                with ollama_call("/api/tags", method="GET") as r:
                    tags = json.load(r)["models"]
                with ollama_call("/api/ps", method="GET") as r:
                    loaded = {m["name"]: m for m in json.load(r)["models"]}
            except (urllib.error.URLError, OSError, ValueError) as e:
                self.send_json({"error": str(e), "models": []})
                return
            self.send_json({"models": [{
                "name": m["name"], "size": m.get("size", 0), "modified": m.get("modified_at", ""),
                "params": m.get("details", {}).get("parameter_size", ""), "quant": m.get("details", {}).get("quantization_level", ""),
                "family": ("Naim" if m["name"].startswith("naim") else "Mimo" if m["name"].startswith("mimo")
                           else m.get("details", {}).get("family", "")),  # its own name, not the technical architecture id
                "loaded": m["name"] in loaded,
                "caps": sorted(model_caps(m["name"])),
                "vram": loaded.get(m["name"], {}).get("size_vram", 0)} for m in tags]})
        elif path == "/api/pick-folder":
            r = subprocess.run(["osascript", "-e", 'POSIX path of (choose folder with prompt "Dossier du projet pour Naim")'],
                               capture_output=True, text=True)
            self.send_json({"path": r.stdout.strip().rstrip("/") if r.returncode == 0 else None})
        else:
            self.send_error(404)

    # ------------------------------------------------------------ PUT / DELETE
    def do_PUT(self):
        path, _ = self.route()
        if path == "/api/mcp":
            b = self.read_json()
            if "json" in b:  # raw editor: accept the standard {"mcpServers": {...}} document
                try:
                    doc = json.loads(b["json"])
                    servers = doc.get("mcpServers", doc.get("servers"))
                    assert isinstance(servers, dict)
                except (ValueError, AssertionError, AttributeError):
                    self.send_json({"error": "JSON invalide : il faut un objet {\"mcpServers\": {...}}"}, 400)
                    return
                ext.MCP.save_config({k: {**v, "enabled": not v.get("disabled", False)} for k, v in servers.items()})
            else:
                ext.MCP.save_config(b.get("servers", {}))
            self.send_json({"servers": ext.MCP.status(), "json": ext.MCP.raw_json()})
        elif path == "/api/global-instructions":
            ext.HOME.mkdir(parents=True, exist_ok=True)
            (ext.HOME / "NAIM.md").write_text(self.read_json().get("content", ""))
            self.send_json({"ok": True})
        elif path == "/api/memory":
            ext.write_memory(self.read_json().get("facts", []))
            self.send_json({"facts": ext.read_memory()})
        elif path == "/api/skill":
            b = self.read_json()
            f = Path(b.get("path", ""))
            if f.name != "SKILL.md" or not f.parent.is_dir():
                self.send_json({"error": "chemin invalide"}, 400)
                return
            f.write_text(b.get("content", ""))
            self.send_json({"ok": True})
        elif path == "/api/settings":
            DATA.mkdir(parents=True, exist_ok=True)
            SETTINGS.write_text(json.dumps(self.read_json(), ensure_ascii=False, indent=2))
            self.send_json({"ok": True})
        elif path.startswith("/api/conversations/"):
            cid = path.rsplit("/", 1)[1]
            if not ID_RE.match(cid):
                self.send_error(400)
                return
            c = self.read_json()
            c["id"] = cid
            if not c.pop("keep_time", False) or "updated" not in c:
                c["updated"] = time.time()
            CONVS.mkdir(parents=True, exist_ok=True)
            (CONVS / f"{cid}.json").write_text(json.dumps(c, ensure_ascii=False))
            self.send_json({"ok": True})
        else:
            self.send_error(404)

    def do_DELETE(self):
        path, q = self.route()
        if path.startswith("/api/schedules/"):
            scheduler.delete(path.rsplit("/", 1)[1])
            self.send_json({"ok": True})
            return
        if path == "/api/skill":
            self.send_json({"ok": ext.delete_skill(q.get("path", ""))})
            return
        cid = path.rsplit("/", 1)[1]
        if path.startswith("/api/conversations/") and ID_RE.match(cid):
            (CONVS / f"{cid}.json").unlink(missing_ok=True)
            self.send_json({"ok": True})
        else:
            self.send_error(404)

    # ------------------------------------------------------------ POST
    def do_POST(self):
        path, _ = self.route()
        if path == "/api/owner/action":
            mod = _private("owner_admin") if self._owner_ok() else None
            if not mod or not mod.available():
                self.send_json({"error": "indisponible"}, 404)
            else:
                b = self.read_json()
                try:
                    self.send_json(mod.action(b.get("action", ""), b.get("args") or {}))
                except Exception as e:  # noqa: BLE001 — show the reason in the Admin tab
                    self.send_json({"error": str(e)[:500]})
        elif path in ("/api/autotrain/run", "/api/autotrain/rollback", "/api/autotrain/delete"):
            at = _private("autotrain")
            if not at:
                self.send_json({"error": "indisponible"})
            elif path.endswith("/delete"):
                self.send_json(at.delete_version(self.read_json().get("label", "")))
            elif path.endswith("/rollback"):
                self.send_json(at.rollback(self.read_json().get("label", ""), _settings()))
            else:
                self.send_json({"error": "un entraînement est déjà en cours"} if at.RUNNING["phase"] else at.launch_standalone())
        elif path.startswith("/api/voicetrain/"):
            vt = _private("voicetrain") if self._owner_ok() else None  # uploads and starts programs: Naim's page only
            b = self.read_json()
            v = b.get("voix") or None
            if not vt or not vt.available():
                self.send_json({"error": "indisponible"})
            elif v and not re.fullmatch(r"[a-z0-9-]+", v):
                self.send_json({"error": "voix inconnue"})
            elif path.endswith("/run"):
                self.send_json(vt.launch_standalone(v))
            elif path.endswith("/pause"):
                self.send_json(vt.pause())
            elif path.endswith("/source"):
                self.send_json(vt.add_source(b.get("nom", ""), b.get("fichier", ""), b.get("data", "")))
            elif path.endswith("/clean"):
                self.send_json(vt.clean(v, b.get("options") or {}))
            elif path.endswith("/try"):
                self.send_json(vt.try_voice(v))
            elif path.endswith("/activate"):
                self.send_json(vt.activate(v))
            else:
                self.send_json({"error": "inconnu"}, 404)
        elif path == "/api/background/ack":
            import naimtools as _nt
            _nt.background_ack(self.read_json().get("id", ""))
            self.send_json({"ok": True})
        elif path == "/api/compact":
            body = self.read_json()
            try:
                self.send_json({"summary": compact_conversation(body)})
            except Exception as e:  # the engine is busy or stopped: the conversation is simply sent whole
                self.send_json({"error": str(e)[:300]})
        elif path == "/api/interject":
            body = self.read_json()
            with _lock:
                agent = _agents.get(body.get("run_id"))
            text = str(body.get("text") or "").strip()[:4000]
            if agent and text:
                agent.interject(text)
            if text and STOP_WORDS_RE.search(text):  # « stop » typed: the reply stops now, in Chat as in Agent
                with _lock:
                    flag = _runs.get(body.get("run_id"))
                if flag:
                    flag.set()
            self.send_json({"ok": bool(agent and text)})
        elif path == "/api/changes/revert":
            body = self.read_json()
            ok = ext.revert_checkpoint_file(body.get("run_id", ""), body.get("path", ""))
            self.send_json({"ok": ok})
        elif path == "/api/answer":
            body = self.read_json()
            with _lock:
                p = _pending.get(body.get("id"))
            if p:
                p["answer"] = str(body.get("answer") or "")[:2000]
                p["event"].set()
            self.send_json({"ok": bool(p)})
        elif path == "/api/approve":
            body = self.read_json()
            with _lock:
                p = _pending.get(body.get("id"))
            if p:
                p["allow"] = bool(body.get("allow"))
                p["event"].set()
            self.send_json({"ok": bool(p)})
        elif path == "/api/models/delete":
            try:
                ollama_call("/api/delete", {"model": self.read_json()["name"]}, method="DELETE").close()
                self.send_json({"ok": True})
            except (urllib.error.URLError, OSError) as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/models/unload":
            try:
                ollama_call("/api/generate", {"model": self.read_json()["name"], "keep_alive": 0}).close()
                self.send_json({"ok": True})
            except (urllib.error.URLError, OSError) as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/models/pull":
            name = self.read_json().get("name", "").strip()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            try:
                with ollama_call("/api/pull", {"model": name, "stream": True}, timeout=3600) as r:
                    for line in r:
                        if line.strip():
                            self.wfile.write(line if line.endswith(b"\n") else line + b"\n")
                            self.wfile.flush()
            except (urllib.error.URLError, OSError) as e:
                try:
                    self.event({"error": str(e)})
                except OSError:
                    pass
        elif path == "/api/processes/start":
            b = self.read_json()
            cwd = Path(b.get("cwd") or Path.home()).expanduser()
            if not cwd.is_dir():
                self.send_json({"error": f"dossier introuvable : {cwd}"}, 400)
                return
            p = PROCESSES.start(b["command"], cwd.resolve(), b.get("name", ""))
            self.send_json(p.info())
        elif path.startswith("/api/processes/") and path.endswith(("/stop", "/remove")):
            pid_id, action = path.split("/")[-2:]
            ok = PROCESSES.stop(pid_id) if action == "stop" else PROCESSES.remove(pid_id)
            self.send_json({"ok": ok})
        elif path == "/api/terminal":
            self.run_terminal(self.read_json())
        elif path == "/api/notify":
            b = self.read_json()
            cu.notify(b.get("title", "Naim"), b.get("text", ""), target=b.get("target") or None)
            self.send_json({"ok": True})
        elif path == "/api/learning/rate-chat":
            b = self.read_json()
            self.send_json({"ok": learning.rate_chat(b.get("id", ""), b.get("messages"), b.get("rating"))})
        elif path == "/api/learning/rate":
            b = self.read_json()
            ok = learning.rate(b.get("run_id", ""), b.get("rating"))
            s = _settings()
            if ok and s.get("share_feedback") and s.get("share_auto") and b.get("rating") in (1, -1):
                feedback_share.send_in_background(s.get("share_url"))
            self.send_json({"ok": ok})
        elif path == "/api/share/preview":
            b = self.read_json()
            items = feedback_share.pending()
            t = next((x for x in items if x["id"] == b.get("run_id")), items[0] if items else None)
            self.send_json({"payload": feedback_share.payload(t) if t else None, "pending": len(items)})
        elif path == "/api/share/send":
            s = _settings()
            if not s.get("share_feedback"):
                self.send_json({"error": "le partage est désactivé"}, 400)
            else:
                self.send_json(feedback_share.send_pending(s.get("share_url")))
        elif path == "/api/share/delete":
            try:
                self.send_json(feedback_share.delete_all(_settings().get("share_url")))
            except Exception as e:
                self.send_json({"error": f"serveur de collecte injoignable ({e})"}, 502)
        elif path == "/api/learning/clear":
            self.send_json({"ok": True, "removed": learning.clear_all(bool(self.read_json().get("keep_rated")))})
        elif path == "/api/learning/delete":
            self.send_json({"ok": learning.delete(self.read_json().get("run_id", ""))})
        elif path == "/api/learning/export":
            try:
                self.send_json(learning.export())
            except ValueError as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/learning/reveal":
            learning.BASE.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["open", str(learning.BASE)])
            self.send_json({"ok": True})
        elif path == "/api/file/write":
            # « Appliquer au projet » from a code block: write the file, keep the previous version as a backup
            b = self.read_json()
            try:
                base, p = project_path(b.get("root", ""), b.get("path", ""))
                if p == base or p.is_dir():
                    raise ValueError("chemin de fichier invalide")
                existed = p.exists()
                backup = None
                if existed:
                    bdir = base / ".naim" / "sauvegardes"
                    bdir.mkdir(parents=True, exist_ok=True)
                    backup = bdir / f"{time.strftime('%Y%m%d-%H%M%S')}_{p.name}"
                    backup.write_bytes(p.read_bytes())
                p.parent.mkdir(parents=True, exist_ok=True)
                content = str(b.get("content", ""))
                p.write_text(content if content.endswith("\n") else content + "\n")
                self.send_json({"ok": True, "existed": existed, "lines": content.count("\n") + 1,
                                "backup": str(backup.relative_to(base)) if backup else None})
            except (ValueError, OSError) as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/model/download":
            self.send_json(model_download.start())
        elif path == "/api/memory/op":
            b = self.read_json()
            op = b.get("op")
            if op == "add":
                f = memory.add(b.get("text", ""), b.get("cat", "autre"), "ajout manuel")
                self.send_json({"ok": bool(f), "duplicate": not f})
            elif op == "update":
                memory.update(b.get("id"), **{k: b[k] for k in ("text", "cat", "pinned", "active") if k in b})
                self.send_json({"ok": True})
            elif op == "delete":
                memory.delete(b.get("id"))
                self.send_json({"ok": True})
            elif op == "clear":
                memory.delete(all_=True, keep_pinned=bool(b.get("keep_pinned")))
                self.send_json({"ok": True})
            elif op == "tidy":  # memory hygiene: preview, then apply the ids the user confirmed
                if b.get("apply"):
                    memory.tidy_apply(b["apply"])
                    self.send_json({"ok": True})
                else:
                    self.send_json({"remove": memory.tidy_preview()})
            elif op == "extract_all":
                chat = self._memory_chat(b)
                threading.Thread(target=memory.extract_from_conversations, args=(CONVS, chat), daemon=True).start()
                self.send_json({"ok": True, "progress": memory.PROGRESS})
            else:
                self.send_json({"error": "opération inconnue"}, 400)
        elif path == "/api/clipboard":
            text = str(self.read_json().get("text", ""))
            r = subprocess.run(["pbcopy"], input=text.encode("utf-8"), timeout=10, env={**os.environ, "LANG": "en_US.UTF-8"})
            self.send_json({"ok": r.returncode == 0})
        elif path == "/api/extract":
            b = self.read_json()
            try:
                data = base64.b64decode(b.get("data") or "")
                if len(data) > 40 * 1024 * 1024:
                    raise docs.DocError("fichier trop gros (max 40 Mo)")
                self.send_json(docs.extract_bytes(b.get("name", "document"), data, b.get("project") or None))
            except docs.DocError as e:
                self.send_json({"error": str(e)}, 400)
            except Exception as e:
                self.send_json({"error": f"{type(e).__name__}: {e}"}, 500)
        elif path in ("/api/skills/browse", "/api/skills/install"):
            b = self.read_json()
            try:
                if path.endswith("browse"):
                    self.send_json({"skills": skill_hub.browse(b.get("url", ""))})
                else:
                    self.send_json({"installed": skill_hub.install(b.get("url", ""), b.get("names") or None,
                                                                   b.get("project"), b.get("scope", "utilisateur"))})
            except skill_hub.SkillError as e:
                self.send_json({"error": str(e)}, 400)
            except Exception as e:
                self.send_json({"error": f"{type(e).__name__}: {e}"}, 500)
        elif path == "/api/skills/popular":
            self.send_json({"sources": skill_hub.POPULAR})
        elif path == "/api/computer/permissions":
            try:
                cu.permissions(request=True)
            except Exception:
                pass
            for pane in ("Privacy_ScreenCapture", "Privacy_Accessibility"):
                subprocess.Popen(["open", f"x-apple.systempreferences:com.apple.preference.security?{pane}"])
            self.send_json(cu.status())
        elif path in ("/api/llama/restart", "/api/llama/stop"):
            b = self.read_json()
            for k, key in (("gpu_layers", "llama_gpu_layers"), ("threads", "llama_threads"), ("batch", "llama_batch"),
                           ("kv_type", "llama_kv_type"), ("checkpoints", "llama_checkpoints"), ("parallel", "llama_parallel")):
                if b.get(key) not in (None, ""):
                    llamacpp.CONFIG[k] = b[key]
            llamacpp.SERVER.stop()
            err = None
            if path.endswith("restart"):
                try:
                    llamacpp.SERVER.ensure(int(b.get("num_ctx") or 32768))
                except RuntimeError as e:
                    err = str(e)
            self.send_json({**llamacpp.SERVER.status(), "error": err})
        elif path == "/api/schedules":
            self.send_json(scheduler.upsert(self.read_json()))
        elif path == "/api/schedules/answer":
            b = self.read_json()
            self.send_json({"ok": scheduler.answer(b.get("id", ""), b.get("allow"))})
        elif path.startswith("/api/schedules/") and path.endswith("/run"):
            tid = path.split("/")[-2]
            task = next((t for t in scheduler.load() if t["id"] == tid), None)
            if not task:
                self.send_json({"error": "tâche inconnue"}, 404)
                return
            threading.Thread(target=scheduler.run_task, args=(task, _settings(), ollama_chat, Agent, CHAT_PROMPT), daemon=True).start()
            self.send_json({"ok": True})
        elif path == "/api/mcp/install":
            b = self.read_json()
            name = b.get("name")
            if name not in mcp_catalog.CATALOG:
                self.send_json({"error": "serveur inconnu"}, 400)
                return
            servers = {k: v for k, v in ext.MCP.config().items()}
            servers[name] = mcp_catalog.build_config(name, b.get("project", ""), b.get("env") or {})
            ext.MCP.save_config(servers)
            srv = ext.MCP.get(name)  # start it now so errors show up immediately
            self.send_json({"servers": ext.MCP.status(), "error": srv.error if srv else None})
        elif path.startswith("/api/mcp/") and path.endswith("/restart"):
            name = path.split("/")[-2]
            srv = ext.MCP.servers.pop(name, None)
            if srv:
                srv.stop()
            ext.MCP.get(name)
            self.send_json({"servers": ext.MCP.status()})
        elif path == "/api/skills":
            b = self.read_json()
            f = ext.write_skill(b["name"], b.get("description", ""), b.get("instructions", ""), b.get("root"), b.get("scope", "utilisateur"))
            self.send_json({"path": str(f)})
        elif path.startswith("/api/checkpoints/") and path.endswith("/restore"):
            files = ext.restore_checkpoint(path.split("/")[-2])
            self.send_json({"restored": files} if files is not None else {"error": "aucun point de restauration"})
        elif path.startswith("/api/git/"):
            b = self.read_json()
            root, action = b.get("root", ""), path.rsplit("/", 1)[1]
            try:
                if action == "init":
                    code, out = ext.git(root, "init")
                elif action == "commit":
                    files = b.get("files") or ["-A"]
                    code, out = ext.git(root, "add", *(["-A"] if files == ["-A"] else ["--", *files]))
                    if code == 0:
                        code, out = ext.git(root, "commit", "-m", b.get("message") or "Mise à jour")
                elif action == "branch":
                    code, out = ext.git(root, "checkout", *(["-b"] if b.get("create") else []), b["name"])
                elif action in ("show", "restore") and not re.fullmatch(r"[0-9a-f]{7,40}", str(b.get("hash", ""))):
                    code, out = 1, "version invalide"
                elif action == "show":  # what this version changed
                    code, out = ext.git(root, "show", "--stat", "--patch", "--format=%h %s%n%an · %ar%n", b["hash"])
                elif action == "restore":
                    # back to that version WITHOUT erasing history: a new commit undoes everything that came after it
                    code, dirty = ext.git(root, "status", "--porcelain")
                    head = ext.git(root, "rev-parse", "--short", "HEAD")[1].strip()
                    if dirty.strip():
                        code, out = 1, "Des modifications ne sont pas encore commitées : fais d'abord un commit (ou annule-les), puis réessaie."
                    elif head.startswith(b["hash"][:7]):
                        code, out = 1, "C'est déjà la version actuelle."
                    else:
                        subject = ext.git(root, "log", "-1", "--format=%s", b["hash"])[1].strip()
                        code, out = ext.git(root, "revert", "--no-commit", f"{b['hash']}..HEAD")
                        if code == 0:
                            code, out = ext.git(root, "commit", "-m", f"Retour à la version {b['hash'][:7]} ({subject})")
                        else:
                            ext.git(root, "revert", "--abort")
                            out = "Impossible de revenir automatiquement à cette version :\n" + out
                else:
                    code, out = 1, "action inconnue"
            except (OSError, KeyError, subprocess.SubprocessError) as e:
                code, out = 1, str(e)
            self.send_json({"ok": code == 0, "output": out})
        elif path == "/api/hooks-file":
            # the user's hooks file (or the project's), created with a commented example the first time, then opened
            b = self.read_json()
            try:
                import hooks as naim_hooks
                f = naim_hooks.files(b.get("project") or ".")[0 if b.get("scope") != "project" else 1]
                if b.get("scope") == "project" and not b.get("project"):
                    raise ValueError("choisis d'abord un dossier de projet")
                if not f.exists():
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text(json.dumps({"hooks": {
                        "PreToolUse": [{"matcher": "run_command", "hooks": [{"type": "command", "command":
                            "python3 -c \"import json,sys; c=json.load(sys.stdin)['tool_input'].get('command',''); sys.exit(2 if 'rm -rf' in c else 0)\" || { echo 'rm -rf est interdit ici' >&2; exit 2; }"}]}],
                        "PostToolUse": [], "UserPromptSubmit": [], "Stop": []}}, ensure_ascii=False, indent=2) + "\n")
                subprocess.Popen(["open", "-t", str(f)])
                self.send_json({"ok": True, "path": str(f)})
            except (OSError, ValueError) as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/open-url":
            url = self.read_json().get("url", "")
            ok = bool(re.match(r"^https?://", url))
            if ok:
                subprocess.Popen(["open", url])
            self.send_json({"ok": ok})
        elif path == "/api/backup":
            self.send_json(backup_make())
        elif path == "/api/tts":  # Naim's voice: one sentence → WAV
            import naim_voice
            try:
                b = self.read_json()
                wav = naim_voice.speak(b.get("text", ""), b.get("engine") or "rapide")
            except Exception as e:  # noqa: BLE001
                self.send_json({"error": str(e)}, 503)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(wav)))
                self.end_headers()
                self.wfile.write(wav)
        elif path == "/api/backup/restore":
            if _agents or _runs:
                self.send_json({"error": "Naim travaille : réessaie quand il a fini."})
            else:
                self.send_json(backup_restore(self.read_json().get("path", "")))
        elif path == "/api/storage/clear":
            b = self.read_json()
            if _agents or (b.get("what") == "restauration" and _runs):
                self.send_json({"error": "Naim travaille : réessaie quand il a fini."})
            else:
                self.send_json({"ok": True, "removed": storage_clear(b.get("what", ""), bool(b.get("keep_pinned", True)))})
        elif path == "/api/save-copy":
            # « Télécharger » on a file card: a copy in ~/Downloads, shown in the Finder
            b = self.read_json()
            try:
                _, src = project_path(b.get("root", ""), b.get("path", ""))
                dl = Path.home() / "Downloads"
                dst, n = dl / src.name, 2
                while dst.exists():
                    dst, n = dl / f"{src.stem} ({n}){src.suffix}", n + 1
                shutil.copy2(src, dst)
                subprocess.Popen(["open", "-R", str(dst)])
                self.send_json({"ok": True, "path": str(dst)})
            except (ValueError, OSError) as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/save-download":
            # a file made in the page (schema.svg, naim.py…): the Mac window cannot download a blob link (it would
            # replace Naim with the file), so the page sends it here and it lands in ~/Downloads, shown in the Finder
            b = self.read_json()
            try:
                name = Path(str(b.get("name") or "")).name.lstrip(".")
                if not name:
                    raise ValueError("nom de fichier manquant")
                data = base64.b64decode(b["base64"]) if b.get("base64") else str(b.get("text") or "").encode()
                dl = Path.home() / "Downloads"
                p = Path(name)
                dst, n = dl / name, 2
                while dst.exists():
                    dst, n = dl / f"{p.stem} ({n}){p.suffix}", n + 1
                dst.write_bytes(data)
                subprocess.Popen(["open", "-R", str(dst)])
                self.send_json({"ok": True, "path": str(dst)})
            except (ValueError, OSError, KeyError) as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/reveal":
            b = self.read_json()
            target = Path(b.get("path", "")).expanduser()
            if b.get("root") and not target.is_absolute():
                target = Path(b["root"]).expanduser() / target
            if target.exists():
                subprocess.Popen(["open", "-R", str(target)] if b.get("select") else ["open", str(target)])
            self.send_json({"ok": target.exists()})
        elif path == "/api/stop":
            with _lock:
                flag = _runs.get(self.read_json().get("run_id"))
            if flag:
                flag.set()
            self.send_json({"ok": bool(flag)})
        elif path == "/api/chat":
            body = self.read_json()
            run_id = body.get("run_id") or uuid.uuid4().hex
            stop = threading.Event()
            with _lock:
                _runs[run_id] = stop
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                body = with_vision(self, body)
                if body.get("mode") == "agent":
                    self.run_agent(body, stop)
                else:
                    self.run_chat(body, stop)
                self._auto_memory(body)
            except (BrokenPipeError, ConnectionResetError):
                stop.set()
            except Exception as e:  # report to the UI instead of dropping the stream
                try:
                    self.event({"type": "error", "text": str(e)})
                    self.event({"type": "done"})
                except OSError:
                    pass
            finally:
                with _lock:
                    _runs.pop(run_id, None)
        else:
            self.send_error(404)

    # ------------------------------------------------------------ memory
    def _memory_chat(self, body):
        """Short, deterministic model call used to extract facts for the long-term memory."""
        b = {**body, "mode": "chat"}
        options, _ = model_options(b)
        options = {**options, "temperature": 0.1, "num_predict": 500, "slot": llamacpp.bg_slot()}  # its own slot: Chat and Agent keep their cache
        model = b.get("model") or (b.get("settings") or {}).get("model") or "naim"
        return lambda msgs: (ollama_chat(model, msgs, options=options) or {}).get("content", "")

    def _auto_memory(self, body):
        """After a conversation turn: remember what the user said that is durable (in the background)."""
        s = body.get("settings") or {}
        if s.get("enable_memory", True) is False or s.get("memory_auto", True) is False:
            return
        msgs = list(body.get("history") or []) + [{"role": "user", "content": body.get("message", "")}]
        if not memory.worth_extracting(msgs[-6:]):
            return
        chat = self._memory_chat(body)
        job = lambda: memory.extract_from_messages(msgs[-6:], chat, "conversation")  # noqa: E731
        if body.get("voice"):  # a spoken conversation: the next answer comes seconds later, it must not share the model
            _when_idle(job)
        else:
            threading.Thread(target=job, daemon=True).start()

    # ------------------------------------------------------------ modes
    def run_chat(self, body, stop):
        options, extra = model_options(body)
        if options.get("backend") == "llamacpp":  # the Chat's own slot: its instructions and the conversation stay read
            options = {**options, "slot": llamacpp.SLOT_CHAT}
        s = body.get("settings") or {}
        mem = ext.memory_prompt() if s.get("enable_memory", True) is not False else ""
        system = CHAT_PROMPT + "\n\n" + today_line() + (f"\n\n{mem}" if mem else "") + (f"\n\nUser instructions:\n{extra}" if extra else "")
        choice = chosen_option(body["message"], body.get("history"))
        text = (f"{body['message']} — je choisis cette option que tu as proposée : « {choice} ». Fais-le maintenant."
                if choice else with_first_request(body["message"], body.get("history")))
        spoken = ("\n\n[Conversation à voix haute : ta réponse sera lue par ta voix. Si je te demande de FAIRE quelque chose "
                  "(fichier, impression, réglage, recherche…), fais-le d'abord avec tes outils, sans l'annoncer, puis dis en une "
                  "ou deux phrases ce que tu as fait. Sinon, parle naturellement, en 2 à 5 phrases courtes, sans liste, sans "
                  "titre ni symbole Markdown, sans emoji. Si du code est nécessaire, mets-le dans un bloc de code (il s'affiche "
                  "à l'écran, il n'est pas lu) et dis en une phrase ce qu'il fait.]") if body.get("voice") else ""
        user = {"role": "user", "content": text + spoken + now_note(), **({"images": body["images"]} if body.get("images") else {})}
        messages = [{"role": "system", "content": system}] + body.get("history", []) + [user]
        wants_schedule = bool(SCHEDULE_NEED_RE.search(body["message"] or ""))
        files = wants_file(body["message"], body.get("history")) or bool(FILE_OFFER_RE.search(choice))
        import mailer
        last_answer = next((m.get("content") or "" for m in reversed(body.get("history") or []) if m.get("role") == "assistant"), "")
        address_given = bool(mailer.EMAIL_RE.search(body["message"] or "")) and bool(re.search(r"adresse|e-?mail", last_answer, re.I))
        email = s.get("enable_email", True) is not False and (bool(EMAIL_NEED_RE.search(f"{body['message']} {choice}")) or address_given)
        if email and files:
            import chatfiles
            named = re.findall(r"[\w() .-]+\.\w{2,5}\b", body["message"])
            if any((chatfiles.OUT / n.strip()).is_file() for n in named):
                files = False  # the file exists (✉ Envoyer on its card): only send it
        web = s.get("enable_web", True) is not False and bool(WEB_NEED_RE.search(body["message"] or ""))
        if options.get("backend") == "llamacpp" and s.get("chat_tools", True) is not False and not body.get("images"):
            # Chat with every tool, like an assistant that talks AND acts: answers stream as usual; when a tool is
            # needed, it is used in the same reply, then the answer goes on
            return self.chat_agentic(body, messages, options, stop, files=files,
                                     act=email and bool(re.search(r"\b(e-?mails?|mails?|courriels?)\b", body["message"] or "", re.I)))
        if wants_schedule or files or web or email:
            if self.chat_with_web(body, messages, options, stop, schedule=wants_schedule, files=files,
                                  web=web or not (files or email), email=email, send_now=address_given):
                return
        think = bool(body.get("think")) and not trivial_message(body["message"])
        for chunk in ollama_chat(body.get("model", "naim"), messages, think=think,
                                 stream=True, options=options):
            if stop.is_set():
                self.event({"type": "stopped"})
                break
            msg = chunk.get("message", {})
            if msg.get("thinking"):
                self.event({"type": "thinking_token", "text": msg["thinking"]})
            if msg.get("content"):
                self.event({"type": "token", "text": msg["content"]})
            if chunk.get("done") and chunk.get("eval_duration"):
                self.event({"type": "stats", "tokens": chunk.get("eval_count", 0),
                            "tps": chunk["eval_count"] / (chunk["eval_duration"] / 1e9),
                            "prompt": chunk.get("prompt_eval_count", 0), "reason": chunk.get("done_reason")})
        self.event({"type": "done"})

    FOLDER_TOOL = {"type": "function", "function": {
        "name": "aller_dans_dossier",
        "description": ("Work in another folder of this Mac: the one the user names (« nous sommes dans INLI », « le dossier "
                        "Factures du Bureau ») or a path. It is searched in Desktop, Documents, Downloads and the home "
                        "folder; then your file tools (list_files, read_file, find_files…) work there. Call it first when "
                        "the user talks about a folder you are not in."),
        "parameters": {"type": "object", "properties": {"dossier": {"type": "string", "description": "name or path of the folder"}},
                       "required": ["dossier"]}}}

    @staticmethod
    def find_folders(q):
        """Folders matching a path or a name (accents and case ignored) in the usual places, the fullest first."""
        import unicodedata
        q = (q or "").strip().rstrip("/")
        p = Path(q).expanduser()
        if p.is_absolute() and p.is_dir():
            return [p]
        norm = lambda t: "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn").strip()
        want, hits = norm(Path(q).name), []
        if "/" in q and (Path.home() / q).is_dir():
            hits.append(Path.home() / q)
        for base in (Path.home() / "Desktop", Path.home() / "Documents", Path.home() / "Downloads", Path.home()):
            for dirpath, dirnames, _ in os.walk(base):
                depth = len(Path(dirpath).relative_to(base).parts)
                # Library, Photos, Music, Movies: never a work folder, and reading them can stop on a macOS permission prompt
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS
                               and not (base == Path.home() and depth == 0 and d in ("Library", "Pictures", "Music", "Movies", "Applications"))
                               and not d.endswith((".photoslibrary", ".musiclibrary", ".app"))] if depth < 3 else []
                hits += [Path(dirpath) / d for d in dirnames if norm(d) == want]
        uniq = {}
        for h in hits:  # same folder reached twice (case-insensitive disk, home + Desktop walk)
            uniq.setdefault(str(h.resolve()).lower(), h.resolve())
        count = lambda d: sum(1 for x in d.rglob("*") if x.is_file() and not x.name.startswith("."))
        return sorted(uniq.values(), key=count, reverse=True)

    FOLDER_RE = re.compile(r"\b(?:r[ée]pertoire|dossier|folder|directory)\s+(?:de\s+|du\s+|nomm[ée]\s+|appel[ée]\s+)?"
                           r"[«\"'`]?\s*([~/]?[\w][\w .\-/À-ÿ]{0,80}?)\s*[»\"'`]?(?=[\s.,;:!?)]|$)", re.I)

    def folder_from_text(self, texts):
        """« nous sommes dans le répertoire INLI » → that folder (the most recent message that names one)."""
        for t in texts:
            for m in self.FOLDER_RE.finditer(t or ""):
                name = m.group(1).strip()
                if len(name) < 2 or name.lower() in ("actuel", "courant", "du projet", "ci-dessus", "suivant"):
                    continue
                found = self.find_folders(name)
                if found:
                    return found[0], found[1:4]
        return None, []

    CHAT_TOOLS_NOTE = (
        "\n\nIn this conversation you can also ACT, with tools: read and write files, run commands, search the web, "
        "create documents (creer_fichier: PDF, Word, Excel, ZIP…), send emails, schedule tasks, and more (use_tools loads "
        "a specialised group, use_mcp an extra server). Answer directly when you can; use a tool only when the request "
        "needs an action, a file or fresh information, then give the answer. Never write code meant to create a file "
        "yourself: call the tool. Files you create go in {folder}.\nTo teach, explain or show code, write it IN your reply: "
        "short explanations and complete examples in Markdown code blocks, step by step, then one question to go on. "
        "Do not create a file for that unless the user asks for a file or a document.\nA diagram or schema asked in the "
        "conversation: draw it IN your reply as a ```mermaid code block (the app shows it as a real diagram, with SVG/PNG "
        "export). Keep it readable: 8-20 boxes, short French labels, no special characters inside labels. When it shows "
        "facts (models, companies, numbers, dates), check them first with web_search: never invent a figure.")

    def chat_agentic(self, body, messages, options, stop, files=False, act=False):
        """Chat mode with all of Naim's tools, streamed: text appears as it is written, tools run in the same reply."""
        def repeating(text):
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            return len(lines) >= 4 and len(set(lines[-3:])) == 1 and len(lines[-1]) > 2
        import chatfiles
        import mailer
        s = body.get("settings") or {}

        def approver(action, detail):
            aid = uuid.uuid4().hex
            entry = {"event": threading.Event(), "allow": False}
            with _lock:
                _pending[aid] = entry
            self.event({"type": "approval", "id": aid, "action": action, "detail": detail[:40000]})
            deadline = time.time() + APPROVAL_TIMEOUT
            while not entry["event"].wait(0.3):
                if stop.is_set() or time.time() > deadline:
                    break
            with _lock:
                _pending.pop(aid, None)
            self.event({"type": "approval_result", "id": aid, "allow": entry["allow"]})
            return entry["allow"]

        folder = Path(s.get("project") or body.get("project") or chatfiles.OUT).expanduser()
        if not folder.is_dir():
            folder = chatfiles.OUT
        folder.mkdir(parents=True, exist_ok=True)
        named, others = self.folder_from_text([body["message"]] + [str(m.get("content") or "") for m in
                                                                   reversed((body.get("history") or [])[-6:]) if m.get("role") == "user"])
        if named and named.resolve() != folder.resolve():  # the user names the folder to work in: go there first
            folder = named
            self.event({"type": "project", "path": str(named)})
        helper = Agent(str(folder), body.get("model", "naim"), auto_yes=bool(body.get("auto_yes")), emit=self.event,
                       approver=approver, options=options, **agent_settings(body))
        run_id = body.get("run_id") or helper.run_id
        helper.conv_id = body.get("conv_id")  # its background jobs report back to this conversation
        helper._bg_intent = bool(Agent.BG_INTENT_RE.search(body.get("message") or ""))
        with _lock:
            _agents[run_id] = helper  # « écris pour guider Naim » reaches this reply too
        helper._preload_tool_groups(" ".join([body["message"]] + [str(m.get("content") or "") for m in (body.get("history") or [])[-2:]
                                                                   if m.get("role") == "user"]))
        own = mailer.own_addresses() if helper.features.get("email") else []
        allowed = mailer.addresses(" ".join(agent_settings(body)["email_allowed"]))
        me = next((a for a in own if a in allowed), None) or (own[0] if own else None)
        note = self.CHAT_TOOLS_NOTE.format(folder=folder) + (
            f"\nYou are working in the folder {folder} (relative paths are inside it). Before asking the user where a "
            "file is, look for it yourself (list_files, find_files)."
            + f" Files you create (creer_fichier) go in this folder; older ones may be in {chatfiles.OUT}. Attach them with their full path."
            + (f"\nFiles in this folder:\n{helper.list_files('.')[:2500]}" if named else "")
            + (f" Other folders with the same name: {', '.join(map(str, others))}." if named and others else "")) + (f"\nThe user's own email address (« moi »): {me}" if me else "")
        if getattr(helper, "_tool_groups", None):
            note += ("\nSpecialised tool groups (use_tools): " + "; ".join(f"{g} ({TOOL_GROUPS[g][1]})" for g in helper._tool_groups))
        messages = [dict(messages[0], content=messages[0]["content"] + note)] + messages[1:]
        think = bool(body.get("think")) and not trivial_message(body["message"])
        try:
            self._chat_steps(body, messages, options, stop, files or act, helper, think, repeating, chatfiles, run_id)
        finally:
            with _lock:
                _agents.pop(run_id, None)

    def _chat_steps(self, body, messages, options, stop, files, helper, think, repeating, chatfiles, run_id):
        made, mail_error, sent, total_tokens, used_tools, shots, content = [], None, False, 0, False, [], ""
        prompt_tokens = 0
        started = time.time()  # files made from now on are this reply's deliverables
        nudges = 1 if body.get("_relaunched") else 0
        plain = trivial_message(body["message"]) and not body.get("_relaunched")  # « salut », « merci » : just an answer
        seen_calls, stuck, last_redirect, mac_tried = {}, False, 0.0, False
        heard = []  # what the user said while Naim worked
        asked = " ".join([body["message"]] + [str(m.get("content") or "") for m in (body.get("history") or [])[-4:] if m.get("role") == "user"])
        hk = helper._user_hooks()
        if hk.get("UserPromptSubmit") and not body.get("_warm") and not body.get("_relaunched"):
            import hooks as naim_hooks
            blocked, msg, ctx = naim_hooks.run(hk, "UserPromptSubmit", {"prompt": body["message"], "session_id": run_id}, helper.root)
            if blocked or ctx or msg:
                self.event({"type": "hook", "event": "UserPromptSubmit", "blocked": blocked, "text": msg or ctx})
            if blocked:
                self.event({"type": "token", "text": f"Message bloqué par un de tes hooks : {msg}"})
                self.event({"type": "done"})
                return
            if ctx:
                messages[-1] = dict(messages[-1], content=str(messages[-1].get("content") or "") + f"\n\n[Contexte ajouté par un hook de l'utilisateur]\n{ctx}")
        file_work = bool(FILE_WORK_RE.search(asked)) and not body.get("_question")  # a pure question: nothing is changed
        named = re.findall(r"[\w./-]+\.[a-z0-9]{1,6}\b", body["message"] or "", re.I) if body.get("_question") else []
        # « imprime mon CV PDF », « envoie le document »: acting on a file that exists is not making one, no skill
        acting_only = bool(MAC_ACTION_RE.search(body["message"] or "")) and not MAKE_RE.search(body["message"] or "")
        if not plain and not body.get("_question") and helper.features.get("skills", True) and helper.auto_skill:
            # the same skills as the Agent (a house plan, a pro email…): their method and tools, not a drawing made up by hand
            recent = " ".join([body["message"]] + [str(m.get("content") or "") for m in (body.get("history") or [])[-2:]
                                                    if m.get("role") == "user"])
            sk = (ext.match_skill(body["message"], helper.root, helper.disabled_skills)
                  or (ext.match_skill(recent, helper.root, helper.disabled_skills) if file_work else None))
            if acting_only and sk and sk["name"] != "mac":
                sk = None  # acting on an existing file (« imprime mon CV ») needs no skill — except the Mac recipes
            if sk and sk["name"] not in ("debug", "application-web", "api-rest", "projet-existant") and (file_work or sk["name"] not in ("schemas",)):
                file_work = True  # « un plan de maison T4 » makes files; « mes rendez-vous ? » runs commands on the Mac
                _, skill_body = ext.parse_skill(Path(sk["path"]))
                self.event({"type": "skill", "name": sk["name"]})
                messages[-1] = dict(messages[-1], content=str(messages[-1].get("content") or "") +
                                    f"\n\n[Skill « {sk['name']} » chargé automatiquement : suis cette méthode]\n{skill_body.strip()}")
        if not file_work and not files:
            messages[-1] = dict(messages[-1], content=str(messages[-1].get("content") or "") + (
                "\n\n(Réponds ici, dans la conversation : explications courtes et exemples de code complets en blocs "
                "Markdown. Ne crée ni ne modifie aucun fichier.)") + (
                f" (Le fichier {', '.join(named[:3])} est dans le dossier du projet : lis-le d'abord avec read_file, "
                "puis explique ce que tu y vois, sans le modifier.)" if named else ""))
        if MAC_ACTION_RE.search(body["message"] or ""):  # « imprime-le », « ouvre Safari »: it acts, it does not explain
            messages[-1] = dict(messages[-1], content=str(messages[-1].get("content") or "") + (
                "\n\n(Fais-le toi-même sur ce Mac avec tes outils, ne m'explique pas comment faire. run_command agit sur le "
                "Mac : imprimer = `lpstat -p -d` pour voir les imprimantes (« inactive » veut dire prête, au repos) puis `lp -d <imprimante> <fichier>` (un fichier à moi qui n'est pas dans le dossier : find_files le cherche sur tout le Mac ; s'il y en a plusieurs ou si le nom ne correspond pas, demande-moi lequel et attends ma réponse, n'imprime jamais un autre fichier) ; ouvrir = "
                "`open` ; réglages = `osascript` ; appeler = `open \"tel:+33…\"` (l'appel passe par l'iPhone) ; SMS ou iMessage = `osascript -e 'tell application \"Messages\" to send \"texte\" to participant \"+33…\"'` (trouve le numéro avec chercher_contact). Ce qui est sensible m'est demandé avant, c'est normal. Ne dis jamais que tu ne "
                "peux pas avant d'avoir essayé ; si ça échoue, dis exactement pourquoi.)"))
        limit = max(8, min(int((body.get("settings") or {}).get("max_steps") or 30), 60))
        for step in range(limit):
            if stop.is_set():
                self.event({"type": "stopped"})
                break
            last = step == limit - 1
            if last and used_tools:  # out of steps: the last one is the answer, with what was found (no more tools)
                messages.append({"role": "user", "content": "Tu as utilisé toutes tes étapes : arrête de chercher. Réponds "
                                 "maintenant à ma demande avec tout ce que tu as déjà trouvé (organisé, complet), et dis "
                                 "ce qui manque encore."})
                self.event({"type": "status", "text": "Naim rédige la réponse avec ce qu'il a trouvé…"})
            elif step == limit * 2 // 3 and used_tools:
                messages.append({"role": "user", "content": f"(Il te reste {limit - step} étapes : termine ce qui est "
                                 "essentiel, puis réponds avec ce que tu as trouvé.)"})
            with helper._inbox_lock:  # what the user typed while Naim was working: taken into account now
                notes, helper._inbox = helper._inbox, []
            if any(STOP_WORDS_RE.search(n) for n in notes):
                stop.set()  # « Stop » typed while Naim works: it stops, like the stop button
                self.event({"type": "stopped"})
                break
            heard += notes
            if notes:
                nudges = 0  # a new instruction (« passons à autre chose, crée… »): it gets its own reminders to act
                messages.append({"role": "user", "content": "(Message de l'utilisateur pendant ton travail — prends-le en "
                                 "compte maintenant, sans recommencer ce qui est déjà fait) : " + "\n".join(notes)})
                self.event({"type": "interjection_read", "count": len(notes)})
            last = last or stuck
            tools = None if last and used_tools else helper.tools + [chatfiles.FILE_TOOL, self.FOLDER_TOOL]

            # « salut », « merci » (plain): no tool_choice "none" — it removes the tools from what the engine reads, so the
            # next real message would find nothing in common and re-read everything (~1 min); a tool call is refused instead
            opts = dict(options, tool_choice="required") if (files and step == 0) else options
            content, calls, shown = "", [], 0
            try:
                stream = ollama_chat(body.get("model", "naim"), messages, tools=tools, think=think, stream=True, options=opts)
            except llamacpp.ContextFull:
                # the conversation outgrew the engine's room: the oldest exchanges go (the instructions, the request
                # and the last steps stay), and the same step is asked again
                self.event({"type": "status", "text": "Naim allège la conversation pour continuer…"})
                head = [m for m in messages[:1]]
                tail = messages[-6:]
                while tail and tail[0].get("role") == "tool":
                    tail = tail[1:]
                for m in tail:
                    if m.get("role") == "tool" and len(str(m.get("content") or "")) > 4000:
                        m["content"] = str(m["content"])[:4000] + "\n… (raccourci)"
                messages[:] = head + tail
                stream = ollama_chat(body.get("model", "naim"), messages, tools=tools, think=think, stream=True, options=opts)
            thought = redirected = False
            for chunk in stream:
                if stop.is_set():
                    stream.close()  # hang up: llama.cpp stops writing at once
                    break
                if helper._inbox and content.strip() and time.time() - last_redirect > 20:  # the user speaks while
                    stream.close()  # Naim answers: it stops here and goes on with what was just said (at most every 20 s)
                    redirected, last_redirect = True, time.time()
                    break
                if repeating(content):  # the model loops on the same line (it happens with images): cut at once
                    stream.close()
                    break
                if chunk.get("writing"):  # a whole file written in a tool call: shown while it is written
                    self.event({"type": "status", "text": writing_text(chunk["writing"])})
                msg = chunk.get("message", {})
                if msg.get("thinking"):
                    thought = True
                    self.event({"type": "thinking_token", "text": msg["thinking"]})
                if msg.get("content"):
                    content += msg["content"]
                    visible = shown_part(content)
                    if len(visible) > shown:
                        self.event({"type": "token", "text": visible[shown:]})
                        shown = len(visible)
                if msg.get("tool_calls"):
                    calls = msg["tool_calls"]
                if chunk.get("done") and chunk.get("eval_duration"):
                    total_tokens += chunk.get("eval_count", 0)
                    prompt_tokens += chunk.get("prompt_eval_count", 0)
                    self.event({"type": "stats", "tokens": total_tokens, "tps": chunk["eval_count"] / (chunk["eval_duration"] / 1e9),
                                "prompt": prompt_tokens, "reason": chunk.get("done_reason")})
            if not redirected and not calls and helper._inbox and not stop.is_set():
                redirected = True  # spoken just as the answer ended: answered too, in the same reply
            if redirected:
                said = shown_part(content.split("<tool_call")[0])
                if said.strip():
                    messages.append({"role": "assistant", "content": said})
                    self.event({"type": "token", "text": "\n\n"})
                continue
            raw = raw_tool_calls(content)
            if not calls and raw:  # written as text: executed anyway
                calls = raw
            if think and thought and not calls and not content.strip() and not stop.is_set():
                # it stopped inside its reasoning, without answering: the same step again, without reasoning
                think = False
                self.event({"type": "status", "text": "Naim reprend (réflexion interrompue)…"})
                continue
            clean = content.split("<tool_call")[0]
            if not calls and len(clean) > shown:  # end of a plain answer: the characters held back
                self.event({"type": "token", "text": clean[shown:]})
            content = clean
            if not calls and not stop.is_set() and nudges < 2 and (
                    not content.strip() or (ANNOUNCE_RE.search(content) and len(content) < 400)):
                # « Je vais envoyer l'e-mail… » without doing it, or an empty reply: do it now
                nudges += 1
                if content.strip():
                    messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "Fais-le maintenant avec tes outils (n'annonce pas, agis), "
                                 "puis dis-moi le résultat. Si une information te manque vraiment, pose une seule question."})
                if content.strip():
                    self.event({"type": "token", "text": "\n\n"})
                continue
            asked = [w for w, rx in (("l'imprimer", r"imprim"), ("envoyer le SMS / message", r"\bsms\b|texto|imessage|message"),
                                      ("passer l'appel", r"appell?e|appeler|appel\b")) if re.search(rx, body["message"] or "", re.I)]
            said_no = NOT_NOW_RE.search(" ".join([body["message"] or ""] + heard))  # « n'imprime pas », « attends mon signal »
            if (not calls and not stop.is_set() and asked and not mac_tried and nudges < 3 and not said_no
                    and MAC_ACTION_RE.search(body["message"] or "")):
                # it was asked to act on the Mac (print, send, call) and finishes without even trying: back to work
                nudges += 1
                if content.strip():
                    messages.append({"role": "assistant", "content": content})
                    self.event({"type": "token", "text": "\n\n"})
                messages.append({"role": "user", "content": "Tu n'as pas encore fait ce que je t'ai demandé : " + ", ".join(asked)
                                 + ". Fais-le maintenant toi-même avec run_command (imprimer : lp -d <imprimante> <fichier> ; "
                                 "SMS : chercher_contact ou le numéro que je t'ai donné, puis osascript avec Messages ; appel : "
                                 "open \"tel:<numéro>\"). Ne me dis pas de le faire moi-même. Je validerai si on me le demande."})
                continue
            if stop.is_set() or not calls:
                break
            if any(c["function"]["name"] == "run_command" for c in calls):
                mac_tried = True
            messages.append({"role": "assistant", "content": content, "tool_calls": calls})
            if content.strip():
                self.event({"type": "token", "text": "\n\n"})
            for c in calls:
                name, args = c["function"]["name"], c["function"].get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                sig = name + json.dumps(args, sort_keys=True, ensure_ascii=False)[:500]
                seen_calls[sig] = seen_calls.get(sig, 0) + 1
                if seen_calls[sig] > 2:  # the same call a third time: it is going round in circles
                    stuck = True
                    messages.append({"role": "tool", "tool_name": name, "content": "refused: you already did exactly this twice."})
                    messages.append({"role": "user", "content": "Tu répètes la même action sans résultat : arrête-la. Change de "
                                     "méthode ou réponds maintenant avec ce que tu sais (pour un schéma : un bloc ```mermaid "
                                     "dans ta réponse)."})
                    continue
                if plain:  # « salut », « merci »: just an answer
                    messages.append({"role": "tool", "tool_name": name, "content": "refused: this is a simple message, "
                                     "answer it directly in one or two sentences, without any tool."})
                    continue
                if not files and not file_work and name not in ANSWER_TOOLS and not name.startswith("mcp__"):
                    # a question or a lesson: the answer goes in the conversation (the tool list stays the same so that
                    # llama.cpp keeps what it already read; only the use is refused). MCP tools always pass: they are
                    # how Naim reads and acts on external services (e.g. the user's Internet box through BOXAI)
                    messages.append({"role": "tool", "tool_name": name, "content": (
                        "refused: this is a question, not a request for files. Answer IN the conversation (explanations "
                        "and code blocks); create or change files only when the user asks for it.")})
                    continue
                self.event({"type": "tool", "name": name, "args": args})
                try:
                    if name == "aller_dans_dossier" and str(args.get("dossier") or "").strip() in ("", ".", "./"):
                        result = f"ok: you are already in {helper.root}.\nFiles:\n" + helper.list_files(".")[:3000]  # nothing to search
                    elif name == "aller_dans_dossier":
                        options_ = self.find_folders(args.get("dossier", ""))
                        found = options_[0] if options_ else None
                        if not found:
                            result = f"error: folder « {args.get('dossier')} » not found in Desktop, Documents, Downloads or home; ask the user for its path"
                        else:
                            helper.root = found.resolve()
                            self.event({"type": "project", "path": str(found)})  # the app now works there too
                            others = [str(o) for o in options_[1:4]]
                            result = (f"ok: now working in {found}."
                                      + (f" Other folders with this name: {', '.join(others)} — if it is not the right one, ask the user." if others else "")
                                      + "\nFiles:\n" + helper.list_files(".")[:3000])
                    elif name == "creer_fichier":
                        here = helper.root if helper.root.resolve() != chatfiles.OUT.resolve() else None
                        result, info = chatfiles.create(args.get("nom", ""), args.get("contenu") or "", args.get("fichiers"), here)
                        made.append(info)
                        self.event({"type": "deliverables", "root": str(here or chatfiles.OUT), "files": list(reversed(made))})
                    else:
                        result = helper.call_tool(name, args)
                        if name == "send_email":
                            sent, mail_error = (True, None) if str(result).startswith("ok") else (sent, result)
                        elif (name in ("convert_document", "make_diagram", "run_command", "write_file", "edit_file")
                              and helper.root.resolve() != Path.home().resolve() and not str(result).startswith(("error", "refused"))):
                            # a PDF, a plan, an image made by another tool than creer_fichier: shown too, with Ouvrir / Finder
                            here = helper.root if helper.root.resolve() != chatfiles.OUT.resolve() else None
                            known = {f["path"] for f in made}
                            new_files = [f for f in helper._deliverables(started) if f["path"] not in known]
                            if new_files and (here or not made):
                                made.extend(reversed(new_files))
                                self.event({"type": "deliverables", "root": str(helper.root), "files": list(reversed(made))})
                except Exception as e:  # a tool error is told to the model, never a crash of the reply
                    result = f"error: {e}"
                result = str(result)
                self.event({"type": "tool_result", "name": name, "result": result[-3000:]})
                if helper._same_error(name, result):
                    result += ("\n\n[STOP: same error twice. Do not call it again. Tell the user the exact error, your "
                               "hypothesis about its cause and what would fix it.]")
                messages.append({"role": "tool", "tool_name": name, "content": result[:12000]})
            # a screenshot or an image looked at: Naim SEES it (only the latest one stays, older ones are dropped)
            imgs, helper._pending_images = getattr(helper, "_pending_images", []), []
            looked, helper._looked = getattr(helper, "_looked", False), False
            if imgs and (helper._can_see() if looked else helper._vision()):
                for i in shots:
                    messages[i].pop("images", None)
                shots.append(len(messages))
                messages.append({"role": "user", "content": "Voici l'image du fichier." if looked else "Voici la capture d'écran.",
                                 "images": imgs})
            used_tools = True
        if used_tools and not stop.is_set() and not content.strip() and not body.get("_relaunched"):
            # it acted but said nothing: once more, WITH its tools, to go on with the task or say what it found
            messages.append({"role": "user", "content": "Continue : poursuis la tâche avec tes outils s'il reste quelque chose "
                             "à faire, sinon réponds à l'utilisateur (ce que tu as vu ou fait)."})
            return self._chat_steps({**body, "_relaunched": True}, messages, options, stop, False, helper, think, repeating,
                                    chatfiles, run_id)
        if mail_error and not sent:  # never let a reply suggest an email left when it did not
            self.event({"type": "token", "text": f"\n\nL'e-mail n'a pas pu partir. Erreur exacte : {mail_error.removeprefix('error: ')[:300]}"})
        self.event({"type": "done"})

    def chat_with_web(self, body, messages, options, stop, schedule=False, files=False, web=True, email=False, send_now=False):
        """Chat mode with tools: web_search / web_fetch, planifier when the user talks about scheduling, creer_fichier
        when they want a file. False = no tool used (the answer is then streamed normally)."""
        from naimtools import SCHEDULE_TOOL
        import chatfiles
        from naimtools import EMAIL_TOOL, CONTACT_TOOL
        import mailer
        allowed = mailer.addresses(" ".join(agent_settings(body)["email_allowed"]))
        own = mailer.own_addresses() if email else []
        # the user's own address: one of this Mac's Mail accounts (an allowed one first); never guessed from the list
        me = next((a for a in own if a in allowed), None) or (own[0] if own else None)
        note = ((WEB_CHAT_NOTE if web else "") + (FILE_CHAT_NOTE if files else "") + (EMAIL_CHAT_NOTE if email else "")
                + (f"\nThe user's own email address (« moi », « une copie à moi »): {me}" if email and me else ""))
        wants_copy = bool(me) and bool(re.search(r"copie\s+(?:à|a|pour)\s+moi|à moi aussi|et moi\b|envoie[- ]moi|envoy\w+[- ]moi",
                                                 " ".join(str(m.get("content") or "") for m in messages[-4:] if m.get("role") == "user"), re.I))
        recipients = set()
        messages = [dict(messages[0], content=messages[0]["content"] + note)] + messages[1:]
        made, last_tool, mailed, nudged, copy_nudged, mail_error = [], None, False, False, False, None
        s = body.get("settings") or {}
        def approver(action, detail):  # same confirmation card as in Agent mode (e.g. an email to a new address)
            aid = uuid.uuid4().hex
            entry = {"event": threading.Event(), "allow": False}
            with _lock:
                _pending[aid] = entry
            self.event({"type": "approval", "id": aid, "action": action, "detail": detail[:40000]})
            deadline = time.time() + APPROVAL_TIMEOUT
            while not entry["event"].wait(0.3):
                if stop.is_set() or time.time() > deadline:
                    break
            with _lock:
                _pending.pop(aid, None)
            self.event({"type": "approval_result", "id": aid, "allow": entry["allow"]})
            return entry["allow"]

        helper = Agent(str(Path(s.get("project") or body.get("project") or Path.home()).expanduser()), body.get("model", "naim"),
                       features={"mcp": False}, auto_yes=bool(body.get("auto_yes")), emit=self.event, approver=approver,
                       email_allowed=agent_settings(body)["email_allowed"])
        tools = ((WEB_TOOLS if web else []) + ([SCHEDULE_TOOL] if schedule else []) + ([chatfiles.FILE_TOOL] if files else [])
                 + ([EMAIL_TOOL, CONTACT_TOOL] if email else []))
        names = {t["function"]["name"] for t in tools}
        used, answered = False, False
        for _ in range(7):
            if stop.is_set():
                self.event({"type": "stopped"})
                break
            self.event({"type": "status", "text": "Naim rédige le fichier (un long document peut prendre quelques minutes)…" if files and not made else
                        "Naim cherche sur le web…" if last_tool in ("web_search", "web_fetch") else "Naim continue…" if used else "Naim réfléchit…"})
            # a file was asked and not made yet: the answer MUST be the creer_fichier call (else the model tends to
            # print Python code that would make the file, as in a code conversation)
            force = (files and not made and not web and not schedule) or ((nudged or send_now) and not mailed) or (
                copy_nudged and me not in recipients)
            opts = dict(options, tool_choice="required") if force else options
            msg = ollama_chat(body.get("model", "naim"), messages, tools=tools, think=bool(body.get("think")), options=opts)
            calls = [c for c in msg.get("tool_calls") or [] if c["function"]["name"] in names]
            if force and not calls and not used:  # engine without forced calls (Ollama, MLX): ask once more, explicitly
                msg = ollama_chat(body.get("model", "naim"), messages + [{"role": "user", "content": (
                    "Crée maintenant le fichier demandé en appelant l'outil creer_fichier, avec le contenu COMPLET. "
                    "N'écris pas de code pour le fabriquer.")}], tools=tools, think=False, options=options)
                calls = [c for c in msg.get("tool_calls") or [] if c["function"]["name"] == "creer_fichier"]
            if not calls and wants_copy and recipients and me not in recipients and not copy_nudged:
                copy_nudged = True  # « une copie à moi » asked but not sent: never claim it, do it
                messages.append(msg)
                messages.append({"role": "user", "content": f"Tu n'as pas encore envoyé la copie à l'utilisateur ({me}) : "
                                 "envoie-la maintenant avec send_email (même pièce jointe)."})
                continue
            if not calls and email and not mailed and used and not nudged:
                nudged = True
                messages.append(msg)
                messages.append({"role": "user", "content": "Continue maintenant : envoie l'email demandé (chercher_contact "
                                 "si tu n'as pas l'adresse, puis send_email avec le fichier en pièce jointe)."})
                continue
            if not calls:
                if not used:
                    return False  # no search needed: answer normally (streamed)
                if msg.get("thinking"):
                    self.event({"type": "thinking", "text": msg["thinking"]})
                text = msg.get("content") or ""
                if mail_error and not recipients:  # the email did not leave: the answer says so, with the real error
                    claims = re.search(r"\b(envoy[ée]e?s?|parti|transmis)\b", text, re.I) and not re.search(r"\b(pas|n'a|échou|erreur|impossible)\b", text, re.I)
                    text = (f"L'e-mail n'a pas pu partir. Erreur exacte : {mail_error.removeprefix('error: ')[:300]}"
                            + ("" if claims or not text.strip() else "\n\n" + text))
                elif not recipients and re.search(r"\b(envoy[ée]e?s?|transmis)\b.{0,60}\b(e-?mail|mail|courriel|à vous|à toi)\b"
                                                r"|\b(e-?mail|mail|courriel)\b.{0,30}\b(envoy[ée]e?s?|parti)\b", text, re.I):
                    text += "\n\n⚠ Aucun e-mail n'a été envoyé pour l'instant : dis-moi si je dois l'envoyer (et à qui)."
                self.event({"type": "token", "text": text})
                answered = bool(text.strip())
                break
            used = True
            messages.append(msg)
            for c in calls:
                name, args = c["function"]["name"], c["function"].get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                self.event({"type": "tool", "name": name, "args": args})
                try:
                    last_tool = name
                    if name in ("send_email", "chercher_contact"):
                        mailed = True
                    if name == "send_email":
                        # a file made in this chat is in chatfiles.OUT, whatever path the model writes
                        atts = [str(chatfiles.OUT / Path(a).name) if not Path(os.path.expanduser(a)).is_file()
                                and (chatfiles.OUT / Path(a).name).is_file() else a for a in args.get("attachments") or []]
                        result = helper.send_email(args.get("to", ""), args.get("subject", ""), args.get("body", ""), atts)
                        if result.startswith("ok"):
                            recipients.update(mailer.addresses(args.get("to", "")))
                        else:
                            mail_error = result
                    elif name == "chercher_contact":
                        result = helper.chercher_contact(args.get("nom", ""))
                    elif name == "creer_fichier":
                        result, info = chatfiles.create(args.get("nom", ""), args.get("contenu") or "", args.get("fichiers"))
                        made.append(info)
                        self.event({"type": "deliverables", "root": str(chatfiles.OUT), "files": list(reversed(made))})
                    else:
                        result = (helper.planifier(**args) if name == "planifier" else helper.web_search(args.get("query", ""))
                                  if name == "web_search" else helper.web_fetch(args.get("url", "")))
                except Exception as e:
                    result = f"error: {e}"
                self.event({"type": "tool_result", "name": name, "result": result[-3000:]})
                if helper._same_error(name, result):  # same failure twice: no third blind try
                    result += ("\n\n[STOP: this tool failed twice with the SAME error. Do not call it again. Tell the user "
                               "the exact error message, your hypothesis about its cause and what would fix it. Never "
                               "invent a vague cause like « formatting problem ».]")
                messages.append({"role": "tool", "tool_name": name, "content": result[:12000]})
        if used and not answered and not stop.is_set():
            # attempts used up (or an empty answer): always say what was done or what blocks, never stay silent
            msg = ollama_chat(body.get("model", "naim"), messages + [{"role": "user", "content": (
                "Réponds maintenant à l'utilisateur en une ou deux phrases naturelles : ce que tu as fait (avec le vrai "
                "nom et le vrai emplacement des fichiers, tels que les outils les ont donnés) ou ce qui manque.")}],
                tools=None, think=False, options=options)
            self.event({"type": "token", "text": (msg.get("content") or "").strip() or
                        "Je n'ai pas réussi à terminer : reformule ou précise ta demande."})
        self.event({"type": "done"})
        return True

    def run_agent(self, body, stop):
        msg = (body.get("message") or "").strip()
        if not body.get("images") and (trivial_message(msg) or SOCIAL_RE.match(msg)):
            # « bonsoir », « merci », « ça va ? » in Agent mode: answered like in the Chat (seconds), the Agent's
            # long instructions and tools are not needed to say hello
            return self.run_chat({**body, "mode": "chat"}, stop)
        mac_ask = (sk := ext.match_skill(msg)) is not None and sk["name"] == "mac"  # « mes rendez-vous ? » reads the Mac
        if not body.get("images") and pure_question(msg) and not mac_ask:
            # « c'est quoi… ? », « pourquoi mon fichier plante ? », « tu penses quoi de… ? » with nothing to DO: an
            # answer in the conversation (it may read files, it changes nothing). Anything to do stays with the Agent.
            return self.run_chat({**body, "mode": "chat", "_question": True}, stop)
        events = queue.Queue()

        def approver(action, detail):
            aid = uuid.uuid4().hex
            entry = {"event": threading.Event(), "allow": False}
            with _lock:
                _pending[aid] = entry
            events.put({"type": "approval", "id": aid, "action": action, "detail": detail[:40000]})
            deadline = time.time() + APPROVAL_TIMEOUT
            while not entry["event"].wait(0.3):
                if stop.is_set() or time.time() > deadline:
                    break
            with _lock:
                _pending.pop(aid, None)
            events.put({"type": "approval_result", "id": aid, "allow": entry["allow"]})
            return entry["allow"]

        def asker(question, choices, multiple):
            aid = uuid.uuid4().hex
            entry = {"event": threading.Event(), "answer": None}
            with _lock:
                _pending[aid] = entry
            events.put({"type": "question", "id": aid, "question": question, "options": choices, "multiple": multiple})
            deadline = time.time() + APPROVAL_TIMEOUT
            while not entry["event"].wait(0.3):
                if stop.is_set() or time.time() > deadline:
                    break
            with _lock:
                _pending.pop(aid, None)
            events.put({"type": "question_result", "id": aid, "answer": entry["answer"]})
            return entry["answer"]

        options, extra = model_options(body)
        if options.get("backend") == "llamacpp":  # the Agent's own slot: its (longer) instructions and tools stay read
            options = {**options, "slot": llamacpp.SLOT_AGENT}
        agent = Agent(body.get("project") or str(Path.home()), body.get("model", "naim"),
                      think=bool(body.get("think")), auto_yes=bool(body.get("auto_yes")),
                      approver=approver, asker=asker, emit=events.put, history=body.get("history", []),
                      options=options, extra_system=extra, run_id=body.get("run_id"), plan=bool(body.get("plan")),
                      **agent_settings(body))
        agent.cancel = stop  # the Stop button cancels the agent and any running command
        agent.conv_id = body.get("conv_id")  # its background jobs report back to this conversation
        with _lock:
            _agents[body.get("run_id") or agent.run_id] = agent

        def work():
            try:
                agent.run(with_first_request(body["message"], body.get("history")), images=body.get("images"))
            except Exception as e:
                events.put({"type": "error", "text": str(e)})
            finally:
                with _lock:
                    _agents.pop(body.get("run_id") or agent.run_id, None)
                events.put(None)

        threading.Thread(target=work, daemon=True).start()
        self.event({"type": "run", "run_id": agent.run_id})
        while (ev := events.get()) is not None:
            self.event(ev)
        self.event({"type": "done"})


def _terminal(self, body):
    run_id = body.get("run_id") or uuid.uuid4().hex
    stop = threading.Event()
    with _lock:
        _runs[run_id] = stop
    cwd = Path(body.get("cwd") or Path.home()).expanduser()
    self.send_response(200)
    self.send_header("Content-Type", "application/x-ndjson")
    self.end_headers()
    try:
        if not cwd.is_dir():
            self.event({"type": "output", "text": f"dossier introuvable : {cwd}\n"})
            self.event({"type": "exit", "code": 1})
            return
        proc = subprocess.Popen(body.get("command", ""), shell=True, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1,
                                start_new_session=True, env={**os.environ, "TERM": "dumb", "CLICOLOR": "0"})

        def watch():
            while proc.poll() is None:
                if stop.is_set():
                    os.killpg(proc.pid, 9)
                    return
                time.sleep(0.2)
        threading.Thread(target=watch, daemon=True).start()
        for line in proc.stdout:
            self.event({"type": "output", "text": line})
        self.event({"type": "exit", "code": proc.wait()})
    except (BrokenPipeError, ConnectionResetError):
        stop.set()
    finally:
        with _lock:
            _runs.pop(run_id, None)


Handler.run_terminal = _terminal


def _settings():
    try:
        return json.loads(SETTINGS.read_text())
    except (OSError, ValueError):
        return {}


COMPACT_PROMPT = (
    "You summarize a conversation between a user and Naim (an AI coding agent) so Naim can continue it without the full "
    "text. Write the summary in the conversation's language, as notes for Naim, at most about 350 words:\n"
    "- what the user wants and their preferences or instructions;\n"
    "- decisions taken, results, file names, paths, commands, names, numbers, dates (exactly as written);\n"
    "- what is done, and what is still pending or asked last.\n"
    "STRICT: write only what is literally in the conversation below. Never add a file, action or result that is not "
    "written there; if the last message is a request not yet answered, write « Demande en attente : … ». "
    "Short bullet points, no preamble, no repetition.")


def compact_conversation(body):
    """Summary of the beginning of a long conversation (earlier summary included): the app then sends it instead of
    those messages, so a long conversation stays fast and within the model's memory."""
    options, _ = model_options(body)
    options.update(temperature=0.1, num_predict=600, slot=1)  # factual and short; its own slot keeps the conversation's cache
    lines = []
    if body.get("previous"):
        lines.append("Earlier summary:\n" + str(body["previous"])[:6000])
    for m in body.get("history") or []:
        text = str(m.get("content") or "")
        if len(text) > 3000:
            text = text[:2000] + " […] " + text[-800:]
        lines.append(f"{'User' if m.get('role') == 'user' else 'Naim'}: {text}")
    msgs = [{"role": "system", "content": COMPACT_PROMPT},
            {"role": "user", "content": "Conversation to summarize:\n<conversation>\n" + "\n\n".join(lines)[-60000:]
             + "\n</conversation>\nNotes (only facts written above):"}]
    out = ollama_chat(body.get("model", "naim"), msgs, think=False, options=options)
    text = re.sub(r"(?s)<think>.*?</think>", "", out.get("content") or "").strip()
    if not text:
        raise RuntimeError("résumé vide")
    return text


def _storage_dirs():
    import docs as _d, computer as _c
    return {"conversations": CONVS, "apercus": _d.PREVIEWS, "captures": _c.SHOTS, "restauration": ext.CKPT}


def _size(p):
    return sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file()) if Path(p).exists() else 0


# ---------------------------------------------------------------- backup / restore
BACKUPS = Path.home() / "Documents" / "Sauvegardes Naim"  # its own folder, apart from the source code


def _backup_items():
    """What a backup holds: (name in the zip, path). Not the model (downloaded again), not the Admin keys."""
    data = Path.home() / "Library" / "Application Support" / "Naim"
    return [("conversations", data / "conversations"), ("settings.json", data / "settings.json"),
            ("schedules.json", data / "schedules.json"), ("naim/NAIM.md", ext.HOME / "NAIM.md"),
            ("naim/memory.json", ext.HOME / "memory.json"), ("naim/memory.md", ext.HOME / "memory.md"),
            ("naim/mcp.json", ext.HOME / "mcp.json"), ("naim/skills", ext.HOME / "skills"),
            ("naim/apprentissage", ext.HOME / "apprentissage")]


def backup_make(note=""):
    import zipfile
    BACKUPS.mkdir(parents=True, exist_ok=True)
    dst = BACKUPS / f"naim-sauvegarde-{time.strftime('%Y-%m-%d-%H%M%S')}{('-' + note) if note else ''}.zip"
    n = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name, p in _backup_items():
            if p.is_file():
                z.write(p, name)
                n += 1
            elif p.is_dir():
                for f in p.rglob("*"):
                    if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".tmp":
                        z.write(f, f"{name}/{f.relative_to(p)}")
                        n += 1
        z.writestr("naim-sauvegarde.json", json.dumps({"date": time.strftime("%Y-%m-%d %H:%M"), "files": n}))
    return {"ok": True, "path": str(dst), "files": n, "size": dst.stat().st_size}


def backup_list():
    out = []
    for f in sorted(BACKUPS.glob("naim-sauvegarde-*.zip"), reverse=True) if BACKUPS.exists() else []:
        out.append({"path": str(f), "name": f.name, "size": f.stat().st_size,
                    "date": time.strftime("%d/%m/%Y %H:%M", time.localtime(f.stat().st_mtime))})
    return {"folder": str(BACKUPS), "backups": out}


def backup_restore(path):
    """Put a backup back. The current state is saved first (« avant-restauration »): nothing can be lost."""
    import zipfile
    src = Path(path).expanduser()
    if not (src.is_file() and src.suffix == ".zip" and zipfile.is_zipfile(src)):
        return {"error": "sauvegarde introuvable ou abîmée"}
    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        if "naim-sauvegarde.json" not in names:
            return {"error": "ce fichier n'est pas une sauvegarde de Naim"}
        safety = backup_make("avant-restauration")
        targets = dict(_backup_items())
        for name in names:
            top = next((k for k in targets if name == k or name.startswith(k + "/")), None)
            if not top or ".." in Path(name).parts:
                continue  # only what Naim saves, never a path outside its folders
            dest = targets[top] if name == top else targets[top] / Path(name).relative_to(top)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as fin, open(dest, "wb") as fout:
                shutil.copyfileobj(fin, fout)
    return {"ok": True, "safety": safety["path"]}


def storage_info():
    """What Naim keeps on this Mac (Personnaliser › Mémoire › Conversations et stockage)."""
    out = {k: {"size": _size(d), "count": sum(1 for _ in Path(d).glob("*")) if Path(d).exists() else 0, "path": str(d)}
           for k, d in _storage_dirs().items()}
    pinned = 0
    for f in CONVS.glob("*.json"):
        try:
            pinned += bool(json.loads(f.read_text()).get("pinned"))
        except (OSError, ValueError):
            pass
    out["conversations"]["pinned"] = pinned
    import chatfiles
    out["fichiers"] = {"size": _size(chatfiles.OUT), "count": sum(1 for _ in chatfiles.OUT.glob("*")) if chatfiles.OUT.exists() else 0,
                       "path": str(chatfiles.OUT)}
    import learning as _l
    out["apprentissage"] = {"size": _size(_l.BASE), "count": sum(1 for _ in _l.TRACES.glob("*.json")) if _l.TRACES.exists() else 0,
                            "path": str(_l.BASE)}
    return out


def storage_clear(what, keep_pinned=True):
    """Empty one of Naim's data folders. Conversations: the pinned ones can be kept. Returns how many items went."""
    d = _storage_dirs().get(what)
    if not d or not Path(d).exists():
        return 0
    n = 0
    for f in list(Path(d).iterdir()):
        if what == "conversations":
            if f.suffix != ".json":
                continue
            try:
                if keep_pinned and json.loads(f.read_text()).get("pinned"):
                    continue
            except (OSError, ValueError):
                pass
        shutil.rmtree(f) if f.is_dir() else f.unlink(missing_ok=True)
        n += 1
    return n


def model_version():
    """The Naim model version on this Mac: the training label on the owner's Mac (and whether the users have it),
    else the version downloaded (naim_version.json), v2 for a download made before versioning."""
    at = _private("autotrain")
    label = ((at.load_state().get("current") or {}).get("label") if at else None)
    if label:
        oa = _private("owner_admin")
        pub = oa._published() if oa and oa.available() else {}
        if pub.get("label") == label:
            return {"name": f"v{pub['version']}", "detail": f"{label} · publiée"}
        return {"name": label.split("-")[0], "detail": f"{label} · pas encore publiée (utilisateurs : v{pub.get('version', 2)})"}
    try:
        v = json.loads((llamacpp.MODELS / "naim_version.json").read_text())
        return {"name": v.get("name") or "v2", "detail": v.get("date") or ""}
    except (OSError, ValueError):
        return {"name": "v2", "detail": ""}


_idle_jobs = []


def _when_idle(job, quiet=60):
    """Run a background job once Naim has answered nothing for `quiet` seconds (spoken conversations)."""
    with _lock:
        _idle_jobs.append(job)
        if len(_idle_jobs) > 1:
            return  # a waiter already runs

    def wait():
        idle_since = time.time()
        while True:
            time.sleep(2)
            with _lock:
                busy = bool(_runs)
            if busy:
                idle_since = time.time()
            elif time.time() - idle_since >= quiet:
                with _lock:
                    jobs, _idle_jobs[:] = list(_idle_jobs), []
                for j in jobs:
                    try:
                        j()
                    except Exception as e:  # noqa: BLE001
                        print(f"mémoire différée : {e}", flush=True)
                return
    threading.Thread(target=wait, daemon=True).start()


def _private(name):
    """Optional module present only on some installations (e.g. the project owner's training); None otherwise."""
    try:
        return __import__(name)
    except ImportError:
        return None


def _busy():
    """True while Naim works (an agent run, a scheduled task): the automatic training waits."""
    return bool(_agents) or bool(scheduler.running_ids())


def warm_voice():
    """Naim's natural voice is heavy to load (~1 min): loaded in the background as soon as Naim opens."""
    try:
        import naim_voice
        vt = _private("voicetrain")
        if vt and vt.training_lock():  # Naim is learning its voice: the GPU is busy
            return
        if naim_voice.fast_natural_available():  # instant: nothing heavy to load
            with naim_voice._fast_lock:
                naim_voice._fast_worker()
        elif naim_voice.natural_available():
            with naim_voice._nat_lock:
                naim_voice._natural_worker()
    except Exception as e:  # noqa: BLE001
        print(f"voix non préchargée : {e}", flush=True)


# where the opening preparation stands, shown discreetly under the conversations (« Naim · préparation… » → « prêt »)
WARM = {"state": "starting", "step": "", "t0": time.time()}


def warm_up():
    """When Naim opens: it reads its tools and instructions once, in the background (one invisible request of one
    token, through the very same path as a real message). The first message then starts at once instead of
    waiting ~1 minute for that reading."""
    try:
        time.sleep(4)
        s = _settings()
        if s.get("naim_backend", "llamacpp") != "llamacpp" or not llamacpp.available():
            WARM["state"] = "ready"
            return
        h = Handler.__new__(Handler)
        h.event = lambda ev: None
        body = {"message": "bonjour, es-tu prêt ?", "mode": "chat", "model": s.get("model") or "naim", "history": [], "_warm": True,
                "project": s.get("project"), "settings": {**s, "num_predict": 1, "memory_auto": False, "think": False}}
        order = ["agent", "chat"] if s.get("mode") == "agent" else ["chat", "agent"]  # the mode in use first
        for i, mode in enumerate(order):
            WARM.update(state="warming", step=f"{'Chat' if mode == 'chat' else 'Agent'} ({i + 1}/2)")
            if mode == "chat":
                h.run_chat(body, threading.Event())
            else:
                warm_agent(s)
    except Exception as e:  # noqa: BLE001 — only a speed-up: never a problem if it fails
        print(f"préchauffage impossible : {e}", flush=True)
    finally:
        WARM.update(state="ready", step="", done=time.time())


def warm_agent(s):
    """The Agent's instructions and tools (longer than the Chat's) read once in its own slot: its first task, even a
    « bonsoir », then starts at once instead of waiting for that reading (~3 min on a MacBook Air)."""
    body = {"model": s.get("model") or "naim", "settings": {**s, "num_predict": 1, "think": False}}
    options, extra = model_options(body)
    options = {**options, "slot": llamacpp.SLOT_AGENT, "num_predict": 1}
    agent = Agent(s.get("project") or str(Path.home()), body["model"], think=False, auto_yes=bool(s.get("autoYes")),
                  approver=lambda *a: False, asker=lambda *a, **k: None, emit=lambda ev: None, history=[],
                  options=options, extra_system=extra, **agent_settings(body))  # built like a real task (same tools)
    for _ in ollama_chat(body["model"], agent.messages + [{"role": "user", "content": "bonjour"}], tools=agent.tools,
                         stream=True, options=options):
        pass


def serve(port=8765):
    threading.Thread(target=warm_up, daemon=True, name="naim-warm-up").start()
    threading.Thread(target=warm_voice, daemon=True, name="naim-warm-voice").start()
    scheduler.start_loop(_settings, ollama_chat, Agent, CHAT_PROMPT)
    if at := _private("autotrain"):
        at.start_loop(_settings, _busy)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    return httpd


if __name__ == "__main__":
    s = serve()
    print("Naim UI sur http://127.0.0.1:8765")
    s.serve_forever()
