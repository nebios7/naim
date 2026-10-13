---
name: jcl
description: Écrire et relire du JCL z/OS (JOB, EXEC, DD, procédures, SORT, IDCAMS) sans erreur de colonnes ni de syntaxe.
---

# JCL (z/OS)

Le JCL ne s'exécute pas sur le Mac : tu l'écris juste et tu le relis à fond. Si l'utilisateur a un accès au mainframe
avec Zowe (`zowe jobs submit local-file job.jcl`, `zowe jobs view all-spool-content --jobid JOB12345`), propose de
le soumettre ; Zowe s'installe avec `npm install -g @zowe/cli` (lui le fait, avec ses identifiants).

## Règles de forme (les erreurs les plus fréquentes)
- `//` en colonnes 1-2, nom en colonne 3 (1 à 8 caractères, commence par une lettre ou @#$), tout en MAJUSCULES.
- Rien au-delà de la colonne 71 ; continuation : ligne terminée par une virgule, suite entre les colonnes 4 et 16.
- Commentaire : `//*` ; fin de job : `//` seul.

## Squelette
```jcl
//MONJOB   JOB (COMPTA),'NOM',CLASS=A,MSGCLASS=X,NOTIFY=&SYSUID
//*--------------------------------------------------------------
//ETAPE1   EXEC PGM=MONPROG
//STEPLIB  DD DSN=MON.LOADLIB,DISP=SHR
//ENTREE   DD DSN=MON.FICHIER.ENTREE,DISP=SHR
//SORTIE   DD DSN=MON.FICHIER.SORTIE,
//            DISP=(NEW,CATLG,DELETE),
//            SPACE=(CYL,(5,5),RLSE),
//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=0)
//SYSOUT   DD SYSOUT=*
//ETAPE2   EXEC PGM=SORT,COND=(4,LT,ETAPE1)
//SORTIN   DD DSN=MON.FICHIER.SORTIE,DISP=SHR
//SORTOUT  DD SYSOUT=*
//SYSIN    DD *
  SORT FIELDS=(1,10,CH,A)
/*
//
```

## Relecture obligatoire
DISP cohérents (NEW/OLD/SHR/MOD, et les cas d'échec), noms de DD = ceux du programme (SELECT … ASSIGN), LRECL = longueur
des enregistrements COBOL, COND/IF-THEN pour ne pas lancer une étape après un échec, RECFM/LRECL du SORTOUT.
Explique chaque étape en une ligne à l'utilisateur.
