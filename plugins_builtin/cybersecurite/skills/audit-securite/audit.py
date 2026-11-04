#!/usr/bin/env python3
"""Security audit of a code project, read-only: the flaws a reviewer looks for first, each with its file:line, its
severity, why it is dangerous and how to fix it.

    python3 audit.py <dossier>              the report (Markdown) on the screen, the most serious first
    python3 audit.py <dossier> --json f     the same findings as JSON (to write a PDF report or to check a fix)
    python3 audit.py <dossier> --deps       also the known vulnerabilities of the dependencies (pip-audit / npm audit
                                            when they are installed: nothing is installed by this script)

Nothing is changed and nothing is sent anywhere. A finding is a lead to check in the code, not a proof: read the
line, say if it is really reachable, then fix it.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "env", "__pycache__", "dist", "build", ".next", "vendor",
             "site-packages", ".tox", ".mypy_cache", ".pytest_cache", "Pods", "DerivedData", ".idea", ".vscode"}
CODE = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".php", ".rb", ".go", ".java", ".kt", ".cs", ".swift",
        ".html", ".htm", ".vue", ".svelte", ".sh", ".bash", ".zsh", ".sql", ".yml", ".yaml", ".toml", ".ini", ".cfg",
        ".conf", ".json", ".xml", ".tf", ".dockerfile", ".env", ".properties", ".c", ".cpp", ".h"}
NAMED = {"Dockerfile", ".env", ".env.local", ".env.production", "docker-compose.yml", ".htaccess", "nginx.conf"}
ORDER = {"critique": 0, "haute": 1, "moyenne": 2, "faible": 3}

# (id, severity, title, regex, file filter (None = all), why, fix)
USER = r"(?:(?<![\w.])request\.(?:args|form|json|values|data|files|cookies|GET|POST|query_params|body|params|get_json)\b|\breq\.(?:query|params|body)\b|\$_(?:GET|POST|REQUEST|COOKIE))"  # what a visitor sends (not urllib.request)
RULES = [
    # ---- secrets
    ("secret-cle-privee", "critique", "Clé privée dans le code", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
     None, "Quiconque lit le dépôt peut se faire passer pour ce serveur ou ce compte.",
     "Retire la clé du dépôt (et de son historique git), révoque-la, range la nouvelle hors du code (fichier ignoré, trousseau)."),
    ("secret-aws", "critique", "Clé d'accès AWS", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", None,
     "Une clé AWS publiée est utilisée par des robots en quelques minutes (facture, données).",
     "Révoque la clé dans la console AWS, puis lis-la depuis une variable d'environnement."),
    ("secret-token", "critique", "Jeton d'API connu (GitHub, Slack, Stripe, Google, OpenAI…)",
     r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk_live_[A-Za-z0-9]{20,}|"
     r"AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{32,})\b", None,
     "Le jeton donne l'accès au compte à qui le trouve.", "Révoque-le chez le fournisseur, puis lis-le depuis l'environnement (os.environ, process.env)."),
    ("secret-mot-de-passe", "haute", "Mot de passe ou secret écrit en dur",
     r"""(?i)\b(?:password|passwd|pwd|mot_?de_?passe|secret(?:_key)?|api_?key|token|auth_?token)\b\s*[:=]\s*["'][^"'\s$%{}<>]{6,}["']""",
     None, "Le secret est lisible par tous ceux qui ont le code (dépôt, sauvegardes, captures).",
     "Mets-le dans une variable d'environnement ou un fichier .env ignoré par git ; change le mot de passe s'il a été publié."),
    # ---- injections
    ("sql-concatenation", "haute", "Requête SQL construite avec du texte de l'utilisateur",
     r"""(?i)(?:execute|executemany|query|raw|cursor\.execute|db\.query|mysqli_query|->query)\s*\(\s*(?:f["']|["'][^"']*\b(?:select|insert|update|delete)\b[^"']*["']\s*(?:\+|%|\.format|\.))""",
     None, "Injection SQL : un ' bien placé lit, modifie ou efface toute la base.",
     "Requête paramétrée : execute(\"... WHERE id = ?\", (id,)) / PDO prepare + bindParam / requêtes de l'ORM."),
    ("commande-shell", "haute", "Commande système avec une variable (injection de commande)",
     r"""(?:os\.system|os\.popen|subprocess\.\w+\([^)]*shell\s*=\s*True|child_process\.exec(?:Sync)?|\bexec\s*\(\s*["'`][^"'`]*\$\{|shell_exec|passthru|\bsystem\s*\(\s*\$)""",
     None, "Si une partie vient de l'utilisateur, il peut lancer n'importe quelle commande sur la machine.",
     "subprocess.run([\"prog\", arg]) sans shell=True ; execFile / spawn avec une liste d'arguments ; jamais de texte utilisateur dans une commande."),
    ("eval", "haute", "eval / exec sur des données", r"""(?<![\w.])(?:eval|exec)\s*\((?!\s*["'][^"']*["']\s*\))""",
     {".py", ".js", ".mjs", ".ts", ".php", ".rb"}, "Exécute du code arbitraire si la donnée est contrôlée par quelqu'un d'autre.",
     "json.loads / JSON.parse pour des données, ast.literal_eval pour des valeurs Python ; un dictionnaire de fonctions autorisées sinon."),
    ("deserialisation", "haute", "Désérialisation non sûre", r"""(?:pickle\.loads?|cPickle\.loads?|yaml\.load\s*\((?![^)]*SafeLoader)|marshal\.loads|unserialize\s*\(\s*\$_)""",
     None, "Un fichier ou une requête piégée exécute du code au chargement.",
     "json pour échanger des données ; yaml.safe_load ; jamais pickle sur une donnée reçue."),
    ("xss-innerhtml", "moyenne", "HTML injecté depuis une variable (XSS)",
     r"""(?:\.innerHTML\s*[+]?=\s*(?!["'`][^"'`$]*["'`]\s*;?\s*$)|\.outerHTML\s*=|document\.write\s*\(|dangerouslySetInnerHTML|v-html=|\|\s*safe\b|\{\{\{|<%-|\{!!)""",
     None, "Un texte venu de l'utilisateur peut exécuter du JavaScript chez les autres visiteurs (vol de session).",
     "textContent au lieu d'innerHTML, ou échapper (esc / DOMPurify) ; laisser le moteur de templates échapper."),
    ("chemin-utilisateur", "moyenne", "Fichier ouvert avec un chemin venu de la requête (traversée de dossier)",
     r"""(?:open|send_file|sendFile|readFile|file_get_contents|include|require)\s*\([^)\n]*""" + USER,
     None, "« ../../etc/passwd » lit n'importe quel fichier du serveur.",
     "Garde seulement le nom (basename), vérifie que le chemin final reste dans le dossier prévu (resolve + is_relative_to)."),
    ("ssrf", "moyenne", "Requête vers une adresse donnée par l'utilisateur (SSRF)",
     r"""(?:requests\.(?:get|post)|urlopen|fetch|axios\.(?:get|post)|curl_exec)\s*\([^)\n]*""" + USER,
     None, "Le serveur peut être poussé à appeler son réseau interne ou les métadonnées du cloud.",
     "Liste d'hôtes autorisés ; refuser les adresses privées et locales après résolution DNS."),
    ("redirection-ouverte", "faible", "Redirection vers une adresse de la requête",
     r"""(?:redirect|res\.redirect|header\s*\(\s*["']Location:)[^\n]*""" + USER,
     None, "Sert à l'hameçonnage : un lien de ton site qui envoie vers un faux site.", "Redirige seulement vers des chemins internes connus."),
    # ---- configuration
    ("debug-actif", "moyenne", "Mode debug activé", r"""(?:\bDEBUG\s*=\s*True\b|app\.run\([^)]*debug\s*=\s*True|app\.debug\s*=\s*True|display_errors\s*=\s*On)""",
     None, "Les pages d'erreur montrent le code, les variables et parfois une console qui exécute du code.",
     "Debug seulement en développement, lu depuis l'environnement (DEBUG=False en production)."),
    ("tls-desactive", "haute", "Vérification HTTPS désactivée", r"""(?:verify\s*=\s*False|rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*["']?0|CURLOPT_SSL_VERIFYPEER\s*,\s*(?:false|0)|InsecureSkipVerify\s*:\s*true|ssl\._create_unverified_context)""",
     None, "N'importe qui sur le réseau peut lire et modifier les échanges (homme du milieu).",
     "Laisse la vérification active ; pour un certificat interne, donne son autorité (verify=\"ca.pem\")."),
    ("cors-ouvert", "moyenne", "CORS ouvert à tous les sites", r"""(?:Access-Control-Allow-Origin["']?\s*[:,]\s*["']\*|origin\s*:\s*["']\*["']|CORS\(\s*app\s*\)|allow_origins\s*=\s*\[\s*["']\*)""",
     None, "N'importe quel site peut appeler ton API avec la session du visiteur si les cookies suivent.",
     "Liste précise des origines autorisées ; jamais * avec credentials."),
    ("ecoute-partout", "faible", "Serveur qui écoute sur toutes les interfaces", r"""(?:host\s*=\s*["']0\.0\.0\.0["']|\.listen\([^)]*["']0\.0\.0\.0["']|bind\s*=\s*["']0\.0\.0\.0)""",
     None, "Le service est joignable par tout le réseau (Wi-Fi public compris), pas seulement par ce Mac.",
     "127.0.0.1 pour un outil local ; derrière un proxy et un pare-feu pour un vrai serveur."),
    ("http-clair", "faible", "Adresse en http:// (non chiffrée) vers un autre site", r"""["']http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|192\.168\.|10\.|172\.(?:1[6-9]|2\d|3[01])\.|schemas\.|www\.w3\.org|xmlns)[^"'\s]+""",
     None, "Les données passent en clair et peuvent être modifiées en route.", "Utilise https://."),
    # ---- cryptography
    ("hash-faible-mdp", "haute", "Mot de passe haché avec MD5 / SHA-1 / SHA-256 simple",
     r"""(?i)(?:md5|sha1|sha256)\s*\([^)]*(?:pass|pwd|mdp|mot_?de_?passe)""", None,
     "Ces hachages se cassent par milliards à la seconde : les mots de passe d'une base volée sont retrouvés.",
     "bcrypt, argon2 ou scrypt (passlib, password_hash en PHP, bcrypt en Node)."),
    ("aleatoire-faible", "moyenne", "Nombre aléatoire non sûr pour un jeton ou un mot de passe",
     r"""(?i)(?:(?:token|secret|password|mdp|otp|code|salt|nonce|session)\w*\s*=\s*[^\n]*(?:random\.(?:random|randint|choice)|Math\.random|\brand\s*\(|mt_rand))""",
     None, "Ces générateurs sont prévisibles : le jeton peut être deviné.", "secrets.token_urlsafe() (Python), crypto.randomUUID() / crypto.getRandomValues() (JS), random_bytes() (PHP)."),
    ("chiffrement-ecb", "moyenne", "Chiffrement en mode ECB ou algorithme dépassé", r"""(?:MODE_ECB|AES/ECB|\bDES3?\.new|TripleDES|createCipheriv\(\s*["'](?:des|rc4|bf)|["'](?:DES|RC4|des-cbc|des-ede3?)["']|\bARC4\.new|Blowfish\.new)""", None,
     "Le mode ECB laisse voir les motifs des données ; DES et RC4 sont cassés.", "AES-GCM (ou ChaCha20-Poly1305) avec une bibliothèque reconnue."),
]
SAFE_HTML = re.compile(r"(?:\besc(?:ape)?(?:Html|HTML)?\s*\(|DOMPurify|sanitize|textContent|=\s*[\"']{2}\s*;?\s*$|=\s*[\"'][^\"'$`{]*[\"']\s*;?\s*$)")
COMPILED = [(i, sev, t, re.compile(rx), f, why, fix) for i, sev, t, rx, f, why, fix in RULES]
SECRET_FILES = re.compile(r"(?:^|/)(?:\.env(?:\.[\w-]+)?|id_rsa|id_ed25519|.*\.pem|.*\.p12|.*\.key|credentials\.json|service-account.*\.json)$")


def mask(text):
    """« password = "hunter2024" » -> « password = "hunt…" »; a key or token: its first 4 characters."""
    text = re.sub(r"""(["'])([^"'\s]{4})[^"'\s]{2,}\1""", lambda m: f"{m.group(1)}{m.group(2)}…{m.group(1)}", text)
    text = re.sub(r"\b((?:AKIA|ASIA|ghp_|github_pat_|xox[baprs]-|sk_live_|AIza|sk-)[A-Za-z0-9]{0,2})[A-Za-z0-9_-]{8,}", r"\1…", text)
    return re.sub(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----).*", r"\1 …", text)


def tracked(root):
    """The files git would publish (when it is a repository): a secret there is a published secret."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, timeout=20)
        return set(out.stdout.split("\n")) if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def files(root):
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".") or x in (".github",)]
        for n in names:
            p = Path(d) / n
            if (p.suffix.lower() in CODE or n in NAMED or n.startswith(".env")) and p.stat().st_size < 1_500_000:
                yield p


def scan(root):
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"erreur : dossier introuvable : {root}")
    git = tracked(root)
    found, count = [], 0
    for p in files(root):
        rel = str(p.relative_to(root))
        if Path(__file__).resolve().parent in p.resolve().parents:
            continue  # the audit's own rules
        count += 1
        if SECRET_FILES.search(rel) and not rel.endswith((".example", ".sample", ".template")):
            published = git is not None and rel in git
            found.append({"id": "fichier-secret", "severity": "critique" if published else "moyenne",
                          "title": "Fichier de secrets " + ("publié dans git" if published else "dans le projet"),
                          "file": rel, "line": 0, "code": "",
                          "why": "Il contient d'habitude des mots de passe ou des clés." + (" Il est suivi par git : il part avec le dépôt." if published else ""),
                          "fix": "Ajoute-le à .gitignore" + (", retire-le de git (git rm --cached) et change les secrets qu'il contient." if published else ".")})
        try:
            lines = p.read_text(errors="replace").split("\n")
        except OSError:
            continue
        test_file = bool(re.search(r"(?:^|/)(?:tests?|spec|__tests__|fixtures?|examples?)/|_test\.|\.test\.|\.spec\.|test_", rel))
        for n, line in enumerate(lines, 1):
            if len(line) > 600:  # minified code: one finding per rule at most, without the line
                line = line[:600]
            for rid, sev, title, rx, only, why, fix in COMPILED:
                if only and p.suffix.lower() not in only:
                    continue
                if rx.search(line):
                    if rid == "xss-innerhtml" and SAFE_HTML.search(line):
                        continue  # escaped (esc(), DOMPurify…) or a fixed text: not a flaw
                    if rid == "xss-innerhtml" and "`" in line and not re.search(r"location|hash|search|params|query|value|\.data\b|message|input", line):
                        sev_override = "faible"  # a template the page builds itself: to look at, rarely a flaw
                    else:
                        sev_override = None
                    s = sev_override or sev
                    if test_file and ORDER[s] < 3:  # a test or an example: lower, still told
                        s = list(ORDER)[min(3, ORDER[s] + 1)]
                    if rid.startswith("secret") and re.search(r"(?i)(?:example|exemple|changeme|xxx+|your[_-]|<.+>|dummy|fake|placeholder|\*\*\*)", line):
                        continue
                    code = line.strip()[:160]
                    if rid.startswith("secret"):
                        code = mask(code)  # a secret found is never shown whole (report, PDF, conversation)
                    found.append({"id": rid, "severity": s, "title": title, "file": rel, "line": n,
                                  "code": code, "why": why, "fix": fix})
    found.sort(key=lambda f: (ORDER[f["severity"]], f["file"], f["line"]))
    return root, count, found


def deps(root):
    """Known vulnerabilities of the dependencies, with the tools already installed (nothing installed here)."""
    out = []
    if (root / "requirements.txt").is_file() or (root / "pyproject.toml").is_file():
        tool = shutil.which("pip-audit")
        if tool:
            arg = ["-r", str(root / "requirements.txt")] if (root / "requirements.txt").is_file() else [str(root)]
            r = subprocess.run([tool, *arg, "-f", "json"], capture_output=True, text=True, timeout=300)
            try:
                for d in json.loads(r.stdout or "{}").get("dependencies", []):
                    for v in d.get("vulns", []):
                        out.append(f"{d['name']} {d.get('version', '')} : {v.get('id')} — corrigé en {', '.join(v.get('fix_versions') or ['?'])}")
            except ValueError:
                out.append("pip-audit : sortie illisible — " + (r.stderr or "")[-200:])
        else:
            out.append("Python : pip-audit n'est pas installé (pip install pip-audit, avec l'accord de l'utilisateur) — dépendances non vérifiées.")
    if (root / "package.json").is_file():
        npm = shutil.which("npm")
        if npm and (root / "package-lock.json").is_file():
            r = subprocess.run([npm, "audit", "--json"], cwd=root, capture_output=True, text=True, timeout=300)
            try:
                for name, v in (json.loads(r.stdout or "{}").get("vulnerabilities") or {}).items():
                    out.append(f"{name} : {v.get('severity')} — {'correctif disponible' if v.get('fixAvailable') else 'pas de correctif'}")
            except ValueError:
                out.append("npm audit : sortie illisible")
        else:
            out.append("JavaScript : npm audit a besoin de npm et de package-lock.json — dépendances non vérifiées.")
    return out


def report(root, count, found, dep_lines):
    by = {s: [f for f in found if f["severity"] == s] for s in ORDER}
    lines = [f"# Audit de sécurité — {root.name}", "",
             f"{count} fichiers lus. Constats : " + ", ".join(f"{len(v)} {k}" for k, v in by.items()) + ".", ""]
    if not found:
        lines += ["Aucune faille connue repérée par les règles automatiques. Cela ne prouve pas l'absence de faille :",
                  "relis aussi les contrôles d'accès (qui peut voir ou modifier quoi) et la logique métier.", ""]
    shown = {}
    for f in found:
        k = (f["id"], f["file"])
        shown[k] = shown.get(k, 0) + 1
        if shown[k] > 3:  # the same flaw ten times in one file: three examples, then the count
            continue
        where = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
        lines += [f"## [{f['severity'].upper()}] {f['title']} — `{where}`"]
        if f["code"]:
            lines += ["```", f["code"], "```"]
        lines += [f"- Risque : {f['why']}", f"- Correction : {f['fix']}", ""]
    extra = {k: v - 3 for k, v in shown.items() if v > 3}
    for (rid, file), more in extra.items():
        lines += [f"(+{more} autres « {rid} » dans {file})"]
    if dep_lines:
        lines += ["", "## Dépendances", *[f"- {d}" for d in dep_lines]]
    lines += ["", "Prochaine étape : vérifier chaque constat dans le code (est-il atteignable par un utilisateur ?),",
              "corriger du plus grave au moins grave, puis relancer l'audit pour voir qu'il a disparu."]
    return "\n".join(lines)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        sys.exit(__doc__)
    root, count, found = scan(a[0])
    dep_lines = deps(root) if "--deps" in a else []
    if "--json" in a:
        i = a.index("--json")
        out = Path(a[i + 1]) if i + 1 < len(a) else root / "audit-securite.json"
        out.write_text(json.dumps({"projet": str(root), "fichiers": count, "constats": found, "dependances": dep_lines},
                                  ensure_ascii=False, indent=1))
        print(f"JSON : {out} ({len(found)} constats)")
    print(report(root, count, found, dep_lines))
