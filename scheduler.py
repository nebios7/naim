"""Scheduled tasks for Naim: run a prompt (chat or agent) once, daily, on some weekdays or every N minutes.

Tasks live in DATA/schedules.json. A background thread started by the UI server checks them every 30 s,
runs the due ones with the user's current settings, saves each run as a conversation (so it shows up in
the sidebar) and sends a macOS notification. Tasks run while the Naim app (or `naim --web`) is running.
"""
import json
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import extensions as ext

FILE = ext.DATA / "schedules.json"
_lock = threading.Lock()
_running = set()
PENDING = {}          # approvals waiting for the user: id -> {task, name, action, detail, time, event, allow}
ASK_TIMEOUT = 15 * 60  # an unanswered question is refused after this delay (the task goes on without it)
POLICIES = ("auto", "ask", "safe")


def load():
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return []


def save(tasks):
    ext.DATA.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))


def next_run(task, after=None):
    """Next datetime (ISO string) at which the task must run, or None."""
    now = after or datetime.now()
    s = task.get("schedule", {})
    kind = s.get("type", "once")
    if kind == "once":
        at = datetime.fromisoformat(s["at"]) if s.get("at") else None
        return at.isoformat(timespec="minutes") if at and at > now and not task.get("last_run") else None
    if kind == "interval":
        minutes = max(5, int(s.get("every_minutes", 60)))
        base = datetime.fromisoformat(task["last_run"]) if task.get("last_run") else now
        nxt = base + timedelta(minutes=minutes)
        return max(nxt, now + timedelta(seconds=30)).isoformat(timespec="minutes")
    hh, mm = (int(x) for x in str(s.get("time", "09:00")).split(":")[:2])
    days = s.get("days") if kind == "weekly" else list(range(7))  # 0 = Monday
    for d in range(0, 8):
        cand = (now + timedelta(days=d)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if cand > now and cand.weekday() in (days or []):
            return cand.isoformat(timespec="minutes")
    return None


def upsert(data):
    with _lock:
        tasks = load()
        task = next((t for t in tasks if t["id"] == data.get("id")), None)
        if task is None:
            task = {"id": uuid.uuid4().hex[:10], "created": datetime.now().isoformat(timespec="minutes"), "runs": []}
            tasks.append(task)
        for k in ("name", "prompt", "mode", "project", "model", "schedule", "enabled", "policy", "emails"):
            if k in data:
                task[k] = data[k]
        task.setdefault("enabled", True)
        task["next_run"] = next_run(task) if task["enabled"] else None
        save(tasks)
        return task


def delete(task_id):
    with _lock:
        save([t for t in load() if t["id"] != task_id])


def ask(task, action, detail):
    """Ask the user (macOS notification + card in Planifier) and wait for the answer. False after ASK_TIMEOUT."""
    aid = uuid.uuid4().hex[:10]
    entry = {"id": aid, "task": task["id"], "name": task.get("name") or "Tâche planifiée", "action": action,
             "detail": detail[:4000], "time": datetime.now().isoformat(timespec="seconds"), "event": threading.Event(),
             "allow": False}
    PENDING[aid] = entry
    import computer
    computer.notify(f"Naim · {entry['name']}", f"{action} — ouvre Naim › Planifier pour autoriser", sound=True,
                    target={"view": "schedules"})
    entry["event"].wait(ASK_TIMEOUT)
    PENDING.pop(aid, None)
    return entry["allow"]


def answer(aid, allow):
    entry = PENDING.get(aid)
    if not entry:
        return False
    entry["allow"] = bool(allow)
    entry["event"].set()
    return True


def pending():
    return [{k: v for k, v in e.items() if k not in ("event", "allow")} for e in PENDING.values()]


def _collect(events):
    """Turn agent events into the same message shape the UI stores (steps, todos, final text)."""
    reply = {"role": "assistant", "content": "", "steps": [], "time": int(time.time() * 1000)}
    last = None
    for ev in events:
        t = ev["type"]
        if t == "tool" and ev["name"] != "update_todos":
            a = ev.get("args") or {}
            meta = {"lines": a["content"].count("\n") + 1} if isinstance(a.get("content"), str) else {}
            last = {"type": "tool", "name": ev["name"], "output": "",
                    "args": {k: a.get(k) for k in ("path", "command", "pattern", "target", "id", "query", "url", "name")} | meta}
            reply["steps"].append(last)
        elif t == "tool_result" and last is not None and ev["name"] != "update_todos":
            last["result"] = ev["result"][-3000:]
        elif t == "output" and last is not None:
            last["output"] = (last["output"] + ev["text"])[-8000:]
        elif t == "todos":
            reply["todos"] = ev["todos"]
        elif t in ("process", "process_stopped", "verify"):
            reply["steps"].append({k: v for k, v in ev.items()})
        elif t == "note":
            reply["steps"].append({"type": "note", "text": ev["text"]})
        elif t == "answer":
            reply["content"] = ev["text"]
    return reply


def run_task(task, settings, chat_fn, agent_cls, chat_prompt):
    """Execute one task now and store the result as a conversation. Returns the conversation id."""
    if task["id"] in _running:
        return None
    _running.add(task["id"])
    started = datetime.now()
    conv_id = "sch" + uuid.uuid4().hex[:10]
    mode = task.get("mode", "agent")
    model = task.get("model") or settings.get("model", "naim")
    project = task.get("project") or settings.get("project") or str(Path.home())
    # addresses written by the user in the task itself (prompt or its email field) are allowed recipients
    body = {"settings": settings, "model": model, "mode": mode,
            "email_allow_extra": task["prompt"] + " " + str(task.get("emails") or "")}
    policy = task.get("policy") if task.get("policy") in POLICIES else "ask"
    status, content = "ok", ""
    try:
        from server import model_options, agent_settings  # late import: avoid a cycle at module load
        options, extra = model_options(body)
        if mode == "agent":
            events = []
            agent = agent_cls(project, model, auto_yes=True, emit=events.append, options=options, extra_system=extra,
                              run_id=conv_id, scheduled=policy, approver=lambda action, detail: ask(task, action, detail),
                              **agent_settings(body))
            agent.run(task["prompt"])
            reply = _collect(events)
        else:
            system = chat_prompt + (f"\n\n{ext.memory_prompt()}" if ext.memory_prompt() else "") + (f"\n\nUser instructions:\n{extra}" if extra else "")
            msg = chat_fn(model, [{"role": "system", "content": system}, {"role": "user", "content": task["prompt"]}], options=options)
            reply = {"role": "assistant", "content": msg.get("content", ""), "steps": [], "time": int(time.time() * 1000)}
        content = reply["content"]
    except Exception as e:
        status, content = "error", f"⚠ La tâche planifiée a échoué : {e}"
        reply = {"role": "assistant", "content": content, "steps": [], "time": int(time.time() * 1000)}
    finally:
        _running.discard(task["id"])
    conv = {"id": conv_id, "title": f"⏱ {task.get('name') or task['prompt'][:40]} · {started:%d/%m %H:%M}", "mode": mode,
            "project": project if mode == "agent" else "", "scheduled": task["id"], "updated": time.time(),
            "messages": [{"role": "user", "content": task["prompt"], "time": int(started.timestamp() * 1000)}, reply]}
    (ext.DATA / "conversations").mkdir(parents=True, exist_ok=True)
    (ext.DATA / "conversations" / f"{conv_id}.json").write_text(json.dumps(conv, ensure_ascii=False))
    with _lock:
        tasks = load()
        for t in tasks:
            if t["id"] == task["id"]:
                t["last_run"] = started.isoformat(timespec="minutes")
                t["last_status"], t["last_conv"] = status, conv_id
                t["runs"] = ([{"at": t["last_run"], "status": status, "conv": conv_id}] + t.get("runs", []))[:20]
                if t.get("schedule", {}).get("type") == "once":
                    t["enabled"] = False
                t["next_run"] = next_run(t) if t.get("enabled") else None
        save(tasks)
    if settings.get("notify", True):
        import computer
        computer.notify(f"Naim · {task.get('name') or 'Tâche planifiée'}", (content or "")[:150], target={"conv": conv_id})
    return conv_id


def start_loop(get_settings, chat_fn, agent_cls, chat_prompt):
    def loop():
        while True:
            try:
                now = datetime.now()
                for t in load():
                    if t.get("enabled") and t.get("next_run") and datetime.fromisoformat(t["next_run"]) <= now:
                        threading.Thread(target=run_task, args=(t, get_settings(), chat_fn, agent_cls, chat_prompt),
                                         daemon=True).start()
                        with _lock:  # push next_run forward right away so it is not started twice
                            tasks = load()
                            for x in tasks:
                                if x["id"] == t["id"]:
                                    x["next_run"] = next_run(x, after=now + timedelta(seconds=61))
                            save(tasks)
            except Exception:
                pass
            time.sleep(30)
    threading.Thread(target=loop, daemon=True, name="naim-scheduler").start()


def running_ids():
    return sorted(_running)
