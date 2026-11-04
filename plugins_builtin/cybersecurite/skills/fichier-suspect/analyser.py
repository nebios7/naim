#!/usr/bin/env python3
"""Is this file or this link dangerous? Looked at WITHOUT opening or running it.

    python3 analyser.py fichier <chemin>     type réel, signature Apple, quarantaine, macros, JavaScript dans un PDF,
                                             contenu d'une archive, commandes dangereuses dans un script, empreinte
    python3 analyser.py lien "<adresse>"     faux domaine qui imite un vrai, adresse IP, raccourcisseur, redirection,
                                             http, caractères trompeurs — l'adresse est seulement lue, jamais visitée

The file is read as bytes (never executed, never opened by its application). The link is never requested.
"""
import hashlib
import ipaddress
import re
import subprocess
import sys
import unicodedata
import urllib.parse
import zipfile
from pathlib import Path

signs, fine = [], []


def flag(level, what, why):
    signs.append((level, what, why))


def sh(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


MAGIC = [(b"MZ", "exécutable Windows (.exe)"), (b"\x7fELF", "exécutable Linux"), (b"\xcf\xfa\xed\xfe", "exécutable Mac"),
         (b"\xca\xfe\xba\xbe", "exécutable Mac (universel)"), (b"%PDF", "PDF"), (b"PK\x03\x04", "archive ZIP (ou Word/Excel/PowerPoint récent)"),
         (b"\xd0\xcf\x11\xe0", "ancien document Office (.doc/.xls)"), (b"Rar!", "archive RAR"), (b"7z\xbc\xaf", "archive 7-Zip"),
         (b"#!", "script"), (b"\x89PNG", "image PNG"), (b"\xff\xd8\xff", "image JPEG"), (b"GIF8", "image GIF"),
         (b"koly", "image disque"), (b"<?xml", "XML / SVG"), (b"{\\rtf", "document RTF")]
DANGER_CMD = [(r"curl[^|\n]*\|\s*(?:ba|z)?sh|wget[^|\n]*\|\s*(?:ba|z)?sh", "télécharge et exécute un script d'Internet"),
              (r"base64\s+(?:-d|--decode|-D)|FromBase64String|atob\(", "décode un contenu caché (souvent un programme)"),
              (r"osascript\s+-e|do shell script", "fait agir le Mac par AppleScript"),
              (r"chmod\s+\+x|xattr\s+-[dc]\s+com\.apple\.quarantine", "rend exécutable / retire la protection de macOS"),
              (r"launchctl\s+load|LaunchAgents|LaunchDaemons|crontab", "s'installe pour se relancer à chaque démarrage"),
              (r"security\s+find-(?:generic|internet)-password|Keychains|Login Data|Cookies\.binarycookies", "lit les mots de passe ou les cookies"),
              (r"powershell\s+-(?:e|enc|nop|w hidden)|Invoke-Expression|IEX\s*\(|DownloadString", "PowerShell caché qui télécharge"),
              (r"rm\s+-rf\s+(?:/|~|\$HOME)", "efface des dossiers entiers"),
              (r"/dev/tcp/|nc\s+-e|bash\s+-i\s+>&", "ouvre une porte dérobée (connexion à distance)")]


def file(path):
    p = Path(path).expanduser()
    if not p.is_file():
        sys.exit(f"erreur : fichier introuvable : {p}")
    data = p.read_bytes()
    head = data[:8]
    kind = next((k for m, k in MAGIC if data.startswith(m)), "texte ou format inconnu")
    print(f"Fichier : {p.name} — {len(data) // 1024} Ko — type réel : {kind}")
    print(f"SHA-256 : {hashlib.sha256(data).hexdigest()} (à chercher sur virustotal.com si besoin, sans envoyer le fichier)")
    names = p.name.lower().split(".")
    if len(names) > 2 and names[-1] in ("exe", "scr", "bat", "cmd", "js", "vbs", "app", "command", "sh", "pkg", "dmg", "jar", "lnk"):
        flag("haute", f"Double extension « .{names[-2]}.{names[-1]} »", "un exécutable déguisé en document")
    if re.search(r"\.(pdf|docx?|xlsx?|jpe?g|png|txt)$", p.name.lower()) and "exécutable" in kind:
        flag("haute", f"Le nom dit « {p.suffix} » mais c'est un {kind}", "un programme déguisé")
    if p.suffix.lower() in (".exe", ".scr", ".bat", ".cmd", ".vbs", ".lnk", ".jar", ".msi"):
        flag("moyenne", f"Programme Windows ({p.suffix})", "il ne s'exécute pas sur Mac, mais ne le transmets pas à un PC sans vérifier")
    q = sh(["xattr", "-p", "com.apple.quarantine", str(p)])
    if q and "No such xattr" not in q:
        src = sh(["mdls", "-raw", "-name", "kMDItemWhereFroms", str(p)])
        origin = re.sub(r"[()\s]+", " ", src).strip()[:200]
        origin = "inconnue" if origin in ("", "null") else origin
        fine.append(f"Téléchargé (marqué par macOS) — origine : {origin}")
    if "exécutable Mac" in kind or p.suffix in (".app", ".pkg", ".dmg"):
        cs = sh(["codesign", "-dv", "--verbose=2", str(p)])
        team = re.search(r"Authority=([^\n]+)", cs)
        if "not signed" in cs or "code object is not signed" in cs:
            flag("haute", "Programme non signé", "macOS ne sait pas qui l'a fait")
        elif team:
            fine.append(f"Signé par : {team.group(1)}")
        gk = sh(["spctl", "-a", "-vv", "-t", "install" if p.suffix in (".pkg",) else "execute", str(p)])
        if "rejected" in gk:
            flag("haute", "Refusé par Gatekeeper", gk.split("\n")[0][:150])
        elif "accepted" in gk:
            fine.append("Accepté par Gatekeeper (notarisé par Apple)")
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(p) as z:
                inner = z.namelist()
                if any(n.lower().endswith("vbaproject.bin") for n in inner):
                    flag("haute", "Document Office avec MACROS", "les macros sont la première façon de piéger un document Word/Excel : n'active jamais « le contenu »")
                exe = [n for n in inner if re.search(r"\.(exe|scr|bat|cmd|js|vbs|app/|command|sh|jar|lnk|ps1)$", n.lower())]
                if exe:
                    flag("haute", f"Archive qui contient des programmes : {', '.join(exe[:5])}", "souvent la vraie charge d'un faux document")
                if any(i.flag_bits & 0x1 for i in z.infolist()):
                    flag("moyenne", "Archive protégée par mot de passe", "astuce courante pour échapper aux antivirus (le mot de passe est dans le mail)")
                ext = [n for n in inner if re.search(r"(?:^|/)(?:word|xl|ppt)/_rels/.*\.rels$", n)]
                for n in ext:
                    if re.search(rb'TargetMode="External"[^>]*Target="https?://|Target="https?://[^"]+"\s+TargetMode="External"', z.read(n)):
                        flag("moyenne", "Le document charge un modèle depuis Internet", "technique pour lancer un contenu piégé à l'ouverture")
                        break
                if not exe and not any(n.lower().endswith("vbaproject.bin") for n in inner):
                    fine.append(f"Archive : {len(inner)} éléments, aucun programme ni macro")
        except zipfile.BadZipFile:
            flag("moyenne", "Archive abîmée ou maquillée", "à ne pas ouvrir")
    if data.startswith(b"\xd0\xcf\x11\xe0") and re.search(rb"VBA|Macros|_VBA_PROJECT", data):
        flag("haute", "Ancien document Office avec MACROS", "n'active jamais « le contenu » ou « les macros »")
    if data.startswith(b"%PDF"):
        for key, why in ((rb"/JavaScript|/JS\b", "le PDF contient du JavaScript"), (rb"/Launch", "le PDF peut lancer un programme"),
                         (rb"/OpenAction|/AA\b", "le PDF fait une action dès l'ouverture"), (rb"/EmbeddedFile", "le PDF cache un fichier dedans"),
                         (rb"/SubmitForm|/URI\s*\(", "le PDF envoie vers une adresse")):
            if re.search(key, data):
                flag("haute" if key in (rb"/JavaScript|/JS\b", rb"/Launch") else "moyenne", why.capitalize(), "rare dans un PDF normal (facture, courrier)")
    text = data[:2_000_000].decode("utf-8", errors="ignore")
    if kind in ("script", "texte ou format inconnu", "XML / SVG") or p.suffix.lower() in (".sh", ".command", ".py", ".js", ".ps1", ".applescript", ".svg", ".html", ".htm"):
        for rx, why in DANGER_CMD:
            m = re.search(rx, text, re.I)
            if m:
                flag("haute", f"Commande dangereuse : « {m.group(0)[:60]} »", why)
        if p.suffix.lower() in (".svg", ".html", ".htm") and re.search(r"<script|onload=|javascript:", text, re.I):
            flag("moyenne", "Contient du JavaScript", "une image SVG ou une page reçue par mail qui exécute du code est suspecte")
        if re.search(r"(?:password|mot de passe|login)[^<]{0,80}<input|<form[^>]+action=[\"']https?://", text, re.I):
            flag("haute", "Formulaire qui demande un mot de passe et l'envoie ailleurs", "page d'hameçonnage reçue en pièce jointe")


SHORT = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "cutt.ly", "rebrand.ly", "shorturl.at", "rb.gy", "tiny.cc"}
BRANDS = ["paypal", "apple", "icloud", "google", "microsoft", "outlook", "amazon", "netflix", "facebook", "instagram", "whatsapp",
          "ameli", "impots", "laposte", "chronopost", "colissimo", "dhl", "ups", "fedex", "orange", "sfr", "free", "bouygues",
          "caf", "creditagricole", "bnpparibas", "societegenerale", "labanquepostale", "boursorama", "lcl", "creditmutuel",
          "antai", "franceconnect", "edf", "engie", "vinted", "leboncoin", "doctolib"]
OFFICIAL = {"impots": "impots.gouv.fr", "ameli": "ameli.fr", "caf": "caf.fr", "antai": "antai.gouv.fr", "franceconnect": "franceconnect.gouv.fr",
            "laposte": "laposte.fr", "apple": "apple.com", "icloud": "icloud.com", "paypal": "paypal.com", "amazon": "amazon.fr"}


def link(url):
    u = url.strip()
    if not re.match(r"[a-z]+://", u, re.I):
        u = "http://" + u
    pr = urllib.parse.urlsplit(u)
    host = (pr.hostname or "").lower()
    print(f"Lien : {url}\nDomaine réel : {host}")
    if pr.scheme == "http":
        flag("moyenne", "Adresse en http:// (non chiffrée)", "les vrais sites de banque ou d'administration sont en https")
    if "@" in pr.netloc:
        flag("haute", "Un « @ » dans l'adresse", f"tout ce qui est avant est ignoré : le vrai site est {host}")
    try:
        ipaddress.ip_address(host)
        flag("haute", "Adresse IP au lieu d'un nom", "un vrai service n'envoie pas vers une adresse en chiffres")
    except ValueError:
        pass
    if host.startswith("xn--") or ".xn--" in host:
        try:
            shown = host.encode().decode("idna")
        except UnicodeError:
            shown = host
        flag("haute", f"Nom avec des lettres étrangères déguisées (affiché « {shown} »)", "imite un vrai nom avec des caractères qui se ressemblent")
    if any(unicodedata.category(c).startswith("L") and ord(c) > 127 for c in host):
        flag("haute", "Lettres non latines dans le nom", "imitation d'un vrai site")
    if host in SHORT:
        flag("moyenne", "Lien raccourci", "on ne voit pas où il mène : demande le lien complet ou ne clique pas")
    parts = host.split(".")
    base = ".".join(parts[-2:]) if len(parts) >= 2 else host
    if len(parts) >= 2 and parts[-2] in ("gouv",):
        base = ".".join(parts[-3:])
    for b in BRANDS:
        if b in host.replace("-", "").replace(".", ""):
            official = OFFICIAL.get(b)
            if official and not (host == official or host.endswith("." + official)):
                flag("haute", f"Utilise le nom « {b} » mais le vrai site est {official}", f"ce lien mène à {base}, pas à {official}")
            elif not official and b not in base.split(".")[0]:
                flag("haute", f"Contient « {b} » mais le site réel est {base}", f"un vrai lien {b} finit par le domaine officiel de {b}")
            break
    if len(parts) > 4:
        flag("moyenne", f"Beaucoup de sous-domaines ({host})", "astuce pour que le début ressemble à un vrai site")
    if re.search(r"\.(zip|mov|top|xyz|click|link|work|rest|cam|icu|buzz|monster|quest|sbs|cfd)$", host):
        flag("moyenne", f"Extension de domaine souvent utilisée par les arnaques (.{parts[-1]})", "pas une preuve, mais une raison de se méfier")
    if re.search(r"(?:login|signin|verify|verif|update|secure|account|compte|confirm|paiement|payment|suspend|bloqu)", pr.path + pr.query, re.I):
        flag("faible", "Le chemin parle de connexion, vérification ou paiement", "typique des liens d'hameçonnage (« votre compte est suspendu »)")
    if re.search(r"(?:url|redirect|next|goto|dest)=https?", pr.query, re.I):
        flag("moyenne", "Redirige vers une autre adresse", "le premier site sert d'appât, le second est le vrai piège")
    if pr.path.lower().endswith((".exe", ".scr", ".zip", ".apk", ".dmg", ".pkg", ".js", ".vbs", ".iso")):
        flag("haute", f"Le lien télécharge directement un fichier ({Path(pr.path).suffix})", "ne l'ouvre pas sans l'analyser")


def report():
    order = {"haute": 0, "moyenne": 1, "faible": 2}
    signs.sort(key=lambda s: order[s[0]])
    hi = sum(s[0] == "haute" for s in signs)
    verdict = ("DANGEREUX — ne l'ouvre pas" if hi >= 2 else "SUSPECT — à ne pas ouvrir sans vérifier" if hi == 1 or len(signs) >= 3
               else "Quelques points à surveiller" if signs else "Aucun signe de danger trouvé")
    out = ["", f"## Verdict : {verdict}", ""]
    for lvl, what, why in signs:
        out.append(f"- [{lvl.upper()}] {what} — {why}")
    for f in fine:
        out.append(f"- [OK] {f}")
    out += ["", "Rien n'a été ouvert ni exécuté. « Aucun signe » n'est pas une garantie : en cas de doute, ne pas ouvrir et"
            " demander à l'expéditeur par un autre moyen (téléphone)."]
    return "\n".join(out)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "fichier":
        file(a[1])
    elif len(a) == 2 and a[0] == "lien":
        link(a[1])
    else:
        sys.exit(__doc__)
    print(report())
