"""Naim's voice: its answers read aloud, with its own voice (not the Mac's), entirely on this Mac.

The voice is a French Piper model (~/.naim/voix/naim-voix.onnx, voice « Pierre » of the UPMC corpus,
CC BY-SA 4.0) run by a small worker in its own Python environment (~/.naim/voix/.venv): it is loaded once,
then each sentence becomes a WAV in a fraction of a second, without slowing Naim's language model.
"""
import json
import re
import subprocess
import tempfile
import threading
from pathlib import Path

import extensions as ext

DIR = ext.HOME / "voix"
MODEL = DIR / "naim-voix.onnx"
PYTHON = DIR / ".venv" / "bin" / "python"
SPEAKER = 1  # « pierre » in the UPMC model

WORKER = r'''
import json, sys, wave
from piper import PiperVoice
from piper.config import SynthesisConfig
voice = PiperVoice.load(sys.argv[1])
cfg = SynthesisConfig(speaker_id=int(sys.argv[2]), length_scale=0.95, noise_scale=0.6, noise_w_scale=0.8)
for line in sys.stdin:
    job = json.loads(line)
    try:
        with wave.open(job["out"], "wb") as w:
            voice.synthesize_wav(job["text"], w, syn_config=cfg)
        print(json.dumps({"ok": True}), flush=True)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:200]}), flush=True)
'''

_proc, _lock = None, threading.Lock()


def available():
    return MODEL.exists() and PYTHON.exists()


def clean(text):
    """What is worth hearing: no code, no links, no Markdown signs."""
    t = re.sub(r"```.*?```", " ", text or "", flags=re.S)       # code blocks: shown, not read
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)             # links: their text only
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"^\s*\|.*\|\s*$", " ", t, flags=re.M)            # tables
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"[*_~>#|]+", " ", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _worker():
    global _proc
    if _proc is None or _proc.poll() is not None:
        _proc = subprocess.Popen([str(PYTHON), "-c", WORKER, str(MODEL), str(SPEAKER)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    return _proc


def speak(text):
    """WAV bytes of the text read by Naim's voice (empty bytes if there is nothing to read)."""
    text = clean(text)[:1500]
    if not text:
        return b""
    with _lock:
        p = _worker()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out = f.name
        p.stdin.write(json.dumps({"text": text, "out": out}) + "\n")
        p.stdin.flush()
        r = json.loads(p.stdout.readline() or '{"ok": false, "error": "la voix ne répond pas"}')
    data = Path(out).read_bytes() if r.get("ok") else b""
    Path(out).unlink(missing_ok=True)
    if not r.get("ok"):
        raise RuntimeError(r.get("error") or "voix indisponible")
    return data
