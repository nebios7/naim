---
name: reseau-local
description: Voir les appareils du réseau local de l'utilisateur (box, ordinateurs, téléphones, imprimantes, caméras, Raspberry) avec leur adresse, leur nom et leurs services ouverts ; trouver une caméra ou un appareil précis. Lecture seule.
---

# Le réseau local

Le script de ce skill regarde le réseau de l'utilisateur, SANS rien changer : un ping et un essai de connexion sur
quelques ports connus, rien d'autre, et seulement sur le réseau local (adresses privées).

```bash
S="$HOME/.naim/plugins/reseau/skills/reseau-local"
python3 "$S/scan.py"                    # tout le réseau : adresse, nom, type, ports ouverts (~10 à 30 s)
python3 "$S/scan.py" 192.168.1.20      # un appareil, ses ports en détail
```

## Lire le résultat
- **box / routeur** : la passerelle (souvent .1 ou .254) ; sa page web est son interface d'administration.
- **CAMÉRA probable** : port 554 ou 8554 (RTSP, le flux vidéo), 8899 (ONVIF) ou 37777 / 34567 (caméras Dahua, DVR).
  Ensuite : le skill **camera-ip** (sonde.py trouve le chemin du flux).
- **imprimante** : 631 ou 9100. **ordinateur / NAS** : 445. **Raspberry / Linux** : 22 (SSH).
- Le **nom** vient de la box (par exemple « ipcam-… », « raspberrypi », « iPhone-de-… ») : il dit souvent ce qu'est l'appareil.
- Un appareil connu de la box mais sans port ouvert : éteint, en veille, ou qui ne répond pas. Dis-le simplement.

## Une application pour une caméra trouvée
N'écris pas l'application toi-même (pas d'OpenCV, pas de Flask) : le skill **camera-ip** a un modèle vérifié. Copie-le,
puis lance-le :
```bash
M="$HOME/.naim/plugins/reseau/skills/camera-ip/modele"; cp "$M/server.py" "$M/index.html" "$M/README.md" .
```
puis écris `camera.json` avec l'adresse trouvée (`{"ip": "…", "port": 554}`, jamais de mot de passe ; ne lis pas
index.html ni server.py, c'est long et inutile), puis `start_process command="python3 server.py" keep=true`, et la page
à l'adresse que le serveur écrit (http://localhost:8099, ou le port libre suivant).

## Les règles
- Seulement le réseau de l'utilisateur. Jamais d'adresse publique, jamais le réseau de quelqu'un d'autre.
- Lecture seule : ne te connecte pas à l'interface d'un appareil, ne change aucun réglage de la box, ne tente aucun
  mot de passe. Pour aller plus loin (entrer dans la caméra, la box), demande d'abord à l'utilisateur (ask_user).
- Donne le résultat dans un tableau clair : adresse, nom, ce que c'est, ce qu'on peut en faire.
