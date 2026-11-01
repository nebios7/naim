---
name: quiz
description: Faire un quiz interactif dans la conversation (QCM avec indice, explication et score) et des cartes mémoire, à partir d'un cours, d'un document joint ou d'un sujet.
---

# Quiz interactif

Le quiz s'affiche DANS la conversation, comme une carte qu'on coche : pas de fichier, pas de PDF, pas d'outil
d'écriture. Tu écris une phrase, puis UN bloc ```quiz (du JSON), puis une phrase.

## 1. Le contenu vient de la source
- Un document joint ou un cours de la conversation : lis-le (read_file pour un fichier joint) et tire les questions
  de CE contenu, avec ses mots, ses chiffres, ses exemples. Rien d'inventé.
- Un sujet seulement : ce que tu sais de sûr ; pour un sujet pointu ou récent, une recherche web d'abord.
- 5 questions si rien n'est demandé (sinon le nombre demandé), du plus simple au plus difficile, chacune sur une
  notion différente.

## 2. Une bonne question
- 4 choix, UNE seule bonne réponse ; des mauvaises réponses plausibles (les erreurs fréquentes, des mots proches),
  jamais absurdes. La bonne réponse change de place d'une question à l'autre.
- `indice` : aide à réfléchir sans donner la réponse.
- `explication` : pourquoi c'est la bonne réponse, et ce qui trompe dans les autres (1 à 3 phrases, d'après la source).

## 3. Le bloc (JSON valide : guillemets droits, pas de virgule finale)
```quiz
{
  "titre": "Le format SAED",
  "questions": [
    {"q": "Que signifie le A de SAED ?", "choix": ["Analyse", "Antécédents", "Action", "Avis"], "bonne": 1,
     "indice": "C'est ce que le patient a eu avant la situation actuelle.",
     "explication": "A = Antécédents : l'histoire du patient utile pour comprendre la situation."}
  ],
  "cartes": [
    {"recto": "S de SAED", "verso": "Situation : ce qui se passe maintenant, en une phrase."}
  ]
}
```
- `bonne` : le numéro du bon choix, en comptant à partir de 0 (0 = le premier).
- `cartes` (facultatif, conseillé) : une carte par notion clé (recto = la notion, verso = sa définition courte).
  Elles s'affichent dans l'onglet « Cartes mémoire ».

## 4. Après
Une phrase : combien de questions, et que l'utilisateur peut demander un quiz plus difficile ou sur une autre partie.
Ne redonne pas les questions en texte : la carte suffit.
