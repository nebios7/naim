"""Share rated agent tasks with the Naim project, to train the next version — only with the user's consent.

Nothing leaves the Mac unless the user enabled « Partager mes tâches notées » (off by default). Each shared task is
first cleaned on the Mac (scrub): secrets, email addresses, phone numbers and personal paths are removed, long outputs
are cut. The user can see the exact payload before it is sent (preview) and ask for the deletion of everything sent
from this installation (delete_all). The installation is identified by a random code, never by a name or an email.

The collection server keeps the Hugging Face token; the app only knows its public URL. Ratings are NOT trusted as-is:
the server and the curation script check them against objective signals (see tools/curate_feedback.py).
"""
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
import uuid

import extensions as ext
import learning

DEFAULT_URL = "https://naim-feedback.contact-abdessemed.workers.dev"
APP_VERSION = "3.0"
MAX_TEXT = 8000      # characters kept per message / tool argument
MAX_RESULT = 2000    # characters kept per tool result

SECRET_PATTERNS = [
    (re.compile(r"\b(hf_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|"
                r"sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
                r"AIza[0-9A-Za-z_-]{30,}|glpat-[A-Za-z0-9_-]{20,})\b"), "[SECRET]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[CLÉ PRIVÉE]"),
    (re.compile(r"(?i)\b(password|passwd|mot de passe|secret|api[_-]?key|token|authorization)\b(\s*[:=]\s*|\s+)(\"[^\"]{3,}\"|'[^']{3,}'|\S{6,})"),
     r"\1\2[SECRET]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{16,}"), "Bearer [SECRET]"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"(?<![\w/])(?:\+33\s?|0)[1-9](?:[\s.-]?\d{2}){4}\b"), "[TÉLÉPHONE]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[NUMÉRO]"),              # card / account numbers
    (re.compile(r"/Users/[^/\s\"']+"), "~"),
    (re.compile(r"/home/[^/\s\"']+"), "~"),
    (re.compile(r"[A-Za-z0-9+/]{300,}={0,2}"), "[DONNÉES BINAIRES]"),  # base64 blobs (images…)
]


def scrub(text, limit=MAX_TEXT):
    text = str(text or "")
    for rx, repl in SECRET_PATTERNS:
        text = rx.sub(repl, text)
    return text if len(text) <= limit else text[:limit] + "\n… (coupé)"


def _scrub_obj(obj, limit=MAX_TEXT):
    if isinstance(obj, str):
        return scrub(obj, limit)
    if isinstance(obj, list):
        return [_scrub_obj(x, limit) for x in obj]
    if isinstance(obj, dict):
        return {k: _scrub_obj(v, limit) for k, v in obj.items()}
    return obj


def install_id():
    f = ext.HOME / "install_id"
    try:
        return f.read_text().strip()
    except OSError:
        iid = uuid.uuid4().hex
        ext.HOME.mkdir(parents=True, exist_ok=True)
        f.write_text(iid)
        return iid


def payload(trace):
    """Exactly what would be sent for one rated task (already cleaned)."""
    msgs = []
    for m in trace.get("messages", []):
        m2 = {"role": m.get("role"), "content": scrub(m.get("content"), MAX_RESULT if m.get("role") == "tool" else MAX_TEXT)}
        if m.get("tool_name"):
            m2["tool_name"] = m["tool_name"]
        if m.get("tool_calls"):
            m2["tool_calls"] = [{"function": {"name": c["function"]["name"],
                                              "arguments": _scrub_obj(c["function"].get("arguments") or {})}}
                                for c in m["tool_calls"]]
        msgs.append(m2)
    iid = install_id()
    return {"id": hashlib.sha256(f"{iid}:{trace['id']}".encode()).hexdigest()[:24], "install": iid,
            "app": APP_VERSION, "time": trace.get("time"), "rating": trace.get("rating"),
            "signals": {k: trace.get(k) for k in ("outcome", "steps", "errors", "todos_left", "verified", "duration")},
            "tools": trace.get("tools", []), "task": scrub(trace.get("task", ""), 2000), "messages": msgs}


def _post(url, body, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json",
                                                                               "User-Agent": f"Naim/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def pending():
    """Rated tasks not shared yet (only rated ones: a rating is the user's explicit choice for that task)."""
    out = []
    for f in sorted(learning.TRACES.glob("*.json")):
        try:
            t = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if t.get("rating") in (1, 0, -1) and not t.get("shared"):  # Bon / Correct / Mauvais
            out.append(t)
    return out


def _mark(trace_id, status):
    f = learning.TRACES / f"{trace_id}.json"
    t = json.loads(f.read_text())
    t["shared"] = status
    f.write_text(json.dumps(t, ensure_ascii=False))


STATE = {"sending": False, "last": None, "error": None}


def send_pending(url=None):
    """Send every rated, not-yet-shared task. Returns {"sent": n, "error": ...}."""
    url = (url or DEFAULT_URL).rstrip("/")
    items = pending()
    if not items:
        return {"sent": 0}
    STATE.update(sending=True, error=None)
    sent = 0
    try:
        for i in range(0, len(items), 10):
            batch = items[i:i + 10]
            r = _post(url + "/api/submit", {"install": install_id(), "items": [payload(t) for t in batch]})
            accepted = set(r.get("accepted", []))
            for t in batch:
                if payload(t)["id"] in accepted:
                    _mark(t["id"], time.strftime("%Y-%m-%d %H:%M"))
                    sent += 1
            if r.get("error"):
                STATE["error"] = r["error"]
                break
    except (urllib.error.URLError, OSError, ValueError) as e:
        STATE["error"] = f"serveur de collecte injoignable ({e})"
    finally:
        STATE.update(sending=False, last=time.strftime("%Y-%m-%d %H:%M"))
    return {"sent": sent, "error": STATE["error"]}


def send_in_background(url=None):
    if not STATE["sending"]:
        threading.Thread(target=send_pending, args=(url,), daemon=True).start()


def delete_all(url=None):
    """Ask the collection server to delete everything sent from this installation."""
    url = (url or DEFAULT_URL).rstrip("/")
    r = _post(url + "/api/delete", {"install": install_id()})
    if r.get("ok"):
        for f in learning.TRACES.glob("*.json"):
            try:
                t = json.loads(f.read_text())
                if t.get("shared"):
                    t["shared"] = None
                    f.write_text(json.dumps(t, ensure_ascii=False))
            except (OSError, ValueError):
                pass
    return r
