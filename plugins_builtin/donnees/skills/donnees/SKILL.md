---
name: donnees
description: Un tableau de bord DANS la conversation (bloc ```donnees) — titre, chiffres clés avec leur évolution, courbes et barres — à partir des vraies valeurs de l'utilisateur ou de tes recherches.
---

# Un tableau de bord dans la conversation

Ta réponse : une phrase courte, puis UN bloc ```donnees, puis une ou deux phrases qui disent ce qu'on y voit (la
tendance, le chiffre qui compte). Naim le dessine : un titre, des cartes de chiffres clés avec leur évolution en vert
ou en rouge, puis les graphiques (valeur de chaque point au survol).

Pas de fichier, pas d'outil.

## Le bloc

```donnees
titre: Commandes hebdo
sous_titre: Les commandes ont augmenté de 12 % en deux mois
kpi: Commandes | 1 284 | +12 %
kpi: Clients fidèles | 342 | +8 %
courbe: Commandes par semaine
14 sept;268
21 sept;262
28 sept;290
5 oct;301
2 nov;356
barres: Commandes par magasin
Paris;540
Lyon;410
Lille;334
```

- `titre:` et `sous_titre:` (une phrase qui dit la tendance).
- `kpi: Nom | valeur | évolution` : 2 à 4 chiffres clés. L'évolution commence par + ou - (`+12 %`, `-3 %`).
- `courbe: Titre` (une évolution dans le temps) ou `barres: Titre` (une comparaison), puis une ligne par point :
  `étiquette;valeur` (une unité possible : `540 €`, `12 %`).
- Les VRAIES valeurs : celles que l'utilisateur donne, ou celles de tes recherches (avec la source dans ta réponse).
  Des exemples inventés seulement s'il le demande, et tu le dis.
- Les chiffres clés concordent avec les graphiques : un total est la somme des points, une évolution se calcule
  entre la première et la dernière valeur.
