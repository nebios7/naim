#!/usr/bin/env python3
"""Quantités de matériaux pour une maison de plain-pied (maçonnerie parpaing, toiture 2 pans en tuiles).

Usage : python3 materiaux.py plan.json [sortie.md]
Utilise l'emprise (largeur × profondeur) et les pièces du plan.json de plan.py. Options facultatives dans le json :
  "hauteur": 2.5 (sous plafond), "pente_toit": 35 (degrés), "debord_toit": 0.5 (m),
  "cloisons_ml": longueur des cloisons en mètres (sinon estimée depuis les pièces).
Ce sont des ESTIMATIONS de métré (pertes comprises) pour préparer un devis : à faire valider par un professionnel
(architecte, bureau d'études, artisan) et par les règles en vigueur (DTU, RE2020, étude de sol).
"""
import json
import math
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
W, P = float(d["largeur"]), float(d["profondeur"])
h = float(d.get("hauteur", 2.5))
pente = math.radians(float(d.get("pente_toit", 35)))
debord = float(d.get("debord_toit", 0.5))
emprise, perim = W * P, 2 * (W + P)
fen = d.get("fenetres", [])
portes = d.get("portes", [])
ouvertures = sum(float(f["l"]) * 1.25 for f in fen) + sum(float(p["l"]) * 2.15 for p in portes if p.get("entree") or p.get("exterieure"))
if "cloisons_ml" in d:
    cloisons = float(d["cloisons_ml"])
else:  # chaque bord de pièce qui n'est pas sur la façade, compté une fois (partagé entre deux pièces)
    edges = 0.0
    for r in d.get("pieces", []):
        x, y, l, p = float(r["x"]), float(r["y"]), float(r["l"]), float(r["p"])
        for (on_facade, length) in ((y <= 0.01, l), (y + p >= P - 0.01, l), (x <= 0.01, p), (x + l >= W - 0.01, p)):
            if not on_facade:
                edges += length
    cloisons = edges / 2

murs_ext = perim * h - ouvertures                                  # m² de murs extérieurs (ouvertures déduites)
toit = (W + 2 * debord) * (P + 2 * debord) / math.cos(pente)        # m² de couverture (2 pans)
nb_fermettes = math.ceil((W + 2 * debord) / 0.6) + 1               # une fermette tous les 60 cm
rows = [
    ("Terrassement", "Décapage et fouilles en rigole (0,50 × 0,80 m)", f"{perim * 0.5 * 0.8:.1f} m³"),
    ("Fondations", "Béton de semelles filantes (0,50 × 0,40 m)", f"{perim * 0.5 * 0.4 * 1.05:.1f} m³"),
    ("Fondations", "Armatures de semelles (chaînage HA 4 × 10 mm)", f"{perim * 1.1:.0f} m"),
    ("Soubassement", "Blocs béton 20 × 20 × 50 (vide sanitaire 3 rangs)", f"{math.ceil(perim / 0.5 * 3 * 1.05)} blocs"),
    ("Plancher bas", "Poutrelles + entrevous (ou dalle) — surface", f"{emprise:.0f} m²"),
    ("Plancher bas", "Béton de dalle de compression 5 cm", f"{emprise * 0.05 * 1.05:.1f} m³"),
    ("Plancher bas", "Treillis soudé (recouvrements compris)", f"{emprise * 1.15:.0f} m²"),
    ("Murs", "Parpaings 20 × 20 × 50 (10 par m², pertes 5 %)", f"{math.ceil(murs_ext * 10 * 1.05)} parpaings"),
    ("Murs", "Mortier de montage (≈ 20 L par m²)", f"{murs_ext * 0.02:.1f} m³"),
    ("Murs", "Chaînages horizontaux et verticaux (béton)", f"{perim * 0.2 * 0.2 * 2 + 4 * h * 0.04:.1f} m³"),
    ("Murs", "Linteaux préfabriqués", f"{len(fen) + len(portes)} pièces"),
    ("Charpente", "Fermettes industrielles (entraxe 60 cm)", f"{nb_fermettes} fermettes"),
    ("Couverture", f"Surface de toiture (pente {round(math.degrees(pente))}°, débords {debord:g} m)", f"{toit:.0f} m²"),
    ("Couverture", "Tuiles mécaniques (≈ 13 par m²)", f"{math.ceil(toit * 13 * 1.05)} tuiles"),
    ("Couverture", "Écran sous toiture + liteaux", f"{toit * 1.1:.0f} m² / {toit * 3.3:.0f} m"),
    ("Isolation", "Laine soufflée ou rouleaux en combles (30 cm, R ≥ 7)", f"{emprise:.0f} m²"),
    ("Isolation", "Doublage murs extérieurs (isolant + plaque de plâtre)", f"{murs_ext * 1.05:.0f} m²"),
    ("Cloisons", f"Cloisons plaques de plâtre 72 mm (≈ {cloisons:.0f} m linéaires)", f"{cloisons * h * 1.05:.0f} m²"),
    ("Plafonds", "Plaques de plâtre sur ossature", f"{emprise * 0.95:.0f} m²"),
    ("Façade", "Enduit monocouche", f"{(perim * (h + 0.6) - ouvertures) * 1.05:.0f} m²"),
    ("Menuiseries", "Fenêtres et portes-fenêtres", f"{len(fen)} unités"),
    ("Menuiseries", "Portes (entrée + intérieures)", f"{len(portes)} unités"),
    ("Sols", "Carrelage ou parquet (pertes 10 %)", f"{emprise * 0.9 * 1.1:.0f} m²"),
]
title = d.get("titre", "Maison")
lines = [f"# Matériaux — {title}", "",
         f"Emprise {W:g} × {P:g} m = {emprise:.0f} m² · périmètre {perim:.0f} m · hauteur sous plafond {h:g} m · "
         f"murs extérieurs {murs_ext:.0f} m² (ouvertures déduites)", "",
         "| Poste | Matériau | Quantité estimée |", "|---|---|---|"]
lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
lines += ["", "Hors réseaux (électricité, plomberie, chauffage, VMC) et raccordements. Estimation de métré à faire valider "
          "par un professionnel (étude de sol, DTU, RE2020) avant tout achat."]
text = "\n".join(lines)
if len(sys.argv) > 2:
    open(sys.argv[2], "w", encoding="utf-8").write(text + "\n")
    key = ("Béton de semelles", "Parpaings", "Fermettes", "Tuiles", "Laine soufflée", "Doublage")
    print(f"liste créée : {sys.argv[2]} ({len(rows)} postes). Chiffres clés à recopier tels quels dans ta réponse :")
    for a, b, c in rows:
        if b.startswith(key):
            print(f"- {b} : {c}")
else:
    print(text)
