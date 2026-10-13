---
name: db2
description: SQL DB2 for z/OS : requêtes, EXEC SQL dans le COBOL, SQLCODE, curseurs, DCLGEN, BIND, et leurs pièges.
---

# DB2 (z/OS)

DB2 ne tourne pas sur le Mac (sauf l'image Docker « ibmcom/db2 », lourde : à proposer seulement si l'utilisateur veut
vraiment exécuter). Le plus souvent : écrire juste, relire, expliquer.

## SQL propre à DB2
- Lignes limitées : `FETCH FIRST 10 ROWS ONLY` (pas LIMIT) · date du jour : `CURRENT DATE`, `CURRENT TIMESTAMP`.
- Concaténation `||` ou `CONCAT`, `COALESCE` pour les NULL, `WITH UR` pour lire sans verrou (lecture sale, à dire).
- Table système : `SYSIBM.SYSTABLES`, une ligne fictive : `SYSIBM.SYSDUMMY1`.

## Dans un programme COBOL
```cobol
           EXEC SQL INCLUDE SQLCA END-EXEC.
           EXEC SQL INCLUDE DCLCLIENT END-EXEC.        *> structure générée par DCLGEN
           EXEC SQL
               SELECT NOM, SOLDE INTO :WS-NOM, :WS-SOLDE :WS-SOLDE-IND
               FROM CLIENT WHERE NUM = :WS-NUM
           END-EXEC
           EVALUATE SQLCODE
               WHEN 0    CONTINUE
               WHEN 100  DISPLAY 'CLIENT INCONNU'
               WHEN OTHER DISPLAY 'ERREUR SQL ' SQLCODE
           END-EVALUATE
```
Variables hôtes préfixées par `:`, indicateur de NULL (PIC S9(4) COMP, -1 = NULL), un curseur (DECLARE / OPEN /
FETCH en boucle jusqu'à SQLCODE 100 / CLOSE) dès que plusieurs lignes peuvent revenir.

## SQLCODE à connaître
0 ok · 100 aucune ligne · -803 doublon de clé · -811 plusieurs lignes pour un SELECT INTO · -305 NULL sans indicateur ·
-911/-913 interblocage ou délai · -818 programme et plan désynchronisés (refaire le BIND) · -204 objet inconnu.

## Chaîne de fabrication
précompilation DB2 → compilation COBOL → édition de liens → BIND PACKAGE/PLAN. Le JCL de chaque étape : skill jcl.
