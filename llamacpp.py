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
    def __init__(self):
        self.proc, self.ctx, self.lock, self.error, self.cfg = None, None, threading.Lock(), None, None

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def healthy(self):
        try:
            with urllib.request.urlopen(URL + "/health", timeout=2) as r:
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
            if hardware()["ram_gb"] >= 16:
                # one more slot for the background jobs (memory, summaries): they no longer overwrite what the
                # conversation's slot has already read (its ~6k tokens of instructions and tools stay in cache)
                slots = max(slots, 2)
            cmd = [exe, "-m", str(gguf), "--host", "127.0.0.1", "--port", str(PORT), "-c", str(ctx * slots),
                   # a checkpoint every 2048 tokens (default 8192): a new task re-reads only what follows Naim's fixed
                   # instructions (~7k tokens shared by every task), not the whole prompt; 16 kept (50 MB each)
                   "--jinja", "--ctx-checkpoints", str(max(int(cfg["checkpoints"]), 16)), "--checkpoint-every-n-tokens", "2048",
                   "-ngl", str(cfg["gpu_layers"]),
                   "-b", str(cfg["batch"]), "-np", str(slots), "--no-webui"]
            if int(cfg.get("threads") or 0) > 0:
                cmd += ["-t", str(cfg["threads"])]
            if cfg.get("kv_type") in ("q8_0", "q4_0"):
                cmd += ["-ctk", cfg["kv_type"], "-ctv", cfg["kv_type"], "-fa", "on"]
            if mmproj:
                cmd += ["--mmproj", str(mmproj)]
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
    if o.get("slot") is not None:  # a background job uses its own slot (see start: the last one)
        body["id_slot"] = int(o["slot"])
    if tools:
        body["tools"] = tools
        if o.get("tool_choice"):  # "required": the answer must be a tool call (constrained by llama.cpp's grammar)
            body["tool_choice"] = o["tool_choice"]
    if stream:
        body["stream_options"] = {"include_usage": True}
    return body


def chat(messages, tools=None, think=False, stream=False, options=None, url=None, ensure=None, vision=None):
    """Same contract as naimtools.ollama_chat: returns an Ollama-shaped message, or yields Ollama-shaped chunks.
    url / ensure / vision: another OpenAI-compatible local server speaking the same language (the MLX engine)."""
    data = json.dumps(_payload(messages, tools, think, stream, options, vision)).encode()
    for attempt in (1, 2):
        (ensure or SERVER.ensure)(int((options or {}).get("num_ctx") or 16384))
        req = urllib.request.Request((url or URL) + "/v1/chat/completions", data=data, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req, timeout=1800)
            break
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
            try:
                args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                args = {}
            calls.append({"function": {"name": c["function"]["name"], "arguments": args}})
        out = {"role": "assistant", "content": m.get("content") or ""}
        if m.get("reasoning_content"):
            out["thinking"] = m["reasoning_content"]
        if calls:
            out["tool_calls"] = calls
        return out

    def chunks():
        first, calls, reason = None, {}, None  # tool calls arrive in pieces while streaming: assembled, then given at the end
        with resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                ev = json.loads(data)
                t = ev.get("timings")
                if ev.get("choices"):
                    delta = ev["choices"][0].get("delta", {})
                    for tc in delta.get("tool_calls") or []:
                        c = calls.setdefault(tc.get("index", len(calls)), {"name": "", "args": ""})
                        f = tc.get("function") or {}
                        c["name"] += f.get("name") or ""
                        c["args"] += f.get("arguments") or ""
                    if first is None and (delta.get("content") or delta.get("reasoning_content")):
                        first = time.time()
                    yield {"message": {"content": delta.get("content") or "", "thinking": delta.get("reasoning_content") or ""},
                           "done": False}
                if ev.get("choices") and ev["choices"][0].get("finish_reason"):
                    reason = ev["choices"][0]["finish_reason"]
                if t and t.get("predicted_n"):
                    yield {"message": {}, "done": True, "eval_count": t["predicted_n"],
                           "eval_duration": int(t.get("predicted_ms", 1) * 1e6), "prompt_eval_count": t.get("prompt_n", 0),
                           "prompt_eval_duration": int(t.get("prompt_ms", 0) * 1e6), "done_reason": reason}
                elif not t and (ev.get("usage") or {}).get("completion_tokens") and first:  # MLX: counts only
                    yield {"message": {}, "done": True, "eval_count": ev["usage"]["completion_tokens"],
                           "eval_duration": int((time.time() - first) * 1e9)}
        if calls:
            out = []
            for _, c in sorted(calls.items()):
                try:
                    args = json.loads(c["args"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                out.append({"function": {"name": c["name"], "arguments": args}})
            yield {"message": {"tool_calls": out}, "done": False}
    return chunks()
