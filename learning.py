"""Naim's self-improvement loop: keep the agent tasks it finished, let the user rate them, export a dataset.

Every finished agent task is saved locally in ~/.naim/apprentissage/traces/<run_id>.json (never sent anywhere):
the request, every action and result, and quality signals (natural finish, errors, web verification).
A task counts as a GOOD example when the user gave it 👍, or — without a rating — when it finished cleanly
(final answer, no step left, verification passed, few errors). 👎 excludes it.

export() turns the good tasks into training files for Naim v3 (MLX LoRA):
  steps_train.jsonl / steps_valid.jsonl  one example per agent decision, with a short recent context, small
                                          enough for this Mac's GPU (the model learns which action to take next)
  full.jsonl                             whole conversations with the tool definitions (for a bigger GPU later)
"""
import hashlib
import json
import random
import re
import time
from pathlib import Path

import extensions as ext

BASE = ext.HOME / "apprentissage"
TRACES = BASE / "traces"
CHATS = BASE / "chat"      # Chat-mode answers the user rated (only 👍 ones are used for training)
DATASET = BASE / "dataset"
GOAL = 100                 # good tasks before a v3 training is worth it
MAX_RESULT = 4000          # characters kept per tool result in a trace
STEP_CONTEXT = 900           # characters of recent context per training step (this Mac trains at 512 tokens)

STEP_SYSTEM = ("You are Naim, an autonomous AI coding agent created by ABDESSEMED Mohamed. You work in the user's "
               "project with tools (files, shell commands, background processes, web, screen, iOS simulator, email). "
               "Decide the next action, then give a short final summary when the task is done.")


def _clean(messages):
    out = []
    for m in messages:
        if m.get("role") == "system":
            continue
        m = {k: v for k, v in m.items() if k in ("role", "content", "tool_calls", "tool_name")}
        if m.get("role") == "tool" and len(m.get("content") or "") > MAX_RESULT:
            m["content"] = m["content"][:MAX_RESULT] + "\n… (tronqué)"
        if m.get("role") == "user" and m.get("content", "").startswith("Voici la capture d'écran"):
            continue  # images are not kept
        out.append(m)
    return out


def record(agent, task, outcome, started):
    """Save one finished agent task. Called by the agent at the end of each run."""
    msgs = _clean(agent.messages[agent._task_idx:] if hasattr(agent, "_task_idx") else agent.messages)
    calls = [c["function"]["name"] for m in msgs for c in m.get("tool_calls") or []]
    if not calls:
        return None  # a plain answer without actions teaches nothing about acting
    errors = sum(1 for m in msgs if m.get("role") == "tool" and str(m.get("content", "")).startswith(("error", "denied")))
    left = [t for t in agent.todos if t["status"] not in ("done", "skipped")]
    trace = {
        "id": agent.run_id, "time": time.strftime("%Y-%m-%dT%H:%M"), "task": task[:2000],
        "project": agent.root.name, "model": agent.model, "outcome": outcome,
        "steps": len(calls), "tools": sorted(set(calls)), "errors": errors, "todos_left": len(left),
        "verified": getattr(agent, "_verified", None), "duration": round(time.time() - started),
        "rating": None, "messages": msgs,
        "tool_schemas": [t for t in agent.tools if not t["function"]["name"].startswith("mcp__")],
    }
    TRACES.mkdir(parents=True, exist_ok=True)
    old = TRACES / f"{agent.run_id}.json"
    if old.exists():  # same conversation continued: keep the user's rating
        try:
            trace["rating"] = json.loads(old.read_text()).get("rating")
        except ValueError:
            pass
    old.write_text(json.dumps(trace, ensure_ascii=False))
    return trace


def auto_good(t):
    return (t["outcome"] == "answer" and not t["todos_left"] and t.get("verified") is not False
            and t["errors"] <= max(2, t["steps"] // 4))


def is_good(t):
    """Bon (1): learned. Correct (0) or not rated: learned only if it finished cleanly. Mauvais (-1): never."""
    return t.get("rating") == 1 or (t.get("rating") in (None, 0) and auto_good(t))


def _load_all():
    out = []
    for f in sorted(TRACES.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            out.append(json.loads(f.read_text()))
        except (OSError, ValueError):
            pass
    return out


def summary(limit=60):
    traces = _load_all()
    good = [t for t in traces if is_good(t)]
    rows = [{k: t.get(k) for k in ("id", "time", "task", "project", "outcome", "steps", "tools", "errors", "todos_left",
                                    "verified", "duration", "rating", "shared")} | {"good": is_good(t), "auto_good": auto_good(t)}
            for t in traces[:limit]]
    return {"total": len(traces), "good": len(good), "rated_up": sum(t.get("rating") == 1 for t in traces),
            "rated_down": sum(t.get("rating") == -1 for t in traces), "goal": GOAL, "chat_up": chat_counts()[0],
            "chat_down": chat_counts()[1], "chat_ok": chat_counts()[2], "rated_ok": sum(t.get("rating") == 0 for t in traces), "traces": rows,
            "path": str(BASE), "exported": _export_info()}


CHAT_SYSTEM = ("You are Naim, an autonomous AI coding agent created by ABDESSEMED Mohamed. "
               "Answer the user directly and helpfully, in their language.")


def rate_chat(chat_id, messages, rating):
    """Save (Bon 1 / Correct 0 / Mauvais -1) or forget (no rating) one Chat-mode answer with the few messages before it.
    Only « Bon » answers are learned; « Mauvais » ones are kept as counter-examples (preference pairs, later)."""
    f = CHATS / f"{Path(str(chat_id)).name}.json"
    if rating not in (1, 0, -1):
        f.unlink(missing_ok=True)
        return True
    msgs = [{"role": m["role"], "content": str(m.get("content") or "")[:6000]} for m in messages or []
            if m.get("role") in ("user", "assistant") and m.get("content")][-4:]
    if not msgs or msgs[-1]["role"] != "assistant":
        return False
    CHATS.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"id": f.stem, "time": time.strftime("%Y-%m-%dT%H:%M"), "rating": rating, "messages": msgs},
                            ensure_ascii=False))
    return True


# automatic sorting before every training: the user's ratings stay the main signal, these rules only keep out what
# must never be learned, whatever the rating (so a training never needs a manual review)
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]+ ?")
ANNOUNCE_ONLY_RE = re.compile(r"^\W*(?:(?:d'accord|ok|très bien|parfait)[ ,.!]*)?(?:je m'en occupe|je (?:lance|crée|cherche|envoie|"
                              r"prépare)\b|(?:je vais|laisse-moi)\s+(?:\S+\s+){0,2}?(?:envoy|cré|lanc|cherch|lire|ouvr|fair|génér|prépar|"
                              r"regard|vérifi|modifi|écri|rédig|exécut|install))", re.I)
GREETING_RE = re.compile(r"^\W*(salut|bonjour|bonsoir|coucou|hello|hey|yo)\b[\w\s,!.']{0,20}$", re.I)
TEST_ROOTS = ("/private/tmp/", "/tmp/", "/private/var/folders/")


def no_emoji(text):
    return EMOJI_RE.sub("", text or "")


def chat_flaw(msgs):
    """Why a rated Chat answer must not be learned (None = fine)."""
    answer = next((m.get("content") or "" for m in reversed(msgs) if m["role"] == "assistant"), "").strip()
    asked = next((m.get("content") or "" for m in reversed(msgs) if m["role"] == "user"), "").strip()
    if not answer:
        return "réponse vide"
    if "<tool_call" in answer or "<function=" in answer:
        return "appel d'outil écrit en texte"
    if ANNOUNCE_ONLY_RE.search(answer) and len(answer) < 300 and "```" not in answer:
        return "annonce sans agir"
    if re.match(r"\W*avec plaisir\b", answer, re.I):
        return "réponse toute faite"
    if GREETING_RE.match(asked) and re.search(r"\bje suis \W*naim\b", answer, re.I):
        return "se présente sur un simple salut"
    return None


def task_flaw(t):
    """Why a finished agent task must not be learned (None = fine)."""
    if str(t.get("project") or "").startswith(TEST_ROOTS):
        return "tâche de test"
    final = next((m.get("content") or "" for m in reversed(t.get("messages") or []) if m.get("role") == "assistant"), "")
    if "<tool_call" in final:
        return "appel d'outil écrit en texte"
    return None


def _chat_examples():
    out = []
    for f in sorted(CHATS.glob("*.json")) if CHATS.exists() else []:
        try:
            c = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if c.get("rating") == 1:
            msgs = c["messages"]
            while msgs and msgs[0]["role"] != "user":
                msgs = msgs[1:]
            if len(msgs) >= 2 and not chat_flaw(msgs):
                msgs = [dict(m, content=no_emoji(m.get("content"))) if m["role"] == "assistant" else m for m in msgs]
                out.append({"messages": [{"role": "system", "content": CHAT_SYSTEM}] + msgs})
    return out


def chat_counts():
    up = down = ok = 0
    for f in CHATS.glob("*.json") if CHATS.exists() else []:
        try:
            r = json.loads(f.read_text()).get("rating")
        except (OSError, ValueError):
            continue
        up, down, ok = up + (r == 1), down + (r == -1), ok + (r == 0)
    return up, down, ok


def rate(run_id, rating):
    f = TRACES / f"{Path(run_id).name}.json"
    if not f.exists():
        return False
    t = json.loads(f.read_text())
    t["rating"] = rating if rating in (1, 0, -1) else None
    f.write_text(json.dumps(t, ensure_ascii=False))
    return True


def delete(run_id):
    f = TRACES / f"{Path(run_id).name}.json"
    if f.exists():
        f.unlink()
        return True
    return False


def clear_all(keep_rated=False):
    """Delete the recorded tasks (and the rated Chat answers). keep_rated: keep those the user rated. Returns the count."""
    n = 0
    for d in (TRACES, CHATS):
        for f in d.glob("*.json") if d.exists() else []:
            try:
                if keep_rated and json.loads(f.read_text()).get("rating") is not None:
                    continue
            except (OSError, ValueError):
                pass
            f.unlink(missing_ok=True)
            n += 1
    return n


def _short(m):
    """Compact text of one message for the step context."""
    if m.get("tool_calls"):
        return "Naim → " + "; ".join(f"{c['function']['name']}({json.dumps(c['function'].get('arguments') or {}, ensure_ascii=False)[:160]})"
                                     for c in m["tool_calls"])
    if m["role"] == "tool":
        return f"Résultat {m.get('tool_name', '')} : {str(m.get('content', ''))[:400]}"
    return f"{m['role']} : {str(m.get('content', ''))[:300]}"


def _steps(trace):
    """One training example per assistant decision: task + summary of what was done + recent results -> action."""
    msgs, task = trace["messages"], trace["messages"][0]["content"] if trace["messages"] else trace["task"]
    out = []
    for i, m in enumerate(msgs):
        if m["role"] != "assistant" or i == 0:
            continue
        done = [_short(x) for x in msgs[1:i]]
        recent = "\n".join(done)[-STEP_CONTEXT:]
        prompt = task[:800] + (f"\n\n[Déjà fait]\n{recent}" if recent else "")
        target = {"role": "assistant", "content": no_emoji(m.get("content"))}
        if m.get("tool_calls"):
            target["tool_calls"] = [{"type": "function", "function": {"name": c["function"]["name"],
                                                                       "arguments": c["function"].get("arguments") or {}}}
                                    for c in m["tool_calls"]]
        out.append({"messages": [{"role": "system", "content": STEP_SYSTEM}, {"role": "user", "content": prompt}, target]})
    return out


def export(valid_ratio=0.1):
    """Write the dataset files from the good tasks. Returns counts and the folder."""
    good = [t for t in _load_all() if is_good(t) and not task_flaw(t)]
    chats = _chat_examples()
    if not good and not chats:
        raise ValueError("aucune tâche réussie à exporter pour l'instant")
    DATASET.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(42)
    steps = [ex for t in good for ex in _steps(t)] + chats  # + the Chat answers rated 👍
    rnd.shuffle(steps)
    n_valid = max(1, int(len(steps) * valid_ratio)) if len(steps) > 5 else 0
    with open(DATASET / "steps_valid.jsonl", "w") as f:
        for ex in steps[:n_valid]:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    with open(DATASET / "steps_train.jsonl", "w") as f:
        for ex in steps[n_valid:]:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    with open(DATASET / "full.jsonl", "w") as f:
        for t in good:
            f.write(json.dumps({"messages": t["messages"], "tools": t["tool_schemas"]}, ensure_ascii=False) + "\n")
    info = {"tasks": len(good), "chat": len(chats), "steps": len(steps), "train": len(steps) - n_valid, "valid": n_valid,
            "time": time.strftime("%Y-%m-%d %H:%M"), "path": str(DATASET),
            "hash": hashlib.md5("".join(sorted(t["id"] for t in good)).encode()).hexdigest()[:8]}
    (DATASET / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))
    return info


def _export_info():
    try:
        return json.loads((DATASET / "info.json").read_text())
    except (OSError, ValueError):
        return None
