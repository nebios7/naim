"""Naim's long-term memory: durable facts about the user, kept in ~/.naim/memory.json.

Each fact: {id, text, cat, pinned, active, created, source}.
- pinned facts are always given to the model; the other active facts are given most recent first, up to a limit;
- an inactive ("déchargé") fact is kept but not given to the model;
- facts are added by Naim's `remember` tool, by hand in Personnaliser › Mémoire, and automatically: after a
  conversation, the model extracts what the USER said that is worth remembering (extract_from_messages).
The old ~/.naim/memory.md (one "- fact" per line) is migrated once and then kept in sync for reading.
"""
import difflib
import json
import re
import threading
import time
import uuid
from pathlib import Path

import extensions as ext

FILE = ext.HOME / "memory.json"
LEGACY = ext.HOME / "memory.md"
CATS = {"profil": "Profil", "preferences": "Préférences", "projets": "Projets", "consignes": "Consignes", "autre": "Autre"}
_lock = threading.RLock()
LIMIT = 60  # facts given to the model (Personnaliser › Mémoire)
PROGRESS = {"running": False, "done": 0, "total": 0, "added": 0, "error": None}


def _now():
    return time.strftime("%Y-%m-%d %H:%M")


def load():
    with _lock:
        try:
            data = json.loads(FILE.read_text())
            return data.get("facts", [])
        except (OSError, ValueError):
            pass
        facts = []
        try:  # migrate the old markdown memory
            for line in LEGACY.read_text().splitlines():
                if line.startswith("- ") and line[2:].strip():
                    facts.append(_fact(line[2:].strip(), "autre", "ancienne mémoire"))
        except OSError:
            pass
        if facts:
            save(facts)
        return facts


def save(facts):
    with _lock:
        ext.HOME.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps({"facts": facts}, ensure_ascii=False, indent=1))
        LEGACY.write_text("".join(f"- {f['text']}\n" for f in facts if f.get("active", True)))


def _fact(text, cat="autre", source=""):
    return {"id": uuid.uuid4().hex[:10], "text": " ".join(str(text).split())[:400], "cat": cat if cat in CATS else "autre",
            "pinned": False, "active": True, "created": _now(), "source": source}


def _similar(a, b):
    a, b = a.lower().strip(" ."), b.lower().strip(" .")
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() > 0.86


# ---------------------------------------------------------------------- memory hygiene
# a fact that is wrong (the user is not Naim), a tool recipe of a scheduled task, or a one-off request is not a memory
BAD_FACT_RE = re.compile(
    r"\b(utilisateur|user)\b.{0,20}\b(s'appelle|se nomme|est|is|named)\s+(naim|mimo|l'assistant)\b"
    r"|\b(mail_\w+|send_email|run_command|write_file|start_process|use_skill|tool_call|creer_fichier)\b"
    r"|\bskill\s+[\w-]+\b.{0,30}\boutils?\b", re.I)
ONE_OFF_RE = re.compile(
    r"^(l'utilisateur\s+)?(souhaite|veut|demande|aimerait)\s+(que\s+(le|la|les|son|sa|ses|ce|cette)\b.{0,60}\b(soi(en)?t|être)\s+"
    r"(amélior|envoy|corrig|génér|cré|tradui|résum|imprim)\w*)"
    r"|^(envoyer|traiter|générer|créer|corriger|améliorer|résumer|imprimer|faire)\s+(le|la|les|un|une|ce|cette|mon|ma|mes)\b", re.I)
NAME_RE = re.compile(r"(?i:\b(s'appelle|se nomme|nom de l'utilisateur))|\b[Ll]'utilisateur est [A-ZÉ][a-zé]+\b")  # a capital: a name
STOP = set("le la les un une des de du d l à a au aux et ou en dans pour par sur avec que qui est sont son sa ses "
           "l'utilisateur utilisateur il elle".split())


def _words(t):
    return {w for w in re.findall(r"[a-zà-ÿ0-9]+", t.lower().replace("'", " ")) if w not in STOP and len(w) > 2}


def why_not(text, facts):
    """Why this fact should not be stored (or kept) given the others, or '' if it is fine."""
    if BAD_FACT_RE.search(text):
        return "faux ou propre à un outil / une tâche planifiée"
    if ONE_OFF_RE.search(text.strip()):
        return "demande ponctuelle, pas un fait durable"
    w = _words(text)
    for f in facts:
        if f["text"] == text:
            continue
        if _similar(text, f["text"]):
            return f"doublon de « {f['text'][:60]} »"
        if NAME_RE.search(text) and NAME_RE.search(f["text"]):
            return f"doublon de « {f['text'][:60]} » (nom)"
        o = _words(f["text"])
        if w and o and len(w & o) / len(w | o) >= 0.6:
            return f"doublon de « {f['text'][:60]} »"
    return ""


def tidy_preview():
    """Facts the hygiene rules would remove: [{id, text, reason}]. For a duplicate, the longer (richer) one is kept."""
    facts = [f for f in load() if not f.get("pinned")]
    out, kept = [], []
    for f in sorted(facts, key=lambda f: -len(f["text"])):
        reason = why_not(f["text"], kept)
        if reason:
            out.append({"id": f["id"], "text": f["text"], "reason": reason})
        else:
            kept.append(f)
    return out


def tidy_apply(ids):
    with _lock:
        ids = set(ids or [])
        facts = [f for f in load() if f["id"] not in ids]
        save(facts)
        return facts


def add(text, cat="autre", source=""):
    """Add a fact unless an equivalent one exists (or it is wrong / a one-off request, for automatic additions).
    Returns the fact, or None."""
    text = " ".join(str(text or "").split())
    if len(text) < 4:
        return None
    with _lock:
        facts = load()
        if any(_similar(text, f["text"]) for f in facts):
            return None
        if source != "ajout manuel" and why_not(text, facts):
            return None
        f = _fact(text, cat, source)
        facts.append(f)
        save(facts)
        return f


def update(fid, **changes):
    with _lock:
        facts = load()
        for f in facts:
            if f["id"] == fid:
                for k in ("text", "cat", "pinned", "active"):
                    if k in changes:
                        f[k] = changes[k]
        save(facts)
        return facts


def delete(fid=None, all_=False, keep_pinned=False):
    with _lock:
        if all_:
            facts = [f for f in load() if keep_pinned and f.get("pinned")]
        else:
            facts = [f for f in load() if f["id"] != fid]
        save(facts)
        return facts


def forget(text):
    """Remove facts containing `text` (used by Naim's forget tool). Returns how many were removed."""
    with _lock:
        facts = load()
        kept = [f for f in facts if text.lower() not in f["text"].lower()]
        save(kept)
        return len(facts) - len(kept)


def prompt(limit=60):
    """Memory block for the system prompt: pinned facts, then the most recent active ones, grouped by category."""
    facts = [f for f in load() if f.get("active", True)]
    if not facts:
        return ""
    pinned = [f for f in facts if f.get("pinned")]
    rest = [f for f in reversed(facts) if not f.get("pinned")][:max(0, limit - len(pinned))]
    chosen = pinned + rest
    lines = []
    for cat, label in CATS.items():
        items = [f["text"] for f in chosen if f["cat"] == cat]
        if items:
            lines.append(f"{label} :\n" + "\n".join(f"- {t}" for t in items))
    return ("What you remember about the user (long-term memory). Use it silently: mention a fact only when the "
            "user's request is about it. To a greeting that opens a conversation (« salut », « bonjour »…) greet back "
            "briefly: never list their projects, never introduce yourself.\n" + "\n".join(lines))


# ---------------------------------------------------------------------- automatic extraction
EXTRACT_PROMPT = """Tu lis un extrait de conversation entre un utilisateur et son assistant.
Relève UNIQUEMENT les informations durables que L'UTILISATEUR donne sur lui-même et qui seront utiles plus tard :
son identité (nom, métier), ses préférences (langue, style, outils), ses projets (nom, techno, dossier), ses consignes
permanentes (« toujours… », « jamais… »). Ignore les questions ponctuelles, le code, ce que dit l'assistant,
les informations temporaires et tout ce qui est sensible (mots de passe, clés, numéros).
Ne retiens JAMAIS : une demande ponctuelle (« améliore mon CV », « envoie le résumé »), les étapes ou outils d'une
tâche (noms d'outils, skills), un fait déjà connu dit autrement, ni le nom de l'assistant (l'assistant s'appelle Naim,
pas l'utilisateur).
Réponds SEULEMENT avec du JSON : {"facts": [{"text": "phrase courte en français", "cat": "profil|preferences|projets|consignes"}]}
Au maximum 5 faits. S'il n'y a rien de durable : {"facts": []}

Déjà en mémoire (ne pas répéter) :
%s

Extrait (messages de l'utilisateur) :
%s"""

HINT_RE = re.compile(r"\b(je suis|je m'appelle|appelle[- ]moi|mon nom|je travaille|mon (projet|app|site|entreprise|métier|travail)|"
                     r"ma (société|boîte|préférence)|je préfère|j'aime|j'utilise|je développe|toujours|jamais|"
                     r"n'oublie pas|souviens|retiens|mes (projets|clients|outils)|je veux que tu)\b", re.I)
SECRET_RE = re.compile(r"(hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,}|mot de passe\s*[:=])", re.I)


def worth_extracting(messages):
    return any(m.get("role") == "user" and HINT_RE.search(str(m.get("content") or "")) for m in messages)


def _parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    out = []
    for f in data.get("facts", []) if isinstance(data, dict) else []:
        if isinstance(f, dict) and isinstance(f.get("text"), str) and not SECRET_RE.search(f["text"]):
            out.append((f["text"], str(f.get("cat", "autre")).lower().replace("é", "e")))
    return out[:5]


def extract_from_messages(messages, chat_fn, source=""):
    """Ask the model for durable facts in the user's messages; store the new ones. Returns the added facts."""
    user = [str(m.get("content") or "")[:1500] for m in messages if m.get("role") == "user" and m.get("content")]
    if not user:
        return []
    excerpt = "\n---\n".join(user[-12:])[-6000:]
    known = "\n".join(f"- {f['text']}" for f in load()[-80:]) or "(rien)"
    reply = chat_fn([{"role": "user", "content": EXTRACT_PROMPT % (known, excerpt)}])
    added = []
    for text, cat in _parse(reply):
        f = add(text, cat, source)
        if f:
            added.append(f)
    return added


def extract_from_conversations(conv_dir, chat_fn, limit=40):
    """Background job: fill the memory from existing conversations (most recent first). Progress in PROGRESS."""
    if PROGRESS["running"]:
        return
    files = []
    for p in sorted(Path(conv_dir).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            if not json.loads(p.read_text()).get("scheduled"):  # scheduled runs say nothing about the user
                files.append(p)
        except (OSError, ValueError):
            continue
        if len(files) >= limit:
            break
    PROGRESS.update(running=True, done=0, total=len(files), added=0, error=None)
    try:
        for f in files:
            try:
                c = json.loads(f.read_text())
                PROGRESS["added"] += len(extract_from_messages(c.get("messages", []), chat_fn, c.get("title", "")))
            except Exception as e:  # one bad conversation must not stop the job
                PROGRESS["error"] = str(e)[:200]
            PROGRESS["done"] += 1
    finally:
        PROGRESS["running"] = False
