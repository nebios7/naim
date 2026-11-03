#!/usr/bin/env python3
"""fiche.py <url> [<url> ...] — for each product page: name, price, photo, shop, as Markdown ready to show.

Reads what shops publish for previews and search engines (Open Graph, schema.org Product/Offer, JSON-LD), so it
works on most shops without knowing them. A page that blocks or has no photo is listed as such."""
import html
import json
import re
import sys
import urllib.request
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read(1_500_000).decode(r.headers.get_content_charset() or "utf-8", "replace")


def meta(page, *names):
    for n in names:
        m = re.search(rf'<meta[^>]+(?:property|name|itemprop)=["\']{re.escape(n)}["\'][^>]*content=["\']([^"\']+)', page, re.I) \
            or re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name|itemprop)=["\']{re.escape(n)}["\']', page, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def jsonld(page):
    out = {}
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for it in items:
            if not isinstance(it, dict) or "Product" not in str(it.get("@type")):
                continue
            out.setdefault("name", it.get("name"))
            img = it.get("image")
            img = img[0] if isinstance(img, list) and img else img
            if isinstance(img, dict):
                img = img.get("url")
            out.setdefault("image", img)
            offers = it.get("offers") or {}
            offers = offers[0] if isinstance(offers, list) and offers else offers
            if isinstance(offers, dict):
                out.setdefault("price", offers.get("price") or offers.get("lowPrice"))
                out.setdefault("currency", offers.get("priceCurrency"))
    return out


def fiche(url):
    try:
        page = get(url)
    except Exception as e:  # noqa: BLE001
        return {"url": url, "error": f"page illisible ({type(e).__name__})"}
    j = jsonld(page)
    name = j.get("name") or meta(page, "og:title", "twitter:title") or (re.search(r"<title>(.*?)</title>", page, re.S | re.I) or [None, ""])[1]
    image = j.get("image") or meta(page, "og:image", "og:image:secure_url", "twitter:image", "image")
    price = j.get("price") or meta(page, "product:price:amount", "og:price:amount", "price")
    cur = j.get("currency") or meta(page, "product:price:currency", "og:price:currency", "priceCurrency") or ("EUR" if price else "")
    if image:
        image = urljoin(url, str(image))
    shop = meta(page, "og:site_name") or urlparse(url).netloc.replace("www.", "")
    return {"url": url, "name": html.unescape(re.sub(r"\s+", " ", str(name or ""))).strip()[:120], "image": image or "",
            "price": str(price or "").replace(",", "."), "currency": cur, "shop": shop}


def main():
    for u in sys.argv[1:]:
        f = fiche(u)
        if f.get("error"):
            print(f"- {u} : {f['error']}")
            continue
        p = f"{float(f['price']):.2f} {('€' if f['currency'] in ('EUR', '') else f['currency'])}".replace(".", ",") if re.match(r"^\d+(\.\d+)?$", f["price"]) else "prix non indiqué"
        print(f"### {f['name'] or 'Produit'}\n" + (f"![{f['name'][:60]}]({f['image']})\n" if f["image"] else "")
              + f"**{p}** · {f['shop']} · [voir le produit]({f['url']})\n")


if __name__ == "__main__":
    main()
