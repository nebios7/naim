---
name: fiches
description: Faire des fiches de révision (flashcards recto / verso, à retourner d'un clic) dans la conversation, à partir d'un texte collé, d'un livre, d'un cours ou d'un document joint.
---

# Fiches de révision

Les fiches s'affichent DANS la conversation, comme des cartes à retourner : pas de fichier, pas de PDF.
Ta réponse : une phrase, puis UN bloc ```quiz avec SEULEMENT des `cartes` (pas de `questions`), puis une phrase.

## 1. Le contenu vient de la source
- Un texte collé, un livre, un cours ou un document joint (lis-le avec read_file) : chaque fiche vient de CE texte,
  avec ses mots, ses chiffres, ses exemples. Rien d'inventé.
- Un long texte (un livre, un chapitre) : couvre-le du début à la fin, pas seulement les premières pages.
- 12 fiches si rien n'est demandé (sinon le nombre demandé), une notion par fiche, dans l'ordre du texte.

## 2. Une bonne fiche
- `recto` : une question courte ou une notion (« Rôle de l'oreillette droite ? », « Date de la Révolution »).
- `verso` : la réponse en une ou deux phrases, précise, avec le chiffre ou l'exemple du texte. Pas de paragraphe.
- Variées : définitions, dates, causes / conséquences, formules (`$…$` est permis), personnages, étapes.

## 3. Le bloc (JSON valide, fermé par ``` sur sa propre ligne)
```quiz
{
  "titre": "Le cœur — fiches",
  "cartes": [
    {"recto": "Que reçoit l'oreillette droite ?", "verso": "Le sang pauvre en oxygène venant du corps, par les veines caves."},
    {"recto": "Rôle du ventricule gauche", "verso": "Envoyer le sang riche en oxygène dans tout le corps, par l'aorte."}
  ]
}
```

## Invente
- `couleur` d'une fiche (une couleur par thème : définitions en bleu, dates en orange…), `style` (pastel, sombre).
- Varie les fiches : questions, définitions, « vrai ou faux ? », compléter une phrase, une formule à retrouver.

## 4. Après
Une phrase : combien de fiches, et que l'utilisateur peut demander un quiz (/quiz) sur les mêmes notions.
Ne redonne pas les fiches en texte : les cartes suffisent.
