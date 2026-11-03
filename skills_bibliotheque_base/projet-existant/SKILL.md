---
name: projet-existant
description: Modifier ou étendre un projet existant sans rien casser (comprendre, changer peu, vérifier).
---

# Travailler dans un projet existant

## 1. Comprendre (avant toute modification)
- `list_files .` puis lire : README, NAIM.md/AGENTS.md, fichier de dépendances (package.json, requirements.txt,
  composer.json, project.yml), le point d'entrée (app.py, src/index.ts, main.swift…).
- `search` le nom de la fonction / route / écran concerné pour trouver TOUS les endroits touchés.
- Repérer comment le projet se lance et se teste (scripts npm, Makefile, README) : c'est ce que tu utiliseras pour vérifier.

## 2. Vérifier l'état de départ
- Lancer les tests ou le build AVANT de modifier : si ça échoue déjà, le noter (ce n'est pas ta faute, mais dis-le).
- `git status` : ne pas mélanger ton travail avec des changements non commités de l'utilisateur.

## 3. Modifier
- Suivre le style existant (nommage, langue des textes, structure des dossiers, bibliothèques déjà utilisées).
- edit_file pour les modifications ciblées ; ne jamais réécrire un gros fichier en entier.
- Une chose à la fois : modifier → vérifier → étape suivante.
- Ne pas ajouter de dépendance si une existante fait le travail.

## 4. Vérifier
- Relancer build + tests + l'app ; tester à la main le cas demandé (curl, simulateur, commande).
- Vérifier aussi un cas voisin qui pourrait avoir cassé.

## 5. Résumer
- Fichiers modifiés (avec le pourquoi), commande de vérification et son résultat, points à surveiller.

## Pièges
- Deviner un chemin ou un nom de fonction au lieu de le chercher → toujours `search` d'abord.
- Oublier de redémarrer le serveur après une modification (process_output / stop_process + start_process).
