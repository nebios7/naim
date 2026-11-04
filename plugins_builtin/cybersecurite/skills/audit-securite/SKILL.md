---
name: audit-securite
description: Audit de sécurité d'un projet de code (Python, JavaScript, PHP, HTML, configuration) — failles d'injection SQL ou de commande, XSS, secrets et mots de passe dans le code, HTTPS désactivé, mode debug, mauvais hachage des mots de passe, dépendances vulnérables — avec un rapport classé par gravité et la correction de chaque faille. Lecture seule tant que l'utilisateur n'a pas dit de corriger.
---

# Audit de sécurité d'un projet

Tu relis un projet comme un auditeur : tu trouves les failles, tu prouves qu'elles sont réelles en lisant le code,
tu les classes, tu dis comment les corriger. Seulement sur un projet de l'utilisateur (ou qu'il a le droit d'auditer).

```bash
A="$HOME/.naim/plugins/cybersecurite/skills/audit-securite"
python3 "$A/audit.py" <dossier>                          # le rapport, le plus grave d'abord
python3 "$A/audit.py" <dossier> --deps                   # + les dépendances vulnérables (pip-audit / npm audit)
python3 "$A/audit.py" <dossier> --json audit.json        # les constats en JSON (pour le rapport PDF)
```

## Méthode

1. **Le projet d'abord** : list_files, le README, le point d'entrée (app.py, server.js, index.php…). Note ce qui
   reçoit des données de l'extérieur : routes web, formulaires, API, fichiers envoyés, arguments.
2. **Le script** : `audit.py <dossier> --deps`. Il ne change rien. Chaque constat est une **piste**, pas une preuve.
3. **Vérifie chaque constat haut ou critique** avec read_file autour de la ligne : la donnée vient-elle vraiment de
   l'utilisateur ? Est-elle déjà filtrée ou échappée ? Garde les vrais, écarte les faux en disant pourquoi
   (« commande fixe, aucune donnée extérieure »). Ne recopie jamais la liste brute du script comme rapport.
4. **Ce que le script ne voit pas** — lis le code toi-même :
   - **contrôle d'accès** : une page d'administration ou une route qui modifie/efface sans vérifier qui demande ;
     un identifiant dans l'adresse qui donne les données d'un autre (`/facture?id=42` → 43) ;
   - **authentification** : mots de passe stockés en clair, pas de limite d'essais, session sans expiration,
     cookie sans `HttpOnly`, `Secure`, `SameSite` ;
   - **CSRF** : un formulaire qui modifie quelque chose sans jeton ;
   - **envoi de fichiers** : type et taille non vérifiés, fichier enregistré sous son nom d'origine, servi tel quel ;
   - **erreurs** : traces techniques montrées à l'utilisateur ;
   - **secrets dans l'historique git** : `git log -p -S "password" --all | head` si c'est un dépôt.
5. **Le rapport** (en français, clair pour quelqu'un qui n'est pas expert) :
   - **En bref** : le nombre de failles par gravité et les 3 à corriger en premier ;
   - pour chaque faille : gravité, `fichier:ligne`, ce qu'un attaquant pourrait faire (une phrase concrète),
     la correction **avec le code corrigé** ;
   - ce qui est bien fait (ça compte aussi) ;
   - les limites : ce qui n'a pas été vérifié (dépendances sans outil, code non lu).
   Demandé en PDF : skill pdf-pro (un chapitre par gravité, un tableau récapitulatif fichier · faille · gravité ·
   correction avec des `tag danger/warn/info`).
6. **Corriger** : seulement si l'utilisateur le demande. Du plus grave au moins grave, une faille à la fois, puis
   relance `audit.py` et les tests du projet pour montrer que la faille a disparu sans rien casser.

## Gravité

- **critique** : exploitable tout de suite par n'importe qui (clé ou mot de passe publié, injection sur une page publique).
- **haute** : prise de contrôle ou fuite de données possible (injection, désérialisation, HTTPS désactivé, mots de passe mal hachés).
- **moyenne** : demande une condition (XSS, CORS ouvert, debug, aléatoire faible).
- **faible** : bonne pratique manquante (http://, écoute sur toutes les interfaces).

## Les corrections type

| Faille | Correction |
|---|---|
| Injection SQL | requête paramétrée : `cur.execute("SELECT … WHERE id = ?", (uid,))`, PDO `prepare` + `execute([$id])` |
| Commande système | `subprocess.run(["ping", "-c", "1", host])` sans `shell=True` ; valider l'entrée (liste blanche) |
| XSS | `el.textContent = texte` ; échapper dans les templates ; en-tête `Content-Security-Policy` |
| Secret dans le code | `os.environ["API_KEY"]` + `.env` dans `.gitignore` ; révoquer l'ancien secret |
| Mot de passe | `bcrypt.hashpw(mdp, bcrypt.gensalt())` / `password_hash()` ; jamais md5/sha1 |
| Jeton | `secrets.token_urlsafe(32)` / `crypto.randomUUID()` |
| Debug | `DEBUG = os.environ.get("DEBUG") == "1"` |
| HTTPS | ne jamais mettre `verify=False` ; donner le certificat de l'autorité interne |

## Règles

- Tu **ne lances aucune attaque** : pas d'exploitation contre un site en ligne, pas de scan d'un serveur qui n'est
  pas à l'utilisateur. Pour montrer qu'une faille est réelle, explique le scénario ou écris un test local.
- Ne montre jamais un secret trouvé en entier dans ta réponse : `sk_live_4f…` (les 4 premiers caractères suffisent).
- Ne dis pas « aucune faille » : dis « aucune faille trouvée par ces vérifications », avec ce qui a été vérifié.
