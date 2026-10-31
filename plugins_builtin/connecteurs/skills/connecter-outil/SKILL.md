---
name: connecter-outil
description: Brancher un outil (Stripe, Supabase, Vercel, GitHub, AWS, Firebase…) à Naim avec son CLI officiel - le trouver, l'installer, le vérifier, laisser l'utilisateur se connecter à son compte, puis écrire un skill global pour s'en servir ensuite tout seul.
---

# Brancher un outil à Naim : son CLI officiel, puis un skill global

But : après ce travail, il suffit de dire « crée un produit Stripe » ou « déploie sur Vercel » et Naim sait le faire,
dans n'importe quelle conversation, parce que le CLI est installé et qu'un skill global explique comment s'en servir.

## 1. Trouver le CLI OFFICIEL (jamais un paquet qui lui ressemble)

- Cherche sur le web « <outil> CLI install », puis lis la page d'installation **sur le site de l'éditeur**
  (stripe.com, supabase.com, vercel.com, cli.github.com, aws.amazon.com…). Seule cette page fait foi.
- Un paquet npm, pip ou brew au nom proche publié par quelqu'un d'autre est un piège (faux paquet) : refuse-le.
- Déjà installé ? `command -v <commande>` puis `<commande> --version` : si oui, passe à l'étape 3.
- Repères (vérifie toujours la page officielle, une commande peut avoir changé) :

| Outil | Commande | Installation officielle sur Mac |
|---|---|---|
| GitHub | `gh` | `brew install gh` |
| Stripe | `stripe` | `brew install stripe/stripe-cli/stripe` |
| Supabase | `supabase` | `brew install supabase/tap/supabase` |
| Vercel | `vercel` | `npm i -g vercel` |
| Netlify | `netlify` | `npm i -g netlify-cli` |
| Firebase | `firebase` | `npm i -g firebase-tools` |
| Cloudflare | `wrangler` | `npm i -g wrangler` |
| AWS | `aws` | `brew install awscli` |
| Google Cloud | `gcloud` | `brew install --cask google-cloud-sdk` |
| Azure | `az` | `brew install azure-cli` |
| Fly.io | `fly` | `brew install flyctl` |
| DigitalOcean | `doctl` | `brew install doctl` |

## 2. Installer

- De préférence avec `brew` (sinon `npm i -g` ou `pipx`, comme le dit la page officielle). Dis en une ligne ce que
  tu installes et d'où, puis lance la commande (run_command, timeout 600 : une installation peut être longue).
- `brew` absent : dis-le à l'utilisateur et donne la commande d'installation de Homebrew. Tu ne la lances pas toi-même.
- Échec : lis l'erreur, corrige la cause (paquet renommé, tap manquant), une seule nouvelle tentative, sinon explique.

## 3. Vérifier que ça marche

- `<commande> --version` doit répondre. Note le chemin (`command -v <commande>`) et la version.
- `<commande> --help` : la liste réelle des sous-commandes, c'est ta source pour le skill (étape 5).

## 4. La connexion au compte : c'est l'utilisateur qui la fait

- Tu ne tapes **jamais** un mot de passe, un token ou une clé API, et tu n'en demandes pas dans la conversation.
- Donne-lui la commande de connexion officielle (`gh auth login`, `stripe login`, `supabase login`, `vercel login`,
  `aws configure sso`, `gcloud auth login`, `firebase login`…) à lancer dans le Terminal : elle ouvre son navigateur.
- Attends qu'il dise que c'est fait, puis vérifie avec la commande d'état (`gh auth status`, `stripe config --list`,
  `supabase projects list`, `vercel whoami`, `aws sts get-caller-identity`…).
- S'il ne veut pas se connecter maintenant, continue quand même : le skill dira comment se connecter.

## 5. Écrire le skill global

Avec `create_skill` (scope « utilisateur » : il sert dans toutes les conversations et tous les dossiers).
Nom = le nom de l'outil en minuscules (`stripe`, `supabase`) : quand l'utilisateur nomme l'outil, ce skill se charge
tout seul. Description = une phrase avec les mots qu'il dira (« paiements, produits, abonnements Stripe »).

Contenu, court et vrai :
1. **Ce que l'outil permet** en 2 lignes, et le lien de la doc officielle du CLI.
2. **Vérifier avant d'agir** : la commande de version et la commande d'état de connexion ; si pas connecté, la
   commande de connexion à donner à l'utilisateur (jamais de token tapé par Naim).
3. **Les 6 à 12 commandes les plus utiles**, recopiées depuis `--help` et la doc officielle (aucune option inventée),
   chacune avec un exemple complet. Les sorties en JSON quand l'outil le permet (`--json`, `-o json`, `--format json`).
4. **Prudence** : les commandes qui coûtent de l'argent, suppriment ou touchent la production (`delete`, `deploy --prod`,
   paiements en mode réel) se font seulement après accord explicite de l'utilisateur ; préférer le mode test ou
   sandbox quand il existe (Stripe : clés `sk_test`, `--livemode` jamais par défaut).
5. **Pièges** rencontrés pendant l'installation ou la vérification (s'il y en a eu).

## 6. Prouver que c'est branché

- Lance une commande en lecture seule qui montre que tout marche (lister ses projets, `whoami`, la liste des produits
  en mode test) et montre le résultat en une ou deux lignes.
- Résumé final : outil, version, chemin, connecté ou non, nom du skill créé, et une phrase d'exemple que l'utilisateur
  peut dire maintenant (« Liste mes projets Supabase », « Déploie ce dossier sur Vercel en prévisualisation »).
