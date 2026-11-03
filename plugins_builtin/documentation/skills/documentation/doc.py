#!/usr/bin/env python3
"""The documentation of what is really installed, then the official sites — checked instead of guessed.

    python3 doc.py python datetime.datetime.strftime   the installed Python's own help (exact version)
    python3 doc.py python sympy                         a module: its contents (what really exists)
    python3 doc.py cmd ffmpeg                           a command: its manual or --help
    python3 doc.py node fs.readFile                     a Node module: what it exports, and its page on nodejs.org
    python3 doc.py web css grid                         the official page (MDN, docs.python.org…) found for a subject

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
         "fastapi": "fastapi.tiangolo.com", "tailwind": "tailwindcss.com/docs", "arduino": "docs.arduino.cc", "cobol": "www.ibm.com/docs"}


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


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    kind, rest = a[0], a[1:]
    out = {"python": lambda: python_doc(rest[0]), "cmd": lambda: cmd_doc(rest[0]), "node": lambda: node_doc(rest[0]),
           "web": lambda: web_doc(rest[0], " ".join(rest[1:]))}.get(kind, lambda: __doc__)()
    print(out[:LIMIT] + ("\n[… suite coupée : précise le nom (module.fonction) pour la partie utile]" if len(out) > LIMIT else ""))


if __name__ == "__main__":
    main()
