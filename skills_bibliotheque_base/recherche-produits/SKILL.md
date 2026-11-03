---
name: recherche-produits
description: Chercher un produit ou un bien sur le web (prix, offres, photos), comparer et conseiller, avec une galerie de photos dans la réponse.
---

# Recherche de produits et de biens, avec photos

## Méthode
1. Comprendre ce qui est cherché (modèle précis ? budget ? neuf ou occasion ? usage). Si c'est vague, fais quand même
   une première recherche large, puis propose de préciser — ne bloque pas sur des questions.
2. Photos + prix en une commande (≈ 5 s) :
   `python3 ~/.naim/skills-bibliotheque/recherche-produits/produits.py "<recherche précise>" 8`
   Elle renvoie des lignes `![…](https://…)` (les PHOTOS, avec leur titre qui contient souvent le prix et la surface)
   et des OFFRES avec un prix et leur lien.
   - Immobilier : mets le type, la ville et le budget dans la recherche, ex. « maison à vendre Bordeaux 200000 € ».
   - « Encore des photos », « d'autres » : relance la MÊME recherche avec `--page=2`, puis `--page=3`… (jusqu'à 20 photos
     par page). Ne réaffiche JAMAIS des photos déjà montrées dans la conversation, et ne les invente pas.
3. Pour comparer plusieurs modèles, lance la commande une fois par modèle (2 à 4 modèles au plus).
4. Si besoin de plus de détails (caractéristiques, avis), web_search puis web_fetch sur 1 ou 2 pages de test ou de comparatif.

## Répondre (dans la conversation, pas de fichier)
1. Une phrase : ce que tu as trouvé.
2. Les PHOTOS : recopie les lignes `![…](…)` telles quelles, à la suite, sans texte entre elles → elles s'affichent en
   galerie (4 à 6 photos).
3. Un tableau : Produit | Prix trouvé | Boutique (lien). Seulement les prix vus dans les résultats, jamais inventés ;
   écris « prix à vérifier » sinon.
4. Ton conseil en 2 ou 3 lignes (meilleur rapport qualité-prix, ce qui fait la différence), et ce que tu peux faire
   ensuite (comparer un autre modèle, chercher d'occasion…).
