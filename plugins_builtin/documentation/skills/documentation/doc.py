#!/usr/bin/env python3
"""The documentation of what is really installed, then the official sites — checked instead of guessed.

    python3 doc.py python datetime.datetime.strftime   the installed Python's own help (exact version)
    python3 doc.py python sympy                         a module: its contents (what really exists)
    python3 doc.py cmd ffmpeg                           a command: its manual or --help
    python3 doc.py node fs.readFile                     a Node module: what it exports, and its page on nodejs.org
    python3 doc.py web css grid                         the official page (MDN, docs.python.org…) found for a subject
    python3 doc.py three exemples extrude shape         three.js: the official examples that match (names, tags)
    python3 doc.py three exemple webgl_geometry_extrude_shapes   the code of one example (same version as Naim's model)
    python3 doc.py three classe ExtrudeGeometry         a class: its parameters and their order, from the source

Nothing is installed or downloaded: it reads what is on the Mac, or one official web page.
"""
import html
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

LIMIT = 6000  # one useful passage, not a whole manual
# the official documentation of common subjects (searched there first, not in forums)
SITES = {"python": "docs.python.org/3", "css": "developer.mozilla.org", "html": "developer.mozilla.org",
         "javascript": "developer.mozilla.org", "js": "developer.mozilla.org", "node": "nodejs.org/api", "react": "react.dev",
         "flask": "flask.palletsprojects.com", "django": "docs.djangoproject.com", "ffmpeg": "ffmpeg.org", "sqlite": "sqlite.org",
         "swift": "developer.apple.com", "swiftui": "developer.apple.com", "git": "git-scm.com/docs", "bash": "www.gnu.org/software/bash",
         "numpy": "numpy.org/doc", "pandas": "pandas.pydata.org/docs", "sympy": "docs.sympy.org", "matplotlib": "matplotlib.org",
         "fastapi": "fastapi.tiangolo.com", "tailwind": "tailwindcss.com/docs", "arduino": "docs.arduino.cc", "cobol": "www.ibm.com/docs",
         "three": "threejs.org", "threejs": "threejs.org", "three.js": "threejs.org"}


def run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return ""


def python_doc(name):
    """help() of the installed Python, for a module, a class or a function; a module: its public names first."""
    py = ".venv/bin/python" if shutil.os.path.exists(".venv/bin/python") else sys.executable
    code = ("import importlib, pydoc, sys\n"
            f"name = {name!r}\nparts = name.split('.')\nobj = None\n"
            "for i in range(len(parts), 0, -1):\n"
            "    try:\n        obj = importlib.import_module('.'.join(parts[:i])); rest = parts[i:]; break\n"
            "    except Exception: pass\n"
            "if obj is None: sys.exit('Introuvable : ' + parts[0] + \" n'est pas installé pour ce Python (pip install dans le .venv ?)\")\n"
            "for p in rest:\n"
            "    if not hasattr(obj, p):\n"
            "        near = [n for n in dir(obj) if p.lower()[:4] in n.lower()]\n"
            "        sys.exit(f'{p} n existe pas dans {obj.__name__ if hasattr(obj, \"__name__\") else obj}. Noms proches : {near[:15]}')\n"
            "    obj = getattr(obj, p)\n"
            "import inspect\n"
            "if inspect.ismodule(obj):\n"
            "    names = [n for n in dir(obj) if not n.startswith('_')]\n"
            "    print('Contenu de', obj.__name__, ':', ', '.join(names[:200]))\n"
            "print(pydoc.render_doc(obj, renderer=pydoc.plaintext))\n")
    return run([py, "-c", code])


def cmd_doc(name):
    out = run(["man", "-P", "cat", name]) if shutil.which("man") else ""
    out = re.sub(r".\x08", "", out)
    if len(out.strip()) < 200:
        out = run([name, "--help"]) or run([name, "-h"])
    return out or f"{name} : ni manuel ni --help (commande installée ? `which {name}`)."


def node_doc(name):
    mod, _, rest = name.partition(".")
    out = run(["node", "-e", f"const m=require({mod!r}); console.log(Object.keys(m).join(', '))"]) if shutil.which("node") else ""
    page = fetch(f"https://nodejs.org/api/{mod}.html", rest)
    return f"Exporté par {mod} : {out.strip()}\n\n{page}"


def fetch(url, focus=""):
    """One page as text; with a word to focus on, the passages around it."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Naim documentation)"})
        raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return f"(page {url} injoignable : {e})"
    text = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()
    if focus:
        hits = [m.start() for m in re.finditer(re.escape(focus), text, re.I)][:6]
        if hits:
            text = "\n…\n".join(text[max(0, h - 400): h + 1200] for h in hits)
    return f"[{url}]\n{text[:LIMIT]}"


def web_doc(subject, query):
    """The official site of the subject, searched with DuckDuckGo restricted to it; the first page read."""
    site = SITES.get(subject.lower(), "")
    q = f"site:{site} {query}" if site else f"{subject} {query} documentation officielle"
    try:
        req = urllib.request.Request("https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": q}),
                                     headers={"User-Agent": "Mozilla/5.0"})
        page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return f"Recherche impossible ({e}) : utilise web_search « {q} »."
    links = [urllib.parse.unquote(m) for m in re.findall(r'uddg=([^&"]+)', page)]
    if not links:  # DuckDuckGo refuses at times: Bing, its result links decoded
        try:
            req = urllib.request.Request("https://www.bing.com/search?" + urllib.parse.urlencode({"q": q, "setlang": "fr"}),
                                         headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15"})
            page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
            for href in re.findall(r'<h2[^>]*><a[^>]+href="([^"]+)"', page):
                href = html.unescape(href)
                if (m := re.search(r"[?&]u=a1([^&]+)", href)):
                    import base64
                    try:
                        href = base64.urlsafe_b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4)).decode()
                    except Exception:  # noqa: BLE001
                        continue
                links.append(href)
        except Exception:  # noqa: BLE001
            pass
    links = [l for l in links if l.startswith("http") and (not site or site.split("/")[0] in l)][:3]
    if not links:
        return f"Aucune page trouvée pour « {q} » : utilise web_search."
    return fetch(links[0], query.split()[-1] if query else "") + ("\n\nAutres pages : " + ", ".join(links[1:]) if links[1:] else "")


THREE_VERSION = "0.185.0"  # the version of the threejs-3d model: its examples and sources, not those of another release
THREE_TAG = "r" + THREE_VERSION.split(".")[1]


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def three_doc(what, words):
    """three.js, version of the model: examples found by their name and tags, an example's code, a class's source."""
    try:
        if what == "exemples":
            names = [n for group in json.loads(_get("https://threejs.org/examples/files.json")).values() for n in group]
            tags = json.loads(_get("https://threejs.org/examples/tags.json"))
            keys = [w.lower() for w in words if len(w) > 2]
            scored = sorted(((sum(k in n or any(k in t for t in tags.get(n, [])) for k in keys), n) for n in names), reverse=True)
            hits = [n for sc, n in scored if sc][:10]
            if not hits:
                return f"Aucun exemple pour « {' '.join(words)} » : essaie d'autres mots en anglais (extrude, lathe, instancing, csg, tube…)."
            return ("Exemples officiels de three.js (lis le code avec : doc.py three exemple <nom>) :\n" +
                    "\n".join(f"- {n} — https://threejs.org/examples/#{n}" for n in hits))
        if what == "exemple":
            page = _get(f"https://raw.githubusercontent.com/mrdoob/three.js/{THREE_TAG}/examples/{words[0]}.html")
            code = re.findall(r'<script type="module">(.*?)</script>', page, re.S)
            return f"[{words[0]}, three.js {THREE_VERSION}]\n" + ("\n".join(code) if code else page)
        if what == "classe":
            flat = json.loads(_get(f"https://data.jsdelivr.com/v1/package/npm/three@{THREE_VERSION}/flat"))["files"]
            path = next((f["name"] for f in flat if f["name"].endswith(f"/{words[0]}.js") and f["name"].startswith(("/src/", "/examples/jsm/"))), None)
            if not path:
                return f"Classe « {words[0]} » introuvable dans three.js {THREE_VERSION} : vérifie l'orthographe (majuscules)."
            src = _get(f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}{path}")
            imp = "three/addons/" + path[len("/examples/jsm/"):] if path.startswith("/examples/jsm/") else "three"
            return f"[{words[0]} — import depuis « {imp} » — three.js {THREE_VERSION}]\n" + src
    except Exception as e:  # noqa: BLE001
        return f"three.js : lecture impossible ({e}) : utilise web_search « threejs {' '.join(words)} »."
    return __doc__


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    kind, rest = a[0], a[1:]
    out = {"python": lambda: python_doc(rest[0]), "cmd": lambda: cmd_doc(rest[0]), "node": lambda: node_doc(rest[0]),
           "web": lambda: web_doc(rest[0], " ".join(rest[1:])), "three": lambda: three_doc(rest[0], rest[1:])}.get(kind, lambda: __doc__)()
    print(out[:LIMIT] + ("\n[… suite coupée : précise le nom (module.fonction) pour la partie utile]" if len(out) > LIMIT else ""))


if __name__ == "__main__":
    main()
