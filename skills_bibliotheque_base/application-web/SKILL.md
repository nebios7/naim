---
name: application-web
description: Créer une application web qui marche (Flask par défaut), la lancer et vérifier chaque page.
---

# Application web

Objectif : une première version qui MARCHE, vérifiée page par page, puis proposer des améliorations.

## Plan type (Flask + SQLite)
1. `requirements.txt` : `flask` (+ ce qui est vraiment nécessaire).
2. `db.py` : connexion `sqlite3` avec `row_factory = sqlite3.Row`, création des tables `CREATE TABLE IF NOT EXISTS`
   au démarrage, fonctions simples (lister, créer, lire, modifier, supprimer).
3. `app.py` : routes ; formulaires en POST puis `redirect(url_for(...))` (évite le double envoi) ;
   `abort(404)` si l'élément n'existe pas ; `app.run(host="127.0.0.1", port=5050, debug=False)`.
4. `templates/base.html` (mise en page, Tailwind et la police : voir Design) et une page par écran (`{% extends "base.html" %}`).
5. venv : `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
6. Lancer : start_process `.venv/bin/python app.py` (keep=true).
7. Vérifier CHAQUE route avec curl :
   - `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5050/` → 200 ;
   - formulaire : `curl -s -X POST -d "nom=Test" -o /dev/null -w "%{http_code}" http://127.0.0.1:5050/clients/nouveau` → 302 ;
   - puis la liste doit contenir « Test ».
8. En cas d'erreur 500 : process_output → lire la trace → corriger → redémarrer (stop_process + start_process).
9. Tester comme un utilisateur avec l'outil browser :
   - `browser action=open url=http://127.0.0.1:5050/` → la liste numérotée des boutons et champs ;
   - remplir le formulaire principal (`type target=<numéro> text=… submit=true`) et vérifier que le résultat apparaît
     dans le texte de la page ; cliquer les boutons importants (`click target=<numéro>`) ;
   - `browser action=console` : zéro erreur JavaScript ni requête en échec (sinon corriger) ;
   - `browser action=screenshot` pour vérifier la mise en page.

## Design : une page qu'on a envie d'utiliser (pas « un peu de CSS »)
- Suis aussi le skill `frontend-design` (use_skill) : une direction visuelle claire, pas un gabarit fade.
- Bibliothèques par le web, dans `<head>` de base.html — jamais `pip` ni `npm` pour du CSS dans une page simple :
  - Tailwind : `<script src="https://cdn.tailwindcss.com"></script>` (classes directement dans le HTML) ;
  - police : `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">` ;
  - icônes au trait : `<script src="https://unpkg.com/lucide@latest"></script>` puis `lucide.createIcons()` (pas d'emoji).
- Mise en page : en-tête (nom + navigation), accroche (grand titre, sous-titre, bouton), grille de cartes
  (`grid sm:grid-cols-2 lg:grid-cols-3 gap-6`, coins arrondis, ombre douce, effet au survol), pied de page ;
  largeur max ~1100 px centrée, beaucoup d'espace, une couleur principale + des gris, contraste lisible, adapté au mobile.
- Le vrai contenu : chaque carte montre les vraies données (titre, description, niveau, un extrait de code dans un
  bloc `<pre>`), un état vide soigné s'il n'y a rien.
- Regarde le RENDU avant de dire « fait » : `browser action=screenshot`, puis juge la capture comme un utilisateur
  exigeant (vide, fade, mal aligné, texte illisible ?) et améliore au moins une fois.
- Un seul serveur par projet : pour relancer, start_process à nouveau (l'ancien est arrêté tout seul).
- Les chemins sont relatifs au projet : `templates/index.html`, jamais `nom-du-projet/templates/index.html`.

## Règles
- Chaque fichier < 150 lignes ; plusieurs petits fichiers plutôt qu'un gros.
- Port 5050 (5000 est pris par AirPlay sur macOS).
- `debug=False` avec start_process (le rechargeur de Flask lance un 2e processus).
- Montants : `Decimal` ou centimes en entier, jamais de float pour de l'argent.
- PDF : skill `pdf` ; export CSV : module `csv` avec `newline=""` et `encoding="utf-8"`.

## Résumé final
URL, pages disponibles, résultat des vérifications (curl, navigateur et capture du rendu), comment relancer,
2-3 améliorations possibles.
