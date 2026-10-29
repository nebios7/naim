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

## Un plugin complet (comme pdf-pro, mods, traduction) : la méthode
Quand une demande revient ou demande un vrai savoir-faire (des PDF soignés, un format de fichier, un affichage) :
1. **Regarder ce qui existe** avant d'écrire : les skills et plugins proches (list_files ~/.naim/plugins,
   ~/.naim/skills, la bibliothèque), et ce qu'ils font déjà. Compléter plutôt que doubler.
2. **Un outil, pas des consignes vagues** : ce que le modèle rate quand il le fait à la main (un design, une syntaxe
   difficile, un calcul) va dans un script `~/.naim/plugins/<nom>/skills/<nom>/<outil>.py`, en Python standard (rien
   à installer), avec une aide (`python3 outil.py` sans argument l'affiche). Modèles : `pdfpro.py` (pdf-pro),
   `livre.py` (traduction-livre).
3. **Un exemple complet à imiter** dans `exemples/` : on copie mieux un exemple qu'une règle.
4. **Le SKILL.md** : QUAND s'en servir (la description), les commandes EXACTES avec leurs chemins, la méthode en
   étapes numérotées, les règles. Court et concret.
5. **Le plugin.json** : `name`, `version`, `description`, `"skills": "skills"`, `triggers` (les mots qui le
   choisissent, une expression régulière), `"priority": true` s'il doit passer avant les skills généraux.
6. **Vérifier qui est choisi** : `python3 ~/.naim/plugins/auto-amelioration/skills/s-ameliorer/verifier_skill.py
   --attendu <nom> "phrase 1" "phrase 2"`, avec 3 phrases qui doivent le choisir ET 2 proches qui ne doivent pas
   (sans `--attendu`, elles affichent le skill qu'elles prennent). Ajuster les mots jusqu'à ce que tout soit juste.
7. **Essayer pour de vrai** : lancer l'outil sur un petit exemple, regarder le résultat (look_at), corriger, recommencer.

## Où ranger le skill
- Par défaut, pour toi partout : `scope="utilisateur"` (~/.naim/skills/<nom>/).
- L'utilisateur veut le voir dans son projet, ou il ne sert que pour ce projet : `scope="projet"` : il va dans
  `<projet>/.naim/skills/<nom>/`, visible dans l'onglet Fichiers. Dis-lui qu'il ne marche alors que dans ce projet.
- Un plugin (avec un outil) : toujours `~/.naim/plugins/<nom>/` ; donne son chemin.

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
