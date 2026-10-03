"""MLX engine for Naim (Apple's own framework): an optional third engine next to llama.cpp and Ollama.

Available only on a Mac that has MLX (mlx_lm) and the MLX version of Naim. It speaks the same language as
llama.cpp's server (OpenAI-compatible), so the chat code is shared (llamacpp.chat with another address).
MLX reads text only: a conversation with an image goes to llama.cpp. Only one of the two engines runs at a time
(each takes about 5 GB of memory).
"""
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import llamacpp

HOME = Path.home() / "Documents/naim"
PYTHON = Path(os.environ.get("NAIM_MLX_PYTHON", HOME / ".venv/bin/python"))
MODEL = Path(os.environ.get("NAIM_MLX_MODEL", HOME / "models/naim-mlx"))
PORT = int(os.environ.get("NAIM_MLX_PORT", "8083"))
URL = f"http://127.0.0.1:{PORT}"
LOG = llamacpp.HOME / "mlx-server.log"


def available():
    return PYTHON.exists() and (MODEL / "config.json").exists()


class Server:
    def __init__(self):
        self.proc, self.lock, self.error = None, threading.Lock(), None

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def healthy(self):
        try:
            with urllib.request.urlopen(URL + "/v1/models", timeout=2) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def ensure(self, ctx=None, timeout=180):
        """Start the MLX server (stopping llama.cpp first: one engine in memory at a time); wait until ready."""
        if llamacpp.BLOCKED:
            raise RuntimeError(llamacpp.BLOCKED)
        with self.lock:
            if self.running and self.healthy():
                return
            if not available():
                self.error = "MLX ou la version MLX de Naim est introuvable sur ce Mac"
                raise RuntimeError(self.error)
            llamacpp.SERVER.stop()  # free the memory llama.cpp used
            self.stop()
            log = open(LOG, "a")
            log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start MLX: {MODEL}\n")
            log.flush()
            self.proc = subprocess.Popen([str(PYTHON), "-m", "mlx_lm", "server", "--model", str(MODEL),
                                          "--host", "127.0.0.1", "--port", str(PORT)],
                                         stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
            self.error = None
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self.proc.poll() is not None:
                    self.error = "le serveur MLX s'est arrêté au démarrage : " + LOG.read_text(errors="replace")[-500:]
                    raise RuntimeError(self.error)
                if self.healthy():
                    return
                time.sleep(0.5)
            self.error = "le serveur MLX ne répond pas"
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
        return {"available": available(), "running": self.running, "model": str(MODEL), "error": self.error}


SERVER = Server()


def chat(messages, tools=None, think=False, stream=False, options=None):
    """Same contract as llamacpp.chat (Ollama-shaped answers), on the MLX server."""
    return llamacpp.chat(messages, tools=tools, think=think, stream=stream, options=options,
                         url=URL, ensure=SERVER.ensure, vision=False)
