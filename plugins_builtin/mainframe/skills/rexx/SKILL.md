---
name: rexx
description: Écrire et exécuter du REXX : sur le Mac avec Regina, et pour z/OS (TSO, ISPF, macros d'édition).
---

# REXX

`rexx` manquant : Personnaliser › Plugins › mainframe › « Installer les outils » (Regina REXX).

## Exécuter sur le Mac
```bash
rexx script.rex arg1 arg2
```
Première ligne d'un script : un commentaire `/* REXX */` (obligatoire sur z/OS, conseillé partout).

## L'essentiel
```rexx
/* REXX */
parse arg nom .
if nom = '' then nom = 'monde'
say 'Bonjour' nom
do i = 1 to 3
  say i '*' i '=' i * i
end
total = 0
do while lines('notes.txt') > 0
  ligne = linein('notes.txt')
  total = total + word(ligne, 2)
end
say 'Total :' total
exit 0
```
Tout est texte ; `parse` découpe les chaînes ; `word`, `substr`, `pos`, `strip`, `translate` ; variables composées
`client.1`, `client.0` = nombre d'éléments ; `signal on error` pour attraper les erreurs.

## Pour z/OS (ne tourne pas sur le Mac : écris juste et dis-le)
`address TSO "ALLOC F(ENTREE) DA('MON.FICHIER') SHR"`, `"EXECIO * DISKR ENTREE (STEM l. FINIS"`,
`address ISPEXEC "DISPLAY PANEL(MONPANEL)"`, macros d'édition : `address ISREDIT "MACRO"` puis
`"(ligne) = LINE .ZCSR"`. Teste sur le Mac tout ce qui ne dépend pas de TSO/ISPF (calculs, découpage de texte).
