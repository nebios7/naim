---
name: animation-algorithme
description: Une simulation visuelle (page HTML autonome) qui exécute un algorithme ou un petit programme pas à pas (tri, recherche, boucle, récursivité, pile, arbre, graphe, liste chaînée) avec son code surligné, ses variables, une explication à chaque étape et les commandes lecture, pause, pas à pas.
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

## Autre chose que des barres (pile, arbre, graphe, liste chaînée, tours de Hanoï…)
Garde TOUT le moteur du modèle (CODE surligné, `build` qui enregistre la trace réelle, `P({...})`, les commandes,
la vitesse, la barre de progression, `msg`) ; change seulement le dessin dans `render()` et ce que `P` enregistre :
- **Pile d'appels (récursivité)** : `P({line, stack: [...], msg})`, une boîte par appel empilée de bas en haut
  (`factorielle(3)`, `factorielle(2)`…), la boîte du dessus surlignée, la valeur rendue affichée quand elle remonte.
- **Arbre / graphe** : un `<svg>` avec les nœuds (cercles + valeur) et les arêtes ; `P({line, visited:[…],
  current: x, queue:[…]})` colore le nœud courant (`cmp`), les visités (`ok`), la file ou la pile sous le dessin.
- **Liste chaînée** : des boîtes reliées par des flèches, le pointeur courant au-dessus de sa boîte.
- **Simple boucle / variables** : un tableau des variables qui changent, la ligne courante surlignée.
Le bras robot ne sert que pour les tableaux : retire-le (et son code) pour les autres dessins.

## Les règles
- La trace vient de l'exécution réelle : jamais d'étapes écrites à la main.
- Les numéros `line` correspondent exactement aux lignes de `CODE` (vérifie-les une par une).
- Recherche (pas de tri) : garde les barres, colore la case regardée en `cmp`, la trouvée en `ok`, et les cases
  éliminées avec une opacité réduite (ajoute une classe `.out{opacity:.25}`).
- Messages en français, courts, pour un élève : ce qui se passe et pourquoi.
- Une seule page, sans bibliothèque externe, qui marche hors ligne.

## Vérifier
1. `look_at` du fichier .html : la première étape s'affiche-t-elle, sans erreur ? (La page s'ouvre aussi toute seule
   dans le panneau Aperçu de Naim à la fin : n'ouvre pas le navigateur du Mac sauf si l'utilisateur le demande.)
2. Pour plusieurs entrées (déjà trié, inversé, valeurs égales), la dernière étape donne le bon résultat : fais-le
   avec un petit script node ou python qui reprend la même logique, si node est disponible.
3. Donne le chemin du fichier et dis comment s'en servir (Espace = lecture/pause, flèches = étape par étape).
