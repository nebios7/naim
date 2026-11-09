---
name: reseau-local
description: Voir les appareils du réseau local de l'utilisateur avec leur adresse IP, leur nom, leur modèle et leurs services ; trouver un appareil précis (même s'il ne répond pas au ping) ; vérifier qu'un projet trouvé en ligne marche sur cet appareil avant de l'installer. Lecture seule.
---

# Le réseau local

Le script de ce skill regarde le réseau de l'utilisateur, SANS rien changer : un ping et un essai de connexion sur
quelques ports connus, rien d'autre, et seulement sur le réseau local (adresses privées).

```bash
S="$HOME/.naim/plugins/reseau/skills/reseau-local"
python3 "$S/scan.py"                    # tout le réseau : adresse, nom, type, ports ouverts (~10 à 30 s)
python3 "$S/scan.py" 192.168.1.20      # un appareil, ses ports en détail
```

python3 "$S/scan.py" --annonces          # ce que les appareils annoncent eux-mêmes : nom, modèle, services (~8 s)

## Trouver un appareil précis : la méthode
1. **Ne conclus jamais « il n'est pas sur le réseau » d'après le ping seul** : beaucoup d'appareils ne répondent pas au
   ping. Lance `scan.py --annonces` : il demande au réseau tout ce qui s'annonce (Bonjour / mDNS) et donne le nom, le
   modèle et les services de chaque appareil. N'installe pas d'outil pour ça, n'écris pas de boucle de ping à la main.
2. **Reconnais l'appareil d'après ce qu'il annonce** (son nom, son modèle) ; un modèle inconnu : cherche-le sur le web
   pour savoir ce que c'est et quel système il fait tourner.
3. Plusieurs appareils possibles : montre le tableau et demande lequel (ask_user).

## Installer un projet trouvé en ligne sur un appareil
1. **D'abord l'appareil** : trouve-le (ci-dessus) et ce qu'il est (marque, modèle, système).
2. **Puis seulement la partie compatibilité du README** (« Supported », « Requirements », « Compatible », la liste des
   appareils) — pas tout le dépôt. Compare avec ce que tu as trouvé.
3. **Pas compatible** : dis-le tout de suite et simplement, avec la phrase du README, et ce que le projet propose à la
   place s'il le dit. N'installe rien.
4. **Compatible** : sauvegarde d'abord ce qui peut l'être (si l'outil le permet), et demande l'accord de l'utilisateur
   avant de changer quoi que ce soit sur l'appareil.

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
