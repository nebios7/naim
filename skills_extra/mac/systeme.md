# Mac : système, réglages, fichiers (détail de la skill mac)

Toutes ces commandes passent par run_command. Après chaque action, dis le résultat réel en une phrase.

## Son et écran
- Volume : `osascript -e 'set volume output volume 60'` · lire : `osascript -e 'output volume of (get volume settings)'`
- Couper / remettre : `osascript -e 'set volume with output muted'` · `osascript -e 'set volume without output muted'`
- Sorties son : `SwitchAudioSource -a -t output` · choisir : `SwitchAudioSource -t output -s "AirPods de …"` (nom exact de la liste)
- Actuelle : `SwitchAudioSource -c` · micro : `SwitchAudioSource -a -t input` puis `-t input -s "Nom"`
- Luminosité : plus `osascript -e 'tell application "System Events" to key code 144'` · moins `key code 145` (Accessibilité)
- Mode sombre : `osascript -e 'tell application "System Events" to tell appearance preferences to set dark mode to true'` (false = clair)
- Fond d'écran : `osascript -e 'tell application "System Events" to tell every desktop to set picture to "/chemin/image.jpg"'`
- Faire parler le Mac : `say "texte"` · voix françaises : `say -v '?' | grep fr_`

## Réseau
- Wi-Fi : `networksetup -setairportpower en0 on` (ou `off`, confirmation : Internet se coupe)
- Adresse IP locale : `ipconfig getifaddr en0` · publique : `curl -s https://ifconfig.me`
- Vitesse Internet : `networkQuality -s` (environ 20 s)
- Bluetooth : état `blueutil -p` · allumer `blueutil -p 1` · éteindre `blueutil -p 0` (confirmation : clavier ou souris peuvent se couper)
- Appareils jumelés : `blueutil --paired` · connecter `blueutil --connect AA-BB-CC-DD-EE-FF` · déconnecter `--disconnect`
- Premier usage du Bluetooth : macOS demande l'accès pour Naim ; l'utilisateur doit accepter.

## Énergie et session
- Batterie : `pmset -g batt` · santé : `system_profiler SPPowerDataType | grep -E "Cycle Count|Condition|Maximum Capacity"`
- Empêcher la veille 1 h : `nohup caffeinate -d -t 3600 >/dev/null 2>&1 &` · arrêter : `pkill caffeinate`
- Écran en veille : `pmset displaysleepnow` · Mac en veille : `pmset sleepnow`
- Verrouiller (confirmation) : `osascript -e 'tell application "System Events" to keystroke "q" using {control down, command down}'`
- Redémarrer (confirmation) : `osascript -e 'tell application "System Events" to restart'`
- Éteindre (confirmation) : `osascript -e 'tell application "System Events" to shut down'`
- Ne pas déranger / Concentration : pas de commande macOS. Si l'utilisateur a un raccourci (`shortcuts list`), lance-le ;
  sinon ouvre le réglage `open "x-apple.systempreferences:com.apple.Focus-Settings.extension"` ou passe par controle-ecran.

## Ouvrir une page des Réglages Système
`open "x-apple.systempreferences:<page>"` avec :
- Son `com.apple.Sound-Settings.extension` · Écrans `com.apple.Displays-Settings.extension`
- Wi-Fi `com.apple.wifi-settings-extension` · Bluetooth `com.apple.BluetoothSettings`
- Batterie `com.apple.Battery-Settings.extension` · Notifications `com.apple.Notifications-Settings.extension`
- Accessibilité (autorisations) `com.apple.preference.security?Privacy_Accessibility`
- Automatisation `com.apple.preference.security?Privacy_Automation`
Tu ouvres la page ; c'est l'utilisateur qui change les autorisations de sécurité, jamais toi.

## Informations
- macOS : `sw_vers -productVersion` · modèle : `system_profiler SPHardwareDataType | grep -E "Model Name|Chip|Memory"`
- Disque : `df -h /` · gros dossiers : `du -sh ~/* 2>/dev/null | sort -h | tail -10`
- Mémoire : `memory_pressure -Q` · allumé depuis : `uptime`
- Ce qui charge le Mac : `ps -Ao pid,%cpu,%mem,comm -r | head -8` (processeur) · `ps -Ao pid,%mem,comm -m | head -8` (mémoire)
- Fermer une application : `osascript -e 'quit app "Nom"'` · forcer (confirmation) : `kill PID` puis, si besoin, `kill -9 PID`
- Time Machine : `tmutil latestbackup` (« Failed to mount » = disque de sauvegarde absent) · lancer : `tmutil startbackup`
- Disques externes : `diskutil list external` · éjecter : `diskutil eject "/Volumes/Nom"`

## Disques, clés USB, partitions, images disque
- Tout voir : `diskutil list` · les disques branchés : `diskutil list external physical` · un volume : `diskutil info disk4s1`
- Monter une partition : `diskutil mount disk4s1` · tout un disque : `diskutil mountDisk disk4`
- Démonter (sans éjecter) : `diskutil unmount "/Volumes/Nom"` · tout le disque : `diskutil unmountDisk disk4`
- Éjecter avant de débrancher : `diskutil eject disk4` (« busy » : une application l'utilise, `lsof +D "/Volumes/Nom" | head`)
- Image disque : `hdiutil attach "fichier.dmg"` (ou .iso) · la retirer : `hdiutil detach "/Volumes/Nom"`
- Espace d'un volume : `df -h "/Volumes/Nom"`
Démonter et éjecter : confirmation de l'utilisateur. Formater, effacer, partitionner : JAMAIS (Naim les bloque) ;
l'utilisateur le fait lui-même dans Utilitaire de disque.

## Fichiers
- Chercher partout : `mdfind -name "mot" 2>/dev/null | head -20` · par contenu : `mdfind "phrase exacte" 2>/dev/null | head -20`
- Montrer dans le Finder : `open -R "chemin"` · ouvrir un dossier : `open ~/Documents`
- Mettre à la Corbeille (confirmation) : `osascript -e 'tell application "Finder" to delete POSIX file "/chemin/complet"'`
  Jamais `rm` sur les fichiers de l'utilisateur, jamais vider la Corbeille.
- Compresser : `ditto -c -k --sequesterRsrc --keepParent "dossier" "dossier.zip"` · décompresser : `ditto -x -k "a.zip" "destination"`
- Taille : `du -sh "chemin"` · dernier téléchargement : `ls -t ~/Downloads | head -5`

## Images et PDF
- Réduire une image : `sips -Z 1600 "in.jpg" --out "out.jpg"` · convertir : `sips -s format jpeg "in.heic" --out "out.jpg"` (png, heic, tiff)
- Infos : `sips -g pixelWidth -g pixelHeight "image.png"`
- Fusionner des PDF : `"/System/Library/Automator/Combine PDF Pages.action/Contents/MacOS/join" -o "fusion.pdf" "a.pdf" "b.pdf"`
- Ouvrir dans Aperçu : `open -a Preview "fichier.pdf"`

## Presse-papiers, raccourcis, minuteur
- Lire : `pbpaste` · copier : `printf %s "texte" | pbcopy` · copier un fichier texte : `pbcopy < "fichier.txt"`
- Raccourcis (app Raccourcis) : `shortcuts list` · lancer : `shortcuts run "Nom"` · avec un fichier : `shortcuts run "Nom" -i "fichier"`
  Un raccourci fait presque tout (domotique, Concentration, réglages) : propose-le quand aucune commande n'existe.
- Minuteur 10 min :
  `nohup sh -c 'sleep 600; osascript -e "display notification \"Minuteur terminé\" with title \"Naim\" sound name \"Glass\""; say "Minuteur terminé"' >/dev/null 2>&1 &`
- Rappel à une heure précise : utilise Rappels (SKILL.md), il sonne même si Naim est fermé.

## Captures
- Écran entier : `screencapture -x ~/Desktop/capture.png` · une zone : `screencapture -x -R 0,0,800,600 ~/Desktop/zone.png`
- Puis look_at pour la regarder.
