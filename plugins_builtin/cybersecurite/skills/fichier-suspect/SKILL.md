---
name: fichier-suspect
description: Dire si un fichier reçu (pièce jointe, téléchargement, document Word/Excel/PDF, archive, script, application) ou un lien (SMS, mail, message « votre colis », « remboursement des impôts ») est dangereux, SANS l'ouvrir ni le visiter — type réel, macros, JavaScript dans un PDF, signature Apple, faux domaine qui imite un vrai, et quoi faire.
---

# Fichier ou lien suspect

```bash
F="$HOME/.naim/plugins/cybersecurite/skills/fichier-suspect"
python3 "$F/analyser.py" fichier "<chemin du fichier>"
python3 "$F/analyser.py" lien "<adresse copiée du message>"
```

Le fichier est lu comme des octets : **jamais ouvert par son application, jamais exécuté**. Le lien est seulement
lu : **jamais visité** (ne fais pas web_fetch ni naim_browser dessus — un lien piégé peut suivre qui l'ouvre).

## Méthode

1. Un fichier : trouve-le (find_files s'il n'a pas de chemin), puis `analyser.py fichier`. Un lien : copie-le
   exactement tel qu'il est dans le message, puis `analyser.py lien`.
2. Réponds par **le verdict d'abord**, en gros et simple : « Dangereux, ne l'ouvre pas », « Suspect », ou « Aucun
   signe de danger trouvé ». Puis les raisons, chacune en une phrase claire (« le lien se dit des impôts mais mène
   à impots-gouv-remboursement.xyz ; le vrai site est impots.gouv.fr »).
3. **Le message autour compte aussi** (s'il est donné) : urgence (« sous 24 h »), menace (« compte bloqué »),
   somme à payer ou à recevoir, fautes, expéditeur dont l'adresse ne correspond pas au nom → dis-le.
4. **Quoi faire** :
   - ne pas ouvrir / ne pas cliquer ; supprimer le message ;
   - en cas de doute : aller sur le site officiel en tapant son adresse soi-même, ou appeler l'organisme ;
   - signaler : SMS frauduleux au **33700**, site d'arnaque sur **internet-signalement.gouv.fr**, mail
     d'hameçonnage sur **signal-spam.fr** ; aide : **cybermalveillance.gouv.fr** ;
   - déjà cliqué ou ouvert : changer le mot de passe du compte concerné (depuis le vrai site), activer la double
     authentification, prévenir la banque si une carte a été donnée (opposition) ; un programme lancé : couper
     Internet, lancer `bilan.py` (skill securite-mac) et demander de l'aide.
5. Le verdict « aucun signe » n'est pas une garantie : dis-le simplement, sans faire peur.

## Ne pas faire

- Ne jamais ouvrir, lancer, décompresser dans le dossier de l'utilisateur, ni visiter le lien « pour voir ».
- Ne jamais envoyer le fichier sur un site d'analyse en ligne sans l'accord de l'utilisateur (il peut contenir des
  données personnelles) : l'empreinte SHA-256 suffit pour chercher sur virustotal.com.
