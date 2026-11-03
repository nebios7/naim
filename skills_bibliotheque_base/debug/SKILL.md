---
name: debug
description: Trouver et corriger un bug de façon méthodique (reproduire, localiser, prouver, corriger, vérifier).
---

# Débogage méthodique

## 1. Reproduire
- Exécuter exactement ce qui échoue (run_command, curl, test) et lire l'erreur COMPLÈTE, pile d'appels comprise.
- Pour un serveur : `process_output` du programme lancé, ou relancer avec les logs visibles.
- Si le bug ne se reproduit pas : demander les étapes exactes plutôt que de deviner.

## 2. Localiser
- La dernière ligne de la pile qui appartient au PROJET (pas aux bibliothèques) est le point de départ.
- `read_file` autour de cette ligne, `search` les appels de la fonction et d'où viennent les données.

## 3. Prouver la cause
- Formuler UNE hypothèse précise (« `user` est None car la requête SQL ne trouve rien »).
- La prouver avec un test ciblé : print temporaire, petite commande `python -c`, requête curl, lecture de la base.
- Si l'hypothèse est fausse : la rayer et en formuler une autre. Ne pas corriger à l'aveugle.

## 4. Corriger
- Le plus petit changement qui traite la CAUSE (pas le symptôme) ; edit_file.
- Données invalides (texte au lieu d'un nombre, valeur manquante) : ne JAMAIS inventer une valeur (ex. mettre
  quantité = 1). Corriger ce qui est certain (« 20 » → 20), rendre le code robuste (conversion, validation avec un
  message clair qui nomme l'élément fautif) et signaler dans le résumé les valeurs à compléter par l'utilisateur.
- Retirer les prints de débogage.

## 5. Vérifier
- Relancer la reproduction exacte de l'étape 1 : elle doit passer.
- Relancer les tests existants ; si possible ajouter un test qui aurait détecté ce bug.

## Erreurs fréquentes
- Python `ModuleNotFoundError` : venv non utilisé → `.venv/bin/python`, `.venv/bin/pip install …`.
- `Address already in use` : un ancien serveur tourne → `lsof -ti :PORT` puis l'arrêter (ou autre port).
- Flask `TemplateNotFound` : dossier `templates/` mal placé ou mauvais nom de fichier.
- Node `Cannot find module` : `npm install` manquant ou mauvais chemin relatif / extension .js en ESM.
- Swift : lire la PREMIÈRE erreur de xcodebuild, les suivantes en découlent souvent.
- 500 sans détail : regarder la sortie du serveur (process_output), la vraie erreur y est.
