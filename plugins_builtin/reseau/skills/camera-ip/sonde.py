#!/usr/bin/env python3
"""Find the video stream of an IP camera: tries the usual RTSP paths with ffprobe and says which one answers.

    CAM_USER=admin CAM_PASS=… python3 sonde.py 192.168.1.20 [port]

The login is read from the environment (asked to the user), never written in a file nor shown. Read-only: each try
only opens the stream for a few seconds, one at a time (most cameras accept a single connection).
"""
import json
import os
import socket
import subprocess
import sys
from urllib.parse import quote

# the paths of the common brands (generic, Hikvision, Dahua, TP-Link, Reolink, Xiaomi/Yi, cheap ONVIF cameras…)
PATHS = ["", "live", "stream1", "stream2", "h264", "11", "12", "onvif1", "live/ch00_0", "ch0_0.h264", "live.sdp",
         "Streaming/Channels/101", "Streaming/Channels/102", "cam/realmonitor?channel=1&subtype=0",
         "h264Preview_01_main", "videoMain", "media/video1", "unicast", "mpeg4", "1"]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ip, port = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 554
    s = socket.socket(); s.settimeout(2)
    if s.connect_ex((ip, port)) != 0:
        sys.exit(f"{ip}:{port} ne répond pas : caméra éteinte, autre port RTSP (8554 ?), ou RTSP désactivé dans son application.")
    s.close()
    user, pw = os.environ.get("CAM_USER", ""), os.environ.get("CAM_PASS", "")
    cred = (quote(user, safe="") + (":" + quote(pw, safe="") if pw else "") + "@") if user else ""
    refused = 0
    for path in PATHS:
        url = f"rtsp://{cred}{ip}:{port}/{path}"
        r = subprocess.run(["ffprobe", "-v", "error", "-rtsp_transport", "tcp", "-timeout", "4000000", "-show_entries",
                            "stream=codec_type,codec_name,width,height,avg_frame_rate", "-of", "json", url],
                           capture_output=True, text=True, timeout=12)
        if r.returncode == 0:
            streams = json.loads(r.stdout or "{}").get("streams", [])
            v = next((x for x in streams if x.get("codec_type") == "video"), {})
            a = next((x for x in streams if x.get("codec_type") == "audio"), None)
            print(f"TROUVÉ : chemin « {path or '/'} » — vidéo {v.get('codec_name')} {v.get('width')}×{v.get('height')}"
                  f" à {v.get('avg_frame_rate')} images/s" + (f", son {a.get('codec_name')}" if a else ", sans son"))
            print("→ " + ("Le navigateur lit le H.264 : ffmpeg peut copier la vidéo sans la ré-encoder (-c:v copy)."
                          if v.get("codec_name") == "h264" else
                          "Ce n'est pas du H.264 : ré-encode avec ffmpeg (-c:v libx264 -preset veryfast -tune zerolatency)."))
            return
        if "401" in r.stderr or "Unauthorized" in r.stderr:
            refused += 1
    if refused:
        sys.exit("La caméra répond mais refuse l'identifiant (401) : demande à l'utilisateur l'identifiant et le mot de "
                 "passe de la caméra (souvent dans son application, rubrique RTSP / ONVIF), puis relance avec CAM_USER et CAM_PASS.")
    sys.exit("Aucun chemin connu ne marche : cherche le chemin RTSP de ce modèle (web_search « <marque modèle> rtsp url »).")


if __name__ == "__main__":
    main()
