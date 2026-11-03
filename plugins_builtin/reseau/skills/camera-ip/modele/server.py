#!/usr/bin/env python3
"""Watch and record an IP camera in the browser.

The browser cannot read RTSP: ffmpeg turns the camera's stream into HLS that this server gives to the page. While it
records, the SAME ffmpeg also writes an MP4 — one connection to the camera only (most accept a single one).
Photos sent by the page are saved too. Everything goes in ./medias/.

    python3 server.py                 then open http://localhost:8099
    PORT=9000 python3 server.py
The camera's address and login are typed in the page: nothing is written in this file.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import base64
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

PORT = int(os.environ.get("PORT", "8099"))
HERE = Path(__file__).resolve().parent
HLS, MEDIA = HERE / "hls", HERE / "medias"
HLS.mkdir(exist_ok=True)
MEDIA.mkdir(exist_ok=True)

lock = threading.Lock()
proc = None
cfg = {}                                   # the last connection asked (address, login, path, transport, re-encode)
state = {"running": False, "recording": False, "file": "", "since": 0, "error": ""}


def source_url(c):
    """rtsp://user:pass@ip:port/path — or a file / any URL ffmpeg reads (to try the app without a camera)."""
    if c.get("url"):
        return c["url"]
    cred = (quote(c.get("user", ""), safe="") + (":" + quote(c["password"], safe="") if c.get("password") else "") + "@") if c.get("user") else ""
    return f"rtsp://{cred}{c['ip']}:{int(c.get('port') or 554)}/{c.get('path', '').lstrip('/')}"


# the stream paths of the common brands, tried in turn when the path is left empty
PATHS = ["stream1", "live", "h264", "11", "stream2", "onvif1", "live/ch00_0", "ch0_0.h264", "live.sdp", "Streaming/Channels/101",
         "cam/realmonitor?channel=1&subtype=0", "h264Preview_01_main", "videoMain", "media/video1", "unicast", ""]


def hide(text):
    """Never a password on the screen: rtsp://user:pass@ip → rtsp://•••@ip (ffmpeg writes the whole address in its errors)."""
    return re.sub(r"(rtsp://)[^@/\s]+@", r"\1•••@", text or "")


def find_path():
    """The path left empty: the usual ones tried with ffprobe, one at a time (one connection), the first that answers."""
    for path in PATHS:
        url = source_url({**cfg, "path": path})
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-rtsp_transport", cfg.get("transport") or "tcp", "-select_streams", "v:0",
                                "-show_entries", "stream=codec_name", "-of", "csv=p=0", url], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0 and r.stdout.strip():
            cfg["codec"] = r.stdout.strip()
            return path
        if "401" in r.stderr:
            return None  # the login is refused: no use trying other paths
    return None


def video_out():
    # re-encoded: one key image a second, so that the 1 s HLS pieces exist (a camera may send one every 4-10 s)
    return (["-an", "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency", "-g", "25", "-sc_threshold", "0"]
            if cfg.get("reencode") else ["-an", "-c:v", "copy"])


def stop_locked():
    global proc
    if proc and proc.poll() is None:
        proc.send_signal(signal.SIGINT)    # SIGINT: ffmpeg closes the MP4 properly
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    proc = None
    state.update(running=False, recording=False, file="")


def codec(url):
    """The camera's video format (h264, hevc…), asked once before the first start; '' if it cannot be read."""
    src = ["-rtsp_transport", cfg.get("transport", "tcp")] if url.startswith("rtsp") else []
    try:
        r = subprocess.run(["ffprobe", "-v", "error", *src, "-select_streams", "v:0", "-show_entries", "stream=codec_name",
                            "-of", "csv=p=0", url], capture_output=True, text=True, timeout=12)
        return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def start_locked(record):
    global proc
    stop_locked()
    if not cfg.get("url") and not cfg.get("path") and "found" not in cfg:
        cfg["found"] = find_path()  # « Chemin du flux » left empty: found by itself
        if cfg["found"] is None:
            state.update(running=False, error="Aucun chemin de flux connu ne répond : vérifie l'identifiant et le mot de passe, "
                                              "ou indique le chemin (il est dans l'application ou la notice de la caméra).")
            return
        cfg["path"] = cfg["found"]
    if not cfg.get("reencode") and "codec" not in cfg:
        # browsers play H.264 live, not HEVC (H.265, frequent on cheap cameras): re-encoded by itself, nothing to tick
        cfg["codec"] = codec(source_url(cfg))
        if cfg["codec"] and cfg["codec"] != "h264":
            cfg["reencode"] = True
    for f in HLS.glob("*"):
        f.unlink(missing_ok=True)
    url = source_url(cfg)
    src = (["-rtsp_transport", cfg.get("transport", "tcp")] if url.startswith("rtsp") else ["-re", "-stream_loop", "-1"]) + ["-i", url]
    cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", *src, *video_out(),
           "-f", "hls", "-hls_time", "1", "-hls_list_size", "6", "-hls_flags", "delete_segments+omit_endlist",
           "-hls_segment_filename", str(HLS / "seg_%04d.ts"), str(HLS / "live.m3u8")]
    name = ""
    if record:
        name = "video_" + datetime.now().strftime("%Y-%m-%d_%Hh%M-%S") + ".mp4"
        cmd += [*video_out(), "-movflags", "+frag_keyframe+empty_moov", str(MEDIA / name)]
    # its messages go to a file: in a pipe nobody reads, they filled it after a while and ffmpeg froze (no more image)
    proc = subprocess.Popen(cmd, stderr=open(HERE / "ffmpeg.log", "wb"))
    state.update(running=True, recording=record, file=name, since=int(time.time()), error="",
                 video=cfg.get("codec", ""), reencode=bool(cfg.get("reencode")), path=cfg.get("path", ""))
    threading.Thread(target=watch, args=(proc,), daemon=True).start()


def watch(p):
    """ffmpeg that stops (wrong login, wrong path, camera gone): the page says why."""
    p.wait()
    err = (HERE / "ffmpeg.log").read_text(errors="replace").strip() if (HERE / "ffmpeg.log").exists() else ""
    with lock:
        if proc is p:
            state.update(running=False, recording=False, error=hide(err[-400:]) or "le flux s'est arrêté")


def medias():
    out = []
    for f in sorted(MEDIA.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True):
        if f.suffix.lower() in (".mp4", ".png", ".jpg"):
            out.append({"name": f.name, "size": f.stat().st_size, "kind": "video" if f.suffix == ".mp4" else "photo",
                        "date": int(f.stat().st_mtime)})
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def file(self, path, ctype, download=False):
        if not path.is_file():
            return self.send(404, {"error": "introuvable"})
        self.send(200, path.read_bytes(), ctype, {"Content-Disposition": f'attachment; filename="{path.name}"'} if download else None)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self.file(HERE / "index.html", "text/html; charset=utf-8")
        if p == "/api/status":
            with lock:
                used = sum(f.stat().st_size for f in MEDIA.iterdir() if f.is_file())
                return self.send(200, {**state, "medias": medias(), "used": used, "free": shutil.disk_usage(MEDIA).free})
        if p.startswith("/hls/"):
            f = HLS / Path(unquote(p[5:])).name
            return self.file(f, "application/vnd.apple.mpegurl" if f.suffix == ".m3u8" else "video/mp2t")
        if p.startswith("/medias/"):
            f = MEDIA / Path(unquote(p[8:])).name
            ctype = {".mp4": "video/mp4", ".png": "image/png", ".jpg": "image/jpeg"}.get(f.suffix.lower(), "application/octet-stream")
            return self.file(f, ctype, download="dl=1" in self.path)
        self.send(404, {"error": "introuvable"})

    def do_POST(self):
        p = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        d = json.loads(self.rfile.read(n) or b"{}") if n else {}
        with lock:
            if p == "/api/start":
                cfg.clear()
                cfg.update({k: d.get(k) for k in ("url", "ip", "port", "user", "password", "path", "transport", "reencode")})
                if not cfg.get("url") and not cfg.get("ip"):
                    return self.send(400, {"error": "adresse de la caméra manquante"})
                start_locked(False)
            elif p == "/api/stop":
                stop_locked()
            elif p == "/api/record":
                if not cfg:
                    return self.send(400, {"error": "démarre d'abord le flux"})
                start_locked(bool(d.get("on")))   # the same connection: ffmpeg restarts with or without the MP4
            elif p == "/api/photo":
                raw = str(d.get("data", "")).split(",", 1)[-1]
                name = "photo_" + datetime.now().strftime("%Y-%m-%d_%Hh%M-%S") + ".png"
                (MEDIA / name).write_bytes(base64.b64decode(raw))
            elif p == "/api/delete":
                f = MEDIA / Path(str(d.get("name", ""))).name
                if f.is_file() and f.name != state.get("file"):
                    f.unlink()
            else:
                return self.send(404, {"error": "introuvable"})
            return self.send(200, state)


def main():
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg manque : brew install ffmpeg")
    for port in range(PORT, PORT + 20):  # the port already taken (another app): the next free one, never another's stopped
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"Aucun port libre entre {PORT} et {PORT + 19}")
    print(f"Caméra : ouvre http://localhost:{port} — médias dans {MEDIA}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with lock:
            stop_locked()


if __name__ == "__main__":
    main()
