"""Computer use and iOS Simulator control for Naim.

A small native helper (naim_input.swift, compiled once into DATA/bin) reads the text on screen with Apple's
Vision OCR and sends mouse/keyboard events. Every screenshot returns the visible texts with their coordinates,
so even a small model can act precisely with `click_text` instead of guessing pixels.

Coordinates given to the model are always in the space of the LAST screenshot image (what it sees); they are
converted here to real screen points. The simulator is driven with `xcrun simctl` (boot, install, launch,
open URL) and, for taps and typing, through the Simulator window on screen.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import extensions as ext

SRC = Path(__file__).with_name("naim_input.swift")
BIN = ext.DATA / "bin" / "naim-input"
SHOTS = ext.DATA / "screenshots"
MAX_W = 1024  # screenshots are scaled down to at most this width for the model


class ComputerError(Exception):
    pass


def helper():
    """Path of the compiled helper (built on first use, rebuilt when the Swift source changes)."""
    if BIN.exists():  # compiled by install.sh (only when its source changes: keeps macOS permissions stable)
        return str(BIN)
    if not SRC.exists():
        raise ComputerError("naim_input.swift introuvable")
    if not shutil.which("swiftc"):
        raise ComputerError("swiftc introuvable : installe les outils Xcode (xcode-select --install)")
    BIN.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["swiftc", "-O", str(SRC), "-o", str(BIN)], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise ComputerError("compilation de naim-input impossible : " + r.stderr[-500:])
    return str(BIN)


BRIDGE_CMDS = {"click", "move", "drag", "scroll", "type", "key"}


def _bridge(cmd, args, timeout=60):
    """Ask Naim.app to post the mouse/keyboard events itself (Accessibility is granted to Naim.app).
    None when Naim runs without the native app (naim --web from a terminal)."""
    spec = os.environ.get("NAIM_BRIDGE", "")
    if ":" not in spec:
        return None
    import socket
    port, token = spec.split(":", 1)
    with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout) as s:
        s.sendall((json.dumps({"token": token, "cmd": cmd, "args": [str(a) for a in args]}) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    res = json.loads(data or b"{}")
    if res.get("error") == "accessibility":
        permissions(request=True)
        raise ComputerError("pas le droit de cliquer/taper. " + PERM_HELP.format(what="Accessibilité"))
    if res.get("error"):
        raise ComputerError(res["error"])
    return res


def _run(*args, timeout=30):
    if args and args[0] in BRIDGE_CMDS:
        try:
            res = _bridge(args[0], args[1:], timeout=max(timeout, 60))
        except OSError:
            res = None  # the app is not reachable: fall back to the helper
        if res is not None:
            return res
    r = subprocess.run([helper(), *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise ComputerError(r.stderr.strip() or f"naim-input {args[0]} a échoué")
    return json.loads(r.stdout or "null")


def permissions(request=False):
    """{"screen", "accessibility"}. With the native app, both are Naim.app's own permissions (and a request makes
    macOS add « Naim » to the lists in System Settings)."""
    try:
        b = _bridge("perm", ["--request"] if request else [])
    except OSError:
        b = None
    if b is not None:
        return {"screen": bool(b.get("screen")), "accessibility": bool(b.get("accessibility"))}
    return _run("perm", *(["--request"] if request else []))


LAST_NOTIF = {"n": 0}  # where the last notification leads (a conversation, a page): opened when Naim comes back


def notify(title, text, sound=False, target=None):
    """macOS notification from Naim itself when the native app runs (osascript notifications belong to
    Script Editor: clicking them opened an empty Script Editor window). target = {"conv": id} or {"view": …}:
    clicking the notification brings Naim back, and the interface then opens that place."""
    title, text = str(title)[:120], " ".join(str(text).split())[:300]
    if target:
        LAST_NOTIF.clear()
        LAST_NOTIF.update({"n": int(time.time() * 1000), "time": time.time(), "title": title,
                           **{k: v for k, v in target.items() if k in ("conv", "view", "tab")}})
    try:
        if _bridge("notify", [title, text]) is not None:
            return
    except (OSError, ComputerError, ValueError):
        pass
    script = f"display notification {json.dumps(text)} with title {json.dumps(title)}" + (' sound name "Glass"' if sound else "")
    subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


PERM_HELP = ("Autorise Naim dans Réglages Système → Confidentialité et sécurité → {what} "
             "(active « Naim » ou le Terminal si tu lances naim --web), puis relance Naim.")


def _need(kind):
    p = permissions()
    if kind == "screen" and not p["screen"]:
        permissions(request=True)
        raise ComputerError("pas d'accès à l'écran. " + PERM_HELP.format(what="Enregistrement de l'écran"))
    if kind == "input" and not p["accessibility"]:
        permissions(request=True)
        raise ComputerError("pas le droit de cliquer/taper. " + PERM_HELP.format(what="Accessibilité"))


def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def _resize(src, dst, width):
    subprocess.run(["sips", "--resampleWidth", str(int(width)), str(src), "--out", str(dst)],
                   capture_output=True, timeout=30)
    return dst if Path(dst).exists() else src


class Screen:
    """State of the last screenshot: mapping image pixels -> screen points, and the OCR texts."""

    def __init__(self):
        self.origin, self.k, self.texts, self.size, self.kind = (0.0, 0.0), 1.0, [], (0, 0), None

    def to_screen(self, x, y):
        return self.origin[0] + float(x) * self.k, self.origin[1] + float(y) * self.k

    def capture(self, window=None, label="écran"):
        """Capture the main display (or one window). Returns (description text, base64 PNG for the model)."""
        _need("screen")
        SHOTS.mkdir(parents=True, exist_ok=True)
        raw = Path(tempfile.mkstemp(suffix=".png", dir=SHOTS)[1])
        if window:
            cmd = ["screencapture", "-x", "-o", f"-l{window['id']}", str(raw)]
            origin, pts_w = (window["x"], window["y"]), window["w"]
        else:
            cmd = ["screencapture", "-x", "-m", str(raw)]
            info = _run("screen")
            origin, pts_w = (0.0, 0.0), info["width"]
        subprocess.run(cmd, capture_output=True, timeout=30)
        if not raw.exists() or raw.stat().st_size == 0:
            raise ComputerError("capture d'écran impossible")
        pw, ph = _png_size(raw)
        scale = pw / pts_w if pts_w else 1.0          # retina pixels per point
        img_w = min(MAX_W, int(pts_w))
        small = _resize(raw, raw.with_name(raw.stem + "_s.png"), img_w)
        iw, ih = _png_size(small)
        self.origin, self.k, self.size, self.kind = origin, pts_w / iw, (iw, ih), label
        ratio = iw / pw                                 # raw pixels -> image pixels
        texts = []
        for t in _run("ocr", raw, timeout=60) or []:
            if t["text"].strip():
                texts.append({"text": t["text"].strip(), "x": round(t["x"] * ratio), "y": round(t["y"] * ratio)})
        texts.sort(key=lambda t: (t["y"] // 12, t["x"]))
        self.texts = texts
        jpg = small.with_suffix(".jpg")
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "70", str(small), "--out", str(jpg)],
                       capture_output=True, timeout=30)
        data = base64.b64encode((jpg if jpg.exists() else small).read_bytes()).decode()
        jpg.unlink(missing_ok=True)
        keep = SHOTS / "dernier.png"
        shutil.copy(small, keep)
        raw.unlink(missing_ok=True)
        small.unlink(missing_ok=True)
        _prune_shots()
        lines = [f'- "{t["text"][:60]}" ({t["x"]}, {t["y"]})' for t in texts[:150]]
        more = f"\n… et {len(texts) - 150} autres textes" if len(texts) > 150 else ""
        desc = (f"Capture de {label} : image {iw}×{ih} (coordonnées x, y dans cette image, origine en haut à gauche).\n"
                f"Textes visibles et leur position (centre) — utilise click_text avec le texte, ou click avec x, y :\n"
                + ("\n".join(lines) or "(aucun texte détecté)") + more)
        return desc, data

    def find(self, text, index=0):
        """OCR entry matching `text` (exact first, then case-insensitive substring)."""
        hits = self.matches(text)
        if not hits:
            return None, hits
        return hits[min(int(index or 0), len(hits) - 1)], hits

    @staticmethod
    def norm(s):
        """Lower case, no accents, no punctuation: « Paramètres… » and « parametres » are the same text."""
        import unicodedata
        s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()
        return " ".join(re.sub(r"[^\w\s]", " ", s).split())

    def matches(self, text):
        """OCR entries for `text`, best first: exact, same text without accents/case, contained, then close
        (one or two letters misread by the text recognition)."""
        import difflib
        want, wn = text.strip().lower(), self.norm(text)
        exact = [t for t in self.texts if t["text"].lower() == want]
        same = [t for t in self.texts if self.norm(t["text"]) == wn and t not in exact]
        part = [t for t in self.texts if wn and wn in self.norm(t["text"]) and t not in exact + same]
        found = exact + same + part
        if not found and len(wn) >= 4:
            scored = [(difflib.SequenceMatcher(None, wn, self.norm(t["text"])).ratio(), t) for t in self.texts]
            found = [t for r, t in sorted(scored, key=lambda x: -x[0]) if r >= 0.8][:5]
        return found

    def nearest(self, hits, anchor):
        """The hit closest to the visible text `anchor` (e.g. the « Supprimer » next to « Facture 12 »)."""
        refs = self.matches(anchor)
        if not refs:
            return None
        return min(hits, key=lambda h: min((h["x"] - r["x"]) ** 2 + (h["y"] - r["y"]) ** 2 for r in refs))

    def snapshot(self):
        return [(t["text"], t["x"], t["y"]) for t in self.texts]

    @staticmethod
    def diff(before, after, limit=12):
        """What changed on screen between two OCR snapshots, in a few lines (to check an action)."""
        b, a = {t for t, _, _ in before}, {t for t, _, _ in after}
        new, gone = [t for t in dict.fromkeys(x for x, _, _ in after) if t not in b], [t for t in dict.fromkeys(x for x, _, _ in before) if t not in a]
        if not new and not gone:
            return "Rien n'a changé à l'écran (le clic n'a peut-être pas eu d'effet, ou l'effet n'a pas de texte)."
        out = []
        if new:
            out.append("Apparu : " + ", ".join(f"« {t[:40]} »" for t in new[:limit]) + (f" … (+{len(new) - limit})" if len(new) > limit else ""))
        if gone:
            out.append("Disparu : " + ", ".join(f"« {t[:40]} »" for t in gone[:limit]) + (f" … (+{len(gone) - limit})" if len(gone) > limit else ""))
        return "\n".join(out)


def thumbnail(width=520):
    """Small JPEG (base64) of the last screenshot, for the chat view."""
    src = SHOTS / "dernier.png"
    if not src.exists():
        return None
    dst = SHOTS / "miniature.jpg"
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "70", "--resampleWidth", str(width),
                    str(src), "--out", str(dst)], capture_output=True, timeout=30)
    return base64.b64encode(dst.read_bytes()).decode() if dst.exists() else None


def _prune_shots(keep=30):
    files = sorted(SHOTS.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files[keep:]:
        p.unlink(missing_ok=True)


def activate(app):
    subprocess.run(["osascript", "-e", f'tell application "{app}" to activate'], capture_output=True, timeout=15)
    time.sleep(0.4)


# ---------------------------------------------------------------------- computer tool
class Computer:
    def __init__(self):
        self.screen = Screen()
        self.window = None  # set by the simulator: captures then target that window only
        self.app = None     # app opened with open_app: screenshots show only its window (smaller, faster)

    def _point(self, x, y):
        if self.screen.kind is None:
            return float(x), float(y)  # no screenshot yet: treat as screen points
        return self.screen.to_screen(x, y)

    def screenshot(self, full=False):
        if self.window:
            return self.screen.capture(self.window, "la fenêtre du simulateur")
        if self.app and not full:
            win = _run("appwin", self.app)
            if win:
                activate(self.app)
                return self.screen.capture(win, f"la fenêtre de {win['owner'] or self.app}")
        return self.screen.capture(None, "l'écran")

    def click(self, x, y, button="left"):
        _need("input")
        sx, sy = self._point(x, y)
        _run("click", round(sx), round(sy), {"double": "double", "right": "right"}.get(button, "left"))
        return f"ok: clic {button} en ({x}, {y})"

    def click_text(self, text, index=None, button="left", near=None):
        """Click a visible text. Several matches and no index / near: nothing is clicked, the candidates are listed."""
        if not self.screen.texts:
            self.screenshot()
        found = self.screen.matches(text)
        if not found:
            self.screenshot()  # the screen may have changed: look again
            found = self.screen.matches(text)
        if not found:
            visible = ", ".join(f'"{t["text"][:30]}"' for t in self.screen.texts[:40])
            return (f"error: texte « {text} » introuvable à l'écran (c'est peut-être une icône sans texte : regarde "
                    f"l'image et clique avec click x, y). Textes visibles : {visible}")
        if near:
            hit = self.screen.nearest(found, near)
            if hit is None:
                return f"error: « {near} » (près de) introuvable à l'écran"
        elif len(found) > 1 and index is None and not (found[0]["text"].lower() == text.strip().lower()
                                                       and sum(t["text"].lower() == text.strip().lower() for t in found) == 1):
            lst = "\n".join(f"  index {i} : « {t['text'][:40]} » en ({t['x']}, {t['y']})" for i, t in enumerate(found[:10]))
            return (f"ambigu : « {text} » apparaît {len(found)} fois. Rien n'a été cliqué. Choisis avec index, ou avec near "
                    f"= un texte proche de la bonne cible :\n{lst}")
        else:
            hit = found[min(int(index or 0), len(found) - 1)]
        self.click(hit["x"], hit["y"], button)
        other = f" ({len(found)} correspondances)" if len(found) > 1 else ""
        return f'ok: clic sur « {hit["text"]} » en ({hit["x"]}, {hit["y"]}){other}'

    def type_text(self, text):
        _need("input")
        _run("type", text, timeout=120)
        return f"ok: tapé {len(text)} caractères"

    def key(self, keys):
        _need("input")
        _run("key", keys)
        return f"ok: touche {keys}"

    def scroll(self, amount=-5, x=None, y=None):
        _need("input")
        if x is not None and y is not None:
            sx, sy = self._point(x, y)
            _run("move", round(sx), round(sy))
        _run("scroll", int(amount))
        return f"ok: défilement de {amount}"

    def drag(self, x, y, x2, y2):
        _need("input")
        a, b = self._point(x, y), self._point(x2, y2)
        _run("drag", *(round(v) for v in (*a, *b)))
        return f"ok: glissé de ({x}, {y}) à ({x2}, {y2})"

    def open_app(self, app):
        r = subprocess.run(["open", "-a", app], capture_output=True, text=True, timeout=30)
        if r.returncode != 0 and (path := find_app(app)):
            r = subprocess.run(["open", path], capture_output=True, text=True, timeout=30)
            app = Path(path).stem
        if r.returncode != 0:
            return f"error: impossible d'ouvrir {app} : application introuvable"
        time.sleep(1.5)
        self.app = app
        return (f"ok: {app} ouvert et au premier plan. Pour saisir du texte ou des nombres, utilise type "
                f"(par exemple text=\"12*7=\") ou key plutôt que de cliquer sur des boutons.")


def find_app(name):
    """Find an installed app by its displayed (possibly translated) name, e.g. « Calculatrice » -> Calculator.app."""
    safe = name.replace("'", "").replace("\\", "")
    r = subprocess.run(["mdfind", f"kMDItemDisplayName == '{safe}*'cd && kMDItemContentType == 'com.apple.application-bundle'"],
                       capture_output=True, text=True, timeout=20)
    paths = [p for p in r.stdout.splitlines() if p.startswith(("/Applications", "/System/Applications", str(Path.home() / "Applications")))]
    return paths[0] if paths else None


# ---------------------------------------------------------------------- iOS Simulator
def simctl(*args, timeout=120):
    r = subprocess.run(["xcrun", "simctl", *map(str, args)], capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def devices():
    code, text = simctl("list", "devices", "available", "-j")
    if code != 0:
        raise ComputerError("simctl indisponible : " + text[-300:])
    out = []
    for runtime, devs in json.loads(text)["devices"].items():
        os_name = runtime.split(".")[-1].replace("-", " ", 1).replace("-", ".")
        for d in devs:
            out.append({"name": d["name"], "udid": d["udid"], "state": d["state"], "os": os_name})
    return out


IOS_PROJECT_YML = """name: {name}
options:
  bundleIdPrefix: com.naim
  deploymentTarget:
    iOS: "17.0"
targets:
  {name}:
    type: application
    platform: iOS
    sources: [Sources]
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: com.naim.{bundle}
        GENERATE_INFOPLIST_FILE: YES
        INFOPLIST_KEY_CFBundleDisplayName: {name}
        INFOPLIST_KEY_UILaunchScreen_Generation: YES
        MARKETING_VERSION: "1.0"
        CURRENT_PROJECT_VERSION: "1"
        CODE_SIGNING_ALLOWED: NO
"""
IOS_APP_SWIFT = """import SwiftUI

@main
struct {name}App: App {{
    var body: some Scene {{
        WindowGroup {{
            ContentView()
        }}
    }}
}}
"""
IOS_CONTENT_SWIFT = """import SwiftUI

struct ContentView: View {{
    @State private var count = 0

    var body: some View {{
        VStack(spacing: 20) {{
            Text("{name}")
                .font(.largeTitle.bold())
            Text("Compteur : \\(count)")
            Button("Ajouter") {{ count += 1 }}
                .buttonStyle(.borderedProminent)
        }}
        .padding()
    }}
}}

#Preview {{
    ContentView()
}}
"""


class Simulator:
    def __init__(self, computer, root):
        self.computer, self.root, self.udid = computer, Path(root), None

    def _device(self, device=None):
        devs = devices()
        if device:
            d = next((x for x in devs if device in (x["udid"], x["name"])), None) or \
                next((x for x in devs if device.lower() in x["name"].lower()), None)
            if not d:
                raise ComputerError(f"simulateur « {device} » introuvable")
            return d
        booted = [x for x in devs if x["state"] == "Booted"]
        if booted:
            return next((x for x in booted if x["udid"] == self.udid), booted[0])
        iphones = [x for x in devs if x["name"].startswith("iPhone")]
        if not iphones:
            raise ComputerError("aucun simulateur iPhone installé (Xcode → Settings → Platforms)")
        return iphones[-1]  # newest runtime is listed last

    def _window(self, d):
        wins = [w for w in _run("windows", "simulator") if w["w"] > 150 and w["h"] > 150]
        named = [w for w in wins if d["name"] in w["name"]]
        wins = named or wins
        return max(wins, key=lambda w: w["w"] * w["h"]) if wins else None

    def list(self):
        rows = [f"- {d['name']} ({d['os']}) — {'démarré' if d['state'] == 'Booted' else 'éteint'} — {d['udid']}"
                for d in devices() if d["name"].startswith(("iPhone", "iPad"))]
        return "\n".join(rows) or "aucun simulateur"

    def boot(self, device=None):
        d = self._device(device)
        if d["state"] != "Booted":
            code, text = simctl("boot", d["udid"])
            if code != 0 and "current state: Booted" not in text:
                return f"error: démarrage impossible : {text[-300:]}"
        subprocess.run(["open", "-a", "Simulator", "--args", "-CurrentDeviceUDID", d["udid"]], capture_output=True)
        simctl("bootstatus", d["udid"], "-b", timeout=240)
        self.udid = d["udid"]
        time.sleep(1.5)
        return f"ok: {d['name']} ({d['os']}) démarré et affiché"

    def shutdown(self, device=None):
        d = self._device(device)
        code, text = simctl("shutdown", d["udid"])
        return f"ok: {d['name']} éteint" if code == 0 else f"error: {text[-300:]}"

    def _booted(self, device=None):
        d = self._device(device)
        if d["state"] != "Booted":
            self.boot(d["udid"])
        self.udid = d["udid"]
        return d

    def install(self, app_path, device=None):
        d = self._booted(device)
        p = (self.root / app_path).resolve() if not os.path.isabs(app_path) else Path(app_path)
        if not p.exists():
            return f"error: {app_path} introuvable"
        code, text = simctl("install", d["udid"], p, timeout=300)
        bid = bundle_id(p)
        return (f"ok: installé sur {d['name']}" + (f" (bundle id {bid})" if bid else "")) if code == 0 else f"error: {text[-500:]}"

    def launch(self, bundle, device=None):
        d = self._booted(device)
        simctl("terminate", d["udid"], bundle)
        code, text = simctl("launch", d["udid"], bundle)
        time.sleep(2)
        return f"ok: {bundle} lancé ({text})" if code == 0 else f"error: {text[-500:]}"

    def terminate(self, bundle, device=None):
        d = self._booted(device)
        code, text = simctl("terminate", d["udid"], bundle)
        return f"ok: {bundle} arrêté" if code == 0 else f"error: {text[-300:]}"

    def open_url(self, url, device=None):
        d = self._booted(device)
        code, text = simctl("openurl", d["udid"], url)
        time.sleep(1.5)
        return f"ok: {url} ouvert" if code == 0 else f"error: {text[-300:]}"

    def logs(self, bundle=None, device=None, seconds=30):
        d = self._booted(device)
        pred = f'process == "{bundle.split(".")[-1]}"' if bundle else 'messageType == error'
        r = subprocess.run(["xcrun", "simctl", "spawn", d["udid"], "log", "show", "--last", f"{int(seconds)}s",
                            "--style", "compact", "--predicate", pred], capture_output=True, text=True, timeout=60)
        return (r.stdout[-6000:] or r.stderr[-1000:] or "(aucun log)")

    def _dir(self, path=None):
        d = (self.root / path).resolve() if path else self.root
        if self.root != d and self.root not in d.parents:
            raise ComputerError("le dossier doit être dans le projet")
        return d

    def new_app(self, name, path=None):
        """Create a minimal SwiftUI app that builds (XcodeGen project), ready to be modified."""
        clean = re.sub(r"[^A-Za-z0-9]", "", name or "") or "MonApp"
        clean = clean[0].upper() + clean[1:]
        d = self._dir(path or clean)
        if (d / "project.yml").exists() or list(d.glob("*.xcodeproj")):
            return f"error: {d} contient déjà un projet ; modifie-le au lieu d'en créer un nouveau"
        (d / "Sources").mkdir(parents=True, exist_ok=True)
        (d / "project.yml").write_text(IOS_PROJECT_YML.format(name=clean, bundle=clean.lower()))
        (d / "Sources" / f"{clean}App.swift").write_text(IOS_APP_SWIFT.format(name=clean))
        (d / "Sources" / "ContentView.swift").write_text(IOS_CONTENT_SWIFT.format(name=clean))
        gen = self._xcodegen(d)
        if gen:
            return gen
        rel = d.relative_to(self.root) if d != self.root else Path(".")
        return (f"ok: app iOS « {clean} » créée dans {rel}/ (project.yml, Sources/{clean}App.swift, "
                f"Sources/ContentView.swift, {clean}.xcodeproj). Modifie Sources/ContentView.swift (et ajoute des fichiers "
                f"dans Sources/), puis simulator action=build_run path={rel}.")

    def _xcodegen(self, d):
        """Generate the .xcodeproj from project.yml. Returns an error message, or None when it worked."""
        if not shutil.which("xcodegen") and not Path("/opt/homebrew/bin/xcodegen").exists():
            return "error: xcodegen n'est pas installé (brew install xcodegen)"
        r = subprocess.run([shutil.which("xcodegen") or "/opt/homebrew/bin/xcodegen", "generate"], cwd=d,
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            return ("error: project.yml invalide — " + (r.stderr or r.stdout).strip()[-600:]
                    + "\nUn project.yml qui marche commence par `name: <App>` puis `targets:` (type: application, "
                      "platform: iOS, sources: [Sources]). Le plus simple : garde tes fichiers .swift, remplace "
                      "project.yml par ce modèle :\n" + IOS_PROJECT_YML.format(name=d.name.capitalize() or "App",
                                                                          bundle=(d.name or "app").lower()))
        return None

    def build_run(self, scheme=None, device=None, emit=None, cancel=None, path=None):
        """Build the project's iOS app for the simulator with xcodebuild, install it and launch it."""
        base = self._dir(path)
        d = self._booted(device)
        # XcodeGen project without its .xcodeproj yet: generate it first
        for yml in [base / "project.yml", *base.glob("*/project.yml")]:
            if yml.exists():  # always regenerate: new source files are picked up
                if err := self._xcodegen(yml.parent):
                    return err
        ws = sorted(base.glob("*.xcworkspace"))
        proj = sorted(base.glob("*.xcodeproj"))
        if not ws and not proj:
            ws, proj = sorted(base.glob("*/*.xcworkspace")), sorted(base.glob("*/*.xcodeproj"))
        if not ws and not proj:
            return ("error: aucun projet Xcode ici. Pour une nouvelle app : simulator action=new_app name=<Nom> "
                    "(crée un projet SwiftUI qui compile).")
        target = ["-workspace", str(ws[0])] if ws else ["-project", str(proj[0])]
        if not scheme:
            r = subprocess.run(["xcodebuild", *target, "-list", "-json"], capture_output=True, text=True, timeout=120)
            try:
                info = json.loads(r.stdout)
                schemes = (info.get("workspace") or info.get("project") or {}).get("schemes") or []
            except ValueError:
                schemes = []
            if not schemes:
                return "error: aucun scheme trouvé ; précise scheme"
            scheme = schemes[0]
        derived = base / ".naim-build"
        cmd = ["xcodebuild", *target, "-scheme", scheme, "-configuration", "Debug", "-destination", f"id={d['udid']}",
               "-derivedDataPath", str(derived), "build"]
        proc = subprocess.Popen(cmd, cwd=base, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines, errors = [], []
        for line in proc.stdout:
            lines.append(line)
            if "error:" in line:
                errors.append(line.strip())
            if re.search(r"error:|BUILD (SUCCEEDED|FAILED)|\*\* ", line):
                if emit:
                    emit({"type": "output", "text": line})
            if cancel is not None and cancel.is_set():
                proc.kill()
                return "error: compilation arrêtée"
        proc.wait()
        if proc.returncode != 0:
            detail = "\n".join(dict.fromkeys(errors)) or "".join(lines[-40:])
            return f"error: la compilation a échoué (scheme {scheme}) :\n{detail[-4000:]}"
        apps = sorted(derived.glob("Build/Products/*-iphonesimulator/*.app"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not apps:
            return "error: compilation réussie mais aucune .app trouvée"
        app = apps[0]
        res = self.install(str(app), d["udid"])
        if res.startswith("error"):
            return res
        bid = bundle_id(app)
        launched = self.launch(bid, d["udid"]) if bid else "bundle id introuvable, app non lancée"
        return f"ok: compilé ({scheme}), installé et lancé sur {d['name']}.\n{launched}\nApp : {app}"

    def screenshot(self, device=None):
        d = self._booted(device)
        activate("Simulator")
        win = self._window(d)
        if win and permissions()["screen"]:
            self.computer.window = win
            try:
                desc, img = self.computer.screenshot()
            finally:
                self.computer.window = None
            return desc + "\n(Pour toucher un élément : simulator action=tap_text ou tap avec ces coordonnées.)", img
        # no Screen Recording permission (or window hidden): device screenshot only, view without tapping
        path = SHOTS / "simulateur.png"
        SHOTS.mkdir(parents=True, exist_ok=True)
        code, text = simctl("io", d["udid"], "screenshot", path)
        if code != 0:
            raise ComputerError(text[-300:])
        small = _resize(path, SHOTS / "dernier.png", 600)
        self.computer.screen.kind = None
        return ("Capture du simulateur (sans accès à l'écran : je peux voir mais pas toucher par coordonnées ; "
                + PERM_HELP.format(what="Enregistrement de l'écran") + ")"), base64.b64encode(Path(small).read_bytes()).decode()

    def tap(self, x, y):
        activate("Simulator")
        return self.computer.click(x, y).replace("clic left", "toucher")

    def tap_text(self, text, index=None, near=None):
        activate("Simulator")
        d = self._booted()
        win = self._window(d)
        if win:
            self.computer.window = win
        try:
            self.computer.screenshot()
            return self.computer.click_text(text, index, near=near).replace("clic", "toucher")
        finally:
            self.computer.window = None

    def swipe(self, x, y, x2, y2):
        activate("Simulator")
        return self.computer.drag(x, y, x2, y2)

    def type_text(self, text):
        activate("Simulator")
        return self.computer.type_text(text)

    def home(self):
        activate("Simulator")
        return self.computer.key("cmd+shift+h").replace("touche cmd+shift+h", "retour à l'écran d'accueil")


def bundle_id(app):
    plist = Path(app) / "Info.plist"
    if not plist.exists():
        return None
    r = subprocess.run(["/usr/libexec/PlistBuddy", "-c", "Print :CFBundleIdentifier", str(plist)],
                       capture_output=True, text=True)
    return r.stdout.strip() or None


def status():
    """For the settings page: helper, permissions, simulators."""
    out = {"helper": BIN.exists(), "screen": False, "accessibility": False, "xcode": bool(shutil.which("xcrun")), "devices": 0}
    try:
        out.update(permissions())
        out["helper"] = True
    except Exception as e:
        out["error"] = str(e)
    try:
        out["devices"] = sum(d["name"].startswith(("iPhone", "iPad")) for d in devices())
    except Exception:
        pass
    return out
