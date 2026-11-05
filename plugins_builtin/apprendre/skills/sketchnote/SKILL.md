---
name: sketchnote
description: Faire un sketchnote (prise de notes visuelle dessinée) d'un texte collé, d'un livre, d'un cours ou d'un document — titre au feutre, idée centrale, blocs avec une icône, flèches, « à retenir » — dessiné dans la conversation.
---

# Sketchnote

Le sketchnote est dessiné par l'application DANS la conversation (feuille, feutres, blocs, icônes) : pas de fichier,
pas de HTML, pas de svg à la main. Ta réponse : une phrase, puis UN bloc ```sketchnote (du JSON), puis une phrase.

## 1. Le contenu vient de la source
- Un texte collé, un livre, un cours ou un document joint (read_file) : tout vient de CE texte. Rien d'inventé.
- Lis tout le texte d'abord ; résume l'essentiel, pas les premières lignes.

## 2. Un bon sketchnote
- `titre` : le sujet, court. `sous_titre` : de quoi parle le texte, en une phrase courte.
- `idee_centrale` : LE message du texte en une ligne (une formule chimique, une règle, une thèse).
- `blocs` : 4 à 6 blocs, un par idée clé, dans l'ordre du texte. Chacun :
  - `titre` : 1 à 4 mots ;
  - `icone` : une de ces icônes : book, brain, bulb, target, star, spark, sun, moon, globe, map, calendar, chart,
    list, check, warn, user, hand, bolt, shield, lock, search, eye, chat, code,
    image, play, layers, thermo, activity, wave, tool, phone, home, help ;
  - `points` : 2 à 4 notes très courtes (mots-clés, 2 à 7 mots chacune) ;
  - `exemple` (facultatif) : un exemple concret du texte, en une ligne.
- `comparaison` (quand le texte oppose deux choses) : `{"gauche": {"titre": "Actifs", "texte": "mettent l'argent
  dans ta poche"}, "droite": {"titre": "Passifs", "texte": "sortent l'argent de ta poche"}}` — dessiné « A VS B ».
- `etapes` (quand le texte décrit un chemin, une méthode, un cycle) : 3 à 5 mots-clés dans l'ordre
  (`["Apprendre", "Gagner", "Investir", "Grandir"]`) — dessinés reliés par des flèches, soulignés en couleur.
- `blocs` devient facultatif quand il y a une comparaison et des étapes ; un sketchnote riche a les trois.
- `a_retenir` : la phrase à retenir.
- Des notes, pas des phrases longues : un sketchnote se lit d'un coup d'œil.

## 3. Le bloc (JSON valide, guillemets droits, fermé par ``` sur sa propre ligne)
```sketchnote
{
  "titre": "La photosynthèse",
  "sous_titre": "Comment les plantes fabriquent leur nourriture",
  "idee_centrale": "Lumière + eau + CO₂ → glucose + oxygène",
  "blocs": [
    {"titre": "Ingrédients", "icone": "sun", "points": ["Lumière du soleil", "Eau des racines", "CO₂ de l'air"]},
    {"titre": "Où ?", "icone": "target", "points": ["Chloroplastes", "Chlorophylle verte"], "exemple": "La feuille est verte grâce à elle"},
    {"titre": "Produits", "icone": "spark", "points": ["Glucose : énergie", "Oxygène rejeté"]},
    {"titre": "Pourquoi c'est vital", "icone": "globe", "points": ["Base des chaînes alimentaires", "L'oxygène que l'on respire"]}
  ],
  "a_retenir": "Sans lumière, pas de photosynthèse"
}
```

## Invente (chaque sketchnote est unique)
- `dessin` : une petite illustration en SVG (`viewBox="0 0 100 70"`, traits épais, 2 ou 3 couleurs) près du titre :
  une maison, une ampoule, un cœur, une fusée, un livre… ce qui résume le sujet.
- `croquis` (dans un bloc) : un petit dessin SVG (`viewBox="0 0 60 60"`) qui illustre CE bloc.
- `style` : cahier (défaut), tableau (craie sur tableau noir : sciences, cours), pastel, sombre, vintage (histoire).
- `couleur` d'un bloc, l'ordre et le mélange comparaison / étapes / blocs : compose selon le texte, pas toujours pareil.
Si le contenu demande une autre mise en page (une frise, un cycle, un schéma annoté), tu peux inventer ta propre
page dessinée avec un bloc ```visuel (skill visuel).

## 4. Après
Une phrase : l'utilisateur peut demander la carte mentale (/mindmap), des fiches (/flashcards) ou une BD (/bd).
