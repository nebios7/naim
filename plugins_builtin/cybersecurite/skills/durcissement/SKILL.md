---
name: durcissement
description: Durcir (sécuriser) un site web, une API ou un serveur de l'utilisateur — HTTPS et certificat, en-têtes de sécurité (HSTS, CSP…), cookies, serveur SSH, nginx, mots de passe, droits d'accès, sauvegardes — en vérifiant d'abord ce qui manque, puis en donnant (ou en appliquant si demandé) la configuration exacte.
---

# Durcissement d'un site, d'une API ou d'un serveur

```bash
D="$HOME/.naim/plugins/cybersecurite/skills/durcissement"
python3 "$D/verifier.py" site https://son-site.fr        # HTTPS, certificat, en-têtes, cookies (une simple visite)
python3 "$D/verifier.py" site http://localhost:5000      # son application en développement
python3 "$D/verifier.py" ssh /etc/ssh/sshd_config        # sur le serveur (ou une copie du fichier)
python3 "$D/verifier.py" nginx /etc/nginx/nginx.conf     # une configuration nginx
```

## Méthode

1. **Vérifie d'abord** avec `verifier.py` (et `audit-securite` si c'est son code) : on durcit ce qui manque
   vraiment, pas une liste générique.
2. **Explique** chaque point en une phrase concrète, puis donne **la configuration exacte** à l'endroit exact
   (le fichier, la ligne, le bloc), dans la technologie du projet :
   - **Flask** : `@app.after_request` qui ajoute les en-têtes ; `SESSION_COOKIE_SECURE=True`,
     `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"` ; Flask-Talisman.
   - **Express** : `helmet()` ; `app.disable("x-powered-by")` ; cookies `{ secure: true, httpOnly: true, sameSite: "lax" }` ;
     `express-rate-limit` sur la connexion.
   - **Django** : `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
     `DEBUG=False`, `ALLOWED_HOSTS` ; `python manage.py check --deploy`.
   - **PHP** : `session.cookie_secure=1`, `session.cookie_httponly=1`, `expose_php=Off`, `display_errors=Off`.
   - **nginx** : bloc `server` 443 avec `ssl_protocols TLSv1.2 TLSv1.3;`, `add_header … always;`, `server_tokens off;`,
     redirection 80 → 443.
3. **Applique** si l'utilisateur le demande, dans ses fichiers : une modification à la fois, puis relance
   `verifier.py` (ou ses tests) pour montrer le résultat. Pour SSH : vérifier d'abord que la connexion par clé
   marche (sinon il se ferme la porte), puis `sudo systemctl restart ssh`.

## Liste de durcissement d'un serveur Linux

- Mises à jour automatiques de sécurité (`unattended-upgrades` sur Debian/Ubuntu).
- Pare-feu : seulement les ports utiles (`ufw allow 22,80,443/tcp && ufw enable`).
- SSH : par clé, pas de root, `fail2ban` contre les essais répétés.
- Un utilisateur par service, sans droits d'administrateur ; fichiers de secrets en `chmod 600`.
- Base de données écoutant sur 127.0.0.1, mot de passe fort, jamais exposée sur Internet.
- Sauvegardes automatiques **testées** (une restauration essayée), une copie hors du serveur.
- Journaux conservés ; une alerte quand le disque ou le certificat arrive à la limite.

## Application web

- Mots de passe : bcrypt/argon2, longueur minimale 12, limite d'essais, double authentification si possible.
- Sessions : cookie `Secure; HttpOnly; SameSite`, expiration, nouvel identifiant après la connexion.
- Chaque route qui modifie vérifie **qui** demande (et s'il en a le droit) ; jeton CSRF sur les formulaires.
- Entrées validées côté serveur ; requêtes SQL paramétrées ; sorties échappées.
- Envois de fichiers : type et taille vérifiés, nom aléatoire, rangés hors du dossier web.
- Erreurs : message simple pour l'utilisateur, détails seulement dans les journaux.

`verifier.py site` fait une simple visite de la page (comme un navigateur) : utilise-le sur les sites de
l'utilisateur ou sur ceux qu'il gère.
