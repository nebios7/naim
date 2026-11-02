"""A real browser for Naim (the Mac's WebKit, driven by naim_browser.swift): open a page, see its text and its
numbered buttons / links / fields, click, type, submit, read the JavaScript errors, take a screenshot.

One browser per agent task, with a clean session (no cookies from the user's own browser); it is closed at the end.
"""
import hashlib
import json
import re
import subprocess
import threading
from pathlib import Path

import extensions as ext

SRC = Path(__file__).with_name("naim_browser.swift")
BIN = ext.DATA / "bin" / "naim-browser"
SHOTS = ext.DATA / "screenshots"


class BrowserError(Exception):
    pass


def tool_path():
    """naim-browser, compiled on first use and again when its source changes."""
    h = hashlib.sha1(SRC.read_bytes()).hexdigest()[:16]
    stamp = BIN.with_name(".naim-browser.hash")
    if BIN.exists() and stamp.exists() and stamp.read_text().strip() == h:
        return str(BIN)
    BIN.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["swiftc", "-O", str(SRC), "-o", str(BIN)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise BrowserError("compilation du navigateur impossible : " + r.stderr[-400:])
    stamp.write_text(h)
    return str(BIN)


class Browser:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()

    def _start(self):
        if self.proc and self.proc.poll() is None:
            return
        self.proc = subprocess.Popen([tool_path()], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def send(self, timeout=45, **cmd):
        with self.lock:
            self._start()
            try:
                self.proc.stdin.write(json.dumps(cmd, ensure_ascii=False) + "\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError):
                self.proc = None
                raise BrowserError("le navigateur s'est fermé, réessaie")
            box = {}
            reader = threading.Thread(target=lambda: box.setdefault("line", self.proc.stdout.readline()), daemon=True)
            reader.start()
            reader.join(timeout)
            if "line" not in box:
                self.close()
                raise BrowserError(f"le navigateur ne répond plus ({timeout} s) : il a été relancé, rouvre la page")
            if not box["line"]:
                self.proc = None
                raise BrowserError("le navigateur s'est arrêté, rouvre la page")
            return json.loads(box["line"])

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write('{"cmd":"quit"}\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
        self.proc = None


def describe(r, full_text=False, limit=None, start=0):
    """Readable summary of a page answer for the model; `start`: the text from there (the next part of a long page)."""
    if r.get("error"):
        return f"error: {r['error']}"
    lines = []
    if r.get("action"):
        lines.append(f"✓ {r['action']}")
    head = f"Page : {r.get('title') or '(sans titre)'} — {r.get('url', '')}"
    if r.get("status"):
        head += f" (HTTP {r['status']})"
    lines.append(head)
    if r.get("js_errors"):
        lines.append(f"⚠ {r['js_errors']} erreur(s) JavaScript ou requête en échec : action=console pour les lire")
    els = r.get("elements") or []
    if els and not start:
        lines.append("Éléments (clique / remplis avec leur numéro) :\n" + "\n".join(els[:80])
                     + (f"\n… et {len(els) - 80} autres : action=page text=<mot> pour trouver celui qu'il te faut" if len(els) > 80 else ""))
    text = r.get("text") or ""
    if text:
        limit = limit or (4000 if full_text else 1500)
        part = text[start:start + limit]
        if start and not part:
            lines.append(f"(fin de la page : son texte a {len(text)} caractères, tout est déjà lu)")
        else:
            if start:
                lines.append(f"(suite : caractères {start} à {start + len(part)} sur {len(text)})")
            more = len(text) - start - len(part)
            cut = (f"\n… (encore {more} caractères : action=page target={start + len(part)} pour lire la suite, "
                   "ou action=page text=<mot> pour aller à ce que tu cherches)") if more > 0 else ""
            lines.append("Texte visible :\n" + part + cut)
    return "\n".join(lines)


def find_in(r, words, context=220, most=25):
    """The passages of the page and its elements that hold these words (any case, any accent): what a person finds
    with Cmd-F, on a page too long to read whole."""
    import unicodedata
    if r.get("error"):
        return f"error: {r['error']}"
    plain = lambda s: unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()  # noqa: E731
    want = [w for w in plain(words).split() if len(w) > 1] or [plain(words).strip()]
    text = r.get("text") or ""
    low = plain(text)  # same length as the text for French letters (one accent = one mark removed, one letter kept)
    if len(low) != len(text):
        low = text.lower()
    hits, last_end = [], -1
    for m in re.finditer("|".join(re.escape(w) for w in want), low):
        if m.start() < last_end:
            continue
        a, b = max(0, m.start() - context), min(len(text), m.end() + context)
        hits.append((-sum(w in low[a:b] for w in want), a, f"[position {a}] …{text[a:b].strip()}…"))
        last_end = b
    hits = [h for _, _, h in sorted(hits)[:most]]  # the passages with all the words first
    els = [e for e in (r.get("elements") or []) if any(w in plain(e) for w in want)]
    head = f"Page : {r.get('title') or '(sans titre)'} — {r.get('url', '')}\nRecherche de « {words} » :"
    if not hits and not els:
        return head + " rien sur cette page (essaie un autre mot, ou action=scroll si la page charge en défilant)."
    return (head + (f"\nÉléments :\n" + "\n".join(els[:40]) if els else "")
            + (f"\nPassages ({len(hits)}{'+' if len(hits) >= most else ''}) — pour lire autour : action=page target=<position> :\n"
               + "\n".join(hits) if hits else ""))
