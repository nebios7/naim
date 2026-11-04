---
name: securite-mac
description: Bilan de sécurité du Mac et du réseau de la maison de l'utilisateur — pare-feu, FileVault, mises à jour, verrouillage de l'écran, services ouverts au réseau, sécurité du Wi-Fi, la box, les appareils (caméras, imprimantes, objets connectés) et leurs ports risqués — avec ce qu'il faut corriger et comment. Lecture seule, sur ses propres appareils.
---

# Bilan de sécurité du Mac et du réseau

```bash
B="$HOME/.naim/plugins/cybersecurite/skills/securite-mac"
python3 "$B/bilan.py"              # le Mac (5 secondes)
python3 "$B/bilan.py" --reseau     # + le Wi-Fi, la box et les appareils du réseau (20 à 40 secondes)
```

Le script **ne change rien** : il lit les réglages et essaie quelques ports connus, seulement sur le réseau local
(adresses privées). Il ne demande aucun mot de passe administrateur.

## Méthode

1. Lance `bilan.py --reseau` (ou sans `--reseau` si l'utilisateur parle seulement du Mac).
2. Réponds avec **le résultat expliqué simplement**, pas la sortie brute :
   - **En bref** : « 6 points en ordre, 3 à corriger en priorité » ;
   - **À corriger**, du plus important au moins important : ce que c'est, pourquoi c'est un risque (une phrase
     concrète : « sur un Wi-Fi public, n'importe qui peut essayer de se connecter à ton Mac »), et **où cliquer**
     (Réglages Système › …) ;
   - **En ordre** : ce qui est bien protégé (ça rassure et ça compte) ;
   - **Bon à savoir** : les services Apple normaux, sans inquiéter.
3. Un appareil du réseau avec un port risqué : nomme-le si possible (skill **reseau-local** : `scan.py <adresse>`
   donne son nom et son type), puis dis quoi faire : changer le mot de passe d'origine, mettre à jour, couper le
   service. Une caméra : vérifier que son flux demande un mot de passe (skill **camera-ip**).
4. Un serveur de l'utilisateur ouvert à tout le réseau (`node … port 8080`) : explique qu'il suffit de le lancer
   sur `127.0.0.1` pour qu'il ne soit visible que du Mac, et montre où le changer dans son code s'il est dans le projet.
5. Demandé en PDF : skill pdf-pro (couverture « Bilan de sécurité », un chapitre « À corriger » avec un tableau
   point · risque · comment · priorité avec des `tag danger/warn/ok`, un chapitre « En ordre »).

## Changer un réglage

L'utilisateur demande clairement de changer un réglage (« active le pare-feu ») : fais-le, en montrant la commande
avant de la lancer — macOS lui demandera son mot de passe administrateur, c'est normal. Par exemple :
`sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on`. Sinon (il demande seulement un bilan),
donne le chemin dans Réglages Système et laisse-le choisir. Après un changement, relance `bilan.py` pour confirmer.

## Règles

- Seulement le Mac et le réseau de l'utilisateur. Jamais le réseau d'un voisin, d'un hôtel, d'une entreprise sans
  autorisation écrite, ni une adresse sur Internet.
- Ne montre jamais un mot de passe Wi-Fi ou une clé, même si tu les trouves.
