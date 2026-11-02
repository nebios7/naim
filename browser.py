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


# What a person sees at a glance and a page cannot say by itself: measured in the real page (Naim does not see images)
AUDIT_JS = r"""(() => {
  const out = [], W = innerWidth, sel = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.classList.length ? '.' + [...e.classList].slice(0, 2).join('.') : '');
  const vis = (e) => { const s = getComputedStyle(e), r = e.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05 && r.width > 0 && r.height > 0; };
  const all = [...document.body.querySelectorAll('*')].filter(vis);
  const over = document.documentElement.scrollWidth - W;
  if (over > 4) out.push('La page déborde à droite de ' + over + ' px (une barre de défilement horizontale) : ' +
    all.filter((e) => e.getBoundingClientRect().right > W + 2).slice(0, 3).map(sel).join(', '));
  const cut = all.filter((e) => e.children.length === 0 && (e.textContent || '').trim().length > 2 && e.scrollWidth > e.clientWidth + 3 && /hidden|clip/.test(getComputedStyle(e).overflow + getComputedStyle(e).overflowX)).slice(0, 4);
  if (cut.length) out.push('Texte coupé (trop long pour sa boîte) : ' + cut.map((e) => sel(e) + ' « ' + e.textContent.trim().slice(0, 30) + ' »').join(', '));
  const texts = all.filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 1)).slice(0, 250);
  const rects = texts.map((e) => e.getBoundingClientRect()), hits = [];
  for (let i = 0; i < texts.length && hits.length < 3; i++) for (let j = i + 1; j < texts.length && hits.length < 3; j++) {
    if (texts[i].contains(texts[j]) || texts[j].contains(texts[i])) continue;
    const a = rects[i], b = rects[j], x = Math.min(a.right, b.right) - Math.max(a.left, b.left), y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (x > 4 && y > 4 && x * y > 0.3 * Math.min(a.width * a.height, b.width * b.height)) hits.push(sel(texts[i]) + ' et ' + sel(texts[j]));
  }
  if (hits.length) out.push('Textes qui se chevauchent : ' + hits.join(' ; '));
  const broken = [...document.images].filter((i) => i.complete && i.naturalWidth === 0 && vis(i));
  if (broken.length) out.push(broken.length + ' image(s) cassée(s) : ' + broken.slice(0, 3).map((i) => i.getAttribute('src') || '').join(', '));
  const tiny = texts.filter((e) => parseFloat(getComputedStyle(e).fontSize) < 10);
  if (tiny.length > 3) out.push(tiny.length + ' textes de moins de 10 px (illisibles)');
  if ((document.body.innerText || '').trim().length < 15 && !document.querySelector('canvas,svg,img,video,iframe')) out.push('La page est vide (presque aucun texte, rien de dessiné)');
  return JSON.stringify(out);
})()"""


def audit(url):
    """The visible problems of a page (overflow, cut or overlapping text, broken images, script errors, empty page), as
    sentences; [] when it looks right. Opened in a fresh WebKit window of 1280 × 800, closed after."""
    b = Browser()
    try:
        r = b.send(cmd="open", url=url)
        if r.get("error"):
            return [f"La page ne s'ouvre pas : {r['error']}"]
        problems = []
        if r.get("status") and int(r["status"]) >= 400:
            problems.append(f"La page répond {r['status']}")
        res = b.send(cmd="eval", js=AUDIT_JS).get("result") or "[]"
        try:
            problems += json.loads(res)
        except ValueError:
            pass
        log = b.send(cmd="console")
        errs = [e.get("text") or e.get("message") or "" for e in (log.get("log") or []) if e.get("level") == "error"][:3]
        if errs:
            problems.append("Erreurs JavaScript : " + " | ".join(str(x)[:160] for x in errs))
        return problems
    except Exception:  # noqa: BLE001 — no browser here: no audit, never a crash
        return []
    finally:
        b.close()
