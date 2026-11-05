---
name: bd-educative
description: Faire une BD éducative (educational comic) qui explique un texte collé, un livre, un cours ou un document — des personnages qui dialoguent en quelques cases, bulles, narration, « à retenir » — dessinée dans la conversation.
---

# BD éducative

La BD est dessinée par l'application DANS la conversation (cases, personnages, bulles) : pas de fichier, pas de
HTML, pas de svg à la main, pas d'image à télécharger. Ta réponse : une phrase, puis UN bloc ```bd (du JSON), puis
une phrase.

## 1. Le contenu vient de la source
- Un texte collé, un livre, un cours ou un document joint (read_file) : ce que les personnages expliquent vient de
  CE texte, exact, avec ses mots justes et ses chiffres. Rien d'inventé, aucune erreur pour faire drôle.
- Lis tout le texte d'abord : la BD suit le fil du texte jusqu'à sa conclusion.

## 2. Une bonne BD
- 2 à 4 personnages. Chacun : `nom`, et pour le dessin `couleur` (son habit, ex. "#4d7fd6"), `cheveux` (court,
  long, boucle, chignon, chauve), `lunettes` (true), `peau` (0 à 3), et un `accessoire` qui dit son rôle d'un coup
  d'œil : couronne (roi, chef), masque (espion, secret), clé (solution, indispensable), livre (savoir), ampoule
  (idée), chapeau, épée (combat).
- 4 à 8 `cases`, chacune sur UNE idée, dans l'ordre : on découvre, on comprend, on applique, on conclut.
- Dans une case : `legende` (l'idée de la case, en bas, 3 à 8 mots — c'est elle qui fait la BD : « Cache tes
  intentions »), `presents` (les noms des personnages dessinés), `bulles` (0 à 3 répliques), `fond` (facultatif, une
  couleur douce ; sinon chaque case a la sienne).
- Pour résumer un livre (« les 48 lois », « les règles de… ») : une case par idée, la `legende` donne l'idée, un
  personnage avec le bon accessoire la montre ; une bulle « ! » ou courte suffit.
- Une réplique : `qui` (le nom exact d'un personnage), `texte` (courte : 25 mots au plus, parlée, vivante),
  `humeur` (facultatif : content, surpris, triste), `pensee` (true pour une pensée).
- Une question, puis l'explication ; une comparaison de la vie courante aide (« le cœur, c'est une pompe »).
- `a_retenir` : 2 à 4 points, les idées clés de la BD.

## 3. Le bloc (JSON valide, guillemets droits, fermé par ``` sur sa propre ligne)
```bd
{
  "titre": "Le cœur, une pompe à deux étages",
  "personnages": [
    {"nom": "Léa", "cheveux": "long", "couleur": "#4d7fd6"},
    {"nom": "Dr Sami", "cheveux": "court", "lunettes": true, "peau": 2, "couleur": "#2f9a6f", "accessoire": "livre"}
  ],
  "cases": [
    {"legende": "Deux côtés, deux circuits", "bulles": [
      {"qui": "Léa", "texte": "Pourquoi le cœur a-t-il deux côtés ?"},
      {"qui": "Dr Sami", "texte": "Le côté droit envoie le sang aux poumons, le gauche à tout le corps."}]},
    {"legende": "Le retour par les poumons", "bulles": [
      {"qui": "Léa", "texte": "Et le sang des poumons revient où ?", "humeur": "surpris"},
      {"qui": "Dr Sami", "texte": "Dans l'oreillette gauche, par les veines pulmonaires."}]},
    {"legende": "Droite = poumons, gauche = corps", "bulles": [
      {"qui": "Léa", "texte": "Droite = poumons, gauche = corps !", "pensee": true}]}
  ],
  "a_retenir": ["Cœur droit → circulation pulmonaire", "Cœur gauche → circulation générale"]
}
```

## Invente (chaque BD est unique)
Le cadre est dessiné par l'application ; toi, tu inventes ce qui rend CETTE BD vivante, d'après le sujet :
- `scene` (dans une case) : le décor, que tu dessines toi-même en SVG `viewBox="0 0 200 150"` — une salle du trône,
  une rue la nuit, un laboratoire, une banque, une forêt, l'intérieur du corps… Formes simples et pleines, couleurs
  douces, rien en bas au centre (les personnages s'y tiennent), pas de texte. Il remplace la couleur de fond.
- `style` (de la page) : couleur (défaut), pastel, noir et blanc (manga, polar), sombre (mystère, espace), vintage
  (histoire) — choisis selon le sujet et le ton.
- `colonnes` (1 à 4) : 1 pour une histoire lue case par case, 3 ou 4 pour une planche de règles.
- Les personnages, leurs couleurs et accessoires, le ton des répliques, les fonds de case (`fond`) : à toi de les
  choisir pour que deux BD sur deux sujets ne se ressemblent pas.
Exemple de décor : `"scene": "<svg viewBox=\"0 0 200 150\"><rect width=\"200\" height=\"150\" fill=\"#2c3e66\"/><circle cx=\"165\" cy=\"28\" r=\"12\" fill=\"#f6e7a6\"/><rect x=\"0\" y=\"118\" width=\"200\" height=\"32\" fill=\"#3b4a6b\"/></svg>"`
Si le sujet demande vraiment une autre forme (un roman-photo, une frise, un storyboard), tu peux inventer ta propre
page avec un bloc ```visuel (skill visuel) à la place.

## 4. Après
Une phrase : l'utilisateur peut demander la suite, des fiches (/flashcards) ou un quiz (/quiz) sur la BD.
