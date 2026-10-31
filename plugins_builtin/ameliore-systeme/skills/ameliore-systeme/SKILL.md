---
name: ameliore-systeme
description: Relire les dernières conversations de Naim et en tirer un rapport d'amélioration (ce qui marche, ce qui coûte du temps, les skills à créer ou corriger, les automatisations possibles), en PDF, puis appliquer ce que l'utilisateur choisit.
---

# Améliorer le système : relire ses conversations, puis un rapport

But : comme un bilan de fin de semaine. Tu relis ton propre travail récent, tu trouves ce qui fait perdre du temps ou
déçoit l'utilisateur, et tu proposes des améliorations concrètes, chacune avec sa preuve. Tu n'appliques rien sans son accord.

## 1. Le digest (rien d'inventé, tout vient des conversations)

```
A="$HOME/.naim/plugins/ameliore-systeme/skills/ameliore-systeme/analyse.py"
python3 "$A"                    # les 7 derniers jours (--jours 30 pour plus)
python3 "$A" --conv <id>        # le détail d'une conversation, en court
```

Un nombre donné avec la demande (« /ameliore-systeme 30 ») = le nombre de jours : `--jours 30`.

Le digest donne : les tâches les plus longues, les erreurs d'outils qui reviennent, les moments où l'utilisateur
n'était pas content, les notes Mauvais, les demandes qui reviennent, les skills utilisés, les heures des demandes, et ce
que les rapports précédents ont déjà proposé.

## 2. Comprendre les 2 ou 3 cas les plus coûteux

Pour chacun, `--conv <id>` et trouve la **cause**, pas le symptôme : une étape refaite, une commande qui échoue toujours
de la même façon, un skill qui manque ou qui donne une mauvaise méthode, un fichier cherché au mauvais endroit.
Pas plus de 3 conversations lues : le digest suffit pour le reste.

## 3. Les propositions (5 à 8, les plus utiles d'abord)

Chacune a : **ce qui se passe** (avec le chiffre du digest : « 54 échecs d'osascript en 7 jours »), **la cause**, **ce que
tu proposes**, **le gain** (temps, étapes, moins d'erreurs) et **la forme** :
- **Skill à créer** : une demande qui revient sans skill adapté (create_skill, scope utilisateur).
- **Skill à corriger** : un skill dont la méthode fait perdre des étapes (dis quelle ligne changer).
- **Script** : une suite d'étapes toujours la même, à faire en une commande (un plugin avec son script).
- **Automatisation** : une demande qui revient aux mêmes heures ou jours → une tâche planifiée (dis laquelle, quand).
- **Pour l'application Naim** (son interface, son code) : tu ne la modifies pas. Mets la demande précise dans le
  rapport, section « Pour l'application » (ce qui se passe, ce qui doit changer) : le rapport est gardé et relu.

Ce qui a déjà été proposé (fin du digest) : dis s'il a été fait, ne le repropose pas tel quel.
Jamais de proposition vague (« être plus rapide ») : une proposition se vérifie.

## 4. Le rapport en PDF (style pdf-pro)

Écris `rapport.html` dans `~/Documents/Naim/Fichiers/Joints/rapport-amelioration/` : SEULEMENT le contenu, avec les
classes de pdf-pro (pas de `<html>`, pas de `<style>`) :
- couverture `<section class="cover">` : kicker « Rapport d'amélioration », titre, période, date ;
- « En bref » : `<div class="kpis">` (conversations, outils lancés, échecs, notes Bon/Mauvais) et 3 phrases ;
- « Ce qui marche » : court, avec les skills les plus utilisés ;
- « Ce qui coûte du temps » : un tableau (problème · preuve · cause) ;
- « Propositions » : chacune en `<h3 class="prop">1. Titre court</h3>`, puis un paragraphe, puis un tableau ou une
  liste gain · forme · effort, avec `<span class="tag ok|warn|danger">` pour la priorité ;
- « Automatisations possibles » et « Pour l'application » s'il y en a, et « Déjà proposé » (fait ou pas).

Puis UNE commande fait le PDF et garde le rapport pour la prochaine fois :
`python3 "$A" --rapport ~/Documents/Naim/Fichiers/Joints/rapport-amelioration/rapport.html`
Regarde le PDF avec look_at, corrige si besoin et relance la même commande.

## 5. Demander, puis appliquer

Réponds en 5 lignes maximum : le chemin du PDF, les 3 propositions les plus utiles. Puis `ask_user` avec
`multiple: true` : les propositions (la plus utile d'abord), pour que l'utilisateur coche ce qu'il veut.
Applique seulement ce qu'il a coché, une à une, et vérifie chacune (un skill créé : dis son nom ; un script : lance-le
une fois). Jamais : modifier le code de l'application, supprimer un fichier, toucher à tes consignes système.
