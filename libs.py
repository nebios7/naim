"""External libraries Naim may use in the sites and apps it builds (Personnaliser → Bibliothèques).

A small catalogue (GSAP, Lenis, React Bits…) plus the ones the user adds from a GitHub link. The enabled ones are
given to Naim, with how to install and use them, whenever it builds something for the web.
State: ~/.naim/bibliotheques.json  {"off": [names], "added": {name: entry}}
"""
import json
import re
import urllib.request

import extensions as ext

FILE = ext.HOME / "bibliotheques.json"

# name: entry — install (npm), cdn (page HTML sans npm), usage (a few lines that work)
CATALOG = {
    "GSAP": {"repo": "greensock/GSAP", "category": "Animation",
             "description": "Animations fluides de tout élément, timelines, animations au défilement (ScrollTrigger).",
             "install": "npm install gsap",
             "cdn": "https://cdn.jsdelivr.net/npm/gsap@3.15/dist/gsap.min.js",
             "usage": 'import gsap from "gsap"; import ScrollTrigger from "gsap/ScrollTrigger"; gsap.registerPlugin(ScrollTrigger);\n'
                      'gsap.from(".reveal", { y: 30, opacity: 0, duration: 0.8, scrollTrigger: ".reveal" });'},
    "Lenis": {"repo": "darkroomengineering/lenis", "category": "Défilement",
              "description": "Défilement doux de toute la page, synchronisable avec GSAP ScrollTrigger.",
              "install": "npm install lenis",
              "cdn": "https://unpkg.com/lenis/dist/lenis.min.js",
              "usage": 'import Lenis from "lenis"; import "lenis/dist/lenis.css";\nnew Lenis({ autoRaf: true });'},
    "React Bits": {"repo": "DavidHDev/react-bits", "category": "Composants React",
                   "description": "Composants React animés prêts à l'emploi : textes, fonds, cartes, curseurs.",
                   "install": "npx shadcn@latest add @react-bits/BlurText-TS-TW",
                   "cdn": "",
                   "usage": "Projet React avec shadcn (sinon npx shadcn@latest init). Nom : <Composant>-<JS|TS>-<CSS|TW>, "
                            "ex. SplitText-JS-CSS, CountUp-TS-TW, Aurora-JS-CSS."},
    "Motion": {"repo": "motiondivision/motion", "category": "Animation",
               "description": "Animations déclaratives pour React (anciennement Framer Motion) : apparitions, gestes, mises en page.",
               "install": "npm install motion",
               "cdn": "",
               "usage": 'import { motion } from "motion/react";\n<motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} />'},
    "Three.js": {"repo": "mrdoob/three.js", "category": "3D",
                 "description": "Scènes 3D dans le navigateur (WebGL) : objets, lumières, caméras.",
                 "install": "npm install three",
                 "cdn": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
                 "usage": 'import * as THREE from "three";'},
    "Chart.js": {"repo": "chartjs/Chart.js", "category": "Graphiques",
                 "description": "Graphiques (barres, courbes, camemberts) simples et responsives.",
                 "install": "npm install chart.js",
                 "cdn": "https://cdn.jsdelivr.net/npm/chart.js",
                 "usage": 'import Chart from "chart.js/auto";\nnew Chart(canvas, { type: "bar", data: { labels, datasets: [{ label, data }] } });'},
    "Swiper": {"repo": "nolimits4web/swiper", "category": "Carrousels",
               "description": "Carrousels et galeries tactiles (glisser au doigt), pour images ou produits.",
               "install": "npm install swiper",
               "cdn": "https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js",
               "usage": 'import Swiper from "swiper/bundle"; import "swiper/css/bundle";\nnew Swiper(".swiper", { loop: true });'},
    "Lottie": {"repo": "airbnb/lottie-web", "category": "Animation",
               "description": "Animations vectorielles exportées d'After Effects (fichiers .json), légères et nettes.",
               "install": "npm install lottie-web",
               "cdn": "https://cdn.jsdelivr.net/npm/lottie-web/build/player/lottie.min.js",
               "usage": 'import lottie from "lottie-web";\nlottie.loadAnimation({ container, path: "anim.json", loop: true, autoplay: true });'},
}
DEFAULT_OFF = {"Motion", "Three.js", "Chart.js", "Swiper", "Lottie"}  # offered, enabled on demand


class LibError(Exception):
    pass


def _state():
    try:
        s = json.loads(FILE.read_text())
    except (OSError, ValueError):
        s = {}
    s.setdefault("off", sorted(DEFAULT_OFF))
    s.setdefault("added", {})
    return s


def _save(s):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1))


def listing():
    s = _state()
    out = []
    for name, e in list(CATALOG.items()) + list(s["added"].items()):
        out.append({"name": name, **e, "enabled": name not in s["off"], "added": name in s["added"]})
    return out


def toggle(name, on):
    s = _state()
    off = set(s["off"])
    off.discard(name) if on else off.add(name)
    s["off"] = sorted(off)
    _save(s)


def remove(name):
    """Only the libraries the user added (the catalogue ones are switched off instead)."""
    s = _state()
    if s["added"].pop(name, None) is None:
        raise LibError("seules les bibliothèques ajoutées par lien se retirent ; les autres se désactivent")
    _save(s)


def _raw(owner, repo, path):
    for ref in ("HEAD", "main", "master"):
        try:
            req = urllib.request.Request(f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}", headers={"User-Agent": ext.UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read(600_000).decode("utf-8", errors="replace")
        except Exception:
            continue
    return ""


def add(url):
    """A library from its GitHub link: its README gives the install command, a CDN link and the first import."""
    m = re.match(r"(?:https?://)?(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?].*)?$", url.strip()) \
        or re.fullmatch(r"([\w.-]+)/([\w.-]+)", url.strip())
    if not m:
        raise LibError("donne le lien GitHub de la bibliothèque (https://github.com/owner/repo)")
    owner, repo = m.groups()
    readme = _raw(owner, repo, "README.md")
    pkg = _raw(owner, repo, "package.json")
    if not readme and not pkg:
        raise LibError(f"dépôt {owner}/{repo} introuvable (ou sans README)")
    try:
        p = json.loads(pkg) if pkg else {}
    except ValueError:
        p = {}
    code = "\n".join(re.findall(r"```[^\n]*\n(.*?)```", readme, re.S)) + "\n" + readme
    find = lambda rx: (re.search(rx, code, re.M) or [None])[0]
    install = find(r"^\s*(?:\$ )?((?:npm (?:i|install)|yarn add|pnpm (?:add|i)|bun add|npx [\w@./-]+ add) [^\n`<]+)")
    install = install.strip().lstrip("$ ").strip() if install else (f"npm install {p['name']}" if p.get("name") and not p.get("private") else "")
    cdn = re.search(r"https://(?:cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com)/[^\s\"'<>)`]+\.(?:m?js|css)", code)
    usage = re.search(r"^\s*(import [^\n]+ from [\"'][^\"']+[\"'];?)", code, re.M)
    desc = p.get("description") or next((re.sub(r"[*_`\[\]]", "", l).strip() for l in readme.splitlines()
                                         if len(l.strip()) > 40 and not l.lstrip().startswith(("#", "<", "!", "[", "|", "```"))), "")
    if not install and not cdn:
        raise LibError("je ne trouve ni commande d'installation (npm…) ni lien CDN dans ce dépôt : est-ce bien une bibliothèque web ?")
    name = p.get("name") if p.get("name") and "/" not in p.get("name", "") else repo
    s = _state()
    s["added"][name] = {"repo": f"{owner}/{repo}", "category": "Ajoutée", "description": desc[:240],
                        "install": install, "cdn": cdn.group(0) if cdn else "", "usage": usage.group(1) if usage else ""}
    s["off"] = [n for n in s["off"] if n != name]
    _save(s)
    return {"name": name, **s["added"][name]}


def prompt():
    """What Naim reads when it builds for the web: the enabled libraries, how to install and use them."""
    on = [l for l in listing() if l["enabled"]]
    if not on:
        return ""
    lines = ["[Bibliothèques web choisies par l'utilisateur — utilise-les quand elles servent ce qu'il demande "
             "(une seule par besoin), installe-les comme indiqué ; dépôt GitHub entre parenthèses]"]
    for l in on:
        how = l["install"] + (f" · sans npm : <script src=\"{l['cdn']}\">" if l.get("cdn") else "")
        lines.append(f"- {l['name']} ({l['repo']}) — {l['description']} Installer : {how}" +
                     (f" · Exemple : {l['usage'].splitlines()[0]}" if l.get("usage") else ""))
    if any(l["name"] in ("GSAP", "Lenis", "React Bits") for l in on):
        lines.append("Recettes détaillées pour GSAP, Lenis et React Bits : ~/.naim/skills/animations-web/SKILL.md (read_file).")
    return "\n".join(lines)


WEB_SKILLS = {"react-app", "application-web", "frontend-design", "animations-web", "react-native", "web-artifacts-builder"}
