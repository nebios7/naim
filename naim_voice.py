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

# Kyutai TTS (open weights, French and English): a very natural voice, loaded once in its own environment
# (~/.naim/voix/kyutai-venv), 8 bits. Used when the voice in service is a Kyutai one (Admin › Mes voix).
KY_PYTHON = DIR / "kyutai-venv" / "bin" / "python"
SERVICE = DIR / "voix-en-service.json"
KY_WORKER = r'''
import json, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, mlx.core as mx, mlx.nn as nn, sentencepiece, sphn
from moshi_mlx import models
from moshi_mlx.utils.loaders import hf_get
from moshi_mlx.models.tts import TTSModel, DEFAULT_DSM_TTS_REPO, DEFAULT_DSM_TTS_VOICE_REPO
repo = DEFAULT_DSM_TTS_REPO
cfg = json.load(open(hf_get(hf_get("config.json", repo))))
lm_config = models.LmConfig.from_config_dict(cfg)
model = models.Lm(lm_config); model.set_dtype(mx.bfloat16)
model.load_pytorch_weights(str(hf_get(hf_get(cfg.get("moshi_name", "model.safetensors"), repo))), lm_config, strict=True)
nn.quantize(model.depformer, bits=8)  # 8 bits: about half the memory, same voice
for layer in model.transformer.layers:
    nn.quantize(layer.self_attn, bits=8); nn.quantize(layer.gating, bits=8)
tok = sentencepiece.SentencePieceProcessor(str(hf_get(hf_get(cfg["tokenizer_name"], repo))))
mimi = models.mimi.Mimi(models.mimi_202407(lm_config.generated_codebooks))
mimi.load_pytorch_weights(str(hf_get(hf_get(cfg["mimi_name"], repo))), strict=True)
tts = TTSModel(model, mimi, tok, voice_repo=DEFAULT_DSM_TTS_VOICE_REPO, n_q=32, temp=0.6, cfg_coef=2.0,
               max_padding=8, initial_padding=2, final_padding=4, padding_bonus=0.0, raw_config=cfg)
cond = None
if tts.valid_cfg_conditionings:
    cond, tts.cfg_coef, no_text, no_prefix = tts.cfg_coef, 1.0, False, False
else:
    no_text = no_prefix = True
print("@@" + json.dumps({"ready": True}), flush=True)
for line in sys.stdin:
    job = json.loads(line)
    try:
        entries = tts.prepare_script([job["text"]], padding_between=1)
        voices = [tts.get_voice_path(job["voice"])] if tts.multi_speaker else []
        attrs = tts.make_condition_attributes(voices, cond)
        prefixes = None if tts.multi_speaker else [tts.get_prefix(hf_get(job["voice"], DEFAULT_DSM_TTS_VOICE_REPO, check_local_file_exists=True))]
        res = tts.generate([entries], [attrs], prefixes=prefixes, cfg_is_no_prefix=no_prefix, cfg_is_no_text=no_text)
        wav = mx.concat([tts.mimi.decode_step(f) for f in res.frames], axis=-1)
        end = res.end_steps[0]
        n = wav.shape[-1] if end is None else int(mimi.sample_rate * (end + tts.final_padding) / mimi.frame_rate)
        wav = wav[0, :, :n]
        if prefixes is not None:
            wav = wav[:, int(mimi.sample_rate * prefixes[0].shape[-1] / mimi.frame_rate):]
        sphn.write_wav(job["out"], np.array(mx.clip(wav, -1, 1)), mimi.sample_rate)
        if hasattr(tts.mimi, "reset_all"):
            tts.mimi.reset_all()
        print("@@" + json.dumps({"ok": True}), flush=True)
    except Exception as e:
        print("@@" + json.dumps({"ok": False, "error": str(e)[:300]}), flush=True)
'''
_ky, _ky_lock = None, threading.Lock()
_proc, _lock = None, threading.Lock()
_nat, _nat_lock = None, threading.Lock()
_fast, _fast_lock = None, threading.Lock()


def available():
    return MODEL.exists() and PYTHON.exists()


def natural_available():
    return fast_natural_available() or (NAT_REF.exists() and NAT_PYTHON.exists())


def fast_natural_available():
    return FAST_NAT.exists() and PYTHON.exists()


def reload():
    """Another voice was put in service (naim.onnx replaced): the next sentence loads it."""
    global _fast, _ky
    with _ky_lock:  # a Kyutai voice is chosen per sentence: its worker only goes if Kyutai is no longer used
        if _ky is not None and _ky.poll() is None and not kyutai_voice():
            _ky.terminate()
            _ky = None
    with _fast_lock:
        if _fast is not None and _fast.poll() is None:
            _fast.terminate()
        _fast = None


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


def _service():
    try:
        return json.loads(SERVICE.read_text())
    except (OSError, ValueError):
        return {}


def kyutai_voice():
    """The Kyutai voice in service (its reference in Kyutai's voice repository), or None."""
    sv = _service()
    return sv.get("ref") if sv.get("moteur") == "kyutai" and KY_PYTHON.exists() else None


def _kyutai_worker():
    global _ky
    if _ky is None or _ky.poll() is not None:
        _ky = subprocess.Popen([str(KY_PYTHON), "-c", KY_WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, bufsize=1)
        _reply(_ky)  # « ready »: the model is loaded (≈ 8 s)
    return _ky


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
    t = re.sub(r"\bna[iï]m\b", "Naïm", t, flags=re.I)  # « Naim » is read « nain » in French: « Naïm » is na-im
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
    extra = {}
    if engine == "naturelle" and (ref := kyutai_voice()):
        lock, start, extra = _ky_lock, _kyutai_worker, {"voice": ref}
    elif engine == "naturelle" and fast_natural_available():
        lock, start = _fast_lock, _fast_worker
    elif engine == "naturelle" and natural_available():
        lock, start = _nat_lock, _natural_worker
    else:
        lock, start = _lock, _worker
    with lock:
        p = start()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out = f.name
        p.stdin.write(json.dumps({"text": text, "out": out, **extra}) + "\n")
        p.stdin.flush()
        r = _reply(p)
    data = Path(out).read_bytes() if r.get("ok") else b""
    Path(out).unlink(missing_ok=True)
    if not r.get("ok"):
        raise RuntimeError(r.get("error") or "voix indisponible")
    return data
