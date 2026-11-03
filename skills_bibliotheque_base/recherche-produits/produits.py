#!/usr/bin/env python3
"""produits.py "<recherche>" [nombre de photos] — photos and prices found on the web for a product, as Markdown.

Photos: an image search (each photo with the site it comes from). Prices: the web results whose text shows a price in
euros. Shops often block direct reading of their pages: the search results are what can be read reliably."""
import base64
import html
import json
import re
import sys
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
PRICE = re.compile(r"(\d{1,3}(?:[  .]\d{3})*(?:[,.]\d{2})?)\s?€|€\s?(\d{1,3}(?:[  .]\d{3})*(?:[,.]\d{2})?)")


def get(url, ref=None):
    h = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"}
    if ref:
        h["Referer"] = ref
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=15) as r:
        return r.read().decode("utf-8", "replace")


def photos(q, n, page=1):
    """n photos for the query; page 2, 3… give the next ones (never the same as the pages before)."""
    page_html = get("https://duckduckgo.com/?" + urllib.parse.urlencode({"q": q, "iax": "images", "ia": "images", "kl": "fr-fr"}))
    m = re.search(r"vqd=['\"]?([\d-]+)", page_html)
    if not m:
        return []
    found, seen, per_site = [], set(), {}
    url = "https://duckduckgo.com/i.js?" + urllib.parse.urlencode({"l": "fr-fr", "o": "json", "q": q, "vqd": m.group(1), "f": ",,,", "p": "1"})
    for _ in range(4):  # up to 4 result pages, enough for several « encore » requests
        data = json.loads(get(url, "https://duckduckgo.com/"))
        for r in data.get("results", []):
            img, site = r.get("image", ""), urllib.parse.urlparse(r.get("url", "")).netloc.replace("www.", "")
            if not img.startswith("https://") or img in seen or per_site.get(site, 0) >= 2:
                continue
            seen.add(img)
            per_site[site] = per_site.get(site, 0) + 1
            found.append({"image": img, "title": html.unescape(r.get("title", ""))[:90], "url": r.get("url", ""), "site": site})
        if len(found) >= page * n or not data.get("next"):
            break
        url = "https://duckduckgo.com/" + data["next"] + "&vqd=" + m.group(1)
    return found[(page - 1) * n: page * n]


# an amount that is not the product's price: a discount, a trade-in, a delivery, a monthly payment
NOT_PRICE = re.compile(r"(?:[ée]conomis\w*|jusqu'?[àa]|remise|r[ée]duction|reprise|rembours\w*|bonus|offerts?|cashback|"
                       r"livraison|frais|[ée]conomie|de moins|baisse de|entre|soit|-)\s*(?:de\s*)?$", re.I)
PER_MONTH = re.compile(r"^\s*(?:/|par)\s*mois|^\s*/\s*m\b", re.I)


def price_in(text):
    """The first amount in euros that is a price (« 1 329 € », « à partir de 1 229,00 € »), not a saving
    (« Économisez entre 30 € et 1 020 € »), a delivery or a monthly payment."""
    for p in PRICE.finditer(text):
        before, after = text[max(0, p.start() - 40):p.start()], text[p.end():p.end() + 12]
        if NOT_PRICE.search(before) or PER_MONTH.search(after) or re.search(r"\bet\s*$", before):
            continue
        val = (p.group(1) or p.group(2)).replace(" ", "").replace("\u202f", "").replace(" ", "")
        try:
            if float(val.replace(".", "").replace(",", ".")) < 2:
                continue
        except ValueError:
            continue
        return val
    return None


def results(q):
    """Web results: DuckDuckGo (its light version when it finds too little), plus Bing (DuckDuckGo often answers « No
    results » to a robot for a product, while the same search has ten results elsewhere)."""
    out = []
    try:
        page = get("https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": q, "kl": "fr-fr"}))
        for m in re.finditer(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>', page, re.S):
            url = html.unescape(m.group(1))
            if "uddg=" in url:
                url = urllib.parse.unquote(url.split("uddg=")[1].split("&")[0])
            out.append((url, m.group(2), m.group(3)))
    except Exception:  # noqa: BLE001
        pass
    if len(out) < 4:
        try:
            page = get("https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": q, "kl": "fr-fr"}))
            for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*class='result-link'[^>]*>(.*?)</a>(.*?)(?=class='result-link'|$)", page, re.S):
                snip = re.search(r"class='result-snippet'[^>]*>(.*?)</td>", m.group(3), re.S)
                out.append((html.unescape(m.group(1)), m.group(2), snip.group(1) if snip else ""))
        except Exception:  # noqa: BLE001
            pass
    if True:  # Bing too, always: for prices, more shops is better than fewer
        try:
            page = get("https://www.bing.com/search?" + urllib.parse.urlencode({"q": q, "setlang": "fr", "cc": "FR"}))
            for item in re.findall(r'<li class="b_algo"(.*?)</li>\s*(?=<li|</ol)', page, re.S):
                h = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', item, re.S)
                if not h:
                    continue
                url = html.unescape(h.group(1))
                u = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("u", [""])[0]
                if u.startswith("a1"):
                    try:
                        url = base64.urlsafe_b64decode(u[2:] + "=" * (-len(u[2:]) % 4)).decode()
                    except ValueError:
                        pass
                snip = re.search(r"<p[^>]*>(.*?)</p>", item, re.S)
                out.append((url, h.group(2), snip.group(1) if snip else ""))
        except Exception:  # noqa: BLE001
            pass
    return out


def offers(q):
    out, seen = [], set()
    for query in (q + " prix", q + " meilleur prix"):
        for url, title, text in results(query):
            if "duckduckgo.com/y.js" in url or url in seen:
                continue
            seen.add(url)
            title = html.unescape(re.sub(r"<.*?>", "", title)).strip()
            text = html.unescape(re.sub(r"<.*?>", "", text))
            val = price_in(title + " · " + text)
            if val:
                out.append({"price": val, "title": title[:90], "url": url, "site": urllib.parse.urlparse(url).netloc.replace("www.", "")})
        if len(out) >= 6:
            break
    return out[:8]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    q = args[0] if args else ""
    n = min(int(args[1]), 20) if len(args) > 1 else 8
    page = next((int(a.split("=")[1]) for a in sys.argv[1:] if a.startswith("--page=")), 1)
    if not q:
        sys.exit('usage : produits.py "recherche" [nombre ≤ 20] [--page=2]')
    try:
        ph = photos(q, n, page)
    except Exception as e:  # noqa: BLE001
        ph = []
        print(f"(photos indisponibles : {type(e).__name__})")
    # « iPhone 17 Pro et Samsung S26 »: one price search per product (both at once found no price at all)
    parts = [x.strip() for x in re.split(r"\s+(?:et|vs\.?|versus|ou|contre|face [àa])\s+|\s*/\s*", q, flags=re.I) if len(x.strip()) > 2]
    of = []
    for part in (parts if len(parts) > 1 else [q]):
        try:
            of += [dict(o, product=part) for o in offers(part)[:5]]
        except Exception as e:  # noqa: BLE001
            print(f"(prix indisponibles pour {part} : {type(e).__name__})")
    print(f"PHOTOS, page {page} (recopie ces lignes telles quelles, elles s'affichent en galerie ; pour d'autres photos : --page={page + 1}) :")
    for p in ph:
        print(f"![{re.sub(r'[\[\]|]', ' ', p['title'])[:60].strip()} — {p['site']}]({p['image']})")
    print("\nSOURCES DES PHOTOS :")
    for p in ph:
        print(f"- [{p['site']}]({p['url']})")
    print("\nOFFRES AVEC UN PRIX (à vérifier sur le site, les prix changent) :")
    for o in of:
        print(f"- {o['product'] + ' : ' if len(parts) > 1 else ''}**{o['price']} €** · {o['site']} · [{o['title']}]({o['url']})")
    if not of:
        print("- aucun prix lisible dans les résultats : donne les liens des boutiques sans inventer de prix")
    print("\nTA RÉPONSE, dans cet ordre : 1) une phrase sur ce que tu as trouvé ; 2) 4 à 6 lignes ![…](…) des PHOTOS "
          "recopiées telles quelles, à la suite (galerie) ; 3) un tableau Produit | Prix | Boutique (lien) avec les "
          "OFFRES ci-dessus, seulement ces prix-là ; 4) ton conseil en 2 ou 3 lignes. Une remise ou une reprise "
          "(« économisez 30 € ») n'est pas un prix.")


if __name__ == "__main__":
    main()
