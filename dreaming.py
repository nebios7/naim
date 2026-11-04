"""Naim's dream: at night, while the Mac is idle, Naim reads back what happened since its last dream and proposes
rules for its instructions. Nothing is changed without the user: in the morning the proposals wait in Naim
(home card and Personnaliser › Mémoire), and only an accepted rule is written to ~/.naim/NAIM.md.

What it reads:
- the moments the user corrected Naim or gave a lasting instruction (« non », « pas ça », « toujours », « !!! »…),
  with what Naim had answered just before;
- the Chat answers rated « Mauvais »;
- its current instructions (NAIM.md), its lessons (lecons.md), its memory and the proposals already refused.
Each proposed rule must point to the moments it comes from (checked here): a rule with no real source is dropped.
The memory is tidied the same way (duplicates, wrong facts, one-off requests), as proposals too.

Dreams are kept in ~/.naim/reves/YYYY-MM-DD.json.
"""
import json
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import extensions as ext
import memory

DIR = ext.HOME / "reves"
NAIM_MD = ext.HOME / "NAIM.md"
SECTION = "## Règles apprises en rêvant"
STATE = {"running": False, "step": "", "done": 0, "total": 0, "error": None}
_lock = threading.Lock()

# a correction or a lasting instruction from the user
CORRECT_RE = re.compile(
    r"\b(non\b|pas (ça|ca|comme ça|bon|bien|ce que|celui|celle|du tout)|toujours pas|encore (une fois|raté|pas)|"
    r"il (manque|a pas|n'a pas)|(t'as|tu as|il a) (pas|oublié)|oubli\w*|je t'ai (dit|demandé)|j'ai (dit|demandé|pas demandé)|"
    r"pourquoi|faux|mauvais|pourri\w*|nul\b|arr[êe]te|refais|recommence|corrige|ne (fais|mets|touche|supprime|change|"
    r"modifie|code) (pas|jamais|rien)|jamais|toujours|à chaque fois|par d[ée]faut|plut[ôo]t|au lieu|attention|"
    r"n'importe quoi|c'est pas|ce n'est pas)\b|!{2,}", re.I)
GREETING_RE = re.compile(r"^\W*(salut|bonjour|bonsoir|merci|ok|oui|d'accord|parfait|super|top)\W*$", re.I)
SECRET_RE = memory.SECRET_RE
PER_CALL = 18  # moments read per model call (the dream reads them all, a call at a time)

PROMPT = """Tu es Naim, un assistant. Cette nuit, tu relis les moments où l'utilisateur t'a corrigé ou t'a donné une
consigne, pour en tirer des règles qui t'éviteront de refaire ces erreurs.

Tes consignes actuelles (ne les répète pas, même dites autrement) :
%s

Les moments relevés :
%s

Propose au plus 5 règles. Une bonne règle :
- vient d'au moins un moment ci-dessus, cité par son numéro dans "sources" ;
- est générale : elle servira à d'autres conversations (pas un nom de fichier, pas une tâche unique) ;
- est à l'impératif, en français, en 30 mots au plus, et se comprend seule ;
- dit ce qu'il faut faire, pas ce qui s'est passé.
Ignore un moment sans leçon durable (une simple question, un merci, un choix ponctuel). N'invente rien.
Réponds SEULEMENT avec du JSON : {"regles": [{"regle": "...", "pourquoi": "une phrase", "sources": [1, 4]}]}
S'il n'y a rien à retenir : {"regles": []}"""


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _file(date):
    return DIR / f"{Path(str(date)).name[:10]}.json"


def load(date):
    try:
        return json.loads(_file(date).read_text())
    except (OSError, ValueError):
        return None


def _save(dream):
    DIR.mkdir(parents=True, exist_ok=True)
    _file(dream["date"]).write_text(json.dumps(dream, ensure_ascii=False, indent=1))


def all_dreams():
    files = sorted(DIR.glob("*.json")) if DIR.exists() else []
    out = []
    for f in files:
        try:
            out.append(json.loads(f.read_text()))
        except (OSError, ValueError):
            continue
    return out


def latest():
    d = all_dreams()
    return d[-1] if d else None


def pending():
    """Proposals still waiting for the user, all dreams together (newest first)."""
    out = []
    for d in reversed(all_dreams()):
        out += [{**p, "date": d["date"]} for p in d.get("proposals", []) if p.get("status") == "attente"]
    return out


# ---------------------------------------------------------------------- what Naim reads
def _text(m):
    return " ".join(str(m.get("content") or "").split())


def moments(conv_dir, since=0.0):
    """The corrections and lasting instructions of the conversations changed since `since` (oldest first)."""
    out = []
    files = sorted(Path(conv_dir).glob("*.json"), key=lambda p: p.stat().st_mtime) if Path(conv_dir).exists() else []
    for f in files:
        if f.stat().st_mtime <= since:
            continue
        try:
            c = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if c.get("scheduled"):  # a scheduled run: nobody corrected anything
            continue
        msgs = c.get("messages") or []
        for i, m in enumerate(msgs):
            if m.get("role") != "user" or i == 0 or (m.get("time") or 0) / 1000 <= since:
                continue
            said = _text(m)
            if len(said) < 4 or GREETING_RE.match(said) or SECRET_RE.search(said) or not CORRECT_RE.search(said):
                continue
            before = next((_text(x) for x in reversed(msgs[:i]) if x.get("role") == "assistant" and _text(x)), "")
            out.append({"conv": c.get("id", f.stem), "title": c.get("title") or "", "naim": before[-260:], "user": said[:420]})
    return out


def bad_answers(since=0.0):
    """Chat answers the user rated « Mauvais » since `since` (the learning store)."""
    import learning
    out = []
    for f in sorted(learning.CHATS.glob("*.json")) if learning.CHATS.exists() else []:
        try:
            if f.stat().st_mtime <= since:
                continue
            c = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        msgs = c.get("messages") or []
        if c.get("rating") == -1 and len(msgs) >= 2:
            ask = next((_text(m) for m in reversed(msgs) if m["role"] == "user"), "")
            out.append({"conv": c.get("id", f.stem), "title": "réponse notée « Mauvais »", "naim": _text(msgs[-1])[-260:],
                        "user": f"(note « Mauvais » à cette réponse ; la demande était : {ask[:300]})"})
    return out


def rules_now():
    """Every rule Naim already follows: NAIM.md lines, lessons, memory instructions."""
    lines = []
    try:
        lines += [l.strip("-* ").strip() for l in NAIM_MD.read_text().splitlines() if len(l.strip("-*# ").strip()) > 8]
    except OSError:
        pass
    try:
        import naim_check
        lines += [re.sub(r"^- \*\*.+?\*\* : ", "", l) for l in naim_check.LESSONS.read_text().splitlines() if l.startswith("- **")]
    except (OSError, ImportError):
        pass
    lines += [f["text"] for f in memory.load() if f.get("cat") == "consignes" and f.get("active", True)]
    return lines


def _known(rule, known):
    """True if the rule is already there (same words, or nearly)."""
    w = memory._words(rule)
    for k in known:
        if memory._similar(rule, k):
            return True
        o = memory._words(k)
        if w and o and len(w & o) / len(w) >= 0.7:  # all its ideas are already in a longer line
            return True
    return False


def _parse(reply, n):
    m = re.search(r"\{.*\}", reply or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except ValueError:
        return []
    out = []
    for r in data.get("regles", []) if isinstance(data, dict) else []:
        if not isinstance(r, dict) or not isinstance(r.get("regle"), str):
            continue
        rule = " ".join(r["regle"].split()).strip("\"«» ")
        src = sorted({int(s) for s in r.get("sources") or [] if str(s).isdigit() and 1 <= int(s) <= n})
        if 8 <= len(rule) <= 300 and src and not SECRET_RE.search(rule):  # no source = invented: dropped
            out.append({"rule": rule, "why": " ".join(str(r.get("pourquoi") or "").split())[:240], "sources": src})
    return out[:5]


# ---------------------------------------------------------------------- the dream
def dream(conv_dir, chat_fn, since=None):
    """Read, then propose. Returns the dream saved for today (proposals of a same day are added together)."""
    with _lock:
        if STATE["running"]:
            return None
        STATE.update(running=True, step="lit ses conversations", done=0, total=0, error=None)
    try:
        last = latest()
        if since is None:
            since = time.mktime(time.strptime(last["date_time"], "%Y-%m-%d %H:%M")) if last and last.get("date_time") else 0.0
        found = moments(conv_dir, since) + bad_answers(since)
        seen = [p["text"] for d in all_dreams() for p in d.get("proposals", []) if p.get("status") in ("refusee", "acceptee", "attente")]
        known = rules_now() + seen  # never proposed twice
        chunks = [found[i:i + PER_CALL] for i in range(0, len(found), PER_CALL)]
        STATE.update(step="cherche des règles", total=len(chunks))
        rules = []
        for chunk in chunks:
            listed = "\n".join(f"[{i}] (« {x['title'][:50]} ») Naim : « {x['naim'] or '—'} »\n    L'utilisateur : « {x['user']} »"
                               for i, x in enumerate(chunk, 1))
            have = "\n".join(f"- {k[:160]}" for k in known[-120:]) or "(aucune)"
            try:
                found_rules = _parse(chat_fn([{"role": "user", "content": PROMPT % (have, listed)}]), len(chunk))
            except Exception as e:  # noqa: BLE001 — one call that fails must not stop the dream
                STATE["error"] = str(e)[:200]
                found_rules = []
            for r in found_rules:
                if _known(r["rule"], known + [x["text"] for x in rules]):
                    continue
                src = [chunk[i - 1] for i in r["sources"]]
                rules.append({"id": uuid.uuid4().hex[:8], "kind": "regle", "text": r["rule"], "why": r["why"],
                              "evidence": [{"user": s["user"][:300], "title": s["title"][:80], "conv": s["conv"]} for s in src[:3]],
                              "status": "attente"})
            STATE["done"] += 1
        STATE["step"] = "range sa mémoire"
        tidy = [{"id": uuid.uuid4().hex[:8], "kind": "retirer", "fact": t["id"], "text": t["text"], "why": t["reason"],
                 "evidence": [], "status": "attente"} for t in memory.tidy_preview()]
        today = datetime.now().strftime("%Y-%m-%d")
        d = load(today) or {"date": today, "proposals": [], "read": {"moments": 0, "conversations": 0}}
        old_facts = {p.get("fact") for p in d["proposals"] if p["kind"] == "retirer"}
        d["proposals"] += rules + [t for t in tidy if t["fact"] not in old_facts]
        d["read"] = {"moments": d["read"].get("moments", 0) + len(found),
                     "conversations": d["read"].get("conversations", 0) + len({x["conv"] for x in found})}
        d["date_time"] = _now()
        _save(d)
        return d
    finally:
        STATE.update(running=False, step="")


# ---------------------------------------------------------------------- the user's answer
def _backup():
    """NAIM.md as it was before the first rule of the day (kept aside, never deleted)."""
    b = ext.HOME / f"NAIM.md.avant-reve-{datetime.now():%Y%m%d}"
    if NAIM_MD.exists() and not b.exists():
        b.write_text(NAIM_MD.read_text())


def accepted_rules():
    """The rules accepted from the dreams, as written in NAIM.md (its own section), in order."""
    try:
        cur = NAIM_MD.read_text()
    except OSError:
        return []
    if SECTION not in cur:
        return []
    part = cur.split(SECTION, 1)[1].split("\n## ", 1)[0]
    return [l[2:].strip() for l in part.splitlines() if l.startswith("- ") and l[2:].strip()]


def remove_rule(text):
    """An accepted rule taken out of NAIM.md (the file as it was is kept aside first). True if it was there."""
    try:
        cur = NAIM_MD.read_text()
    except OSError:
        return False
    line = f"- {' '.join(str(text).split())}"
    if SECTION not in cur or line not in cur.splitlines():
        return False
    _backup()
    head, part = cur.split(SECTION, 1)
    part = "\n".join(l for l in part.split("\n") if l.strip() != line)
    NAIM_MD.write_text(head + SECTION + part)
    return True


def add_rule(text):
    """Write an accepted rule at the end of NAIM.md, in its own section — not a second time in other words."""
    text = " ".join(str(text).split())
    if _known(text, accepted_rules()):
        return  # already there, said differently (« Vérifie toujours le résultat réel… » twice)
    _backup()
    try:
        cur = NAIM_MD.read_text()
    except OSError:
        cur = "# Consignes de Naim (globales)\n"
    if SECTION not in cur:
        cur = cur.rstrip("\n") + f"\n\n{SECTION}\n\n"
    NAIM_MD.write_text(cur.rstrip("\n") + f"\n- {text}\n")


def answer(date, pid, accept, text=None):
    """Accept (with the user's wording if changed) or refuse one proposal. Returns the proposal, or None."""
    with _lock:
        d = load(date)
        p = next((x for x in (d or {}).get("proposals", []) if x["id"] == pid), None)
        if not p or p.get("status") != "attente":
            return None
        if accept:
            if text and text.strip():
                p["text"] = " ".join(text.split())
            if p["kind"] == "regle":
                add_rule(p["text"])
            elif p["kind"] == "retirer":
                memory.tidy_apply([p["fact"]])
        p["status"] = "acceptee" if accept else "refusee"
        p["answered"] = _now()
        _save(d)
        return p


# ---------------------------------------------------------------------- at night, by itself
def due(settings, last_dream, idle_s, awake_s, hour):
    """A dream is due once a day: at night (1 h to 6 h) when the Mac has been idle 30 min, or after a day and a half
    without one when it has been idle 2 h. Never just after the Mac wakes up (awake 20 min first)."""
    if settings.get("dreaming", True) is False or awake_s < 1200:
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    if last_dream and last_dream.get("date") == today:
        return False
    age = (time.time() - time.mktime(time.strptime(last_dream["date_time"], "%Y-%m-%d %H:%M"))) \
        if last_dream and last_dream.get("date_time") else 1e9
    return (1 <= hour <= 6 and idle_s >= 1800) or (age >= 36 * 3600 and idle_s >= 7200)


def start_loop(conv_dir, get_settings, busy, last_activity, chat_fn):
    def loop():
        awake, tick = time.time(), time.time()
        while True:
            time.sleep(300)
            now = time.time()
            if now - tick > 900:  # the loop slept far longer than asked: the Mac was asleep, it just woke up
                awake = now
            tick = now
            try:
                if not STATE["running"] and not busy() and due(get_settings(), latest(), now - last_activity(),
                                                               now - awake, datetime.now().hour):
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} Naim rêve (Mac inactif)", flush=True)
                    dream(conv_dir, chat_fn())
            except Exception:  # noqa: BLE001
                pass
    threading.Thread(target=loop, daemon=True, name="naim-dream").start()
