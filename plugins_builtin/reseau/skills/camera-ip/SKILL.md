---
name: camera-ip
description: Une application web locale pour une caméra IP — voir le direct dans le navigateur, enregistrer en MP4, prendre des photos, régler l'image, détecter les mouvements, galerie — à partir du modèle vérifié de ce skill ; trouver le flux RTSP de la caméra.
---

# Une caméra IP dans une application

Le navigateur ne lit pas le RTSP (le flux des caméras). La méthode qui marche, déjà écrite et vérifiée dans `modele/` :
**ffmpeg convertit le flux en HLS** que le petit serveur Python donne à la page ; pendant l'enregistrement, **le même
ffmpeg** écrit aussi un MP4 — une seule connexion à la caméra (la plupart n'en acceptent qu'une : deux programmes
en même temps et l'image se coupe).

## 1. Trouver la caméra et son flux
```bash
python3 "$HOME/.naim/plugins/reseau/skills/reseau-local/scan.py"          # son adresse (CAMÉRA probable, nom « ipcam… »)
CAM_USER=… CAM_PASS=… python3 "$HOME/.naim/plugins/reseau/skills/camera-ip/sonde.py" <adresse>   # le bon chemin RTSP
```
L'identifiant et le mot de passe de la caméra : demande-les à l'utilisateur (ask_user). Ne les écris JAMAIS dans
un fichier, un message ou une commande affichée : ils passent seulement par CAM_USER / CAM_PASS, puis l'utilisateur
les tape dans la page de l'application. La sonde dit le chemin, le format (H.264 → copie sans ré-encoder ; sinon
« Ré-encoder » coché), ou pourquoi ça ne marche pas (401 = mauvais identifiant).

## 2. Créer l'application : copie le modèle, puis adapte
```bash
M="$HOME/.naim/plugins/reseau/skills/camera-ip/modele"
mkdir -p <dossier> && cp "$M/server.py" "$M/index.html" "$M/README.md" <dossier>/
```
Le modèle a déjà : connexion (adresse, port, identifiant, mot de passe, chemin, TCP/UDP, ré-encodage), direct, photo,
enregistrement MP4, plein écran, rotation, miroir, luminosité, contraste, zoom, détection de mouvement avec photo
automatique, galerie (voir, télécharger, supprimer), espace disque, journal. Ne le réécris pas : ajoute seulement
ce que l'utilisateur demande en plus (edit_file), sans casser l'existant. Pré-remplis l'adresse trouvée et le chemin
dans les `placeholder` de index.html si tu veux, jamais le mot de passe.

Ce qui fait que ça marche, à garder si tu modifies :
- une seule commande ffmpeg à la fois (`start_locked` arrête l'ancienne avant) ; l'enregistrement relance ffmpeg
  avec une 2e sortie MP4 ;
- la sortie d'erreur de ffmpeg va dans `ffmpeg.log` (dans un tube jamais lu, ffmpeg se fige au bout d'un moment) ;
- SIGINT pour arrêter ffmpeg : le MP4 est fermé proprement ;
- HLS lu nativement par Safari et l'Aperçu de Naim ; hls.js seulement pour les autres navigateurs.

## 3. Lancer et vérifier
```bash
start_process command="python3 server.py" keep=true      # dans <dossier> ; PORT=… pour un autre port
```
Puis `curl -s localhost:8099/api/status`, ouvre http://localhost:8099 dans l'Aperçu, et vérifie le direct
(`curl -s localhost:8099/hls/live.m3u8` liste des .ts après quelques secondes). Sans la caméra sous la main, essaie
avec une vidéo : `ffmpeg -f lavfi -i testsrc=size=640x360:rate=25 -t 20 -c:v libx264 -g 25 -pix_fmt yuv420p test.mp4`
puis `curl -X POST localhost:8099/api/start -d '{"url": "<chemin>/test.mp4"}'`.

## Pour finir
Dis à l'utilisateur l'adresse de l'application, comment se connecter (champs à remplir), où vont les vidéos et les
photos (`medias/`), et comment relancer (`python3 server.py`).
