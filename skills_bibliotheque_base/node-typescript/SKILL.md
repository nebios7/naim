---
name: node-typescript
description: Travailler sur un projet Node.js / TypeScript (Express, scripts npm, tests, typecheck).
---

# Node.js / TypeScript

1. Lire `package.json` : scripts (`dev`, `build`, `test`, `start`), type de modules (`"type": "module"` = ESM).
2. Installer : `npm install` (ou `npm ci` s'il y a un package-lock.json et qu'on veut l'exactitude).
3. Lancer en dev avec start_process (`npm run dev`), vérifier avec curl.
4. Vérifier le typage : `npx tsc --noEmit` ; les tests : `npm test`.
5. ESM + TypeScript : imports relatifs avec l'extension `.js` (`import { x } from "./x.js"`) si le projet le fait déjà.
6. Variables d'environnement : `.env` (jamais commité) ; lire avec `process.env.NOM` et une valeur par défaut sûre.
7. SQLite : `better-sqlite3` ou le module déjà utilisé ; requêtes préparées uniquement.

Pièges : oublier de redémarrer `npm run dev` si pas de rechargement auto ; `Cannot find module` → install ou chemin ;
port déjà pris → `lsof -ti :PORT`.
