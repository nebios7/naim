---
name: api-rest
description: Créer une API REST (Flask ou Node/Express) avec validation, erreurs JSON et tests curl.
---

# API REST

## Conception
- Ressources au pluriel : `GET /items`, `GET /items/<id>`, `POST /items`, `PUT/PATCH /items/<id>`, `DELETE /items/<id>`.
- Codes : 200 lecture, 201 création (+ l'objet créé), 204 suppression, 400 données invalides, 401/403 accès,
  404 introuvable, 409 conflit. Erreurs toujours en JSON : `{"error": "message clair"}`.
- Valider CHAQUE champ reçu (type, obligatoire, longueur) ; ne jamais faire confiance au client.
- Authentification simple : en-tête `Authorization: Bearer <clé>` comparé à une clé dans `.env`.

## Python (Flask)
- `request.get_json(silent=True) or {}` ; `jsonify(...)`, `return jsonify(obj), 201`.
- Gestionnaire d'erreurs 404/500 qui renvoie du JSON.

## Node (Express / TypeScript)
- `express.json()` ; routes dans `src/routes/*.ts` ; validation avec `zod` si déjà présent.
- Démarrage : `npm run dev` avec start_process ; typecheck `npx tsc --noEmit`.

## Vérification (obligatoire)
- Pour chaque route, un curl réel, par exemple :
  `curl -s -X POST http://127.0.0.1:PORT/items -H "Content-Type: application/json" -d '{"nom":"A"}'`
- Tester aussi un cas d'erreur (champ manquant → 400, id inconnu → 404).
- Écrire `tests/` (pytest ou vitest/jest) et les lancer.

## Documentation
- README : une ligne par route + un exemple curl testé.
