---
name: pdf-styles
description: Créer des PDF soignés avec ReportLab (Platypus) dans plusieurs styles visuels (classique, moderne, minimaliste). À utiliser quand on demande un PDF "joli", un rapport, une facture, un CV ou un comparatif de styles.
---

# Création de PDF stylés avec ReportLab

## Principe
Un style = un dictionnaire de thème (polices, couleurs, alignement du titre, présence d'un bandeau).
Le contenu (story) reste identique : seul le thème change l'ambiance du document.
Le script `pdf_styles.py` génère les 3 styles de démonstration.

## Installation
    pip install reportlab --break-system-packages

## Les 3 thèmes
| Thème | Police | Couleurs | Usage |
|---|---|---|---|
| classique | Times (serif) | bleu nuit + bordeaux, double filet, titre centré | courrier, rapport officiel |
| moderne | Helvetica | bandeau sombre + turquoise, encadré à barre colorée | présentation, document commercial |
| minimal | Helvetica | noir/blanc/gris, titres en capitales, filets fins | CV, document épuré |

## Structure d'un document
1. `SimpleDocTemplate` avec marges (2 à 2,5 cm) et métadonnées (title, author).
2. Styles `ParagraphStyle` : titre, sous-titre, h1, corps (leading = 1,5 x taille), cellule de tableau.
3. Story : Paragraph, Spacer, HRFlowable, ListFlowable, Table.
4. En-tête / pied de page dessinés au canvas via `onFirstPage` / `onLaterPages`.

## Techniques clés
- Bandeau de titre : `Table` d'une cellule avec `BACKGROUND`.
- Tableau : `repeatRows=1`, `ROWBACKGROUNDS` pour alterner les lignes, padding 6-7 pt.
- Encadré : `Table` à une cellule avec `BACKGROUND` + `LINEBEFORE` (barre) ou `BOX` (cadre).
- Liste à puces : `ListFlowable` + `ListItem`, `bulletColor` aux couleurs du thème.
- Numérotation : `d.page` dans la fonction de pied de page.
- Texte riche dans un Paragraph : `<b>`, `<i>`, `<font color='#RRGGBB'>`, `<sub>`, `<super>`.

## Pièges à éviter
- Ne jamais utiliser les caractères Unicode en indice/exposant (₂, ²) : ils s'affichent en carrés noirs. Utiliser `<sub>` et `<super>`.
- Les polices intégrées (Helvetica, Times, Courier) gèrent les accents français, mais pas tous les symboles (émojis, flèches). Pour plus de glyphes, enregistrer une police TTF avec `pdfmetrics.registerFont`.
- Mettre le texte des cellules dans des `Paragraph` pour qu'il passe à la ligne.
- Vérifier le rendu : `pdftoppm -png -r 60 fichier.pdf apercu` puis regarder l'image.

## Ajouter un nouveau style
Ajouter une entrée dans `THEMES` (file, name, font, bold, ital, ink, acc, light, grey, center, band, tbl_head, size)
puis, si besoin, une branche `k == "monstyle"` dans `deco()` pour l'en-tête/pied de page.
