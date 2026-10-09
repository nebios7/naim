#!/usr/bin/env python3
"""One-command launcher for Naim.

  naim            open Naim.app (native macOS app)
  naim --web      open the web UI in the default browser
  naim --tools    terminal agent (same as `naimtools`)
  naim --server   engine only (server + scheduler), started by Naim.app
  naim --window   old Python window (pywebview), if Naim.app is missing

Makes sure Ollama is running, starts the local server on 127.0.0.1:8765 (or reuses a running one),
then opens the UI.
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from naimtools import OLLAMA_HOST  # noqa: E402

PORT = int(os.environ.get("NAIM_PORT", "8765"))
URL = f"http://127.0.0.1:{PORT}"


def reachable(url, timeout=1.5):
    try:
        urllib.request.urlopen(url, timeout=timeout).close()
        return True
    except OSError:
        return False


def uses_ollama():
    """True when Naim's settings choose Ollama as the engine (the default engine is Naim's own llama.cpp)."""
    import json
    data = Path(os.environ.get("NAIM_DATA", Path.home() / "Library/Application Support/Naim"))
    try:
        s = json.loads((data / "settings.json").read_text())
    except (OSError, ValueError):
        return False
    model = str(s.get("model") or "naim").split(":")[0]
    return s.get("naim_backend", "llamacpp") == "ollama" or model != "naim"


def ensure_ollama():
    tags = f"{OLLAMA_HOST.rstrip('/')}/api/tags"
    if reachable(tags):
        return True
    if Path("/Applications/Ollama.app").exists():
        subprocess.Popen(["open", "-g", "-a", "Ollama"])
    elif shutil.which("ollama"):
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(30):
        time.sleep(0.5)
        if reachable(tags):
            return True
    print("⚠ Ollama ne répond pas : l'interface s'ouvrira quand même.", file=sys.stderr)
    return False


def port_in_use():
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def start_server():
    """Start the server in a background thread unless one is already running. Returns True if we own it."""
    if port_in_use():
        return False
    from server import serve
    httpd = serve(PORT)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return True


NAIM_VERSION = "3.0"


def brand_process():
    """Show Naim (name, icon, version, author) in the Dock, the menu bar and « À propos de Naim »
    instead of the Python interpreter's identity (the window is drawn by Python)."""
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSBundle
    except ImportError:
        return
    info = NSBundle.mainBundle().infoDictionary()
    info["CFBundleName"] = info["CFBundleDisplayName"] = "Naim"
    info["CFBundleShortVersionString"] = info["CFBundleVersion"] = NAIM_VERSION
    info["NSHumanReadableCopyright"] = "© ABDESSEMED Mohamed — agent autonome local, successeur de Mimo"
    app = NSApplication.sharedApplication()
    icon = Path(__file__).resolve().parent.parent / "Naim.app/Contents/Resources/Naim.icns"
    if icon.exists():
        app.setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(str(icon)))
    _replace_about(app)


def _replace_about(app):
    """Point the « À propos » menu item to a panel filled with Naim's own values (the standard one reads the
    interpreter's Info.plist)."""
    try:
        from AppKit import NSObject
        from Foundation import NSDictionary
    except ImportError:
        return

    class NaimAbout(NSObject):
        def show_(self, sender):
            opts = NSDictionary.dictionaryWithDictionary_({
                "ApplicationName": "Naim", "Version": "", "ApplicationVersion": f"Version {NAIM_VERSION}",
                "Copyright": "© ABDESSEMED Mohamed — agent autonome local, successeur de Mimo",
                "ApplicationIcon": app.applicationIconImage()})
            app.activateIgnoringOtherApps_(True)
            app.orderFrontStandardAboutPanelWithOptions_(opts)

    global _about_target
    _about_target = NaimAbout.alloc().init()

    def patch():
        menu = app.mainMenu()
        if menu is None or menu.numberOfItems() == 0:
            return False
        for item in menu.itemAtIndex_(0).submenu().itemArray():
            if str(item.action()) == "orderFrontStandardAboutPanel:":
                item.setTitle_("À propos de Naim")
                item.setTarget_(_about_target)
                item.setAction_(b"show:")
        return True

    try:  # the menu bar exists only once the window is up: retry a few times
        from PyObjCTools import AppHelper
        for delay in (0.5, 2, 5):
            AppHelper.callLater(delay, patch)
    except ImportError:
        pass


_about_target = None


def run_server():
    """Engine for the native app: HTTP server + scheduler in the foreground; SIGTERM stops everything cleanly."""
    import atexit
    import signal
    from naimtools import PROCESSES
    import extensions
    import llamacpp
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # run the atexit cleanups below
    if uses_ollama():  # Ollama is optional: started only when the chosen engine is Ollama (not with llama.cpp / MLX)
        threading.Thread(target=ensure_ollama, daemon=True).start()
    if port_in_use():
        print(f"Naim tourne déjà sur {URL}", file=sys.stderr)
        return
    from server import serve
    httpd = serve(PORT)
    atexit.register(PROCESSES.stop_all)
    atexit.register(extensions.MCP.stop_all)
    atexit.register(llamacpp.SERVER.stop)
    parent = os.getppid()
    try:
        by_app = "Naim.app" in subprocess.run(["ps", "-o", "comm=", "-p", str(parent)], capture_output=True, text=True).stdout
    except OSError:
        by_app = False
    if by_app:  # Naim.app force-quit: its engine must not stay alone, the next Naim would reuse this old code
        def orphan_watch():
            while os.getppid() == parent:
                time.sleep(3)
            os.kill(os.getpid(), signal.SIGTERM)
        threading.Thread(target=orphan_watch, daemon=True, name="naim-orphan-watch").start()
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} moteur Naim prêt sur {URL}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser(prog="naim", description="Lance Naim (application, web ou terminal).")
    ap.add_argument("--web", action="store_true", help="ouvrir dans le navigateur")
    ap.add_argument("--tools", action="store_true", help="agent dans le terminal (NaimTools)")
    ap.add_argument("--server", action="store_true", help="moteur seul (lancé par Naim.app)")
    ap.add_argument("--window", action="store_true", help="ancienne fenêtre Python (pywebview)")
    args, rest = ap.parse_known_args()

    if args.server:
        return run_server()
    native = Path.home() / "Applications/Naim.app"
    if not (args.web or args.tools or args.window) and native.exists():
        subprocess.run(["open", str(native)])
        return

    if args.tools:
        import naimtools
        sys.argv = ["naimtools"] + rest
        if uses_ollama():
            ensure_ollama()
        return naimtools.main()

    if uses_ollama():
        ensure_ollama()
    owned = start_server()
    if owned:  # background programs launched from Naim stop when Naim quits
        import atexit
        from naimtools import PROCESSES
        import extensions
        atexit.register(PROCESSES.stop_all)
        atexit.register(extensions.MCP.stop_all)

    if not args.web:
        try:
            import webview
        except ImportError:
            print("pywebview absent : ouverture dans le navigateur.", file=sys.stderr)
        else:
            brand_process()
            from webview.menu import Menu, MenuAction, MenuSeparator

            def cmd(name):
                return lambda: window.evaluate_js(f"window.naimCmd && naimCmd({name!r})")

            menu = [
                Menu("Fichier", [
                    MenuAction("Nouvelle conversation   ⌘N", cmd("new")),
                    MenuAction("Palette de commandes   ⌘K", cmd("palette")),
                    MenuSeparator(),
                    MenuAction("Exporter la conversation", cmd("export")),
                    MenuAction("Ouvrir le projet dans le Finder", cmd("reveal")),
                ]),
                Menu("Présentation", [
                    MenuAction("Zoom avant   ⌘+", cmd("zoomIn")),
                    MenuAction("Zoom arrière   ⌘−", cmd("zoomOut")),
                    MenuAction("Taille réelle   ⌘0", cmd("zoomReset")),
                    MenuSeparator(),
                    MenuAction("Masquer / afficher la barre latérale   ⌘B", cmd("sidebar")),
                    MenuAction("Afficher le terminal   ⌘J", cmd("terminal")),
                    MenuAction("Afficher les fichiers   ⇧⌘F", cmd("files")),
                    MenuAction("Artéfacts", cmd("artifacts")),
                    MenuSeparator(),
                    MenuAction("Actualiser   ⌘R", cmd("reload")),
                ]),
                Menu("Naim", [
                    MenuAction("Personnaliser…   ⌘,", cmd("settings")),
                    MenuAction("Modèles…", cmd("models")),
                    MenuAction("Raccourcis clavier   ⌘/", cmd("shortcuts")),
                ]),
            ]
            window = webview.create_window("Naim", URL, width=1240, height=840, min_size=(720, 520),
                                           text_select=True, zoomable=True, background_color="#161615")
            webview.start(menu=menu, private_mode=False,
                          storage_path=str(Path.home() / "Library/Application Support/Naim/webview"))
            return

    webbrowser.open(URL)
    if owned:
        print(f"Naim tourne sur {URL}  (Ctrl+C pour arrêter)")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
