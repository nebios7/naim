---
name: raspberry-pi
description: Travailler sur un Raspberry Pi depuis le Mac : SSH, envoyer des fichiers, GPIO en Python, programmes au démarrage.
---

# Raspberry Pi depuis le Mac

## Le trouver et s'y connecter
- Sur le réseau : `ping -c 2 raspberrypi.local` (ou le nom choisi à l'installation) ; sinon `arp -a` et l'adresse IP.
- Connexion : `ssh pi@raspberrypi.local "commande"` (une commande à la fois avec run_command, jamais une session
  interactive). Le mot de passe n'est jamais tapé par toi : demande à l'utilisateur d'installer une clé une fois
  (`ssh-copy-id pi@raspberrypi.local`, qu'il lance lui-même) ; ensuite tout passe sans mot de passe.
- Carte SD vierge : l'utilisateur la prépare avec Raspberry Pi Imager (`brew install --cask raspberry-pi-imager`),
  en activant SSH et le Wi-Fi dans ses réglages avancés.

## Envoyer, récupérer
```bash
scp programme.py pi@raspberrypi.local:~/projets/        # du Mac vers le Pi
scp pi@raspberrypi.local:~/mesures.csv .                # du Pi vers le Mac
rsync -av --exclude .venv projet/ pi@raspberrypi.local:~/projet/
```

## GPIO en Python (gpiozero, déjà sur Raspberry Pi OS)
```python
from gpiozero import LED, Button
from signal import pause
led = LED(17)            # numéro BCM (GPIO17 = broche physique 11)
bouton = Button(2)
bouton.when_pressed = led.toggle
pause()
```
Toujours les numéros BCM, dits clairement avec la broche physique. 3,3 V sur les GPIO (jamais 5 V en entrée).

## Lancer au démarrage (service)
```bash
ssh pi@raspberrypi.local 'sudo tee /etc/systemd/system/monprog.service >/dev/null <<EOF
[Unit]
Description=Mon programme
After=network-online.target
[Service]
ExecStart=/usr/bin/python3 /home/pi/projets/programme.py
Restart=on-failure
User=pi
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now monprog'
```
`sudo` sur le Pi demande la confirmation de l'utilisateur. Journal : `ssh pi@raspberrypi.local "journalctl -u monprog -n 30"`.

## État du Pi
`ssh pi@raspberrypi.local "vcgencmd measure_temp; df -h /; free -h; uptime"`.
