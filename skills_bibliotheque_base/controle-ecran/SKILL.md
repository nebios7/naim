---
name: controle-ecran
description: Utiliser une application du Mac à l'écran (ouvrir, lire, cliquer, taper) de façon fiable.
---

# Contrôle de l'écran

1. `computer action=open_app app=<Nom>` (noms français acceptés : Calculatrice, Réglages, Notes…).
2. `computer action=screenshot` : lire la liste des textes visibles et leurs positions.
3. Agir de la façon la plus sûre :
   - saisir du texte ou des nombres → `type` (ex. `12*7=` dans Calculatrice), `key` pour Entrée/Tab/raccourcis ;
   - cliquer sur un bouton ou un menu → `click_text` avec le texte exact visible ;
   - coordonnées (`click` x,y) seulement pour un élément sans texte, d'après la dernière capture.
4. Après chaque action importante : nouvelle capture, et comparer avec ce qui était attendu.
5. Raccourcis utiles : `cmd+n` nouveau, `cmd+s` enregistrer, `cmd+f` chercher, `cmd+w` fermer, `escape`.
6. Rapporter exactement ce que montre la dernière capture (valeurs, messages), même si c'est inattendu.

Ne jamais : taper un mot de passe, valider un paiement, envoyer ou supprimer quelque chose sans que la demande
le dise clairement.
