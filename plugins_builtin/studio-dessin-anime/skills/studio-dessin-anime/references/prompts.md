# Formules de prompt pour dessins animés IA

À lire au moment de rédiger le découpage plan par plan.

## Sommaire
1. Anatomie d'un prompt de plan
2. Flux image vers vidéo (recommandé)
3. Flux texte vers vidéo
4. Verrouillage du personnage
5. Mouvements de caméra utiles
6. Erreurs fréquentes et corrections
7. Exemple complet

## 1. Anatomie d'un prompt de plan

Ordre fixe, une phrase par bloc :

1. **Format et style** : « Vertical 9:16, animation 3D douce, couleurs saturées. »
2. **Bloc de verrouillage** du personnage, recopié mot pour mot.
3. **Décor et lumière** : « Cuisine lumineuse, lumière de fin d'après-midi par la fenêtre. »
4. **Action unique** : un verbe principal, au présent.
5. **Caméra** : cadrage et mouvement (voir section 5).
6. **À éviter** : « pas de texte dans l'image, pas de déformation des mains, pas de changement de vêtements ».

## 2. Flux image vers vidéo (recommandé)

C'est le flux le plus fiable pour garder un personnage identique.
1. Générer une **image clé** par plan (même bloc de verrouillage, même style).
2. Choisir les meilleures, vérifier que le visage et les vêtements concordent.
3. Animer chaque image avec un prompt de mouvement court : l'action, la caméra, la durée. Ne pas redécrire tout le personnage dans le prompt de mouvement.
4. Garder la première image du plan suivant proche de la dernière du plan précédent pour des raccords fluides.

## 3. Flux texte vers vidéo

Plus rapide mais moins constant. À réserver aux plans sans gros plan sur le visage (silhouettes, plans larges, décors). Recopier le bloc de verrouillage dans chaque prompt.

## 4. Verrouillage du personnage

Le bloc doit être **concret et stable**, 40 à 70 mots :
- âge apparent et morphologie, forme du visage
- cheveux (longueur, couleur, coiffure), yeux
- vêtements (pièces, couleurs, un détail distinctif)
- style de rendu
- une expression par défaut

Exemple : « Fillette d'environ 8 ans, visage rond, joues roses, grands yeux marron foncé, cheveux noirs mi-longs avec raie au milieu, capuche bleu marine, t-shirt crème à manches courtes, salopette bleu marine avec petite broche blanche. Rendu 3D de film d'animation, textures douces, expression curieuse. »

Ne jamais modifier le bloc en cours de projet. Si une variation est nécessaire (manteau, pyjama), créer une variante nommée dans la bible.

## 5. Mouvements de caméra utiles

- Plan fixe : le plus stable, à privilégier pour les dialogues
- Léger travelling avant : pour mettre l'accent sur une émotion
- Panoramique lent : pour révéler un décor
- Caméra à l'épaule légère : pour l'énergie, à utiliser avec parcimonie

Éviter les mouvements complexes combinés (rotation + zoom + travelling) dans un même plan.

## 6. Erreurs fréquentes et corrections

| Problème | Cause probable | Correction |
|---|---|---|
| Le visage change d'un plan à l'autre | Bloc de verrouillage modifié ou absent | Recopier le bloc, partir d'une image clé commune |
| Mains ou doigts déformés | Mains en gros plan, geste complexe | Cadrer plus large, cacher les mains, geste simple |
| Mouvement saccadé ou flottant | Plan trop long ou action multiple | Réduire à 3 à 4 s, une seule action |
| Texte illisible dans l'image | Texte demandé dans le prompt | Retirer, ajouter au montage |
| Synchronisation labiale approximative | Dialogue trop long | Phrases courtes, plans moyens, ou voix off sans bouche visible |
| Vêtements qui changent | Description trop vague | Détailler pièces et couleurs dans le bloc |
| Style qui dérive | Mots de style variables | Fixer 3 à 5 mots de style, les répéter à l'identique |

## 7. Exemple complet (un plan)

**Plan 2 (4 s) : le personnage découvre une porte lumineuse**

Prompt image clé : « Vertical 9:16, animation 3D douce, couleurs saturées. [BLOC DE VERROUILLAGE]. Couloir de bibliothèque aux étagères en bois, une porte entrouverte émet une lumière dorée. Plan moyen de face, le personnage regarde la porte, bouche légèrement ouverte d'émerveillement. Pas de texte dans l'image. »

Prompt de mouvement : « Le personnage fait un petit pas en avant et lève la main vers la porte. Léger travelling avant. 4 secondes. »

Dialogue (voix off) : « Mais... c'était quoi, ça ? »
