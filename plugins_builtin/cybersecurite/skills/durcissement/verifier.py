#!/usr/bin/env python3
"""Hardening check of the user's own web site / server, read-only.

    python3 verifier.py site <https://son-site.fr | http://localhost:5000>   HTTPS, certificate, security headers, cookies
    python3 verifier.py ssh  [/etc/ssh/sshd_config]                           the SSH server's settings (a file read)
    python3 verifier.py nginx <nginx.conf>                                    an nginx configuration (a file read)

One ordinary page request for « site » (what a browser does), nothing else; « ssh » and « nginx » only read a file.
Each point: OK, or what to change and the line to write.
"""
import re
import socket
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

good, bad = [], []


def note(ok, what, fix="", level="moyenne"):
    (good if ok else bad).append((what, fix, level))


HEADERS = {
    "strict-transport-security": ("haute", "HSTS : le navigateur n'utilise plus jamais http pour ce site",
                                  "Strict-Transport-Security: max-age=31536000; includeSubDomains"),
    "content-security-policy": ("moyenne", "CSP : limite ce que la page peut charger (bloque la plupart des XSS)",
                                "Content-Security-Policy: default-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"),
    "x-content-type-options": ("faible", "le navigateur ne devine pas le type des fichiers", "X-Content-Type-Options: nosniff"),
    "referrer-policy": ("faible", "l'adresse complète des pages ne part pas vers les autres sites",
                        "Referrer-Policy: strict-origin-when-cross-origin"),
    "permissions-policy": ("faible", "caméra, micro, position refusés par défaut", "Permissions-Policy: camera=(), microphone=(), geolocation=()"),
}


def site(url):
    if not re.match(r"https?://", url):
        url = "https://" + url
    local = re.match(r"https?://(localhost|127\.|192\.168\.|10\.|\[::1\])", url)
    req = urllib.request.Request(url, headers={"User-Agent": "Naim-verification/1.0"})
    try:
        r = urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as e:
        r = e
    except (urllib.error.URLError, socket.timeout, ssl.SSLError) as e:
        sys.exit(f"erreur : le site ne répond pas ({e}). Vérifie l'adresse, ou que le serveur est lancé.")
    final = r.geturl() if hasattr(r, "geturl") else url
    h = {k.lower(): v for k, v in r.headers.items()}
    if url.startswith("http://") and not local:
        note(final.startswith("https://"), "http:// renvoie vers https://" if final.startswith("https://") else "Le site reste en http:// (non chiffré)",
             "Redirige tout http vers https (nginx : return 301 https://$host$request_uri;) et obtiens un certificat gratuit (Let's Encrypt, certbot).", "haute")
    if final.startswith("https://"):
        host = re.match(r"https://([^/:]+)(?::(\d+))?", final)
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host.group(1), int(host.group(2) or 443)), timeout=10) as s:
                with ctx.wrap_socket(s, server_hostname=host.group(1)) as t:
                    cert, version = t.getpeercert(), t.version()
            end = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days = (end - datetime.now(timezone.utc)).days
            note(days > 20, f"Certificat valide encore {days} jours", "Renouvelle-le (certbot renew) et automatise le renouvellement.", "haute" if days < 7 else "moyenne")
            note(version in ("TLSv1.3", "TLSv1.2"), f"Chiffrement {version}", "Désactive TLS 1.0 et 1.1 (nginx : ssl_protocols TLSv1.2 TLSv1.3;).", "haute")
        except ssl.SSLCertVerificationError as e:
            note(False, f"Certificat refusé par les navigateurs ({e.verify_message})", "Installe un certificat valide pour ce nom (Let's Encrypt).", "haute")
        except (OSError, ValueError, KeyError):
            pass
    for name, (lvl, why, line) in HEADERS.items():
        if name == "strict-transport-security" and not final.startswith("https://"):
            continue
        note(name in h, f"En-tête {name}" + ("" if name in h else f" absent — {why}"), f"Ajoute : `{line}`", lvl)
    if "x-frame-options" not in h and "frame-ancestors" not in h.get("content-security-policy", ""):
        note(False, "Le site peut être affiché dans un cadre d'un autre site (clickjacking)", "Ajoute : `X-Frame-Options: DENY` (ou frame-ancestors 'none' dans la CSP)", "moyenne")
    srv = h.get("server", "") + " " + h.get("x-powered-by", "")
    if re.search(r"\d+\.\d+", srv):
        note(False, f"Le serveur annonce sa version ({srv.strip()})", "Masque-la (nginx : server_tokens off; PHP : expose_php = Off ; Express : app.disable('x-powered-by')).", "faible")
    cookies = r.headers.get_all("Set-Cookie") or []
    for c in cookies:
        name = c.split("=", 1)[0]
        miss = [f for f in ("Secure", "HttpOnly", "SameSite") if f.lower() not in c.lower()]
        if final.startswith("http://"):
            miss = [m for m in miss if m != "Secure"]
        note(not miss, f"Cookie « {name} »" + (f" sans {', '.join(miss)}" if miss else " bien protégé"),
             "Ajoute les attributs : Secure; HttpOnly; SameSite=Lax (une session ne doit jamais être lisible par le JavaScript).", "moyenne")


SSH = [  # setting, good value(s), level, why
    ("PermitRootLogin", {"no", "prohibit-password"}, "haute", "personne ne se connecte directement en root"),
    ("PasswordAuthentication", {"no"}, "haute", "connexion par clé seulement : les robots qui essaient des mots de passe échouent"),
    ("PermitEmptyPasswords", {"no"}, "haute", "aucun compte sans mot de passe"),
    ("X11Forwarding", {"no"}, "faible", "pas d'affichage graphique à distance inutile"),
    ("MaxAuthTries", {"1", "2", "3", "4"}, "faible", "peu d'essais par connexion"),
]


def ssh(path="/etc/ssh/sshd_config"):
    p = Path(path)
    if not p.is_file():
        sys.exit(f"erreur : {p} introuvable (sur un serveur Linux : /etc/ssh/sshd_config).")
    text = p.read_text(errors="replace")
    for d in sorted(p.parent.glob("sshd_config.d/*.conf")):
        text += "\n" + d.read_text(errors="replace")
    conf = {}
    for line in text.split("\n"):
        m = re.match(r"\s*([A-Za-z]+)\s+(\S+)", line)
        if m and m.group(1) not in conf:  # sshd keeps the first value it reads
            conf[m.group(1)] = m.group(2).lower()
    for key, okv, lvl, why in SSH:
        v = conf.get(key)
        default_ok = key in ("PermitEmptyPasswords",) or (key == "PermitRootLogin" and v is None)
        note((v in okv) if v else default_ok, f"{key} = {v or '(valeur par défaut)'}", f"Écris `{key} {sorted(okv)[0] if key != 'MaxAuthTries' else '3'}` — {why}, puis redémarre sshd (après avoir vérifié que ta clé marche).", lvl)
    port = conf.get("port", "22")
    if port == "22":
        good.append(("Port 22 (normal ; le changer réduit seulement le bruit des robots)", "", "faible"))


def nginx(path):
    text = Path(path).read_text(errors="replace")
    note("server_tokens off" in text, "server_tokens off", "Ajoute `server_tokens off;` dans http { } (la version n'est plus annoncée).", "faible")
    note(not re.search(r"ssl_protocols[^;]*TLSv1(?:\.1)?\s", text + " "), "Pas de TLS 1.0/1.1", "`ssl_protocols TLSv1.2 TLSv1.3;`", "haute")
    note("Strict-Transport-Security" in text, "HSTS", "`add_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;`", "moyenne")
    note("X-Content-Type-Options" in text, "X-Content-Type-Options", "`add_header X-Content-Type-Options nosniff always;`", "faible")
    note("Content-Security-Policy" in text, "Content-Security-Policy", "`add_header Content-Security-Policy \"default-src 'self'\" always;` (à adapter au site)", "moyenne")
    note(not re.search(r"autoindex\s+on", text), "Pas de liste des fichiers des dossiers (autoindex)", "`autoindex off;`", "moyenne")
    note(bool(re.search(r"return\s+301\s+https", text)), "http renvoie vers https", "`server { listen 80; return 301 https://$host$request_uri; }`", "haute")
    note(bool(re.search(r"client_max_body_size", text)), "Taille des envois limitée", "`client_max_body_size 10m;` (selon le besoin)", "faible")


def report():
    order = {"haute": 0, "moyenne": 1, "faible": 2}
    bad.sort(key=lambda b: order.get(b[2], 1))
    out = ["# Vérification de durcissement", "", f"{len(good)} points en ordre, {len(bad)} à améliorer.", ""]
    if bad:
        out.append("## À améliorer")
        for what, fix, lvl in bad:
            out += [f"- [{lvl.upper()}] {what}", f"  Comment : {fix}"]
        out.append("")
    if good:
        out.append("## En ordre")
        out += [f"- {w}" for w, _, _ in good]
    return "\n".join(out)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "site":
        site(a[1])
    elif a and a[0] == "ssh":
        ssh(*a[1:2])
    elif len(a) >= 2 and a[0] == "nginx":
        nginx(a[1])
    else:
        sys.exit(__doc__)
    print(report())
