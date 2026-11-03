---
name: plan-maison
description: Plan de maison ou d'appartement à l'échelle (pièces, murs, portes, fenêtres, cotes, surfaces) et liste des matériaux pour la construire, en fichiers SVG, Markdown et PDF.
---

# Plan de maison + matériaux

Deux outils dans ce dossier (`~/.naim/skills/plan-maison/`) font le dessin et les calculs : ne dessine pas le plan
« à la main » en SVG ni en Mermaid, et ne calcule pas les quantités de tête.

## Méthode
1. Comprendre la demande : type (T2, T3, T4…), surface, plain-pied ou étage, nombre de chambres, contraintes
   (terrain, orientation, garage). Ce qui n'est pas dit : plain-pied, forme simple (carré ou rectangle), séjour
   au nord sur ce plan (fenêtres sur la façade du haut), chambres côté calme. Ne pose une question que si c'est bloquant.
2. Créer un NOUVEAU dossier pour ce projet, nommé avec le type et la surface, par exemple `plans/maison-t4-120m2/`
   (si ce dossier existe déjà, ajouter `-2`, `-3`… : ne jamais écraser un plan existant), et y écrire `plan.json`. Pour un T4 de 100 m²,
   partir de `~/.naim/skills/plan-maison/exemple-t4-100m2.json` (le lire avec read_file, l'adapter à la demande).
   Format : voir l'en-tête de `plan.py`. Mesures en mètres, origine en haut à gauche, `l` = largeur, `p` = profondeur.
3. Vérifier `plan.json` AVANT de dessiner :
   - les pièces couvrent toute l'emprise sans se chevaucher (somme des l × p = largeur × profondeur) ;
   - chaque pièce est accessible (une porte vers le séjour ou le dégagement) ; une porte d'entrée sur une façade ;
   - fenêtres seulement sur les murs extérieurs (x = 0, x = largeur, y = 0, y = profondeur) ; aucune dans le dégagement ;
   - chambres ≥ 9 m², salle de bain ≥ 4 m², WC séparé si T3 ou plus, dégagement ≥ 0,90 m de large.
4. Dessiner : `python3 ~/.naim/skills/plan-maison/plan.py plans/<dossier>/plan.json plans/<dossier>/plan.svg`
5. Matériaux : `python3 ~/.naim/skills/plan-maison/materiaux.py plans/<dossier>/plan.json plans/<dossier>/materiaux.md`
6. Dossier PDF, au style de tous les PDF de Naim (skill pdf-pro) : `plans/<dossier>/page.html` avec seulement le
   contenu : couverture (`<section class="cover">`), le plan (`<figure><img src="plan.svg"><figcaption>…</figcaption></figure>`),
   le tableau des pièces (surfaces en `td class="num"`), le tableau des matériaux, un `callout` par contrainte ;
   puis `python3 ~/.naim/plugins/pdf-pro/skills/pdf-pro/pdfpro.py render plans/<dossier>/page.html plans/<dossier>/dossier.pdf`.
   Vérifier avec look_at : textes lisibles, rien ne déborde, plan entier sur la page.
7. Répondre en quelques lignes : les pièces et leurs surfaces, les quantités clés EXACTEMENT comme materiaux.py les a
   affichées (n'en invente aucune, n'arrondis pas), et les fichiers créés avec leur chemin complet
   (plan.svg, materiaux.md, dossier.pdf).

## À dire à chaque fois (une phrase, sans dramatiser)
Le plan et les quantités sont des estimations pour préparer un projet ou un devis : à faire valider par un
professionnel (architecte, bureau d'études, artisan) avec l'étude de sol et les règles en vigueur (DTU, RE2020,
PLU de la commune). En France, un architecte est obligatoire au-delà de 150 m² de surface de plancher.

## Si la demande change
- Étage : un `plan.json` par niveau (rez-de-chaussée, étage), même emprise ; l'escalier est une pièce (≈ 1 × 3 m).
- Autre forme (en L) : décrire le grand rectangle et mettre une pièce « Terrasse » ou « Jardin » (couleur `#eef3ea`)
  pour la partie non construite.
- Ossature bois, toit plat, garage : adapter le texte des postes dans la réponse, et le dire comme une estimation.
