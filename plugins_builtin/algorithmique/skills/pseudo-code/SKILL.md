---
name: pseudo-code
description: Écrire un algorithme en pseudo-code français (conventions scolaires), avec lexique, trace et version Python.
---

# Pseudo-code (conventions françaises)

## Forme attendue
```
Algorithme MoyenneDesNotes
Variables
    n, i : entier
    note, somme, moyenne : réel
Début
    Écrire("Combien de notes ?")
    Lire(n)
    somme ← 0
    Pour i de 1 à n Faire
        Écrire("Note ", i, " :")
        Lire(note)
        somme ← somme + note
    FinPour
    Si n > 0 Alors
        moyenne ← somme / n
        Écrire("Moyenne : ", moyenne)
    Sinon
        Écrire("Aucune note")
    FinSi
Fin
```
- Affectation `←` (jamais `=`), comparaison `=`, `≠`, `<`, `≤`, `>`, `≥` ; `ET`, `OU`, `NON` ; `mod` et `div`.
- Boucles : `Pour i de a à b [pas p] Faire … FinPour` · `TantQue condition Faire … FinTantQue` ·
  `Répéter … Jusqu'à condition` · choix : `Selon valeur Faire cas 1 : … autrement : … FinSelon`.
- Tableaux : `T : tableau[1..10] de entier`, indices à partir de 1 sauf demande contraire.
- Sous-programmes : `Fonction Max(a : entier, b : entier) : entier … Retourner … FinFonction`,
  `Procédure Afficher(T : tableau) … FinProcédure`.
- Indentation de 4 espaces, un mot-clé de fin pour chaque bloc. Garde les conventions de son cours si l'utilisateur
  en donne d'autres (DEBUT/FIN en majuscules, `:=`…).

## Toujours livrer
1. Le **lexique** (chaque variable, son type, son rôle) si l'algorithme a plus de 3 variables.
2. Le **pseudo-code**.
3. Un **tableau de trace** sur un petit exemple (une colonne par variable, une ligne par tour de boucle).
4. Sur demande, ou s'il aide à vérifier : la **version Python**, exécutée avec run_command pour prouver qu'elle marche.
Pour un exercice noté : explique la démarche, sans faire tout le travail à la place de l'élève s'il demande de l'aide.
