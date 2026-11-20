---
name: tableur-vivant
description: Un tableur vivant DANS la conversation (bloc ```feuille) — budget, suivi, liste chiffrée, comparatif, planning, notes — avec des formules qui se recalculent et des cellules que l'utilisateur modifie lui-même. Un fichier Excel (.xlsx) seulement si on le demande (skill tableur).
---

# Une feuille dans la conversation

Ta réponse : une phrase courte, puis UN bloc ```feuille, puis une ou deux phrases pour s'en servir. Naim le dessine
en vrai tableur : colonnes A, B, C…, lignes 1, 2, 3…, barre de formule, calculs en direct. L'utilisateur clique une
cellule, tape, et tout se recalcule. Ses changements restent dans la conversation : au message suivant, tu lis la
feuille telle qu'il l'a laissée.

Pas de fichier, pas d'outil, pas de tableau Markdown pour ce travail. Un fichier Excel seulement si l'utilisateur dit
Excel, .xlsx ou fichier : c'est alors le skill tableur.

## Le bloc

```feuille
titre: Budget du week-end
Poste;Type;Coût
Course d'orientation;Loisirs;560 €
Feu de camp;Loisirs;90 €
Bar à tacos;Repas;640 €
Crêpes;Repas;180 €
Chalets;Dormir;2400 €
Total;;=SOMME(C2:C6)
```

- Ligne `titre:` en premier (facultative), puis une ligne par ligne du tableur, les cellules séparées par `;`.
- La première ligne est l'en-tête (les noms des colonnes).
- Une cellule qui commence par `=` est une formule. Références : `C2`, `$C$2`, plages `C2:C6`.
- Fonctions : SOMME, MOYENNE, MIN, MAX, NB, NBVAL, PRODUIT, ARRONDI, ABS, SI, ET, OU, CONCATENER (ou leurs noms
  anglais SUM, AVERAGE, IF…). Opérateurs : `+ - * / ^`, `&` pour coller du texte, comparaisons `= <> < > <= >=`.
  Arguments séparés par `;` : `=SI(C7>3000;"trop cher";"ok")`, `=ARRONDI(C7/4;2)`.
- Les nombres : `560`, `1 250,50`, `560 €`, `12 %`. Une colonne en euros : écris `€` sur ses valeurs, les formules
  qui les additionnent l'affichent aussi.
- Aucun `;` dans un texte (écris une virgule).

## Les règles d'un bon tableur
1. **Des formules, jamais un résultat calculé de tête.** Le total est `=SOMME(C2:C6)`, une moyenne `=MOYENNE(…)`, une
   TVA `=C2*20%`. Si l'utilisateur change un chiffre, tout suit.
2. **Une colonne, une seule sorte de donnée** : les textes d'un côté, les montants de l'autre. Une colonne de
   catégories qui se répètent (Loisirs, Repas…) s'affiche en étiquettes de couleur.
3. **Les vraies valeurs** de l'utilisateur ou de tes recherches ; des exemples réalistes seulement s'il le demande,
   et tu le dis.
4. **La ligne Total** en dernier, avec « Total » dans sa première cellule.
5. **Les références justes** : compte les lignes (l'en-tête est la ligne 1, la première donnée la ligne 2). Une
   formule ne se référence jamais elle-même.

## Quand l'utilisateur a modifié la feuille
Sa dernière version est dans la conversation (le bloc ```feuille de ton message précédent, mis à jour). Pour la
changer : redonne le bloc ENTIER avec ses changements ET les tiens, sans perdre ce qu'il a tapé. Dis en une phrase ce
que tu as changé.
