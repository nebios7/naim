---
name: pdf-pro
description: Faire un PDF professionnel et joli (cours, analyse d'un courrier ou d'un document, rapport, dossier avec plans) avec un seul style soigné, des tableaux, des graphiques, des schémas, des formules mathématiques et du code coloré, prêt à imprimer en A4. Rien à installer.
---

# PDF professionnel : un seul style, soigné, prêt à imprimer

C'est le style par défaut de TOUS tes PDF, même quand l'utilisateur ne le nomme pas : jamais un PDF sans style.
Des fichiers .md déjà écrits (un cours en chapitres : 01-intro.md, 02-…) « en PDF » : UNE commande, sans les relire
ni les réécrire : `python3 ~/.naim/plugins/pdf-pro/skills/pdf-pro/pdfpro.py render README.md 01-*.md 02-*.md … cours.pdf`
(ou `[0-9][0-9]-*.md`, dans l'ordre ; README.md donne le titre) : couverture, sommaire, un chapitre par fichier, code
coloré. Puis `check` et look_at. Un mot de couleur à la fin si demandé.
Un PDF, un Word ou un texte donné « à mettre en PDF » : read_file pour son texte (mot pour mot), puis écris-le en HTML
avec les classes ci-dessous et `render`. Jamais python-docx ni un .docx au milieu, jamais un CSS à toi.

Une couleur demandée (« trait gris », « en bleu », « couleur bordeaux ») : ajoute-la à la fin de la commande render
(`pdfpro.py render page.html sortie.pdf gris`) : traits, petits titres et chiffres prennent cette couleur, le reste
du style ne change pas. Possibles : gris, noir, bleu, marine, vert, rouge, bordeaux, violet, turquoise, jaune, or,
rose, marron, ou un code #rrggbb. Rien de demandé : orange, ne mets rien.

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
   Après chaque recherche, juge toi-même : qu'ai-je appris, que manque-t-il ? Cherche seulement ce qui manque
   (jamais la même recherche reformulée) et passe à l'écriture dès que tu as de quoi faire. Aucun chiffre inventé. Plan avec update_todos : couverture, sommaire, 3 à 8 chapitres, conclusion.
2. Travaille dans un dossier à toi (ex. `cours-python/`). Les graphiques : un fichier JSON de données par graphique,
   puis `pdfpro.py chart …` → un .svg dans ce dossier.
3. Écris `page.html` : SEULEMENT le contenu (pas de `<html>`, pas de `<style>`, pas de couleur à toi).
   **Par morceaux**, jamais tout d'un coup (un long fichier en un seul appel se perd) : la couverture et le sommaire
   avec `write_file(page.html, …)`, puis CHAQUE chapitre avec `write_file(page.html, <le chapitre>, append=true)`.
4. `pdfpro.py render page.html document.pdf`, puis `pdfpro.py check document.pdf` et look_at sur les deux PNG :
   rien de coupé, formules affichées, graphiques lisibles. Corrige page.html et relance si besoin.
   Avant de dire « c'est fait » : compare avec la demande et les sources (chaque chapitre, chaque élément demandé) ;
   n'annonce que ce que tu as vu sur la page. Si quelque chose bloque, dis-le au lieu d'improviser un autre format.
5. Copie le PDF dans le dossier du projet ouvert (ou `~/Documents/Naim/Fichiers`) et donne son chemin : seulement
   le PDF. `page.html`, `page.pro.html` et les PNG sont tes brouillons : ne les présente pas, n'en crée pas d'autres
   (une suite de cours = un nouveau dossier avec SON page.html et SON PDF, jamais des séance1.html, séance2.html…).

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

- **Un texte donné à mettre en PDF** (une note, un compte rendu, quelques lignes) : son texte, TOUT son texte, rien
  d'autre. Pas de couverture, pas de sommaire, pas de chapitre ajouté : un `<h1>` (le titre du texte, ou ses premiers
  mots), puis ses paragraphes et ses listes. Quelques lignes = une page. Tu n'inventes aucun contenu.
- **Cours** : couverture, sommaire, un chapitre par notion (explication, exemple de code ou formule, encadré
  « À retenir », exercice en `callout ok`), corrigés en dernier chapitre.
- **Analyse d'un courrier / d'un document** : chapitre « En bref » (3 à 5 points, `kpis` si chiffres), puis
  « Ce que dit le courrier », « Points d'attention » (`callout warn`), « Ce qu'il faut faire » (tableau action ·
  échéance · priorité avec `tag`), et les chiffres du courrier en tableau ou en graphique.
- **Rapport / statistiques** : chiffres clés en `kpis`, un graphique par message important, tableaux sourcés.
- **CV et lettre de motivation** : ce n'est PAS ce skill. Charge le skill cv-lettre (use_skill) et suis-le : son
  script fait le CV dans ce style, avec tous les postes et la photo, même quand l'utilisateur dit « style pdf-pro ».
- **Plan d'architecte** : le plan en SVG (skill plan-maison pour les pièces et les cotes), une pièce par ligne de
  tableau (nom, surface m², orientation), un encadré par contrainte (normes, budget).
