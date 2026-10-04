"""Download Naim's model (GGUF + vision projector) into ~/.naim/models, with progress.

The model is reserved for the Naim application: it is not freely downloadable. Naim's server gives each
installation (its random identifier, the same as for the voluntary feedback sharing) a short-lived download link.

Used by the welcome screen (« Télécharger le modèle ») and by install.sh. Files are written as *.part and renamed
when complete, so an interrupted download never leaves a broken model behind; a restart resumes where it stopped.
"""
import json
import threading
import time
import urllib.error
import urllib.request

import feedback_share
import llamacpp

SERVER = feedback_share.DEFAULT_URL  # Naim's server (Cloudflare): checks the installation, then redirects
FILES = [("naim-Q4_K_M.gguf", "modèle Naim"), ("naim-mmproj-f16.gguf", "vision"), ("llama-server-naim", "moteur Naim")]
STATE = {"running": False, "file": "", "label": "", "done": 0, "total": 0, "finished": False, "error": None}


def missing():
    return [(f, label) for f, label in FILES if not (llamacpp.MODELS / f).exists()
            and not (f == "llama-server-naim" and STATE.get("engine_absent"))]


def _fetch(name, label):
    dest = llamacpp.MODELS / name
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    url = f"{SERVER}/api/model/{name}?install={feedback_share.install_id()}"
    req = urllib.request.Request(url, headers={"User-Agent": f"Naim/{feedback_share.APP_VERSION}",
                                               **({"Range": f"bytes={have}-"} if have else {})})
    try:
        r = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:  # refused by Naim's server: say why (blocked, limit of the day…)
        try:
            msg = json.loads(e.read()).get("error")
        except (ValueError, OSError):
            msg = None
        raise IOError(msg or f"téléchargement refusé ({e.code})") from None
    with r:
        if have and r.status != 206:  # server ignored the range: start over
            have = 0
        total = have + int(r.headers.get("Content-Length") or 0)
        STATE.update(file=name, label=label, done=have, total=total)
        with open(part, "ab" if have else "wb") as out:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                STATE["done"] += len(chunk)
    if total and part.stat().st_size < total:
        raise IOError(f"téléchargement incomplet de {name}")
    part.rename(dest)
    if name == "llama-server-naim":
        dest.chmod(0o755)  # the engine is a program


def save_version():
    """Write ~/.naim/models/naim_version.json (the version just downloaded), shown in Personnaliser › À propos."""
    try:
        req = urllib.request.Request(f"{SERVER}/api/model-version", headers={"User-Agent": f"Naim/{feedback_share.APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            v = json.load(r)
        if v.get("name"):
            (llamacpp.MODELS / "naim_version.json").write_text(json.dumps(v))
    except (OSError, ValueError):
        pass  # not essential


def _run():
    try:
        llamacpp.MODELS.mkdir(parents=True, exist_ok=True)
        for name, label in missing():
            for attempt in range(3):
                try:
                    _fetch(name, label)
                    break
                except Exception as e:
                    if attempt == 2:
                        if name == "llama-server-naim" and llamacpp.gguf_arch(llamacpp.model_files()[0]) != "naim":
                            STATE["engine_absent"] = True  # not published yet: the model works with llama.cpp
                            break  # the engine is only needed for a model in Naim's own architecture
                        raise
                    STATE["error"] = f"nouvelle tentative ({e})"
                    time.sleep(3)
        save_version()
        STATE.update(finished=True, error=None)
    except Exception as e:
        STATE["error"] = str(e)[:300]
    finally:
        STATE["running"] = False


def start():
    if STATE["running"] or not missing():
        STATE["finished"] = not missing()
        return STATE
    STATE.update(running=True, finished=False, error=None, done=0, total=0)
    threading.Thread(target=_run, daemon=True, name="naim-model-download").start()
    return STATE
