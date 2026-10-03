"""Naim feedback collection server (Hugging Face Space).

Receives the rated tasks that Naim users chose to share, checks them, cleans them again, applies limits, and stores
them in a PRIVATE Hugging Face dataset. The HF token lives only here (Space secret HF_TOKEN), never in the app.

Environment:
  HF_TOKEN       write token for the dataset (Space secret)
  DATASET_REPO   private dataset, default "redhamohamed/naim-feedback"
Without HF_TOKEN (local test), files are only written to ./collecte.
"""
import json
import os
import re
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

ROOT = Path(os.environ.get("COLLECT_DIR", "collecte"))
ROOT.mkdir(parents=True, exist_ok=True)
REPO = os.environ.get("DATASET_REPO", "redhamohamed/naim-feedback")
LIMIT_INSTALL = 50      # items per installation per day
LIMIT_IP = 300          # items per IP address per day
MAX_ITEM = 300_000      # bytes per item
MAX_BATCH = 20

scheduler = None
if os.environ.get("HF_TOKEN"):
    from huggingface_hub import CommitScheduler
    scheduler = CommitScheduler(repo_id=REPO, repo_type="dataset", folder_path=ROOT, path_in_repo="data",
                                every=10, private=True, token=os.environ["HF_TOKEN"])
lock = scheduler.lock if scheduler else threading.Lock()

SECRETS = [
    re.compile(r"\b(hf_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{20,}|"
               r"xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|glpat-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
]
HEX32 = re.compile(r"^[0-9a-f]{32}$")
counts = defaultdict(int)     # (day, key) -> items accepted
seen = set()                  # item ids accepted today (duplicates)
app = FastAPI(title="Naim — collecte des tâches partagées")


def day():
    return time.strftime("%Y-%m-%d")


def clean(obj):
    """Second cleaning pass (the app already cleaned): secrets and emails."""
    if isinstance(obj, str):
        for rx in SECRETS:
            obj = rx.sub("[RETIRÉ]", obj)
        return obj
    if isinstance(obj, list):
        return [clean(x) for x in obj]
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    return obj


def check(item, install):
    if not isinstance(item, dict):
        return "format invalide"
    if item.get("install") != install:
        return "identifiant d'installation incohérent"
    if item.get("rating") not in (1, -1):
        return "note manquante"
    msgs = item.get("messages")
    if not isinstance(msgs, list) or not 2 <= len(msgs) <= 400:
        return "messages invalides"
    if not any(m.get("tool_calls") for m in msgs if isinstance(m, dict)):
        return "tâche sans action (rien à apprendre)"
    if len(json.dumps(item)) > MAX_ITEM:
        return "tâche trop volumineuse"
    if not isinstance(item.get("signals"), dict):
        return "signaux manquants"
    return None


def store(name, record):
    with lock:
        with open(ROOT / name, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


@app.get("/", response_class=PlainTextResponse)
def home():
    return "Naim — serveur de collecte des tâches partagées (volontaires, nettoyées, anonymes). POST /api/submit, /api/delete"


@app.post("/api/submit")
async def submit(request: Request):
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"error": "JSON invalide"}, 400)
    install = str(body.get("install", ""))
    items = body.get("items") or []
    if not HEX32.match(install) or not isinstance(items, list) or len(items) > MAX_BATCH:
        return JSONResponse({"error": "requête invalide"}, 400)
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    d = day()
    accepted, rejected, error = [], [], None
    for item in items:
        iid = str(item.get("id", ""))[:64] if isinstance(item, dict) else ""
        if counts[(d, install)] >= LIMIT_INSTALL or counts[(d, ip)] >= LIMIT_IP:
            error = "limite quotidienne atteinte, réessaie demain"
            break
        if (d, iid) in seen:
            accepted.append(iid)  # already stored: acknowledge without duplicating
            continue
        why = check(item, install)
        if why:
            rejected.append({"id": iid, "reason": why})
            continue
        record = {**clean(item), "received": time.strftime("%Y-%m-%dT%H:%M:%S"), "ip_hash": hash((ip, d)) & 0xffffffff}
        store(f"submissions-{d}.jsonl", record)
        seen.add((d, iid))
        counts[(d, install)] += 1
        counts[(d, ip)] += 1
        accepted.append(iid)
    return {"accepted": accepted, "rejected": rejected, "error": error}


@app.post("/api/delete")
async def delete(request: Request):
    body = await request.json()
    install = str(body.get("install", ""))
    if not HEX32.match(install):
        return JSONResponse({"error": "identifiant invalide"}, 400)
    # recorded here, applied by the curation script before every training (the data is never used afterwards)
    store("deletions.jsonl", {"install": install, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "id": uuid.uuid4().hex})
    return {"ok": True}
