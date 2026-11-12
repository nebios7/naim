---
name: anglais
description: Apprendre l'anglais en jouant dans la conversation — les mots d'un thème avec de vraies images et leur prononciation, puis des jeux (images, écoute, orthographe, paires, phrases à remettre dans l'ordre) avec score.
---

# Apprendre l'anglais en jouant

Le jeu s'affiche DANS la conversation : pas de fichier, pas de page HTML, pas d'outil. Tu écris une phrase, puis UN
bloc ```anglais (du JSON), puis une phrase. L'application fait le reste : elle trouve une vraie image libre pour
chaque mot (Wikipédia, gardée sur le Mac), fait entendre les mots avec la voix anglaise du Mac, et propose six
onglets : Vocabulaire (les cartes à écouter), Images, Écoute, Orthographe, Paires, Phrases — avec le score.

## 1. Le contenu
- **Un thème** par jeu (celui demandé, sinon un thème de débutant : les fruits, les animaux, la maison, les
  vêtements, la météo, le corps, les métiers, l'école, les sports, les transports, la famille, la nourriture).
- **8 à 12 mots** du thème, du plus courant au moins courant, au niveau de l'utilisateur (débutant : des noms
  concrets ; intermédiaire : verbes, adjectifs ; avancé : expressions, phrasal verbs).
- **4 à 6 phrases** courtes qui utilisent ces mots (débutant : 3 à 6 mots par phrase). Pour un point de grammaire
  demandé (présent simple, prétérit, comparatifs, prépositions…), les phrases montrent CE point.
- Un anglais juste et naturel, l'orthographe britannique ou américaine mais pas les deux mélangées. Rien d'inventé.

## 2. Le bloc (JSON valide : guillemets droits, pas de virgule finale, le bloc FERMÉ par ``` sur sa propre ligne)
```anglais
{
  "titre": "Les fruits",
  "niveau": "débutant",
  "mots": [
    {"en": "apple", "fr": "pomme"},
    {"en": "banana", "fr": "banane"},
    {"en": "strawberry", "fr": "fraise"},
    {"en": "orange", "fr": "orange", "image": "orange fruit"},
    {"en": "grapes", "fr": "raisin", "image": "grape"}
  ],
  "phrases": [
    {"en": "I like apples", "fr": "J'aime les pommes"},
    {"en": "The banana is yellow", "fr": "La banane est jaune"}
  ]
}
```
- `en` : le mot anglais seul (pas d'article, sauf dans une expression) ; `fr` : sa traduction.
- `image` (seulement si besoin) : ce que l'image doit montrer, en anglais, quand le mot seul serait ambigu ou
  abstrait — « orange fruit » (pas la couleur), « running » pour run, « smiling child » pour happy, « grape » pour
  grapes. Le mieux : le titre de l'article Wikipédia anglais qui montre ce mot.
- `phrases` : chaque phrase sans ponctuation finale compliquée ; l'utilisateur remet ses mots dans l'ordre.
- `jeux` (facultatif) : limiter les onglets, par exemple `["images", "ecoute"]` pour un petit enfant.

## 3. Après le bloc
Une phrase : le thème, et ce que l'utilisateur peut demander ensuite (un autre thème, plus difficile, les phrases au
passé…). Ne réécris pas la liste des mots en texte : les cartes la montrent. Si l'utilisateur te donne son score ou
les mots ratés, refais un jeu avec ces mots-là et quelques nouveaux.
