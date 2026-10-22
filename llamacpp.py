"""llama.cpp backend for Naim: a managed `llama-server` with prompt-cache checkpoints and vision.

Ollama re-reads the whole prompt at every call for Naim's hybrid architecture (no prefix cache), which
makes agent steps slow. llama-server keeps context checkpoints, so each step only processes the new
tokens, and it loads the vision projector (mmproj) so Naim sees images itself.

`chat()` takes and returns messages in the same shape as Ollama's /api/chat, so the agent and the UI
server do not care which backend answers.
"""
import atexit
import http.client
import json
import re
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("NAIM_HOME", Path.home() / ".naim"))
MODELS = HOME / "models"
PORT = int(os.environ.get("NAIM_LLAMA_PORT", "8081"))
URL = f"http://127.0.0.1:{PORT}"
LOG = HOME / "llama-server.log"



ERRLOG = HOME / "cache" / "erreurs-moteur.log"


def note_error(kind, text):
    """What went wrong with the engine, kept (last ~200 KB) so that the cause can be found afterwards."""
    try:
        ERRLOG.parent.mkdir(parents=True, exist_ok=True)
        if ERRLOG.exists() and ERRLOG.stat().st_size > 200_000:
            ERRLOG.write_text(ERRLOG.read_text(errors="replace")[-100_000:])
        with ERRLOG.open("a") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {kind}\n{text[:4000]}\n")
    except OSError:
        pass


def _repair(raw):
    """The usual ways a small model breaks the JSON of its arguments, mended: a backslash that escapes nothing
    (a Windows path, a regex digit class), and a call cut just before its closing quote and brace."""
    fixed = re.sub(r"\\(.)", lambda m: m.group(0) if m.group(1) in '"\\/bfnrtu' else "\\\\" + m.group(1), raw, flags=re.S)
    for tail in ("", '"}', "}", '"]}'):
        try:
            return json.loads(fixed + tail, strict=False), bool(tail)
        except json.JSONDecodeError:
            continue
    return None, False


def _args(raw):
    """A tool call's arguments. A raw line break or tab inside a string (frequent in code) is accepted; arguments
    that still cannot be read are reported instead of becoming an empty call that fails without saying why."""
    if not isinstance(raw, str):
        return raw or {}
    try:
        return json.loads(raw or "{}", strict=False)
    except json.JSONDecodeError as e:
        args, cut = _repair(raw)
        if isinstance(args, dict):
            if cut:  # it ended too early: the content may be incomplete, the tool says so to the model
                args["_maybe_cut"] = True
            return args
        note_error("arguments illisibles", f"{e.msg} at {e.pos}\n{raw[max(0, e.pos - 300):e.pos + 300]}")
        return {"_unreadable": f"{e.msg} at character {e.pos} of {len(raw)}"}

def model_files():
    gguf = Path(os.environ.get("NAIM_GGUF", MODELS / "naim-Q4_K_M.gguf"))
    mmproj = Path(os.environ.get("NAIM_MMPROJ", MODELS / "naim-mmproj-f16.gguf"))
    return gguf, (mmproj if mmproj.exists() else None)


NAIM_BIN = MODELS / "llama-server-naim"  # Naim's own llama.cpp build: it knows the « naim » architecture


def gguf_arch(path):
    """general.architecture of a GGUF file (read from its header), or None."""
    import struct
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return None
            f.read(4 + 8 + 8)  # version, tensor count, key count
            for _ in range(64):
                n = struct.unpack("<Q", f.read(8))[0]
                key = f.read(n).decode(errors="replace")
                vtype = struct.unpack("<I", f.read(4))[0]
                if vtype != 8:  # only strings matter here; general.architecture comes first
                    return None
                n = struct.unpack("<Q", f.read(8))[0]
                val = f.read(n).decode(errors="replace")
                if key == "general.architecture":
                    return val
    except (OSError, struct.error):
        return None
    return None


def binary():
    if NAIM_BIN.exists() and os.access(NAIM_BIN, os.X_OK):
        return str(NAIM_BIN)
    if gguf_arch(model_files()[0]) == "naim":
        return None  # a stock llama.cpp cannot open it: the Naim engine must be downloaded first
    return shutil.which("llama-server") or next(
        (p for p in ("/opt/homebrew/bin/llama-server", "/usr/local/bin/llama-server") if Path(p).exists()), None)


def available():
    gguf, _ = model_files()
    return gguf.exists() and binary() is not None


_HW = None


def hardware():
    """RAM, chip and GPU cores of this machine, and the recommended number of parallel slots (cached)."""
    global _HW
    if _HW is not None:
        return _HW
    def sysctl(k):
        r = subprocess.run(["sysctl", "-n", k], capture_output=True, text=True)
        return r.stdout.strip()
    try:
        ram = int(sysctl("hw.memsize") or 0) / 2**30
    except ValueError:
        ram = 0
    chip = sysctl("machdep.cpu.brand_string") or "?"
    gpu = 0
    try:
        out = subprocess.run(["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True, timeout=15).stdout
        import re as _re
        m = _re.search(r"Total Number of Cores:\s*(\d+)", out)
        gpu = int(m.group(1)) if m else 0
    except Exception:
        pass
    # each 32k slot costs ~1.1 GB on top of the model (~6 GB); keep 40 % of the RAM for the system and other apps
    by_ram = max(1, int((ram * 0.6 - 6) / 1.1)) if ram else 1
    by_gpu = 2 if gpu <= 10 else 3 if gpu <= 20 else 4 if gpu <= 40 else 6
    rec = 1 if ram < 16 else max(1, min(by_ram, by_gpu if gpu else 2, 8))
    _HW = {"ram_gb": round(ram), "chip": chip, "gpu_cores": gpu, "recommended": rec}
    return _HW


def slots_for(value):
    """Number of llama.cpp slots for the setting value ("auto" or a number)."""
    if str(value or "1").lower() == "auto":
        return hardware()["recommended"]
    try:
        return max(1, min(int(value), 8))
    except ValueError:
        return 1


DEFAULT_CFG = {"gpu_layers": 99, "threads": 0, "batch": 512, "kv_type": "f16", "checkpoints": 16, "parallel": 1}
CONFIG = dict(DEFAULT_CFG)  # updated from the app settings (Personnaliser → Moteur)


BLOCKED = None  # message while the automatic training runs (autotrain.py): the engine must not start


class Server:
    """One llama-server. The main one (port 8081) has no vision: then what its slots read can be saved to disk
    (llama.cpp refuses it with --mmproj) and Naim starts in a second. Images go to a second one, with vision, started
    only when a message has one and stopped after 5 idle minutes (VISION below)."""

    def __init__(self, port=PORT, vision=False):
        self.proc, self.ctx, self.lock, self.error, self.cfg = None, None, threading.Lock(), None, None
        self.port, self.url, self.vision, self.used = port, f"http://127.0.0.1:{port}", vision, 0.0

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def healthy(self):
        try:
            with urllib.request.urlopen(self.url + "/health", timeout=2) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def ensure(self, ctx=16384, timeout=180):
        """Start llama-server for Naim (or restart it with a new context size); wait until it is ready."""
        if BLOCKED:  # the automatic training uses the GPU
            raise RuntimeError(BLOCKED)
        for private in ("autotrain", "voicetrain"):  # a training in its own window (Naim reopened meanwhile): engine off
            try:
                mod = __import__(private)
            except ImportError:
                continue
            if (msg := mod.training_lock()):
                raise RuntimeError(msg)
        with self.lock:
            cfg = dict(CONFIG)
            if self.running and self.ctx == ctx and self.cfg == cfg and self.healthy():
                return
            if not self.running and self.healthy():
                # another Naim process (the app, the web UI, a script) already runs llama-server: share it
                self.ctx = self.ctx or ctx
                return
            self.stop()
            gguf, mmproj = model_files()
            exe = binary()
            if not exe or not gguf.exists():
                self.error = "llama-server ou le modèle GGUF de Naim est introuvable"
                raise RuntimeError(self.error)
            _unload_from_ollama()  # never keep Naim twice in memory
            try:  # nor the MLX engine (optional, see mlxengine.py)
                import mlxengine
                mlxengine.SERVER.stop()
            except ImportError:
                pass
            # parallel slots (sub-agents working at the same time): llama.cpp splits -c between them,
            # so each slot keeps the full context
            slots = slots_for(cfg.get("parallel"))
            if self.vision:
                slots = 1  # the images engine: one request at a time
            elif hardware()["ram_gb"] >= 16:
                # its own slot for each kind of work, so that none overwrites what another has already read:
                # 0 = Chat, 1 = Agent (their instructions and tools differ: ~6k and ~10k tokens to read), last =
                # background jobs (memory, summaries). Sub-agents get the slots in between.
                slots = max(slots, 3)
            cmd = [exe, "-m", str(gguf), "--host", "127.0.0.1", "--port", str(self.port), "-c", str(ctx * slots),
                   # a checkpoint every 2048 tokens (default 8192): a new task re-reads only what follows Naim's fixed
                   # instructions (~7k tokens shared by every task), not the whole prompt; 16 kept (50 MB each)
                   "--jinja", "--ctx-checkpoints", str(max(int(cfg["checkpoints"]), 16)), "--checkpoint-every-n-tokens", "2048",
                   "-ngl", str(cfg["gpu_layers"]),
                   "-b", str(cfg["batch"]), "-np", str(slots), "--no-webui"]
            if int(cfg.get("threads") or 0) > 0:
                cmd += ["-t", str(cfg["threads"])]
            # flash attention: measured on an M4 with Naim's Agent prompt, a new conversation reads its instructions
            # 1.7× faster (85 s instead of 144 s) and writes 1.5× faster (8.8 instead of 5.9 tokens/s), same memory
            cmd += ["-fa", "on"]
            if cfg.get("kv_type") in ("q8_0", "q4_0"):
                cmd += ["-ctk", cfg["kv_type"], "-ctv", cfg["kv_type"]]
            if self.vision:
                if not mmproj:
                    self.error = "la vision de Naim (mmproj) est introuvable"
                    raise RuntimeError(self.error)
                cmd += ["--mmproj", str(mmproj)]
            else:
                SLOTS_DIR.mkdir(parents=True, exist_ok=True)
                cmd += ["--slot-save-path", str(SLOTS_DIR)]  # what a slot has read, saved to disk (see warm_prefix)
            HOME.mkdir(parents=True, exist_ok=True)
            log = open(LOG, "a")
            log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start: {' '.join(cmd)}\n")
            log.flush()
            self.proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         start_new_session=True)
            self.ctx, self.cfg, self.error = ctx, cfg, None
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self.proc.poll() is not None:
                    self.error = "llama-server s'est arrêté au démarrage : " + LOG.read_text()[-600:]
                    raise RuntimeError(self.error)
                if self.healthy():
                    return
                time.sleep(0.5)
            self.error = "llama-server ne répond pas"
            raise RuntimeError(self.error)

    def stop(self):
        if self.running:
            try:
                os.killpg(self.proc.pid, 15)
                self.proc.wait(5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(self.proc.pid, 9)
                except ProcessLookupError:
                    pass
        self.proc = None

    def status(self):
        gguf, mmproj = model_files()
        return {"available": available(), "running": self.running or self.healthy(), "ctx": self.ctx, "vision": mmproj is not None,
                "model": str(gguf), "error": self.error, "config": self.cfg or CONFIG, "port": PORT,
                "hardware": hardware(), "slots": slots_for((self.cfg or CONFIG).get("parallel")),
                "binary": binary() is not None, "gguf": gguf.exists()}

    def log_tail(self, n=60):
        try:
            return "\n".join(LOG.read_text(errors="replace").splitlines()[-n:])
        except OSError:
            return ""


SERVER = Server()
VISION = Server(PORT + 1, vision=True)
VISION_IDLE = 300  # seconds without an image: the images engine leaves memory


def _vision_reaper():
    while True:
        time.sleep(30)
        if VISION.running and time.time() - VISION.used > VISION_IDLE:
            VISION.stop()


threading.Thread(target=_vision_reaper, daemon=True, name="naim-vision-reaper").start()
SLOT_CHAT, SLOT_AGENT = 0, 1
_slots_seen = {"n": 0, "at": 0.0}


def total_slots():
    """How many slots the running llama-server has (asked to it: it may have been started by another Naim)."""
    import time as _t
    if _t.time() - _slots_seen["at"] > 30:
        try:
            with urllib.request.urlopen(URL + "/props", timeout=2) as r:
                _slots_seen["n"] = int(json.load(r).get("total_slots") or 1)
            _slots_seen["at"] = _t.time()  # remembered only when the engine answered (it may be starting)
        except (urllib.error.URLError, OSError, ValueError):
            return _slots_seen["n"] or 1
    return _slots_seen["n"]


_slot_ctx_seen = {"n": 0, "at": 0.0}


def slot_ctx():
    """The real room of one conversation in the running engine (its context divided between its slots), or 0."""
    import time as _t
    if _t.time() - _slot_ctx_seen["at"] > 30:
        try:
            with urllib.request.urlopen(URL + "/props", timeout=2) as r:
                p = json.load(r)
            _slot_ctx_seen.update(n=int((p.get("default_generation_settings") or {}).get("n_ctx") or 0), at=_t.time())
        except (urllib.error.URLError, OSError, ValueError):
            pass
    return _slot_ctx_seen["n"]


class ContextFull(Exception):
    """The conversation no longer fits in the engine's room: the caller shortens it and asks again."""


def bg_slot():
    """The slot of the background jobs (memory, summaries): the last one, never the Chat's nor the Agent's."""
    n = total_slots()
    return n - 1 if n >= 3 else (1 if n == 2 else 0)
atexit.register(SERVER.stop)


def _unload_from_ollama():
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    host = host if host.startswith("http") else "http://" + host
    for name in ("naim", "naim:latest"):
        try:
            req = urllib.request.Request(f"{host.rstrip('/')}/api/generate", data=json.dumps({"model": name, "keep_alive": 0}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).close()
        except (urllib.error.URLError, OSError):
            pass


# ------------------------------------------------------------------ message conversion (Ollama <-> OpenAI)
def _to_openai(messages, vision):
    out, pending_ids, n = [], [], 0
    for m in messages:
        role = m.get("role")
        if role == "assistant":
            msg = {"role": "assistant", "content": m.get("content") or ""}
            calls = []
            for c in m.get("tool_calls") or []:
                n += 1
                cid = f"call_{n}"
                fn = c.get("function", {})
                args = fn.get("arguments", {})
                calls.append({"id": cid, "type": "function",
                              "function": {"name": fn.get("name"), "arguments": args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)}})
            if calls:
                msg["tool_calls"] = calls
            pending_ids = [c["id"] for c in calls]
            out.append(msg)
        elif role == "tool":
            cid = pending_ids.pop(0) if pending_ids else f"call_{n}"
            out.append({"role": "tool", "tool_call_id": cid, "content": m.get("content") or ""})
        elif role == "user" and m.get("images") and vision:
            parts = [{"type": "text", "text": m.get("content") or ""}]
            parts += [{"type": "image_url", "image_url": {"url": f"data:image/{'jpeg' if img.startswith('/9j/') else 'png'};base64,{img}"}} for img in m["images"]]
            out.append({"role": "user", "content": parts})
        else:
            out.append({"role": role, "content": m.get("content") or ""})
    return out


def _payload(messages, tools, think, stream, options, vision=None):
    o = dict(options or {})
    vision = SERVER.status()["vision"] if vision is None else vision
    body = {"messages": _to_openai(messages, vision), "stream": stream, "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": bool(think)},
            "temperature": o.get("temperature", 0.3), "top_p": o.get("top_p", 0.95), "top_k": o.get("top_k", 20)}
    for src, dst in (("repeat_penalty", "repeat_penalty"), ("presence_penalty", "presence_penalty"), ("seed", "seed")):
        if o.get(src) is not None:
            body[dst] = o[src]
    # safety cap: a small model can fall into an endless repetition; one reply never needs more than this
    body["max_tokens"] = o["num_predict"] if o.get("num_predict") else 8192
    if o.get("slot") is not None and int(o["slot"]) < total_slots():  # its own slot (Chat 0, Agent 1, background last)
        body["id_slot"] = int(o["slot"])
        if body["id_slot"] in (SLOT_CHAT, SLOT_AGENT) and (not messages or messages[0].get("role") != "system"):
            # a side request (a check, a summary: no instructions of its own) in the Chat's or the Agent's slot would wipe
            # what that slot has read — measured: the Agent then re-read its whole 18k-token task at every step (minutes)
            body["id_slot"] = bg_slot()
    elif o.get("slot") is None and total_slots() == 3 and not vision:
        # no slot asked (a sub-agent, a description): left to the engine, it would take the idle slot whose text is the
        # most alike — the Agent's — and wipe it; with only Chat, Agent and background slots, it goes to the background one
        body["id_slot"] = bg_slot()
    if tools:
        body["tools"] = tools
        if o.get("tool_choice"):  # "required": the answer must be a tool call (constrained by llama.cpp's grammar)
            body["tool_choice"] = o["tool_choice"]
    if stream:
        body["stream_options"] = {"include_usage": True}
    return body


SLOTS_DIR = HOME / "cache" / "slots"
WARM_LOG = []  # « restored » / « saved » for each start-up reading (shown in the status)


def _post(path, body, timeout=1800):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def warm_prefix(messages, tools, think, options):
    """Naim's start: its instructions and tools (everything before the first user message), as the engine formats
    them, read ONCE then kept on disk. At the next start they are loaded back in a fraction of a second instead of
    being read again (~2 min each for the Chat and the Agent). Naim's model is hybrid (SSM layers): its memory cannot
    go back, so exactly the instructions are kept — the next request goes on from there. A file whose instructions
    changed (new skill, memory, another day: the date is in them) is replaced: a temporary memory, purged by itself."""
    import hashlib
    o = dict(options or {})
    slot = int(o.get("slot") or 0)
    payload = _payload(messages, tools, think, False, o)
    mark = "NAIMMARK7731"
    msgs = [m for m in payload["messages"]]
    while msgs and msgs[-1]["role"] != "user":
        msgs.pop()
    if not msgs:
        return False
    msgs[-1] = {"role": "user", "content": mark}
    text = _post("/apply-template", {"messages": msgs, "tools": tools or [], "chat_template_kwargs": payload["chat_template_kwargs"]})["prompt"]
    cut = text.rfind("<|im_start|>", 0, text.index(mark))
    prefix = text[:cut] if cut > 0 else text[:text.index(mark)]
    gguf, _ = model_files()
    key = hashlib.sha256((prefix + str(gguf) + str(gguf.stat().st_mtime if gguf.exists() else 0)
                          + str(CONFIG.get("kv_type"))).encode()).hexdigest()[:16]
    name = f"slot{slot}-{key}.bin"
    if (SLOTS_DIR / name).exists():
        try:
            if _post(f"/slots/{slot}?action=restore", {"filename": name}).get("n_restored"):
                return "restored"
        except Exception:  # noqa: BLE001 — an unusable file: read again below
            (SLOTS_DIR / name).unlink(missing_ok=True)
    _post("/completion", {"prompt": prefix, "n_predict": 0, "cache_prompt": True, "id_slot": slot})
    for old in SLOTS_DIR.glob(f"slot{slot}-*.bin"):  # the instructions changed: the old memory goes
        if old.name != name:
            old.unlink(missing_ok=True)
    try:
        _post(f"/slots/{slot}?action=save", {"filename": name})
    except urllib.error.HTTPError as e:  # an engine started without --slot-save-path (an older Naim): read, not kept
        if e.code == 501:
            return "read"
        raise
    return "saved"


def chat(messages, tools=None, think=False, stream=False, options=None, url=None, ensure=None, vision=None):
    """Same contract as naimtools.ollama_chat: returns an Ollama-shaped message, or yields Ollama-shaped chunks.
    url / ensure / vision: another OpenAI-compatible local server speaking the same language (the MLX engine)."""
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
    if last_user.get("images") and not url:
        # a message with an image: the images engine (vision), started on demand; the main one keeps its saved memory
        options = {k: v for k, v in (options or {}).items() if k != "slot"}
        VISION.used = time.time()
        url, ensure, vision = VISION.url, VISION.ensure, True
    if not url and vision is None:
        vision = False  # the main engine has no vision: earlier images of the conversation stay as text
    if (options or {}).get("warm_prefix") and not url:  # Naim's start: load (or read once) its instructions, no answer
        SERVER.ensure(int((options or {}).get("num_ctx") or 16384))
        done = warm_prefix(messages, tools, think, options)
        WARM_LOG.append(done)
        reply = {"role": "assistant", "content": "."}
        return iter([{"message": reply, "done": True}]) if stream else reply
    payload = _payload(messages, tools, think, stream, options, vision)
    if url:  # another server (vision, MLX): the main engine's slot numbers mean nothing there
        payload.pop("id_slot", None)
    data = json.dumps(payload).encode()
    for attempt in (1, 2):
        (ensure or SERVER.ensure)(int((options or {}).get("num_ctx") or 16384))
        req = urllib.request.Request((url or URL) + "/v1/chat/completions", data=data, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req, timeout=1800)
            break
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")
            except OSError:
                body = ""
            if "exceeds the available context" in body or "context size" in body:
                raise ContextFull(body[:300]) from e
            note_error(f"HTTP {e.code}", body or str(e))
            if e.code >= 500 and attempt == 1:  # a passing failure of the engine: once more before giving up
                time.sleep(2)
                continue
            raise RuntimeError(f"le moteur a répondu {e.code} : {(body or str(e))[:300]}") from e
        except (http.client.RemoteDisconnected, ConnectionError, urllib.error.URLError) as e:
            # the shared llama-server was stopped (another Naim window quit, crash): start it again once
            if attempt == 2 or isinstance(e, urllib.error.HTTPError):
                raise
            time.sleep(1)
    if not stream:
        with resp:
            r = json.load(resp)
        m = r["choices"][0]["message"]
        calls = []
        for c in m.get("tool_calls") or []:
            args = c["function"].get("arguments") or "{}"
            args = _args(args)
            calls.append({"function": {"name": c["function"]["name"], "arguments": args}})
        out = {"role": "assistant", "content": m.get("content") or ""}
        if m.get("reasoning_content"):
            out["thinking"] = m["reasoning_content"]
        if calls:
            out["tool_calls"] = calls
        return out

    def chunks():
        first, calls, reason = None, {}, None  # tool calls arrive in pieces while streaming: assembled, then given at the end
        told = 0.0  # last « writing » progress given (a whole file written in a tool call is otherwise invisible)
        with resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                ev = json.loads(data)
                if ev.get("error"):  # the engine failed in the middle of the answer: said, not an empty reply
                    err = ev["error"] if isinstance(ev["error"], str) else (ev["error"].get("message") or json.dumps(ev["error"]))
                    note_error("erreur pendant la réponse", err)
                    raise RuntimeError(f"le moteur s'est arrêté pendant la réponse : {err[:300]}")
                t = ev.get("timings")
                if ev.get("choices"):
                    delta = ev["choices"][0].get("delta", {})
                    for tc in delta.get("tool_calls") or []:
                        c = calls.setdefault(tc.get("index", len(calls)), {"name": "", "args": ""})
                        f = tc.get("function") or {}
                        c["name"] += f.get("name") or ""
                        c["args"] += f.get("arguments") or ""
                        if time.time() - told > 1.0 and len(c["args"]) > 400:
                            told = time.time()
                            path = re.search(r'"(?:path|nom|output|file|filename)"\s*:\s*"([^"]{1,200})"', c["args"])
                            yield {"message": {}, "done": False,
                                   "writing": {"name": c["name"], "chars": len(c["args"]), "path": path.group(1) if path else ""}}
                    if first is None and (delta.get("content") or delta.get("reasoning_content")):
                        first = time.time()
                    yield {"message": {"content": delta.get("content") or "", "thinking": delta.get("reasoning_content") or ""},
                           "done": False}
                if ev.get("choices") and ev["choices"][0].get("finish_reason"):
                    reason = ev["choices"][0]["finish_reason"]
                if t and t.get("predicted_n"):
                    yield {"message": {}, "done": True, "eval_count": t["predicted_n"], "prompt_total": t.get("cache_n", 0) + t.get("prompt_n", 0),
                           "eval_duration": int(t.get("predicted_ms", 1) * 1e6), "prompt_eval_count": t.get("prompt_n", 0),
                           "prompt_eval_duration": int(t.get("prompt_ms", 0) * 1e6), "done_reason": reason}
                elif not t and (ev.get("usage") or {}).get("completion_tokens") and first:  # MLX: counts only
                    yield {"message": {}, "done": True, "eval_count": ev["usage"]["completion_tokens"],
                           "eval_duration": int((time.time() - first) * 1e9)}
        if calls:
            out = []
            for _, c in sorted(calls.items()):
                args = _args(c["args"])
                out.append({"function": {"name": c["name"], "arguments": args}})
            yield {"message": {"tool_calls": out}, "done": False}
    return chunks()
