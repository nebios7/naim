---
name: github
description: Travailler avec Git et GitHub : branches, commits propres, push, pull requests (gh), conflits.
---

# Git et GitHub

## Avant tout
- `git status` et `git branch --show-current`. Ne jamais travailler directement sur main pour une nouvelle fonction :
  `git switch -c fonction/nom-court` (ou `correctif/…`).
- Ne JAMAIS commiter de secrets : vérifier `git diff --cached` (clés, tokens, mots de passe, .env) et `.gitignore`.

## Commits
- Un commit = une intention. `git add` des fichiers concernés seulement, puis `git commit -m "type: résumé"`.
- Auteur : la configuration git de l'utilisateur (`git config user.name`). N'ajoute jamais de ligne « Co-Authored-By »
  ni de mention d'un assistant dans les messages.

## Pousser et pull requests (seulement si l'utilisateur l'a demandé)
1. `gh auth status` : si non connecté, demander à l'utilisateur de lancer `gh auth login` lui-même (interactif),
   ne jamais lui demander son token dans la conversation.
2. `git push -u origin <branche>`.
3. `gh pr create --title "…" --body "…"` : le corps dit quoi, pourquoi, comment tester. Donner l'URL de la PR.
4. Suivre : `gh pr view`, `gh pr checks` (tests), `gh pr diff`. Fusionner seulement sur demande : `gh pr merge --squash`.

## Conflits
- `git pull --rebase origin main` ; pour chaque fichier en conflit : lire les deux versions, garder la bonne
  combinaison, retirer les marqueurs `<<<<<<<`, `git add`, `git rebase --continue`. Relancer les tests.

## Interdits sans demande explicite
`git push --force` sur main, `git reset --hard`, supprimer une branche distante, réécrire l'historique publié.
