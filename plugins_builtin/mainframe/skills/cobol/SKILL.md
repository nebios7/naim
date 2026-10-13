---
name: cobol
description: Écrire, compiler et tester du COBOL sur le Mac avec GnuCOBOL (format fixe mainframe ou libre, fichiers, copybooks).
---

# COBOL avec GnuCOBOL

`cobc` manquant : Personnaliser › Plugins › mainframe › « Installer les outils » (GnuCOBOL).

## Format
- **Fixe** (mainframe, par défaut) : colonnes 1-6 numéro de séquence (espaces), 7 indicateur (`*` commentaire,
  `-` suite), 8-11 zone A (DIVISION, SECTION, paragraphes, niveaux 01/77), 12-72 zone B, rien après 72.
- **Libre** : `-free` à la compilation, `>>SOURCE FORMAT FREE` en première ligne.
Garde le format du fichier existant. Pour un programme destiné au mainframe, toujours le format fixe.

## Squelette
```cobol
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BONJOUR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-NOM          PIC X(20) VALUE 'MONDE'.
       01  WS-TOTAL        PIC 9(5)V99 VALUE ZERO.
       PROCEDURE DIVISION.
           DISPLAY 'BONJOUR ' WS-NOM
           STOP RUN.
```

## Compiler, exécuter
```bash
cobc -x -fixed BONJOUR.cbl -o bonjour && ./bonjour          # -free pour le format libre
cobc -x -fixed -I copybooks PROG.cbl -o prog                # COPY depuis le dossier copybooks
```
Le hook du plugin vérifie la syntaxe après chaque fichier .cbl/.cob écrit : s'il signale des erreurs, corrige-les.

## Fichiers (simuler un DD)
`SELECT FIC-ENTREE ASSIGN TO 'ENTREE'` lit la variable d'environnement : `DD_ENTREE=data/entree.txt ./prog`
(ou `ENTREE=…`). Enregistrements de longueur fixe : `ORGANIZATION IS LINE SEQUENTIAL` pour des fichiers texte du Mac.

## Bonnes pratiques mainframe
Noms en majuscules préfixés (WS-, LK-, FD-), PIC signés `S9(7)V99 COMP-3` pour les montants (packed decimal),
FILE STATUS vérifié après chaque OPEN/READ/WRITE, un paragraphe par action (PERFORM … THRU … -EXIT),
pas de GO TO hors des sorties de paragraphe, `EVALUATE TRUE` plutôt que des IF imbriqués.
Ce qui ne tourne pas sur le Mac (CICS, EXEC SQL DB2, appels système z/OS) : écris-le juste, compile le reste avec
des bouchons, et dis clairement ce qui sera à tester sur le mainframe.
