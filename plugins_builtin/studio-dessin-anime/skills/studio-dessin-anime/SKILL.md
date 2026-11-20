---
name: studio-dessin-anime
description: Produit un dossier de production professionnel pour un dessin animé ou une vidéo animée créée avec des outils d'IA (image vers vidéo, texte vers vidéo, voix, montage) et destinée à TikTok, YouTube Shorts, Instagram Reels ou YouTube. Génère le concept et l'accroche, la bible du personnage, le découpage plan par plan avec les prompts prêts à coller, la voix, le montage, l'export et le pack de publication. À utiliser dès que l'utilisateur parle de créer, scénariser, prompter, animer ou publier un dessin animé, un cartoon, une série animée, un personnage animé ou une vidéo animée par IA, même s'il ne dit pas « dossier de production » ou « skill ».
---

# Studio dessin animé IA

Ce skill transforme une idée en dossier de production complet, utilisable tel quel dans les outils de génération vidéo IA. Le résultat doit se lire comme le document d'un petit studio : précis, cohérent, directement exécutable.

## Pourquoi cette méthode

Les outils de génération vidéo produisent de bons plans courts, mais deux choses font la différence entre un résultat amateur et un résultat professionnel : un personnage identique d'un plan à l'autre, et un rythme pensé pour l'attention (accroche immédiate, un seul événement par plan, chute claire). Tout le dossier est construit autour de ces deux points.

## Déroulement

### 1. Cadrer (poser au plus 3 questions, seulement si l'information manque)

Rassembler, en déduisant de la conversation ce qui est déjà connu :
- Idée ou sujet, et le ton (drôle, tendre, éducatif, suspense)
- Plateforme cible et durée (par défaut : vertical 9:16, 20 à 30 secondes)
- Style visuel (3D type film d'animation, 2D plat, anime, aquarelle, pâte à modeler)
- Langue de la voix et des sous-titres
- Images de référence du personnage fournies par l'utilisateur

Si l'utilisateur fournit des images, les décrire précisément (cheveux, vêtements, couleurs, proportions) pour construire la bible du personnage. Ne pas nommer ni identifier de personnes réelles à partir d'une image. Ne travailler qu'avec des images dont l'utilisateur dit avoir les droits.

Si le brief est déjà assez clair, ne pas poser de question : faire des hypothèses, les énoncer en une ligne, et produire.

### 2. Se renseigner sur les tendances (obligatoire avant le pack de publication)

Les formats, outils et règles de plateforme changent vite. Avant de proposer un angle « tendance », des hashtags ou un outil, faire une recherche web récente avec l'outil web_search (formats courts qui performent, outils actuels, règles de publication), et lire les pages utiles avec web_fetch. Citer ce qui est trouvé et dire clairement ce qui n'a pas pu être vérifié. Ne jamais inventer un son, un hashtag ou une statistique « du moment ».

### 3. Produire le dossier

Utiliser la structure de `assets/dossier-template.md`. Les sections sont toujours dans cet ordre :

1. **Concept et accroche** : une phrase de pitch, trois accroches alternatives pour test A/B, la chute.
2. **Bible du personnage** : une fiche d'identité visuelle, et surtout un **bloc de verrouillage** (un paragraphe de description fixe) à recopier mot pour mot dans chaque prompt. C'est ce qui limite la dérive du visage d'un plan à l'autre.
3. **Guide de style** : rendu, palette (4 à 6 couleurs nommées), lumière, cadrage, mouvement de caméra, ce qu'il faut éviter.
4. **Découpage plan par plan** : tableau avec numéro, durée, intention, action unique, dialogue, son, et prompt prêt à coller. Lire `references/prompts.md` pour les formules de prompt et les erreurs fréquentes.
5. **Voix et son** : texte final de la voix off ou des dialogues avec indications d'intonation, ambiance sonore, musique (genre et énergie, pas de titres protégés).
6. **Montage et export** : ordre, transitions, sous-titres, zones de sécurité, formats d'export.
7. **Pack de publication** : titre, description, hashtags vérifiés, meilleur moment, idée de suite. Lire `references/publication.md`.
8. **Contrôle qualité et conformité** : checklist remplie (voir plus bas).

### 4. Livrer

Présenter le dossier dans la conversation si c'est court (moins de 6 plans), sinon dans un fichier Markdown (creer_fichier, un .md) dont tu donnes le chemin. Les fichiers `references/` et `assets/` de ce skill se lisent avec read_file au moment indiqué. Terminer par une seule proposition de suite (par exemple : générer l'épisode 2 avec le même personnage).

## Règles de qualité

- **Un plan = une action.** Un plan qui mélange deux actions échoue presque toujours dans les outils actuels.
- **3 à 5 secondes par plan.** Au-delà, la cohérence se dégrade.
- **Accroche en moins de 2 secondes** : action ou question visible dès la première image, pas de logo ni de titre d'introduction.
- **Dialogue court** : 6 à 10 mots par réplique, une réplique par plan.
- **Pas de texte lisible dans l'image générée** : les sous-titres et titres s'ajoutent au montage.
- **Format d'abord** : écrire les prompts directement en 9:16 si la cible est verticale, pas en 16:9 recadré ensuite.
- **Style générique** : décrire un style par ses caractéristiques (volumes doux, grands yeux, couleurs saturées), jamais par le nom d'un personnage ou d'une série protégés.
- **Pas de personnes réelles** sans accord explicite : pas de visage, de voix ou de nom de personne existante dans les prompts.

## Contrôle qualité et conformité

Remplir cette checklist à la fin du dossier, en indiquant oui, non, ou à vérifier :
- Le bloc de verrouillage figure dans tous les prompts
- Chaque plan a une seule action et une durée de 3 à 5 s
- L'accroche est visible en moins de 2 s
- Sous-titres prévus et lisibles dans les zones de sécurité
- Les images de référence appartiennent à l'utilisateur ou sont libres de droits
- Musique et voix : droits clairs (outil avec licence commerciale, ou bibliothèque libre)
- **Mention IA** : indiquer à l'utilisateur ce que les règles actuelles de la plateforme choisie demandent pour ce type de contenu (en vérifiant la page d'aide officielle récente). Présenter les faits : ce qui est exigé pour du contenu réaliste, ce qui l'est moins pour de l'animation clairement stylisée, et ce que les outils ajoutent automatiquement (métadonnées). La décision revient à l'utilisateur ; ne pas faire la morale, ne pas répéter.

## Cas particuliers

- **Série ou épisodes multiples** : créer une bible de série (personnages, décors récurrents, formule d'épisode) et la réutiliser à l'identique.
- **Contenu pour enfants** : rester sobre, sans peur intense ni langage inapproprié, et signaler à l'utilisateur que les plateformes ont des règles spécifiques pour ce public.
- **Demande d'imiter un personnage ou une série protégés** : proposer un personnage original dans un style comparable plutôt que de copier.
- **L'utilisateur veut juste un prompt** : donner un seul prompt soigné avec le bloc de verrouillage, sans dossier complet.
