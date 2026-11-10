"""The links of an answer checked before it is shown: a small model writes addresses that look right and do not
exist (https://site.fr/guide-2024 → 404). Only the links it did not get from a tool or from the user are tried;
a link is dead only when the server says so (404, 410) or the name does not exist - a site that refuses robots
(403, 429) or a slow one is not a dead link. With no network at all, nothing is reported."""
import re
import socket
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://[^\s<>()\[\]\"'`]+")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
LOCAL = re.compile(r"^(localhost|127\.|0\.0\.0\.0|192\.168\.|10\.|\[::1\]|.*\.local$|.*\.test$|.*\.localhost$|example\.(com|org|net)$)")


def links(text):
    """The web addresses of a text, without the punctuation that ends a sentence."""
    out = []
    for u in URL_RE.findall(text or ""):
        u = u.rstrip(".,;:!?*_»")
        if u not in out:
            out.append(u)
    return out


def _status(url, timeout):
    """'dead' (404, 410, unknown name), 'ok', or 'unknown' (refused, slow, other error: not reported)."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout):
                return "ok"
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                if method == "HEAD":
                    continue  # some servers answer HEAD badly: GET decides
                return "dead"
            if e.code in (405, 501) and method == "HEAD":
                continue
            return "unknown"
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.gaierror):
                return "dead"
            return "unknown"
        except Exception:  # noqa: BLE001 — a bad address, a timeout: not reported
            return "unknown"
    return "unknown"


def _online():
    try:
        socket.getaddrinfo("apple.com", 443)
        return True
    except OSError:
        return False


def dead(text, known="", limit=6, timeout=5):
    """The links of `text` that do not exist, among those not already in `known` (tool results, the user's words)."""
    todo = [u for u in links(text) if u not in (known or "") and not LOCAL.match(urlparse(u).hostname or "")][:limit]
    if not todo:
        return []
    with ThreadPoolExecutor(max_workers=len(todo)) as ex:
        res = list(ex.map(lambda u: _status(u, timeout), todo))
    bad = [u for u, r in zip(todo, res) if r == "dead"]
    if bad and len(bad) == len(todo) and not _online():
        return []  # no network: nothing can be said
    return bad
