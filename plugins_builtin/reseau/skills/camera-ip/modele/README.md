# Caméra

Application locale pour voir et enregistrer une caméra IP dans le navigateur.

## Lancer
```bash
python3 server.py            # puis ouvre http://localhost:8099
PORT=9000 python3 server.py  # un autre port
```
Prérequis : `python3` et `ffmpeg` (`brew install ffmpeg`).

## Utiliser
Indique l'adresse de la caméra, son identifiant, son mot de passe et le chemin du flux, puis « Démarrer ».
Photo, Enregistrer (MP4), réglages de l'image, détection de mouvement, galerie.
Les vidéos et les photos vont dans `medias/`. Le mot de passe n'est jamais enregistré.
