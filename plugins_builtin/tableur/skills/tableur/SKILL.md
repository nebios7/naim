---
name: tableur
description: Créer ou modifier un vrai fichier Excel (.xlsx) avec openpyxl — formules vivantes, mise en forme pro, graphiques — puis le vérifier avant de le livrer.
---

# Un vrai fichier Excel, pas un tableau collé

`python3` a déjà openpyxl, pandas et matplotlib (le Python de Naim). Écris UN script `faire_xlsx.py`, lance-le, puis vérifie.

## Les règles qui font un bon classeur

1. **Des formules, pas des résultats.** Un total s'écrit `=SOMME(B2:B13)` (en openpyxl : `"=SUM(B2:B13)"`, les noms de fonctions en anglais). Une valeur calculée en Python et collée ne se met pas à jour : c'est une erreur.
2. **Les hypothèses à part.** Taux, prix, quantités de départ dans des cellules d'entrée (en bleu `0000FF`), référencées par les formules (`=B2*$F$1`). Jamais un nombre en dur dans une formule.
3. **Une ligne d'en-tête nette** : gras, fond doux (`F2F2F2` ou la couleur du thème), bordure basse, ligne figée (`ws.freeze_panes = "A2"`), filtre (`ws.auto_filter.ref = ws.dimensions`).
4. **Les bons formats** : montants `'#,##0.00 €'`, pourcentages `'0.0%'`, dates `'DD/MM/YYYY'`, négatifs entre parenthèses pour la finance. Largeur de colonne adaptée au contenu (`ws.column_dimensions["A"].width = 24`).
5. **Une feuille, un rôle** : « Données », « Synthèse », « Hypothèses ». Noms courts, sans caractères spéciaux.
6. **Un graphique quand il aide** : `from openpyxl.chart import BarChart, LineChart, PieChart, Reference` — titre, axes nommés, placé à côté du tableau (`ws.add_chart(ch, "H2")`).
7. **Modifier un fichier existant** : `load_workbook(chemin)` (sans `data_only=True`, qui effacerait les formules à l'enregistrement), change seulement ce qui est demandé, garde ses styles.

## Squelette

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
wb = Workbook(); ws = wb.active; ws.title = "Données"
ws.append(["Mois", "Recettes", "Dépenses", "Solde"])
for i, m in enumerate(["Janvier", "Février", "Mars"], start=2):
    ws.append([m, 0, 0, f"=B{i}-C{i}"])
n = ws.max_row; ws.append(["Total", f"=SUM(B2:B{n})", f"=SUM(C2:C{n})", f"=SUM(D2:D{n})"])
for c in ws[1]: c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="F2F2F2"); c.border = Border(bottom=Side("thin"))
for row in ws.iter_rows(min_row=2, min_col=2):
    for c in row: c.number_format = '#,##0.00 €'
for c in ws[ws.max_row]: c.font = Font(bold=True)
ws.freeze_panes = "A2"; ws.column_dimensions["A"].width = 16
wb.save("budget.xlsx")
```

## Vérifier avant de livrer (obligatoire)

```
python3 ~/.naim/plugins/tableur/skills/tableur/verifier.py budget.xlsx
```
Il fait calculer le classeur par LibreOffice (sur une copie), montre chaque feuille comme un tableau, chaque formule suivie de son résultat (`=SOMME(B2:B9) → 1250`), et signale ce qui cloche : formule qui donne `#DIV/0!`, `#REF!` ou `#NAME?` une fois calculée, formule vers une feuille absente, nombre en dur dans une formule, colonne trop étroite, en-tête sans style. Regarde aussi si les résultats sont plausibles (un total négatif, un pourcentage à 4000 %). Corrige tout ce qu'il signale, relance, puis livre le fichier. Pour le voir en image : `python3 ~/.naim/plugins/convertisseurs/skills/convertisseurs/convertir.py budget.xlsx apercu.pdf` puis look_at.
