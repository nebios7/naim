---
name: git-commit
description: Rédiger et faire un commit Git propre (messages conventionnels).
---

# Commit Git propre

1. `git status` et `git diff` pour voir exactement ce qui a changé.
2. Regrouper les changements par intention ; un commit = une intention.
3. Message au format conventionnel : `type(portée): résumé à l'impératif` (feat, fix, refactor, docs, test, chore),
   72 caractères max, puis une ligne vide et le *pourquoi* si utile.
4. `git add` seulement les fichiers concernés, puis `git commit -m "..."`.
5. Ne jamais pousser (`git push`) sans que l'utilisateur le demande.
