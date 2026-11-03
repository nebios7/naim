#!/usr/bin/env python3
"""Plan de maison à l'échelle, en SVG (et une page HTML prête à convertir en PDF).

Usage : python3 plan.py plan.json sortie.svg
plan.json (mesures en mètres, origine en haut à gauche de la maison) :
{
  "titre": "Maison T4 — 100 m²",
  "largeur": 10, "profondeur": 10,              // emprise extérieure
  "mur_ext": 0.30, "mur_int": 0.10,             // épaisseurs (facultatif)
  "pieces": [ {"nom": "Séjour / cuisine", "x": 0, "y": 0, "l": 6, "p": 6.3}, ... ],   // l = largeur, p = profondeur
  "portes":   [ {"x": 4.5, "y": 10, "l": 0.9, "mur": "bas", "entree": true}, ... ],     // sur un bord de pièce
  "fenetres": [ {"x": 1, "y": 0, "l": 2.4, "mur": "haut"}, ... ],
  "nord": "haut"
}
Les pièces sont mesurées à l'axe des cloisons ; la surface affichée est la surface intérieure approximative.
"""
import html
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
W, H = float(d["largeur"]), float(d["profondeur"])
e_ext, e_int = float(d.get("mur_ext", 0.30)), float(d.get("mur_int", 0.10))
S = 60                      # pixels par mètre
M = 90                      # marge autour du plan (cotes, titre)
TW, TH = W * S + 2 * M, H * S + 2 * M + 110
X = lambda m: M + m * S     # noqa: E731
Y = lambda m: M + 40 + m * S  # noqa: E731
esc = html.escape
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{TW:.0f}" height="{TH:.0f}" viewBox="0 0 {TW:.0f} {TH:.0f}" '
       'font-family="Helvetica, Arial, sans-serif">',
       f'<rect width="100%" height="100%" fill="#ffffff"/>',
       f'<text x="{M}" y="44" font-size="22" font-weight="600" fill="#1f1e1d">{esc(d.get("titre", "Plan"))}</text>',
       f'<text x="{M}" y="66" font-size="12" fill="#6b6a66">Échelle : 1 carreau = 1 m · cotes en mètres · plan indicatif</text>']

# grille légère (1 m)
for i in range(int(W) + 1):
    svg.append(f'<line x1="{X(i)}" y1="{Y(0)}" x2="{X(i)}" y2="{Y(H)}" stroke="#eeede9" stroke-width="1"/>')
for j in range(int(H) + 1):
    svg.append(f'<line x1="{X(0)}" y1="{Y(j)}" x2="{X(W)}" y2="{Y(j)}" stroke="#eeede9" stroke-width="1"/>')

total = 0.0
for r in d["pieces"]:
    x, y, l, p = float(r["x"]), float(r["y"]), float(r["l"]), float(r["p"])
    inner = max(0.0, (l - e_int) * (p - e_int))
    total += inner
    svg.append(f'<rect x="{X(x)}" y="{Y(y)}" width="{l * S}" height="{p * S}" fill="{r.get("couleur", "#f7f5f0")}" '
               f'stroke="#2b2a27" stroke-width="{max(2, e_int * S):.1f}"/>')
    cx, cy = X(x + l / 2), Y(y + p / 2)
    if l < 1.6 and p > 2 * l:  # a corridor: its name runs along it
        svg.append(f'<text x="{cx + 4}" y="{cy}" font-size="12" font-weight="600" text-anchor="middle" fill="#1f1e1d" '
                   f'transform="rotate(-90 {cx + 4} {cy})">{esc(r["nom"])} · {inner:.1f} m²</text>')
        continue
    small = l < 2.6 or p < 1.8
    size = 15 if not small else 11.5
    svg.append(f'<text x="{cx}" y="{cy - 3}" font-size="{size}" font-weight="600" text-anchor="middle" fill="#1f1e1d">{esc(r["nom"])}</text>')
    detail = f"{inner:.1f} m²" if small else f"{inner:.1f} m² · {l:g} × {p:g} m"
    svg.append(f'<text x="{cx}" y="{cy + 14}" font-size="{11 if small else 12}" text-anchor="middle" fill="#6b6a66">{detail}</text>')

# murs extérieurs (épais)
svg.append(f'<rect x="{X(0)}" y="{Y(0)}" width="{W * S}" height="{H * S}" fill="none" stroke="#1f1e1d" stroke-width="{e_ext * S:.1f}"/>')


def opening(o, color, dash=""):
    x, y, l = float(o["x"]), float(o["y"]), float(o["l"])
    t = e_ext * S + 4
    if o.get("mur", "bas") in ("haut", "bas"):
        return f'<rect x="{X(x)}" y="{Y(y) - t / 2}" width="{l * S}" height="{t}" fill="{color}"{dash}/>'
    return f'<rect x="{X(x) - t / 2}" y="{Y(y)}" width="{t}" height="{l * S}" fill="{color}"{dash}/>'


for f in d.get("fenetres", []):  # fenêtres : vide clair avec double trait
    svg.append(opening(f, "#d8e6ee"))
for po in d.get("portes", []):   # portes : vide blanc + arc d'ouverture
    svg.append(opening(po, "#ffffff"))
    x, y, l = float(po["x"]), float(po["y"]), float(po["l"])
    if po.get("mur", "bas") in ("haut", "bas"):
        sgn = -1 if po.get("mur", "bas") == "bas" else 1
        svg.append(f'<path d="M{X(x)} {Y(y)} L{X(x)} {Y(y) + sgn * l * S} A{l * S} {l * S} 0 0 {0 if sgn < 0 else 1} {X(x + l)} {Y(y)}" '
                   'fill="none" stroke="#9a978f" stroke-width="1.2"/>')
    else:
        sgn = 1 if po.get("mur") == "gauche" else -1
        svg.append(f'<path d="M{X(x)} {Y(y)} L{X(x) + sgn * l * S} {Y(y)} A{l * S} {l * S} 0 0 {1 if sgn > 0 else 0} {X(x)} {Y(y + l)}" '
                   'fill="none" stroke="#9a978f" stroke-width="1.2"/>')
    if po.get("entree"):
        svg.append(f'<text x="{X(x + l / 2)}" y="{Y(y) + 30}" font-size="11" text-anchor="middle" fill="#6b6a66">Entrée</text>')


def cote(x1, y1, x2, y2, label, off):
    if y1 == y2:
        yy = y1 + off
        return (f'<line x1="{x1}" y1="{yy}" x2="{x2}" y2="{yy}" stroke="#6b6a66" stroke-width="1"/>'
                f'<line x1="{x1}" y1="{yy - 6}" x2="{x1}" y2="{yy + 6}" stroke="#6b6a66"/><line x1="{x2}" y1="{yy - 6}" x2="{x2}" y2="{yy + 6}" stroke="#6b6a66"/>'
                f'<text x="{(x1 + x2) / 2}" y="{yy - 6}" font-size="12" text-anchor="middle" fill="#1f1e1d">{label}</text>')
    xx = x1 + off
    return (f'<line x1="{xx}" y1="{y1}" x2="{xx}" y2="{y2}" stroke="#6b6a66" stroke-width="1"/>'
            f'<line x1="{xx - 6}" y1="{y1}" x2="{xx + 6}" y2="{y1}" stroke="#6b6a66"/><line x1="{xx - 6}" y1="{y2}" x2="{xx + 6}" y2="{y2}" stroke="#6b6a66"/>'
            f'<text x="{xx - 8}" y="{(y1 + y2) / 2}" font-size="12" text-anchor="middle" fill="#1f1e1d" transform="rotate(-90 {xx - 8} {(y1 + y2) / 2})">{label}</text>')


svg.append(cote(X(0), Y(0), X(W), Y(0), f"{W:g} m", -34))
svg.append(cote(X(0), Y(0), X(0), Y(H), f"{H:g} m", -34))

# nord et échelle
nx, ny = X(W) + 40, Y(0) + 10
svg.append(f'<path d="M{nx} {ny} l-9 26 l9 -7 l9 7 z" fill="#1f1e1d"/><text x="{nx}" y="{ny + 44}" font-size="12" text-anchor="middle">N</text>')
sy = Y(H) + 52
svg.append(f'<line x1="{X(0)}" y1="{sy}" x2="{X(5)}" y2="{sy}" stroke="#1f1e1d" stroke-width="3"/>'
           f'<text x="{X(0)}" y="{sy + 18}" font-size="11" fill="#6b6a66">0</text><text x="{X(5)}" y="{sy + 18}" font-size="11" text-anchor="end" fill="#6b6a66">5 m</text>')
svg.append(f'<text x="{X(W)}" y="{sy + 4}" font-size="13" text-anchor="end" fill="#1f1e1d">Emprise {W * H:.0f} m² · '
           f'surface intérieure ≈ {total:.0f} m²</text>')
svg.append("</svg>")
open(out, "w", encoding="utf-8").write("\n".join(svg))
print(f"plan créé : {out} ({W:g} × {H:g} m, emprise {W * H:.0f} m², surface intérieure ≈ {total:.0f} m², {len(d['pieces'])} pièces)")
