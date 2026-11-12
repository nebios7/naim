---
name: anglais
description: Apprendre l'anglais en jouant dans la conversation — les mots d'un thème avec de vraies images et leur prononciation, puis des jeux (images, écoute, orthographe, paires, phrases à remettre dans l'ordre) avec score.
---

# Apprendre l'anglais en jouant

Le jeu s'affiche DANS la conversation : pas de fichier, pas de page HTML, pas d'outil. Tu écris une phrase, puis UN
bloc ```anglais (du JSON), puis une phrase. L'application fait le reste : elle trouve une vraie image libre pour
chaque mot (Wikipédia, gardée sur le Mac), fait entendre les mots avec ta voix anglaise (Admin › Mes voix ; la voix
du Mac seulement si elle manque), et propose six onglets : Vocabulaire (les cartes à écouter), Images, Écoute, Orthographe, Paires, Phrases — avec le score.

## 1. Le contenu
- **Un thème** par jeu (celui demandé, sinon un thème de débutant : les fruits, les animaux, la maison, les
  vêtements, la météo, le corps, les métiers, l'école, les sports, les transports, la famille, la nourriture).
- **8 à 12 mots** du thème, du plus courant au moins courant, au niveau de l'utilisateur (débutant : des noms
  concrets ; intermédiaire : verbes, adjectifs ; avancé : expressions, phrasal verbs).
- **4 à 6 phrases** courtes qui utilisent ces mots (débutant : 3 à 6 mots par phrase). Pour un point de grammaire
  demandé (présent simple, prétérit, comparatifs, prépositions…), les phrases montrent CE point.
- Un anglais juste et naturel, l'orthographe britannique ou américaine mais pas les deux mélangées. Rien d'inventé.

## 1 bis. Chercher sur le web quand il le faut
- **Les données** : un programme ou un manuel précis (« le vocabulaire de 6e », « les mots du chapitre 3 de mon
  livre »), un thème pointu (métiers de la santé, vocabulaire du code, anglais des affaires), des expressions ou des
  phrases authentiques : cherche d'abord (web_search, puis web_fetch de la meilleure page) et prends les mots et les
  phrases de cette source. Un document joint : lis-le (read_file) et prends ses mots.
- **Les images** : l'image automatique ne montre pas bien le mot (un mot abstrait, une marque, un objet rare) ?
  Cherche une image sur le web (web_search « <mot> photo » ou une banque d'images libres), ouvre la page (web_fetch)
  et mets l'adresse DIRECTE de l'image (qui finit souvent par .jpg, .png ou .webp) dans `photo`. Jamais une adresse
  devinée : seulement une adresse lue dans un résultat de tes outils. Une adresse morte est remplacée par l'image
  automatique.

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
- `photo` (facultatif) : l'adresse d'une image trouvée sur le web pour ce mot (voir 1 bis) ; elle passe avant
  l'image automatique et sa source est écrite au survol.
- `phrases` : chaque phrase sans ponctuation finale compliquée ; l'utilisateur remet ses mots dans l'ordre.
- `jeux` (facultatif) : limiter les onglets, par exemple `["images", "ecoute"]` pour un petit enfant.

## 3. Après le bloc
Une phrase : le thème, et ce que l'utilisateur peut demander ensuite (un autre thème, plus difficile, les phrases au
passé…). Ne réécris pas la liste des mots en texte : les cartes la montrent. Si l'utilisateur te donne son score ou
les mots ratés, refais un jeu avec ces mots-là et quelques nouveaux.
