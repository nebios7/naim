---
name: s-ameliorer
description: Apprendre ce que l'utilisateur montre (capture d'écran, lien, site, réponse d'un autre assistant, façon de faire) et le garder pour toujours en skill ou en plugin, testé, que Naim réutilise ensuite de lui-même.
---

# S'améliorer : apprendre une fois, savoir faire toujours

Quand l'utilisateur te montre quelque chose de bien fait (un affichage, une façon d'écrire, une méthode de travail, un
outil) et veut que tu fasses pareil, ne te contente pas de le faire une fois : transforme-le en savoir-faire durable.

## 1. Comprendre exactement ce qui est bien fait
- Une image ou une capture : regarde-la (look_at). Décris pour toi, précisément, ce qui la rend réussie : disposition,
  ordre des informations, icônes au trait, couleurs, animations, textes courts, ce qui est caché ou replié.
- Un lien ou un site : lis-le (web_fetch). Un nom d'outil ou de méthode : cherche comment il marche (web_search),
  lis deux sources.
- Note les règles concrètes, vérifiables : « titre en une ligne, puis la liste, jamais de gras pour un titre »,
  « chaque commande montrée avec $ et sa sortie ». Pas de règles vagues comme « faire joli ».

## 2. Choisir la forme
- Une façon d'écrire, de répondre, de présenter, une méthode de travail : un **skill** (create_skill). Nom court en
  minuscules avec des tirets, description qui dit QUAND s'en servir, instructions = les règles + un exemple complet.
- Un vrai outil (un script, une conversion, une vérification) : un **plugin** dans ~/.naim/plugins/<nom>/ avec
  `plugin.json` (name, version, description, skills, triggers), `skills/<nom>/SKILL.md` et le script à côté ; le
  SKILL.md donne la commande exacte à lancer (comme le skill traduction-livre avec livre.py).
- Un skill qui existe déjà sur internet (npx skills add, un dépôt GitHub de skills) : install_skill.
- L'interface de l'application Naim elle-même (ses boutons, ses animations) : tu ne modifies pas le code de
  l'application. Écris la demande précise dans ~/.naim/ameliorations.md (ce que l'utilisateur a montré, le chemin de
  la capture, ce qui doit changer) et dis-le en une phrase.

## 3. Tester avant de dire que c'est appris
- Applique tout de suite le nouveau skill sur un petit exemple réel (use_skill puis le travail).
- Regarde le résultat (look_at pour un affichage, un PDF, une page). S'il ne ressemble pas à ce qui t'a été montré,
  corrige les instructions du skill et refais le test.
- Ensuite seulement, dis en une phrase ce que tu as appris, son nom, et quand tu t'en serviras.

## Règles
- Ne crée pas deux skills pour la même chose : cherche d'abord s'il en existe un (skills de la bibliothèque) et
  complète-le plutôt.
- Rien de privé dans un skill (mots de passe, adresses, numéros).
- Pas d'emoji, des icônes au trait seulement.
