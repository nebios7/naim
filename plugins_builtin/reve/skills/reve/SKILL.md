---
name: reve
description: Le rêve de Naim — relire les corrections de l'utilisateur et la mémoire, proposer des règles pour les consignes (NAIM.md), montrer les propositions en attente. L'utilisateur seul les accepte.
---

# Le rêve

La nuit, quand le Mac est inactif, Naim relit tout seul les moments où l'utilisateur l'a corrigé (« non », « pas ça »,
« toujours… », « !!! », les réponses notées « Mauvais ») et sa mémoire. Il en tire des règles pour ses consignes
(`~/.naim/NAIM.md`) et des faits en double à retirer de la mémoire. Ce sont des **propositions** : elles attendent
l'utilisateur sur l'accueil (carte « Pendant la nuit… ») et dans Personnaliser › Mémoire › Rêves de la nuit.

## Ce que tu fais

- « rêve maintenant », « relis mes corrections », « propose-moi des règles » :
  `python3 "$HOME/.naim/plugins/reve/skills/reve/reve.py" lancer` (il attend la fin et affiche les propositions).
- « qu'as-tu appris cette nuit ? », « tes règles proposées » : `python3 "$HOME/.naim/plugins/reve/skills/reve/reve.py" voir`.
- Présente chaque proposition en une ligne, avec ce que l'utilisateur avait dit (la preuve), sans tout recopier.
  Puis dis où les accepter : la carte de l'accueil, ou Personnaliser › Mémoire › Rêves de la nuit
  (Ajouter, Modifier ou Refuser).

## Interdit

- Accepter une règle toi-même, ou écrire dans `~/.naim/NAIM.md` pour l'ajouter : c'est l'utilisateur qui décide.
- Inventer une règle qui n'est pas dans les propositions, ou une preuve que l'utilisateur n'a pas écrite.
- S'il n'y a rien de nouveau, dis-le simplement : pas de règle « pour faire quelque chose ».
