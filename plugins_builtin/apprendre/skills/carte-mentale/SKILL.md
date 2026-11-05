---
name: carte-mentale
description: Faire la carte mentale (mind map) d'un texte collé, d'un livre, d'un cours ou d'un document, dessinée dans la conversation — le sujet dans un ovale au centre, les grandes idées en branches colorées, leurs points dessous.
---

# Carte mentale

La carte est dessinée par l'application DANS la conversation : pas de fichier, pas de PDF, pas de make_diagram,
pas de Mermaid. Ta réponse : une phrase, puis UN bloc ```carte (du JSON), puis rien ou une phrase.

## 1. Le contenu vient de la source
- Un texte collé, un livre, un cours ou un document joint (read_file) : les idées viennent de CE texte. Rien d'inventé.
- Lis tout le texte avant d'écrire : les branches couvrent l'ensemble, pas seulement le début.

## 2. Une bonne carte
- `centre` : le sujet en 1 à 4 mots (le titre du livre, la notion).
- `branches` : 4 à 6 grandes idées (8 au plus), dans l'ordre du texte. Chacune : `titre` (2 à 5 mots, au plus
  26 caractères) et `points` : 2 à 4 détails très courts (au plus 30 caractères : un mot-clé, un chiffre, un exemple).
- `a_retenir` (facultatif) : une phrase sous la carte.

## 3. Le bloc (JSON valide, guillemets droits, fermé par ``` sur sa propre ligne)
```carte
{
  "centre": "Atomic Habits",
  "branches": [
    {"titre": "Rends-la attirante", "points": ["Associer à un plaisir", "Rejoindre un groupe"]},
    {"titre": "Rends-la évidente", "points": ["Signal visible", "Empiler les habitudes"]},
    {"titre": "Rends-la satisfaisante", "points": ["Récompense immédiate", "Suivre ses progrès"]},
    {"titre": "Rends-la facile", "points": ["Règle des 2 minutes", "Réduire la friction"]}
  ],
  "a_retenir": "De petites habitudes, répétées, font de grands changements"
}
```

## Invente
- `couleur` de chaque branche (sinon une palette vive est choisie), `style` (sombre, pastel…), `dessin` : une petite
  illustration SVG (`viewBox="0 0 100 70"`) au-dessus de la carte qui résume le sujet.
- Le nombre de branches, leurs titres et leurs détails suivent le texte : une carte n'en copie jamais une autre.

## 4. Après
Une phrase : l'utilisateur peut demander des fiches (/flashcards), un sketchnote (/sketchnotes) ou une BD (/bd)
du même texte.
