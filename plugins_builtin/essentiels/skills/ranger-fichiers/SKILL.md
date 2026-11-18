---
name: ranger-fichiers
description: Ranger et organiser les fichiers et dossiers du Mac par thème (Téléchargements, Documents, Bureau), toujours avec une proposition d'abord, sans rien supprimer.
---

# Ranger les fichiers par thème

L'outil `ranger_dossier` fait le travail en trois temps. Ne déplace jamais les fichiers un par un avec move_file ou
run_command : passe toujours par lui (une seule validation, et tout s'annule).

## 1. Quel dossier
- L'utilisateur le nomme (« mes téléchargements » = `~/Downloads`, « le bureau » = `~/Desktop`, « mes documents » =
  `~/Documents`) : prends celui-là.
- Il décrit des fichiers sans dossier (« mes factures sont partout ») : `chercher_sur_mac` pour les trouver, puis
  demande dans quel dossier les rassembler.
- Rien de clair : demande-lui quel dossier (ask_user), une seule question.

## 2. Voir, puis proposer
1. `ranger_dossier(dossier, action="voir")` : la liste numérotée, avec quelques mots de chaque document.
2. Classe par **thème**, le sujet de la vie de l'utilisateur, pas le type de fichier :
   « Factures et banque », « Travail », « Cours/Maths », « Voyages », « Santé », « Papiers administratifs »,
   « Photos/Vacances 2025 »… Le nom, le début du texte et les noms du dossier disent le sujet.
   - Réutilise les dossiers qui existent déjà s'ils conviennent.
   - Peu de thèmes (4 à 10), des noms courts en français, comme l'utilisateur les écrirait.
   - Un sous-thème seulement s'il y a beaucoup d'éléments (`Cours/Maths`, `Cours/Anglais`).
   - Pas sûr d'un élément : laisse-le hors du plan. Les « projet, laissé en place » ne bougent jamais.
3. `ranger_dossier(dossier, action="proposer", plan={"Thème": [numéros], …})`.
4. **Montre la proposition** telle que l'outil la rend, puis arrête-toi : « Je range comme ça ? Tu peux changer un
   thème ou retirer un fichier. » Rien n'est déplacé tant qu'il n'a pas répondu.

## 3. Appliquer, seulement après son oui
- Il dit oui : `ranger_dossier(dossier, action="appliquer")`, puis dis combien d'éléments ont été rangés et où.
- Il veut des changements : refais `proposer` avec le plan corrigé, montre-le, attends encore son oui.
- Il veut revenir en arrière : `ranger_dossier(dossier, action="annuler")`.

## Pièges
- Ne supprime jamais rien, même un doublon ou un fichier qui semble inutile : signale-le seulement.
- Ne range jamais le dossier personnel entier, la Bibliothèque, les Applications ni les dossiers de Naim.
- Ne dis « rangé » que si l'outil a répondu « ok ».
