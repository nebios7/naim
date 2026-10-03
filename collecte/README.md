---
title: Naim — collecte
emoji: 🤖
colorFrom: gray
colorTo: red
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# Serveur de collecte de Naim

Reçoit les tâches que les utilisateurs de [Naim](https://github.com/nebios7/naim) ont **choisi de partager**
(Personnaliser › Apprentissage), pour entraîner la version suivante du modèle.

- Seules les tâches **notées 👍/👎** par l'utilisateur, déjà **nettoyées sur son Mac** (mots de passe, clés, emails,
  téléphones, chemins personnels retirés), avec un **identifiant anonyme** d'installation.
- Deuxième nettoyage ici, vérification du format, limites (50 tâches par jour et par installation, 300 par adresse IP),
  doublons refusés.
- Stockage dans un **dataset privé** Hugging Face. Une demande de suppression (bouton dans l'app) exclut toutes les
  tâches de l'installation de tout entraînement.

Deux versions, même comportement :

| Fichier | Hébergement |
|---|---|
| `worker.js` + `wrangler.toml` | **Cloudflare Workers** (gratuit) — version utilisée |
| `app.py` + `Dockerfile` | Space Docker Hugging Face (abonnement PRO requis) |

## Déploiement sur Cloudflare (propriétaire du projet)

```bash
cd collecte
export CLOUDFLARE_API_TOKEN=…            # modèle de token « Edit Cloudflare Workers »
npx wrangler kv namespace create LIMITS  # recopie l'id dans wrangler.toml
npx wrangler secret put HF_TOKEN         # token Hugging Face d'écriture du dataset
npx wrangler deploy
```

## Distribution du modèle (réservé à l'application Naim)

Le dépôt du modèle sur Hugging Face est **privé**. Ce Worker le distribue aux installations de Naim :
`GET /api/model/<fichier>?install=<identifiant>` (en-tête `User-Agent: Naim…`) répond par un lien de téléchargement
signé et temporaire. Limites : 20 téléchargements par installation et par jour, 40 par adresse IP.

Secrets supplémentaires :

```bash
npx wrangler secret put HF_MODEL_TOKEN   # token Hugging Face en LECTURE (accès au dépôt privé du modèle)
npx wrangler secret put ADMIN_TOKEN      # mot de passe des routes /api/admin (liste, blocage d'une installation)
```

Bloquer une installation : `POST /api/admin/block {"install": "<id>"}` (ou `{"install": "<id>", "blocked": false}`
pour la débloquer), avec `Authorization: Bearer <ADMIN_TOKEN>`.
