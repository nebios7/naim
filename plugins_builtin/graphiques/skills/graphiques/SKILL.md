---
name: graphiques
description: Faire un graphique, une carte ou un réseau en FICHIER — PNG ou PDF net pour un rapport, un Word ou une diapo (matplotlib, seaborn), page HTML interactive (plotly), carte géographique HTML (folium), graphe de relations (networkx) — et sortir les tableaux d'un PDF vers Excel (pdfplumber). Dans la conversation : c'est le bloc visuel, pas ce skill.
---

# Graphiques, cartes et réseaux en fichiers

Les bibliothèques sont installées dans le Python des outils : `python3` les trouve (matplotlib, seaborn, plotly,
kaleido, folium, networkx, pandas, scipy, sympy, cairosvg, pdfplumber, openpyxl). Écris un script `.py`, lance-le
avec `python3 script.py`, puis REGARDE le résultat (look_at sur le PNG, ou le PDF converti) avant de livrer.

## Choisir
| Demande | Outil | Sortie |
|---|---|---|
| Graphique pour un rapport, un Word, un PDF, une diapo | matplotlib (+ seaborn pour les statistiques) | PNG 200 dpi ou PDF |
| Graphique qu'on explore (survol, zoom) envoyé en fichier | plotly | `.html` (+ `.png` avec kaleido) |
| Carte géographique en fichier (lieux, trajet, zones) | folium | `.html` |
| Relations, organigramme calculé, chemins, liens | networkx (+ matplotlib pour le dessin) | PNG |
| Tableaux d'un PDF (relevé, facture, rapport) vers Excel | pdfplumber + openpyxl | `.xlsx` (puis skill tableur) |
| Un SVG vers PNG / PDF | cairosvg | PNG / PDF |
| Dans la conversation, sans fichier | bloc ```visuel avec naimGraphe / naimCarte (skill visuel) | — |
| Graphique natif DANS un PowerPoint | skill presentation-pro (type `graphique`) | — |

## matplotlib / seaborn : le style de Naim
```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
plt.style.use(str(Path.home() / ".naim/plugins/graphiques/skills/graphiques/naim.mplstyle"))

mois = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin"]
ventes = [120, 200, 150, 80, 170, 210]
fig, ax = plt.subplots()
barres = ax.bar(mois, ventes)
ax.bar_label(barres, padding=3, fontsize=9, color="#555555")
ax.set_title("Les ventes repartent en mai")      # le titre dit le message
ax.set_ylabel("Ventes (unités)")
fig.savefig("ventes.png")                         # ou ventes.pdf pour un document imprimé
```
- Seaborn : `import seaborn as sns` APRÈS `plt.style.use(...)` ; `sns.histplot`, `sns.boxplot`, `sns.heatmap(annot=True, fmt=".0f", cmap="Oranges")`,
  `sns.regplot`. Jamais `sns.set_theme()` (il remplacerait le style de Naim).
- Une seule idée par graphique ; le titre dit ce qu'il faut voir ; les unités sur l'axe ; des valeurs sur les barres
  quand il y en a peu ; un camembert seulement pour 2 à 6 parts d'un tout (sinon des barres).
- Dates : `fig.autofmt_xdate()` ; grands nombres : `ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))`.
- Plusieurs graphiques : `fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))`.

## plotly : un graphique interactif en fichier
```python
import plotly.express as px
fig = px.line(x=mois, y=ventes, markers=True, title="Ventes 2026", color_discrete_sequence=["#d97757"])
fig.update_layout(template="simple_white", font_family="Helvetica Neue")
fig.write_html("ventes.html", include_plotlyjs=True)   # un seul fichier, marche hors ligne
fig.write_image("ventes.png", scale=2)                 # la même en image (kaleido)
```

## folium : une carte géographique en fichier
```python
import folium
carte = folium.Map(location=[48.8566, 2.3522], zoom_start=12)   # fond OpenStreetMap
for nom, lat, lng in [("Tour Eiffel", 48.8584, 2.2945), ("Louvre", 48.8606, 2.3376)]:
    folium.CircleMarker([lat, lng], radius=8, color="white", weight=2, fill=True,
                        fill_color="#d97757", fill_opacity=1, tooltip=nom).add_to(carte)
carte.fit_bounds([[48.8584, 2.2945], [48.8606, 2.3376]], padding=(30, 30))
carte.save("carte.html")
```
Des coordonnées justes (lieu connu ou cherché), jamais au hasard. Pour la regarder : open_preview sur le fichier.

## networkx : un graphe de relations
```python
import networkx as nx
G = nx.Graph([("Alice", "Bob"), ("Bob", "Chloé"), ("Alice", "Chloé"), ("Chloé", "David")])
pos = nx.spring_layout(G, seed=7)
fig, ax = plt.subplots(figsize=(7, 5)); ax.axis("off")
nx.draw_networkx(G, pos, ax=ax, node_color="#d97757", node_size=1400, font_color="white", font_weight="bold", edge_color="#bbbbbb", width=2)
fig.savefig("reseau.png")
```
Chemin le plus court : `nx.shortest_path(G, "Alice", "David")` ; les plus connectés : `sorted(G.degree, key=lambda x: -x[1])`.

## pdfplumber : les tableaux d'un PDF vers Excel
```python
import pdfplumber
from openpyxl import Workbook
wb = Workbook(); ws = wb.active; ws.title = "Tableaux"
with pdfplumber.open("releve.pdf") as pdf:
    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                ws.append([(c or "").strip() for c in row])
            ws.append([])
wb.save("releve.xlsx")
```
Convertis les montants en nombres (`float(x.replace(" ", "").replace(",", "."))`), puis suis le skill tableur
(style, formules de total) et son vérificateur. Un PDF scanné (sans texte) : pdfplumber ne voit rien, lis-le avec
look_at ou l'OCR de Naim.

## Avant de livrer
1. Regarde le PNG avec look_at (ou le PDF : convertir.py fichier.pdf apercu.png) : texte lisible, rien de coupé,
   légende qui ne cache pas les données, bonnes valeurs.
2. Corrige et relance si besoin. Donne le chemin du fichier et une phrase sur ce qu'il montre.
