---
name: animation-algorithme
description: Une page HTML qui anime un algorithme pas à pas (tri, recherche, boucle, récursivité) avec son code surligné, ses variables et une explication à chaque étape.
---

# Animer un algorithme (une page HTML autonome)

Le modèle `modele-tri-bulles.html` (dans le dossier de cette skill) est une animation complète et vérifiée.
Pars TOUJOURS de lui : `cp "<dossier de la skill>/modele-tri-bulles.html" "<dossier>/<algo>.html"`, puis adapte avec
`multi_edit`. Ne réécris pas la page depuis zéro : la mise en page, les contrôles et le bras animé y sont déjà justes.

## Ce que tu changes (et seulement ça)
1. Titre `<h1>`, sous-titre `.sub`, nom du fichier dans l'onglet (`bubble_sort.c` → `tri_selection.py`…).
2. `CODE` : le code de l'algorithme demandé, une ligne par entrée, dans le langage demandé (C par défaut), avec les
   mêmes classes de couleur (`k` mot-clé, `t` type, `f` fonction, `n` nombre, `c` commentaire). Échappe `<` `>` `&`.
3. `build(vals)` : exécute VRAIMENT l'algorithme sur `a` et appelle `P({...})` à chaque ligne exécutée, avec
   `line` (numéro de ligne dans CODE, à partir de 1), les variables (i, j, min, pivot…), `pair` (les cases regardées),
   `locked` (cases définitivement à leur place), `note` (petit calcul affiché sur la ligne) et `msg` (une phrase
   simple qui explique pourquoi). Les compteurs `c` (comparaisons) et `s` (échanges) suivent les vraies opérations.
4. `render()` : seulement si l'algorithme a d'autres variables à montrer (`.vars`) ou d'autres couleurs
   (`cmp` comparé, `swp` échangé, `ok` à sa place).

## Les règles
- La trace vient de l'exécution réelle : jamais d'étapes écrites à la main.
- Les numéros `line` correspondent exactement aux lignes de `CODE` (vérifie-les une par une).
- Recherche (pas de tri) : garde les barres, colore la case regardée en `cmp`, la trouvée en `ok`, et les cases
  éliminées avec une opacité réduite (ajoute une classe `.out{opacity:.25}`).
- Messages en français, courts, pour un élève : ce qui se passe et pourquoi.
- Une seule page, sans bibliothèque externe, qui marche hors ligne.

## Vérifier
1. Ouvre la page (`open "<fichier>"`), puis `look_at` d'une capture : la première étape s'affiche-t-elle, sans erreur ?
2. Pour plusieurs entrées (déjà trié, inversé, valeurs égales), la dernière étape donne le bon résultat : fais-le
   avec un petit script node ou python qui reprend la même logique, si node est disponible.
3. Donne le chemin du fichier et dis comment s'en servir (Espace = lecture/pause, flèches = étape par étape).
