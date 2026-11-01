---
name: cobol
description: Écrire, compiler et tester du COBOL sur le Mac avec GnuCOBOL (format fixe mainframe ou libre, fichiers, copybooks).
---

# COBOL avec GnuCOBOL

**Une explication demandée** (« explique-moi », « c'est quoi », « comment marche… ») : réponds dans la conversation,
avec un exemple court en bloc ```cobol (format fixe, colonne 8), sans écrire de fichier. Un fichier et une
compilation seulement si l'utilisateur veut un programme, ou l'essayer.

`cobc` manquant : Personnaliser › Plugins › mainframe › « Installer les outils » (GnuCOBOL).

## Format
- **Fixe** (mainframe, par défaut) : colonnes 1-6 numéro de séquence (espaces), 7 indicateur (`*` commentaire,
  `-` suite), 8-11 zone A (DIVISION, SECTION, paragraphes, niveaux 01/77), 12-72 zone B, rien après 72.
- **Libre** : `-free` à la compilation, `>>SOURCE FORMAT FREE` en première ligne.
Garde le format du fichier existant. Pour un programme destiné au mainframe, toujours le format fixe.

## Pièges fréquents
- Une FUNCTION prend ses arguments entre parenthèses : `MOVE FUNCTION UPPER-CASE(WS-NOM) TO WS-NOM`.
- Assembler un texte : `STRING 'Bonjour ' WS-NOM DELIMITED BY SIZE INTO WS-MESSAGE END-STRING`.
- `SET` : seulement pour les index et les conditions (niveau 88). Une valeur dans une variable : `MOVE`.
- Un sous-programme appelé avec `CALL 'PROG' USING A B` reçoit A et B en `LINKAGE SECTION` et
  `PROCEDURE DIVISION USING A B`, et finit par `GOBACK` (pas `STOP RUN`).

## Appeler un sous-programme (CALL … USING) : l'exemple exact
L'APPELANT passe ses variables (WORKING-STORAGE, pas de LINKAGE) ; l'APPELÉ les reçoit (LINKAGE SECTION +
PROCEDURE DIVISION USING), dans le même ordre, et rend la main avec GOBACK. Passage par référence : l'appelé peut
les modifier.
```cobol
      *> PRINCIPAL.cbl : l'appelant
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PRINCIPAL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-NOM          PIC X(20) VALUE 'MARIE'.
       01  WS-AGE          PIC 9(3)  VALUE 30.
       PROCEDURE DIVISION.
           CALL 'SALUTER' USING WS-NOM WS-AGE
           DISPLAY 'Age apres appel : ' WS-AGE
           STOP RUN.
```
```cobol
      *> SALUTER.cbl : l'appelé
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SALUTER.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-NOM          PIC X(20).
       01  LK-AGE          PIC 9(3).
       PROCEDURE DIVISION USING LK-NOM LK-AGE.
           DISPLAY 'Bonjour ' LK-NOM
           ADD 1 TO LK-AGE
           GOBACK.
```
Compiler les deux ensemble : `cobc -x -fixed PRINCIPAL.cbl SALUTER.cbl -o principal && ./principal`.

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
