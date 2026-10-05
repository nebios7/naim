"""Naim's voice: its answers read aloud, with its own voice (not the Mac's), entirely on this Mac.

Naim's voice (~/.naim/voix/naim.onnx) is its own: a voice model trained for Naim, from a French LibriVox reader
of Multilingual LibriSpeech (CC BY 4.0). A small worker in its own Python environment (~/.naim/voix/.venv) loads it
once, then each sentence becomes a WAV in a fraction of a second, without slowing Naim's language model.

Before that model exists, « naturelle » falls back to the voice imitated from a recording
(~/.naim/voix/naim-voix-naturelle.wav, much slower), and « rapide » is a stock French voice
(~/.naim/voix/naim-voix.onnx, « Pierre » of the UPMC corpus, CC BY-SA 4.0).
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
FAST_NAT = DIR / "naim.onnx"  # Naim's own voice (single speaker)

WORKER = r'''
import json, sys, wave
from piper import PiperVoice
from piper.config import SynthesisConfig
voice = PiperVoice.load(sys.argv[1])
cfg = SynthesisConfig(speaker_id=None if sys.argv[2] == "-" else int(sys.argv[2]), length_scale=0.95, noise_scale=0.6, noise_w_scale=0.8)
for line in sys.stdin:
    job = json.loads(line)
    try:
        with wave.open(job["out"], "wb") as w:
            voice.synthesize_wav(job["text"], w, syn_config=cfg)
        print(json.dumps({"ok": True}), flush=True)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:200]}), flush=True)
'''

NAT_REF = DIR / "naim-voix-naturelle.wav"
NAT_PYTHON = Path.home() / "Documents" / "naim" / "voix" / "cb" / "bin" / "python"  # Chatterbox environment (owner's Mac)
NAT_WORKER = r'''
import json, sys, warnings
warnings.filterwarnings("ignore")
import torch, torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
dev = "mps" if torch.backends.mps.is_available() else "cpu"
m = ChatterboxMultilingualTTS.from_pretrained(device=dev)
m.prepare_conditionals(sys.argv[1], exaggeration=0.5)  # Naim's voice, prepared once
print("@@" + json.dumps({"ready": True}), flush=True)
for line in sys.stdin:
    job = json.loads(line)
    try:
        wav = m.generate(job["text"], language_id="fr", exaggeration=0.5, cfg_weight=0.5)
        ta.save(job["out"], wav, m.sr)
        print("@@" + json.dumps({"ok": True}), flush=True)
    except Exception as e:
        print("@@" + json.dumps({"ok": False, "error": str(e)[:200]}), flush=True)
'''

_proc, _lock = None, threading.Lock()
_nat, _nat_lock = None, threading.Lock()
_fast, _fast_lock = None, threading.Lock()


def available():
    return MODEL.exists() and PYTHON.exists()


def natural_available():
    return fast_natural_available() or (NAT_REF.exists() and NAT_PYTHON.exists())


def fast_natural_available():
    return FAST_NAT.exists() and PYTHON.exists()


def _fast_worker():
    global _fast
    if _fast is None or _fast.poll() is not None:
        _fast = subprocess.Popen([str(PYTHON), "-c", WORKER, str(FAST_NAT), "-"], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    return _fast


def _natural_worker():
    global _nat
    if _nat is None or _nat.poll() is not None:
        _nat = subprocess.Popen([str(NAT_PYTHON), "-c", NAT_WORKER, str(NAT_REF)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        _reply(_nat)  # « ready »: the model is loaded
    return _nat


def _reply(p):
    """The worker's answer; other lines (libraries print things) are skipped. Piper's worker has no « @@ » mark."""
    while True:
        line = p.stdout.readline()
        if not line:
            return {"ok": False, "error": "la voix ne répond pas"}
        line = line.strip()
        if line.startswith("@@"):
            return json.loads(line[2:])
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                pass


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


def speak(text, engine="rapide"):
    """WAV bytes of the text read by Naim's voice (empty bytes if there is nothing to read)."""
    text = clean(text)[:1500]
    if not text:
        return b""
    if engine == "naturelle" and fast_natural_available():
        lock, start = _fast_lock, _fast_worker
    elif engine == "naturelle" and natural_available():
        lock, start = _nat_lock, _natural_worker
    else:
        lock, start = _lock, _worker
    with lock:
        p = start()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out = f.name
        p.stdin.write(json.dumps({"text": text, "out": out}) + "\n")
        p.stdin.flush()
        r = _reply(p)
    data = Path(out).read_bytes() if r.get("ok") else b""
    Path(out).unlink(missing_ok=True)
    if not r.get("ok"):
        raise RuntimeError(r.get("error") or "voix indisponible")
    return data
