---
name: mem-search
description: Retrouver ce qui a été fait lors des sessions passées (demandes, actions, réponses) avec la mémoire naim-mem.
---

# Mémoire des sessions (naim-mem)

naim-mem garde automatiquement, sur ce Mac : chaque demande, chaque action qui change quelque chose (fichier écrit,
commande, recherche web, e-mail…) et chaque réponse finale. Utilise-la AVANT de refaire un travail ou quand
l'utilisateur parle du passé (« la dernière fois », « on avait corrigé », « tu te souviens », « qu'est-ce que j'avais
demandé », « on en était où »).

1. Chercher par mots : `use_mcp(server="naim-mem-memoire", tool="chercher", arguments={"requete": "facture tva"})`
2. Voir les dernières sessions : `use_mcp(server="naim-mem-memoire", tool="chronologie", arguments={"jours": 7})`
   (ajoute `"projet": "trello"` pour un seul projet)
3. Lire une entrée entière : `use_mcp(server="naim-mem-memoire", tool="detail", arguments={"id": 42})`

Réponds avec ce que tu as retrouvé (la date, ce qui a été fait, les fichiers), sans inventer ce qui n'y est pas.
Les conversations elles-mêmes se cherchent avec `chercher_conversations` ; tes faits durables sont dans ta mémoire.
