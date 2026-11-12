"""Pictures for the English games: one free image per word, kept on this Mac.

A word is shown by the lead image of its English Wikipedia article (« apple » → the article Apple → a real apple),
free licences only; without one, the best file of Wikimedia Commons whose name holds the word. Every picture is
downloaded once (400 px), with its author and licence, then served from the cache: a game played again needs no
network, and Wikipedia is asked in one batch (it refuses too many calls in a row).
"""
import hashlib
import html
import json
import re
import threading
import urllib.parse
import urllib.request
from pathlib import Path

DIR = Path.home() / ".naim" / "cache" / "anglais"
INDEX = DIR / "index.json"
UA = {"User-Agent": "Naim/1.0 (assistant local ; jeux pour apprendre l'anglais)"}
WIKI, COMMONS = "https://en.wikipedia.org/w/api.php", "https://commons.wikimedia.org/w/api.php"
_lock = threading.Lock()


def _get(url, params, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers=UA), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()


def key(item):
    """What a word's picture is looked up by: its hint (« red apple »), else the English word."""
    return re.sub(r"\s+", " ", str(item.get("image") or item.get("en") or "")).strip().lower()


def _load():
    try:
        return json.loads(INDEX.read_text())
    except (OSError, ValueError):
        return {}


def _credit(meta):
    who = _plain((meta.get("Artist") or {}).get("value")) or "auteur inconnu"
    lic = _plain((meta.get("LicenseShortName") or {}).get("value")) or "licence libre"
    return f"{who[:60]} · {lic} · Wikimedia Commons"


def _files_info(files):
    """{file name: (thumbnail url, credit)} for Commons files, in one call."""
    out = {}
    if not files:
        return out
    d = _get(COMMONS, {"action": "query", "format": "json", "titles": "|".join("File:" + f for f in files),
                       "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "400"})
    norm = {n["to"]: n["from"] for n in (d.get("query") or {}).get("normalized", [])}
    for p in (d.get("query") or {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("thumburl"):
            name = norm.get(p.get("title"), p.get("title", ""))[5:]
            out[name.replace(" ", "_")] = (ii["thumburl"], _credit(ii.get("extmetadata") or {}))
    return out


def _wiki_lead(words):
    """{word: Commons file} - the free lead image of each word's English Wikipedia article, in one call."""
    if not words:
        return {}
    d = _get(WIKI, {"action": "query", "format": "json", "titles": "|".join(w.capitalize() for w in words), "prop": "pageimages",
                    "piprop": "name", "pilicense": "free", "redirects": "1"})
    q = d.get("query") or {}
    back = {}
    for kind in ("normalized", "redirects"):
        for n in q.get(kind, []):
            back[n["to"]] = back.get(n["from"], n["from"])
    out = {}
    for p in q.get("pages", {}).values():
        if p.get("pageimage"):
            asked = back.get(p["title"], p["title"])
            out[asked.lower()] = p["pageimage"]
    return out


def _commons_search(word):
    """The best Commons file for a word: a bitmap whose name holds the word, not too long or narrow."""
    d = _get(COMMONS, {"action": "query", "format": "json", "generator": "search", "gsrnamespace": "6", "gsrlimit": "10",
                       "gsrsearch": f"{word} filetype:bitmap", "prop": "imageinfo", "iiprop": "size"})
    pages = sorted((d.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    first = word.split()[-1].lower()
    def score(p):
        ii = (p.get("imageinfo") or [{}])[0]
        w, h = ii.get("width") or 1, ii.get("height") or 1
        return (first not in p["title"].lower(), not 0.5 < w / h < 2.2, len(p["title"]))
    pages.sort(key=score)
    return pages[0]["title"][5:].replace(" ", "_") if pages else None


def resolve(items, fetch=True):
    """{key: {"file": cached name, "credit": …}} for the words of a game; a word with no picture is left out."""
    keys = []
    for it in items or []:
        k = key(it)
        if k and k not in keys:
            keys.append(k)
    keys = keys[:40]
    with _lock:
        idx = _load()
        missing = [k for k in keys if k not in idx or not (DIR / idx[k].get("file", "-")).exists()]
        if missing and fetch:
            DIR.mkdir(parents=True, exist_ok=True)
            try:
                files = _wiki_lead(missing)
            except Exception:  # noqa: BLE001 — no network: the words show without pictures
                files = {}
            for k in missing:
                if k not in files:
                    try:
                        f = _commons_search(k)
                        if f:
                            files[k] = f
                    except Exception:  # noqa: BLE001
                        pass
            try:
                info = _files_info(sorted({f.replace(" ", "_") for f in files.values()}))
            except Exception:  # noqa: BLE001
                info = {}
            for k, f in files.items():
                got = info.get(f.replace(" ", "_"))
                if not got:
                    continue
                url, credit = got
                ext = (Path(urllib.parse.urlparse(url).path).suffix or ".jpg").lower()
                name = hashlib.sha1(k.encode()).hexdigest()[:16] + (ext if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp") else ".jpg")
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                        (DIR / name).write_bytes(r.read())
                except Exception:  # noqa: BLE001
                    continue
                idx[k] = {"file": name, "credit": credit, "source": f}
            INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    return {k: idx[k] for k in keys if k in idx and (DIR / idx[k]["file"]).exists()}


def path_of(name):
    """The cached picture called `name` (only names this module wrote), or None."""
    if not re.fullmatch(r"[0-9a-f]{16}\.(jpg|jpeg|png|gif|webp)", name or ""):
        return None
    f = DIR / name
    return f if f.is_file() else None
