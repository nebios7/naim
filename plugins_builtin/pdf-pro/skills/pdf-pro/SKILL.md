---
name: pdf-pro
description: Faire un PDF professionnel et joli (cours, analyse d'un courrier ou d'un document, rapport, dossier avec plans) avec un seul style soigné, des tableaux, des graphiques, des schémas, des formules mathématiques et du code coloré, prêt à imprimer en A4. Rien à installer.
---

# PDF professionnel : un seul style, soigné, prêt à imprimer

Tu ne fais PAS de design : le style est déjà fait (`theme.css`, couleurs chaudes, titres élégants, tout en A4).
Tu écris seulement le contenu en HTML simple, avec les classes ci-dessous, puis l'outil fait le PDF.
Rien à installer : pas de pip, pas de matplotlib, pas de bibliothèque. L'outil (les chemins exacts) :

```
T="$HOME/.naim/plugins/pdf-pro/skills/pdf-pro"
python3 "$T/pdfpro.py" chart bars donnees.json graphique.svg "Titre"     # bars, hbars, line, donut ; « small » à la fin pour deux côte à côte
python3 "$T/pdfpro.py" render page.html document.pdf                     # le style, les formules, le code coloré → PDF A4
python3 "$T/pdfpro.py" check document.pdf                                # page 1 et 2 en PNG, à regarder avec look_at
```

Modèle complet à imiter (couverture, sommaire, chapitres, tableau, code, formules, graphiques, schéma, encadrés) :
`$T/exemples/cours.html`. Lis-le avec read_file avant d'écrire ta page.

## Méthode

1. Le fond d'abord : lis les documents donnés (read_file lit .pdf, .docx, .xlsx), cherche sur le web si besoin.
   Aucun chiffre inventé. Plan avec update_todos : couverture, sommaire, 3 à 8 chapitres, conclusion.
2. Travaille dans un dossier à toi (ex. `cours-python/`). Les graphiques : un fichier JSON de données par graphique,
   puis `pdfpro.py chart …` → un .svg dans ce dossier.
3. Écris `page.html` : SEULEMENT le contenu (pas de `<html>`, pas de `<style>`, pas de couleur à toi).
4. `pdfpro.py render page.html document.pdf`, puis `pdfpro.py check document.pdf` et look_at sur les deux PNG :
   rien de coupé, formules affichées, graphiques lisibles. Corrige page.html et relance si besoin.
5. Copie le PDF dans le dossier du projet ouvert (ou `~/Documents/Naim/Fichiers`) et donne son chemin.

## Les éléments (classes du thème)

- Couverture : `<section class="cover"><div><div class="kicker">Cours · Niveau</div><h1>Titre</h1>`
  `<div class="subtitle">Sous-titre</div><div class="band"></div></div>`
  `<div class="meta"><div><b>Auteur</b>Naim</div><div><b>Date</b>…</div><div><b>Durée</b>…</div></div></section>`
- Sommaire : `<section class="toc"><h2>Sommaire</h2><ol><li><a href="#c1">Chapitre</a></li>…</ol></section>`
- Chapitre (nouvelle page) : `<section class="chapter" id="c1"><h2><span class="num">01</span>Titre</h2>…</section>`
  ; `<p class="lead">` pour l'introduction ; `<h3>`, `<h4>` pour les sous-parties.
- Encadrés : `<div class="callout"><div class="title">À retenir</div><p>…</p></div>` ; variantes
  `callout info` (Définition, bleu), `callout ok` (Exercice, vert), `callout warn` (Attention, or), `callout danger` (Risque, rouge).
- Chiffres clés : `<div class="kpis"><div class="kpi"><b>1 240</b><span>observations</span></div>…</div>` ;
  `kpi up` (vert), `kpi down` (rouge), `kpi accent` (orange).
- Tableau : `<table><thead><tr><th>…</th><th class="num">Montant</th></tr></thead><tbody>…</tbody>`
  `<caption>Tableau 1 — …</caption></table>` ; `td class="num"` aligne les nombres ; étiquettes
  `<span class="tag ok">payé</span>` (ok, warn, danger, info).
- Figure : `<figure><img src="graphique.svg"><figcaption><b>Figure 1</b> — …</figcaption></figure>` ;
  deux côte à côte : `<div class="grid2"><figure>…</figure><figure>…</figure></div>` (graphiques faits avec `small`).
- Schéma, plan, figure de géométrie : un SVG dans la page (`<figure><svg viewBox=…>`) avec les couleurs du thème :
  traits `#1f1e1d` ou `#6b6a65`, accent `#c96442`, bleu `#4f7fae`, vert `#6f8452`, or `#b7862b`,
  fonds doux `#f6f2ea`, `#e5edf5`, `#e9eee0`. Coter les longueurs, nommer les points (A, B, C), légender.
- Formules : `<span class="tex">a^2 + b^2 = c^2</span>` dans une phrase, `<div class="tex-block">…</div>` seule
  (LaTeX : `\frac{a}{b}`, `\sqrt{x}`, `\sum_{i=1}^{n}`, `\int_0^1`, `\vec{u}`, `\widehat{ABC}`, `\pi`).
- Code : `<pre class="code python"><span class="file">fichier.py</span>…le code tel quel…</pre>` (python, js, sql, bash) :
  il est coloré tout seul. Écris `<` et `&` du code comme `&lt;` et `&amp;`.

## Selon la demande

- **Cours** : couverture, sommaire, un chapitre par notion (explication, exemple de code ou formule, encadré
  « À retenir », exercice en `callout ok`), corrigés en dernier chapitre.
- **Analyse d'un courrier / d'un document** : chapitre « En bref » (3 à 5 points, `kpis` si chiffres), puis
  « Ce que dit le courrier », « Points d'attention » (`callout warn`), « Ce qu'il faut faire » (tableau action ·
  échéance · priorité avec `tag`), et les chiffres du courrier en tableau ou en graphique.
- **Rapport / statistiques** : chiffres clés en `kpis`, un graphique par message important, tableaux sourcés.
- **Plan d'architecte** : le plan en SVG (skill plan-maison pour les pièces et les cotes), une pièce par ligne de
  tableau (nom, surface m², orientation), un encadré par contrainte (normes, budget).
