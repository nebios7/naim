# Mac : les applications (détail de la skill mac)

Nom exact d'une application : `ls /Applications | grep -i nom` (par exemple « Pages Creator Studio », pas « Pages »).
Ouvrir : `open -a "Nom"` · quitter : `osascript -e 'quit app "Nom"'`. Une application qui refuse (-1743) : il faut
l'autoriser dans Réglages Système › Confidentialité et sécurité › Automatisation › Naim (l'utilisateur le fait).
Si une application n'a pas de commande : skill controle-ecran (regarder l'écran, cliquer, taper).

## Messages, appels (voir SKILL.md : chercher_contact d'abord, numéro international)
- SMS / iMessage : `osascript -e 'tell application "Messages" to send "TEXTE" to participant "+33612345678"'`
- Appel : `open "tel:+33612345678"` · FaceTime : `open "facetime://+33612345678"` · audio : `open "facetime-audio://+33612345678"`
- WhatsApp (si installé) : `open "whatsapp://send?phone=33612345678&text=Bonjour%20Paul"` (numéro sans « + »,
  texte encodé pour une adresse web) : le message s'ouvre rempli, l'utilisateur appuie sur Entrée (ou controle-ecran).
- Lire les anciens SMS : impossible sans l'accès complet au disque ; dis-le, ne l'invente pas.

## Safari / Chrome
- Ouvrir un site : `open -a Safari "https://…"` · une recherche : `open "https://www.google.com/search?q=mots+cherchés"`
- Page affichée : `osascript -e 'tell application "Safari" to get {name, URL} of current tab of front window'`
- Onglets ouverts : `osascript -e 'tell application "Safari" to get {name, URL} of every tab of front window'`
- Texte de la page : `osascript -e 'tell application "Safari" to do JavaScript "document.body.innerText" in current tab of front window'`
  (demande « Autoriser JavaScript depuis les Événements Apple » dans le menu Développement de Safari ; sinon web_fetch sur l'URL)
- Chrome : `osascript -e 'tell application "Google Chrome" to get {title, URL} of active tab of front window'`

## Mail
- Envoyer : outil send_email (pas d'AppleScript) · lire la boîte : outil mail_inbox.
- Non lus : `osascript -e 'tell application "Mail" to get unread count of inbox'`
- Nouveau message prêt (l'utilisateur relit) :
  `osascript -e 'tell application "Mail" to make new outgoing message with properties {subject:"Objet", content:"Texte", visible:true}'`

## Finder
- Ouvrir un dossier : `open ~/Documents` · montrer un fichier : `open -R "chemin"`
- Sélection dans le Finder : `osascript -e 'tell application "Finder" to get POSIX path of (selection as alias list)'`
- Dossier de la fenêtre : `osascript -e 'tell application "Finder" to get POSIX path of (target of front window as alias)'`
- Corbeille : voir systeme.md (confirmation, jamais vider).

## Musique, vidéo
- Musique : `osascript -e 'tell application "Music" to play'` · `pause` · `next track` · `previous track` · `play playlist "Nom"`
- Morceau en cours : `osascript -e 'tell application "Music" to get {name, artist} of current track'`
- Chercher et jouer : `osascript -e 'tell application "Music" to play (first track of library playlist 1 whose name contains "titre")'`
- Spotify (si installé) : `osascript -e 'tell application "Spotify" to playpause'` · `next track` · `play track "spotify:track:…"`
- Vidéo : `open -a VLC "fichier"` · QuickTime : `open -a "QuickTime Player" "fichier"`

## Plans
- Itinéraire en voiture : `open "maps://?daddr=10+rue+de+Paris,+Lyon&dirflg=d"` (`w` à pied, `r` transports)
- Chercher autour : `open "maps://?q=boulangerie"`

## Contacts, Calendrier, Rappels, Notes (voir aussi SKILL.md)
- Créer un contact :
  `osascript -e 'tell application "Contacts"' -e 'set p to make new person with properties {first name:"Jean", last name:"Dupont"}' -e 'make new phone at end of phones of p with properties {label:"mobile", value:"+33612345678"}' -e 'save' -e 'end tell'`
- Changer le numéro d'un contact (on change la VALEUR du téléphone, jamais `phone 1` lui-même ; nom exact, pris de
  chercher_contact ; ne garde que les chiffres de l'ancien numéro, sans le +33, pour le retrouver) :
  `osascript -e 'tell application "Contacts"' -e 'set p to first person whose name is "Jean Dupont"' -e 'set value of (first phone of p whose value contains "612345678") to "+33698765432"' -e 'save' -e 'end tell'`
  Ajouter un numéro : `make new phone at end of phones of p with properties {label:"mobile", value:"+33…"}` puis `save`.
  Un `person id` s'écrit entre guillemets : `person id "649EB6BB-…"`. Vérifie ensuite avec chercher_contact.
- Rappels à faire : `osascript -e 'tell application "Reminders" to get name of reminders of list "Rappels" whose completed is false'`
- Dernières notes : `osascript -e 'tell application "Notes" to get name of notes 1 thru 10'`

## Photos
- Albums : `osascript -e 'tell application "Photos" to get name of every album'`
- Importer : `osascript -e 'tell application "Photos" to import {POSIX file "/chemin/photo.jpg"}'`

## Bureautique
- Pages / Numbers / Keynote en PDF (nom exact de l'application) :
  `osascript -e 'tell application "Pages Creator Studio" to export front document to POSIX file "/chemin/sortie.pdf" as PDF'`
- Word / Excel / PowerPoint : `open -a "Microsoft Word" "fichier.docx"` (créer un document : skills docx, excel, pptx)
- Aperçu : `open -a Preview "fichier.pdf"` · TextEdit : `open -a TextEdit "fichier.txt"`

## Développement
- VS Code : `code "dossier"` (ou `open -a "Visual Studio Code" "dossier"`) · Xcode : `open -a Xcode "Projet.xcodeproj"`
- Terminal avec une commande : `osascript -e 'tell application "Terminal" to do script "cd ~/Documents && ls"'`

## Visio
- Zoom / Teams / Meet : `open "lien de la réunion"` (l'application s'ouvre seule si elle est installée).

## App Store
- `open "macappstore://"` · installer une application : l'utilisateur le fait (achat ou identifiant Apple).
