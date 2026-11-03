#!/usr/bin/env python3
"""Real images for a document (an anatomy plate, a photo, a map), free to reuse, from Wikimedia Commons.

  python3 images.py chercher "<mots en anglais>" [nombre]   numbered list: title, size, licence, author, description
  python3 images.py prendre <numéro> <dossier/image.jpg>     the image (1400 px wide) + its credit + the HTML figure

Every image of Commons has a free licence; its author and licence are written under it in the document (the
figcaption given by « prendre »). Nothing to install: the Commons API, read with Python alone.
"""
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "Naim/1.0 (assistant local ; documents de cours)"}
CACHE = Path.home() / ".naim" / "cache" / "images-recherche.json"


def _get(url, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        data = r.read()
    return data if binary else json.loads(data.decode("utf-8", errors="replace"))


def _plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()


def chercher(words, n=8):
    q = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": "6", "gsrlimit": str(max(n * 2, 10)),
         "gsrsearch": f"{words} filetype:bitmap|drawing", "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime",
         "iiurlwidth": "1400"}
    data = _get(API + "?" + urllib.parse.urlencode(q))
    pages = sorted((data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    found = []
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        if info.get("width", 0) < 500 or "image" not in str(info.get("mime", "")):
            continue  # too small to print, or not an image (a PDF, a video)
        found.append({"title": p["title"], "width": info.get("width"), "height": info.get("height"),
                      "thumb": info.get("thumburl") or info.get("url"), "page": info.get("descriptionurl"),
                      "license": _plain((meta.get("LicenseShortName") or {}).get("value")) or "licence libre",
                      "author": _plain((meta.get("Artist") or {}).get("value"))[:80] or "auteur inconnu",
                      "description": _plain((meta.get("ImageDescription") or {}).get("value"))[:160]})
        if len(found) >= n:
            break
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(found, ensure_ascii=False))
    if not found:
        print(f"Aucune image pour « {words} ». Essaie d'autres mots, en anglais (ex. : human heart anatomy diagram).")
        return
    for i, f in enumerate(found, 1):
        print(f"{i}. {f['title'][5:]} — {f['width']}×{f['height']} px — {f['license']} — {f['author']}\n"
              f"   {f['description'] or '(sans description)'}")
    print("\nChoisis celle qui montre VRAIMENT le sujet (la description le dit), puis : "
          "python3 images.py prendre <numéro> <dossier/nom.jpg>\n"
          "Un schéma légendé : cherche d'abord sa version en français (ajoute « fr » aux mots : "
          "« digestive system diagram fr »).")


def prendre(which, dest):
    try:
        found = json.loads(CACHE.read_text())
    except (OSError, ValueError):
        found = []
    if str(which).isdigit() and 1 <= int(which) <= len(found):
        f = found[int(which) - 1]
    else:
        sys.exit("erreur : donne le numéro d'une image de la dernière recherche (python3 images.py chercher …)")
    out = Path(dest).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    data = _get(f["thumb"], binary=True)
    real = Path(urllib.parse.urlparse(f["thumb"]).path).suffix.lower() or ".jpg"  # a drawing (svg) comes as a .png
    if real == ".png":
        # a drawing on a transparent background (black labels): put on white, as it will be printed — seen black otherwise
        import subprocess
        import tempfile
        out = out.with_suffix(".jpg")
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            Path(tmp.name).write_bytes(data)
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90", tmp.name, "--out", str(out)],
                           capture_output=True, timeout=60)
        if not out.is_file():  # no sips: the image as it came
            out = out.with_suffix(".png")
            out.write_bytes(data)
        data = out.read_bytes()
    else:
        if out.suffix.lower() not in (".jpg", ".jpeg") or real not in (".jpg", ".jpeg"):
            out = out.with_suffix(real)
        out.write_bytes(data)
    credit = f"Source : Wikimedia Commons — {f['author']}, {f['license']}"
    print(f"{out} ({len(data) // 1024} Ko)\nCrédit (à mettre sous l'image) : {credit}\n")
    print(f'<figure><img src="{out.name}" alt="{html.escape(f["description"][:90] or f["title"][5:])}">'
          f'<figcaption><b>Figure</b> — <ce que l\'image montre, en français>. <span class="credit">{html.escape(credit)}</span>'
          "</figcaption></figure>")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "chercher":
        chercher(a[1], int(a[2]) if len(a) > 2 and a[2].isdigit() else 8)
    elif len(a) == 3 and a[0] == "prendre":
        prendre(a[1], a[2])
    else:
        sys.exit(__doc__)
