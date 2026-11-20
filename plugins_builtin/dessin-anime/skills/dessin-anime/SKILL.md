---
name: dessin-anime
description: Un dessin animé DANS la conversation (bloc ```visuel) à partir des images que l'utilisateur donne — sa photo devient le décor qui vit, ses personnages sont redessinés et bougent (marcher, cligner des yeux, parler, sauter), en scènes avec sous-titres, Lecture / Pause / Rejouer.
---

# Un dessin animé à partir d'une image

Travaille comme le réalisateur d'un petit studio d'animation : chaque film a son caractère, tiré de l'image qu'on t'a
donnée, jamais un modèle passe-partout. L'utilisateur a déjà vu des animations « génériques » et n'en veut pas : il
veut SON image qui prend vie, avec une idée, un rythme, un moment drôle ou touchant.

Ta réponse : une phrase courte, puis UN bloc ```visuel (HTML, CSS, script), puis une ou deux phrases sur ce qui se passe
et ce qu'on peut changer (le texte, la durée, un autre personnage). Pas de fichier, pas d'outil, pas de vidéo à fabriquer.

## Partir de l'image, toujours
Regarde d'abord l'image et décris-toi en 3 points (sans l'écrire dans la réponse) : qui ou quoi (les personnages,
l'animal, l'objet), où (le lieu, la lumière, la saison), l'humeur (calme, joyeuse, mystérieuse). Les couleurs, les
formes et le décor du dessin animé viennent de là — un dessin d'enfant au feutre donne des traits épais et des couleurs
franches ; une photo de plage au coucher du soleil, des orangés et un mouvement lent.

Si l'utilisateur ne dit pas l'histoire, invente-en une courte qui va avec l'image (3 scènes, 10 à 15 secondes) et
dis-la en une phrase après le bloc. S'il donne une histoire, suis-la exactement.

## Deux façons d'animer (souvent les deux ensemble)
1. **L'image elle-même vit.** `image:1` est la première image donnée dans la conversation (`image:2` la suivante,
   `image:derniere` la dernière) : Naim la remplace par l'image. Mets-la en décor (`background-image: url("image:1")`
   ou `<image href="image:1">` dans le svg) et fais-la vivre : zoom lent, parallaxe quand le personnage avance, une
   lumière qui passe, une respiration (scale 1 → 1,02). Un morceau découpé peut bouger seul (`clip-path`, `mask`).
2. **Les personnages sont redessinés.** En SVG, avec des formes simples (cercles, rectangles arrondis, chemins), aux
   couleurs et proportions de l'image : tête, corps, bras, yeux, bouche dans des `<g>` séparés pour bouger chaque partie.
   Un personnage de dessin animé connu (une marque, un film) : crée un personnage original inspiré de ses couleurs et de
   son allure, jamais une copie.

## Le mouvement donne la vie
- Chaque personnage fait au moins 3 choses : il **cligne des yeux** (toutes les 3 s), il **respire ou rebondit**, et il
  a une **action** par scène (marcher, faire signe, sauter, parler avec la bouche qui bouge et une bulle).
- Le temps est une horloge (`requestAnimationFrame`), et chaque scène calcule les positions à l'instant t : jamais
  une suite de `setTimeout` qui se désynchronise. Des départs et arrivées doux (ease-in-out), pas de mouvements raides.
- Un seul moment fort par film (le saut, la surprise, le clin d'œil) : le reste reste calme pour qu'on le voie.
- Si l'utilisateur préfère moins de mouvement (`prefers-reduced-motion`), le décor ne zoome pas.

## Le plan, puis le film, puis la critique
1. Le plan (dans ta tête) : l'image en 3 points, l'histoire en 3 scènes (durée, action, sous-titre), la palette (4 à 6
   couleurs prises dans l'image), ce qui sera le moment fort.
2. Relis ce plan : s'il pourrait servir pour n'importe quelle image, change ce qui est banal.
3. Le bloc, partie par partie, avec un commentaire `// étape : …` ou `<!-- étape : … -->` avant chacune (le plan, le
   décor, le personnage, le scénario, le moteur, les commandes) : Naim montre ces étapes pendant que tu écris.
4. Avant de finir, vérifie : le personnage reste dans le cadre, les sous-titres sont lisibles, Rejouer recommence à zéro.

## Le cadre et les commandes
- Le film dans un cadre 16 / 9 aux coins arrondis, le svg en `viewBox="0 0 1600 900"`.
- Sous le cadre : Pause / Lecture, Rejouer, une barre de progression et « Scène 1 / 3 ».
- Les sous-titres en bas du cadre, blancs sur un fond sombre transparent, une phrase par scène.
- Les commandes aux couleurs du thème (`var(--text)`, `var(--muted)`, `var(--line)`). Jamais d'emoji, jamais de
  police ni d'image extérieure (tout est bloqué) : seulement `image:N` et tes dessins.

## Exemple vérifié : exemples/scene-image.html
La photo en décor qui vit, un personnage redessiné qui marche, cligne des yeux, salue en parlant et repart en sautant,
3 scènes avec sous-titres, Pause / Rejouer. Garde son moteur (l'horloge, les scènes, `dessine()`) ; change tout le
reste selon l'image : le personnage, le décor, l'histoire, les couleurs, le moment fort.
