---
name: pli
description: Écrire et relire du PL/I (Enterprise PL/I z/OS) : déclarations, structures, fichiers, ON-conditions.
---

# PL/I

Il n'existe pas de compilateur PL/I pour le Mac : tu écris un code juste, tu le relis ligne à ligne et tu dis
clairement qu'il se compile sur le mainframe (ou avec Iron Spring PL/I sous Linux).

## Squelette
```pli
 BONJOUR: PROCEDURE OPTIONS(MAIN);
   DCL NOM      CHAR(20) VARYING INIT('MONDE');
   DCL TOTAL    FIXED DECIMAL(9,2) INIT(0);
   DCL I        FIXED BINARY(31);
   DO I = 1 TO 3;
     TOTAL = TOTAL + I;
   END;
   PUT SKIP LIST('BONJOUR', NOM, 'TOTAL =', TOTAL);
 END BONJOUR;
```
Code entre les colonnes 2 et 72 (la colonne 1 est réservée), chaque instruction finit par `;`.

## Fichiers et erreurs
```pli
   DCL ENTREE FILE RECORD INPUT;
   DCL 1 ENREG,
         2 NUM   CHAR(10),
         2 SOLDE FIXED DECIMAL(9,2);
   DCL FIN BIT(1) INIT('0'B);
   ON ENDFILE(ENTREE) FIN = '1'B;
   OPEN FILE(ENTREE);
   READ FILE(ENTREE) INTO(ENREG);
   DO WHILE(¬FIN);
     /* traitement */
     READ FILE(ENTREE) INTO(ENREG);
   END;
   CLOSE FILE(ENTREE);
```
Toujours un ON ENDFILE avant la lecture, ON ERROR pour le reste ; FIXED DECIMAL pour l'argent (jamais FLOAT).
Le DD du fichier (ENTREE) se déclare dans le JCL : skill jcl.
