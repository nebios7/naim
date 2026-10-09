"""Built-in skill library for Naim (installed once into ~/.naim/skills; users can edit or delete them)."""

LIBRARY = {
    # ------------------------------------------------------------------ documents
    "pdf": ("Créer un beau PDF (CV, lettre, rapport, facture) ou convertir un document en PDF ; lire, fusionner un PDF.", """# PDF

## Lire un document existant (Word, PDF, Excel, PowerPoint)
- `read_file` donne directement son TEXTE (jamais les octets bruts). Ne pas écrire de script pour lire un .docx.

## Créer un PDF : la méthode qui marche (aucune installation)
1. Écrire une page HTML avec `write_file` (ex. `cv.html`), mise en page en CSS :
   - `@page { size: A4; margin: 0 }` puis les marges dans le HTML (`.page { padding: 16mm 15mm }`), ou `@page { size: A4; margin: 16mm }`.
   - Police : `font-family: -apple-system, Helvetica, Arial, sans-serif` ; texte 10-11pt ; titres en couleur.
   - Colonnes : `display: flex` ou `grid` (ex. colonne latérale colorée de 60mm + contenu).
   - Couleurs de fond conservées dans le PDF. Nouvelle page : `<div style="page-break-before: always">`.
   - Tout en UTF-8 (`<meta charset="utf-8">`) : accents, €, emojis OK.
2. `convert_document` source=`cv.html` output=`cv.pdf` → répond « cv.pdf créé (N pages) ».
3. Vérifier avec `look_at cv.pdf` (tu vois la page) : rien de coupé ni de superposé. Un CV tient en 1 page (2 max).
   S'il déborde : réduire les marges, la police (10pt) ou les espacements, puis reconvertir et regarder à nouveau.
4. Si l'utilisateur veut le PDF par mail : `send_email` avec `attachments: ["cv.pdf"]`.

## Convertir un document existant en PDF
- `convert_document` source=`fichier.docx` (ou .md, .rtf, .odt, .txt, .html) output=`fichier.pdf`.
- Pour AMÉLIORER le document en même temps (CV, rapport) : lire le .docx avec `read_file`, réécrire le contenu
  amélioré dans une page HTML soignée (méthode ci-dessus), puis convertir : le rendu est bien meilleur.

## Modèle de CV (à adapter, contenu RÉEL de l'utilisateur uniquement, rien d'inventé)
```html
<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>
@page { size: A4; margin: 0 }
body { margin: 0; font: 10pt/1.4 -apple-system, Helvetica, Arial, sans-serif; color: #222 }
.cv { display: flex; min-height: 297mm }
aside { width: 62mm; background: #1f3a5f; color: #fff; padding: 14mm 7mm }
aside h2 { font-size: 10pt; text-transform: uppercase; letter-spacing: .08em; border-bottom: 1px solid #ffffff55; padding-bottom: 2pt }
main { flex: 1; padding: 14mm 11mm }
h1 { font-size: 22pt; margin: 0; color: #1f3a5f } .titre { font-size: 12pt; color: #555; margin: 2pt 0 10pt }
main h2 { font-size: 12pt; color: #1f3a5f; border-bottom: 1.5pt solid #1f3a5f; padding-bottom: 2pt; margin: 12pt 0 5pt }
.poste { display: flex; justify-content: space-between; font-weight: 600 } .date { color: #666; font-weight: 400 }
ul { margin: 3pt 0 6pt 14pt; padding: 0 } li { margin: 1.5pt 0 }
</style></head><body><div class="cv">
<aside><h2>Contact</h2><p>…</p><h2>Compétences</h2><ul><li>…</li></ul><h2>Langues</h2><p>…</p></aside>
<main><h1>Prénom NOM</h1><div class="titre">Poste visé</div>
<h2>Profil</h2><p>…</p>
<h2>Expérience</h2><div class="poste"><span>Poste — Employeur</span><span class="date">2021 – 2024</span></div><ul><li>…</li></ul>
<h2>Formation</h2><div class="poste"><span>Diplôme — École</span><span class="date">2020</span></div>
</main></div></body></html>
```

## Autres opérations sur les PDF (Python, dans un venv)
- Fusionner / découper / pivoter / formulaires : `pypdf` (`.venv/bin/pip install pypdf`).
- Tableaux d'un PDF : `pdfplumber`. Graphiques dans un PDF : image PNG (matplotlib) insérée dans le HTML (`<img src="graph.png">`).
"""),
    "excel": ("Créer ou modifier des fichiers Excel (.xlsx) : tableaux, formules, mise en forme, graphiques.", """# Excel

- Bibliothèque : `openpyxl` (lecture/écriture .xlsx), `pandas` pour les calculs (`df.to_excel`).
- En-têtes en gras, largeur de colonnes ajustée, format nombre/date (`cell.number_format = "#,##0.00 €"`).
- Formules Excel en texte : `ws["C2"] = "=A2*B2"` (elles se recalculent à l'ouverture).
- Graphiques : `openpyxl.chart` (BarChart, LineChart) référencés sur les cellules.
- Figer la 1re ligne : `ws.freeze_panes = "A2"` ; filtre : `ws.auto_filter.ref = ws.dimensions`.
- Vérifier : relire le fichier avec openpyxl et afficher quelques cellules.
- Lire un .xlsx existant : `read_file`. Version PDF : tableau HTML (`<table>`) puis `convert_document`.
"""),
    "word": ("Créer des documents Word (.docx) : titres, paragraphes, tableaux, images.", """# Word

- Bibliothèque : `python-docx`.
- Structure : `doc.add_heading(text, level)`, `doc.add_paragraph`, styles `List Bullet`, `doc.add_table(rows, cols, style="Table Grid")`.
- Images : `doc.add_picture(path, width=Inches(5))`. Saut de page : `doc.add_page_break()`.
- Marges et police : `section.left_margin`, `style.font.name = "Calibri"`.
- Enregistrer puis vérifier en relisant avec python-docx (nombre de paragraphes, tableaux).
- Lire un .docx existant : `read_file` (donne son texte). Le convertir : `convert_document` (→ .pdf, .rtf, .odt, .html, .txt).
- Version PDF demandée : suivre le skill pdf (page HTML soignée puis `convert_document`), pas python-docx.
"""),
    "presentation": ("Créer une présentation PowerPoint (.pptx) claire, une idée par diapositive.", """# Présentation

- Bibliothèque : `python-pptx`.
- Plan : titre, 5 à 10 diapositives d'une idée chacune, conclusion. 3 à 5 puces courtes par diapositive.
- `prs.slide_layouts[0]` (titre), `[1]` (titre + contenu). Images : `slide.shapes.add_picture`.
- Graphiques : `slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, ...)` avec `CategoryChartData`.
- Enregistrer puis `open fichier.pptx` pour que l'utilisateur la voie.
- Version PDF : une page HTML avec une diapositive par `<section style="page-break-after: always">` (format paysage),
  puis `convert_document` avec orientation=landscape.
"""),
    # ------------------------------------------------------------------ data
    "analyse-donnees": ("Analyser un CSV/Excel avec pandas et produire des graphiques et un résumé.", """# Analyse de données

1. Charger : `pd.read_csv` / `pd.read_excel` ; afficher `df.shape`, `df.dtypes`, `df.head()`, valeurs manquantes.
2. Nettoyer : types, dates (`pd.to_datetime`), doublons, valeurs aberrantes.
3. Analyser : `groupby`, `pivot_table`, tendances, top N ; toujours chiffrer les conclusions.
4. Graphiques : `matplotlib` (enregistrer en PNG, titres et axes lisibles), un graphique par question.
   `plt.figure(figsize=(8, 4.5))`, `plt.tight_layout()`, `plt.savefig("graphiques/x.png", dpi=200)`, étiquettes en français.
   Vérifier chaque graphique avec `look_at`.
5. Livrer : script `analyse.py` + graphiques + résumé en 5 points avec les chiffres clés.
   Rapport demandé : suivre le skill rapport (page HTML avec les graphiques, puis PDF).
"""),
    "schemas": ("Dessiner un schéma en fichier PNG/SVG/PDF : architecture, flux, séquence, base de données, organigramme, Gantt, carte mentale.", """# Schémas (Mermaid → fichier)

## Méthode
1. Comprendre ce qu'il faut montrer. Si c'est un projet existant : list_files, lire les fichiers clés (points d'entrée,
   routes, modèles, config) pour décrire le VRAI système, rien d'inventé.
2. Choisir le type : architecture / flux → `flowchart LR` (ou TB) ; échanges dans le temps → `sequenceDiagram` ;
   base de données → `erDiagram` ; classes → `classDiagram` ; étapes d'un objet → `stateDiagram-v2` ;
   planning → `gantt` ; idées → `mindmap` ; chronologie → `timeline` ; répartition → `pie`.
3. `make_diagram` code=… output=`docs/architecture.png` (PNG pour un mail ou un document, SVG pour le web, PDF pour imprimer).
4. Erreur de syntaxe : lire la ligne indiquée, corriger, relancer make_diagram.
5. `look_at` sur le fichier : textes lisibles ? rien ne se chevauche ? trop large → passer de LR à TB ou regrouper.
6. Répondre avec le nom du fichier et 2-3 phrases qui expliquent le schéma.

## Règles de syntaxe qui évitent 90 % des erreurs
- Identifiants simples sans accents ni espaces (`api`, `db1`), texte affiché entre crochets : `api[API Flask]`.
- Texte avec parenthèses, deux-points, virgules, accents ou `/` : entre guillemets → `api["API (Flask) : port 5050"]`.
- Retour à la ligne dans une boîte : `<br/>`. Pas de guillemets doubles à l'intérieur d'un texte.
- Formes : `[rectangle]`, `(arrondi)`, `[(base de données)]`, `{décision}`, `((cercle))`, `[/entrée/]`.
- Flèches : `-->`, avec texte `-->|HTTP JSON|`, pointillés `-.->`, épaisse `==>`.
- Groupes : `subgraph front["Application iOS"]` … `end`. Un subgraph = une couche (client, serveur, données).
- Couleurs : `classDef db fill:#e8f1fb,stroke:#1f5fa8` puis `class db1,db2 db`.

## Modèles
```
flowchart LR
  subgraph client["Clients"]
    web["Site web"]
    ios["App iOS"]
  end
  subgraph serveur["Serveur"]
    api["API Flask<br/>port 5050"]
    auth["Authentification"]
  end
  db[("PostgreSQL")]
  web -->|HTTPS| api
  ios -->|HTTPS JSON| api
  api --> auth
  api --> db
```
```
sequenceDiagram
  participant U as Utilisateur
  participant A as App
  participant S as API
  U->>A: Se connecte
  A->>S: POST /login
  S-->>A: jeton
  A-->>U: Accueil
```
```
erDiagram
  CLIENT ||--o{ FACTURE : recoit
  FACTURE ||--|{ LIGNE : contient
  CLIENT { int id string nom string email }
  FACTURE { int id date date float total }
```
```
gantt
  title Projet
  dateFormat YYYY-MM-DD
  section Conception
  Maquettes :a1, 2026-10-01, 7d
  section Développement
  API :after a1, 14d
```

## Dans un document
Schéma dans un rapport PDF : faire le PNG, puis `<img src="docs/architecture.png" style="width:100%">` dans la page HTML
du rapport (chemin relatif à la page), puis convert_document.
"""),
    "rapport": ("Produire un rapport / dossier technique / cahier des charges en PDF soigné : plan, sections, schémas, tableaux, graphiques.", """# Rapport en PDF

1. Rassembler le fond : lire les fichiers / documents fournis (read_file lit aussi .docx, .pdf, .xlsx), chercher sur le
   web si besoin (web_search puis web_fetch, citer les sources). Ne rien inventer : chiffres et faits vérifiés seulement.
2. Plan avec update_todos : page de titre, sommaire, 4 à 8 sections, conclusion / recommandations, annexes.
3. Visuels d'abord : schémas avec make_diagram (PNG), graphiques de données avec matplotlib (PNG, dans un venv),
   enregistrés dans `rapport/img/`.
4. Écrire `rapport/rapport.html` (une seule page HTML, CSS dans `<style>`) :
   - `@page { size: A4; margin: 18mm 16mm }`, police `-apple-system, Helvetica, Arial` 10.5pt, interligne 1.45.
   - Page de titre : `<section class="cover" style="page-break-after: always">` (titre, sous-titre, auteur, date).
   - Sommaire : liste des sections avec leurs numéros.
   - Chaque grande section : `<h2 style="page-break-before: always">` ; titres en couleur, tableaux à bordures fines,
     en-têtes de tableau sur fond clair, `<figure><img src="img/x.png" style="width:100%"><figcaption>…</figcaption></figure>`.
   - Encadrés « À retenir » : `<div style="background:#eef4fb;border-left:4px solid #1f5fa8;padding:8px 12px">`.
5. `convert_document` source=`rapport/rapport.html` output=`rapport/rapport.pdf`.
6. `look_at` page 1 puis une page avec schéma / tableau : rien de coupé, images nettes, pas de page presque vide.
   Corriger le HTML et reconvertir si besoin.
7. Réponse : nombre de pages, plan en une ligne par section, fichiers produits. Mail demandé → send_email avec le PDF.
"""),
    "visuels": ("Créer un logo, une bannière, une icône, une affiche, une infographie ou une carte de visite (SVG puis PNG/PDF).", """# Visuels (SVG → PNG / PDF)

1. Demander ou déduire : nom / texte exact, couleurs (sinon 2 couleurs + un gris), usage (web, impression, réseaux).
2. Écrire un fichier `.svg` avec write_file, dimensions explicites :
   `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">`
   - Logo : 512×512 ; icône d'app : 1024×1024 (coins arrondis `rx="220"`) ; bannière web : 1200×630 ;
     affiche A4 : 794×1123 ; carte de visite : 1050×600.
   - Texte : `font-family="-apple-system, Helvetica, Arial, sans-serif"`, `font-weight="700"`, `text-anchor="middle"` pour centrer.
   - Formes simples (rect, circle, path), dégradés `<linearGradient>`, pas d'image externe.
3. `convert_document` source=`logo.svg` output=`logo.png` (image nette 2x). Impression : output=`affiche.pdf`.
4. `look_at` sur le PNG : texte lisible, centré, rien ne dépasse. Corriger le SVG et recommencer si besoin.
5. Proposer 2 variantes (couleurs ou disposition) seulement si l'utilisateur le demande.
6. Infographie avec des chiffres : une page HTML (flex / grid, gros chiffres) → convert_document en .png ou .pdf.
"""),
    "recherche-approfondie": ("Recherche approfondie sur le web : 10 à 20 sources recoupées, rapport cité (état de l'art, étude de marché, comparatif).", """# Recherche approfondie

Objectif : une réponse fiable et sourcée, pas un résumé de la première page trouvée.

1. Découper la question en 3 à 5 sous-questions (update_todos). Exemple « marché des vélos cargo en France » :
   taille du marché, acteurs, prix, réglementation, tendances.
2. Pour chaque sous-question : `web_search` avec 2 formulations (français ET anglais si utile), en UNE étape
   (plusieurs appels dans la même réponse : ils partent en parallèle).
3. Choisir 10 à 20 sources variées et sérieuses : officielles (INSEE, ministères, Eurostat), études, presse reconnue,
   sites des acteurs. Écarter les pages sans auteur ni date, les contenus sponsorisés, les copies d'autres articles.
4. `web_fetch` de 4 à 6 pages à la fois (même étape). Pour chaque source, noter : titre, date, URL, 2-4 faits
   précis avec les chiffres exacts.
5. Recouper : un chiffre important doit venir de 2 sources ; si elles divergent, donner les deux avec leur date.
   Toujours dater (« en 2025 selon … »). Jamais de chiffre sans source.
6. Livrer :
   - Réponse courte : 5 à 8 points clés, chacun avec sa source [1], [2]…
   - Rapport complet si demandé (ou si > 1 page) : `recherche/rapport.md`, ou en PDF avec le skill rapport
     (synthèse, sections par sous-question, tableau comparatif, limites, liste numérotée des sources avec liens).
7. Dire clairement ce qui n'a PAS été trouvé ou reste incertain.
"""),
    "github": ("Travailler avec Git et GitHub : branches, commits propres, push, pull requests (gh), conflits.", """# Git et GitHub

## Avant tout
- `git status` et `git branch --show-current`. Ne jamais travailler directement sur main pour une nouvelle fonction :
  `git switch -c fonction/nom-court` (ou `correctif/…`).
- Ne JAMAIS commiter de secrets : vérifier `git diff --cached` (clés, tokens, mots de passe, .env) et `.gitignore`.

## Commits
- Un commit = une intention. `git add` des fichiers concernés seulement, puis `git commit -m "type: résumé"`.
- Auteur : la configuration git de l'utilisateur (`git config user.name`). N'ajoute jamais de ligne « Co-Authored-By »
  ni de mention d'un assistant dans les messages.

## Pousser et pull requests (seulement si l'utilisateur l'a demandé)
1. `gh auth status` : si non connecté, demander à l'utilisateur de lancer `gh auth login` lui-même (interactif),
   ne jamais lui demander son token dans la conversation.
2. `git push -u origin <branche>`.
3. `gh pr create --title "…" --body "…"` : le corps dit quoi, pourquoi, comment tester. Donner l'URL de la PR.
4. Suivre : `gh pr view`, `gh pr checks` (tests), `gh pr diff`. Fusionner seulement sur demande : `gh pr merge --squash`.

## Conflits
- `git pull --rebase origin main` ; pour chaque fichier en conflit : lire les deux versions, garder la bonne
  combinaison, retirer les marqueurs `<<<<<<<`, `git add`, `git rebase --continue`. Relancer les tests.

## Interdits sans demande explicite
`git push --force` sur main, `git reset --hard`, supprimer une branche distante, réécrire l'historique publié.
"""),
    "scraping": ("Récupérer des données d'un site web proprement (requests + BeautifulSoup).", """# Scraping

- Respecter robots.txt et les conditions du site ; ajouter un User-Agent et une pause entre les requêtes.
- `requests` + `BeautifulSoup(html, "html.parser")` ; sélecteurs CSS avec `soup.select`.
- Pages dynamiques (JavaScript) : Playwright (`playwright install chromium`).
- Gérer erreurs réseau, pagination, encodage ; sauvegarder en CSV/JSON.
- Tester d'abord sur une seule page, afficher 3 résultats, puis généraliser.
"""),
    # ------------------------------------------------------------------ apps & stacks
    "react-app": ("Créer une application React (Vite) soignée et complète, la lancer et l'ouvrir : boutique, tableau de bord, outil…", """# Application React (Vite) — un livrable fini, beau et lancé

## Ce que l'utilisateur attend
Une application qui a l'air d'un vrai produit, qui marche quand il clique partout, et qui est OUVERTE à la fin.
« Ne me demande rien » : choisir soi-même des valeurs réalistes (noms, prix, textes en français) et avancer.

## 1. Créer (≈ 1 min)
- `npm create vite@latest <nom> -- --template react` puis `cd <nom> && npm install` (le nom en minuscules, sans espace).
- Ne rien installer d'autre sans raison (pas de Tailwind, pas de routeur pour une seule page).

## 2. Organiser
- `src/data.js` : les données (pour une boutique : 8 à 12 produits avec nom, prix, catégorie, description courte,
  note, stock, et une couleur ou un dégradé par produit).
- `src/components/` : un composant par fichier, court (Header, ProductCard, ProductGrid, Cart, Filters, Toast…).
- État avec `useState` ; ce qui doit survivre au rechargement (le panier) dans `localStorage` via `useEffect`.

## 3. Le design (c'est ce qui se voit en premier)
- `src/index.css` : variables CSS (`--bg`, `--text`, `--accent`, `--radius`…), une police système propre, des espaces
  généreux, des ombres douces, `:hover` et transitions sur tout ce qui se clique, mise en page `grid` qui passe en
  une colonne sur téléphone (`@media (max-width: 700px)`).
- JAMAIS de carrés gris « image » : chaque produit a un visuel — un dégradé de couleur + une icône SVG en ligne
  (t-shirt, chaussure, sac…) ou ses initiales en grand ; pas d'image venue d'internet.
- En-tête avec le nom de la boutique et le panier (pastille avec le nombre d'articles).

## 4. Les fonctions qu'une boutique doit avoir
Recherche, filtre par catégorie, tri par prix ; ajout au panier avec un petit message de confirmation ; panier
(quantités + / −, retirer, total) ; « Commander » ouvre un récapitulatif avec un formulaire (nom, adresse) et une
confirmation de commande. Tout en français, prix au format `12,90 €` (`toLocaleString("fr-FR", {style:"currency", currency:"EUR"})`).

## 5. Vérifier puis lancer et ouvrir
1. `npm run build` doit passer sans erreur ni avertissement de React ; corriger sinon.
2. Lancer avec start_process (keep=true) : `npm run dev -- --port 5173`, attendre que l'adresse réponde.
3. Ouvrir l'application dans le navigateur (outil browser) : vérifier qu'elle s'affiche, ajouter un produit au
   panier, regarder la capture. Si quelque chose est cassé ou moche, corriger avant de répondre.
L'application reste lancée : l'utilisateur la voit s'ouvrir dans l'Aperçu de Naim.

## 6. Répondre
Court : ce que fait l'application (3 ou 4 lignes), le dossier, l'adresse http://localhost:5173. Ne PAS écrire
« pour la lancer, tapez… » : elle est déjà lancée et ouverte.
"""),
    "react-native": ("Créer et lancer une app mobile React Native (Expo) dans le simulateur iPhone, et la vérifier.", """# React Native (Expo)

React Native ≠ React web : ne JAMAIS utiliser Vite ni `create-react-app` ici.

## Créer (≈ 1 min)
1. Dans le dossier du projet : `npx -y create-expo-app@latest <nom> --template blank --no-agents-md`
   (non interactif ; `--template blank-typescript` si TypeScript est demandé).
2. Code dans `<nom>/App.js` (composants `View`, `Text`, `Pressable`, `TextInput`, `FlatList`, `StyleSheet` de
   `react-native`) ; écrans supplémentaires dans `<nom>/src/`. Pas de balises HTML (div, p…), pas de CSS.
3. Bibliothèque Expo : `npx expo install <paquet>` (jamais `npm install` pour un module natif Expo).

## Lancer dans le simulateur iPhone
4. start_process (keep=true), dans `<nom>` : `npx expo start --ios --port 8082`
   (démarre le simulateur, installe Expo Go la 1re fois, ouvre l'app ; compter 1 à 2 min la première fois).
5. Attendre « Bundled » dans la sortie du processus, puis `simulator action=screenshot`. La 1re fois, Expo Go
   affiche son « developer menu » : toucher « Continue » (simulator action=tap). Puis regarder l'écran :
   l'app doit s'afficher sans écran rouge d'erreur. Si erreur : lire le message, corriger App.js, l'app se
   recharge toute seule.
6. Aperçu web en plus (facultatif) : `npx expo install react-dom react-native-web @expo/metro-runtime` puis
   `npx expo start --web --port 8083`.

## Si l'utilisateur ne veut PAS Expo (React Native « CLI », sans Expo Go)
- Créer : `npx -y @react-native-community/cli@latest init <Nom> --skip-git-init --install-pods true`
  (nom en PascalCase, sans tiret ; 3 à 6 min : CocoaPods). JAMAIS `create-react-native-app` (abandonné).
- Code dans `<Nom>/App.tsx` ; modules natifs : `npm install <paquet>` puis `cd ios && pod install`.
- Lancer : start_process (keep=true) `npx react-native start`, puis run_command `npx react-native run-ios`
  (compile et ouvre le simulateur), puis `simulator action=screenshot`.

## Règles
- Commandes toujours non interactives (--yes, -y, --template…) : ne JAMAIS lancer « y » ou « yes » comme commande.
- Ne pas mélanger : pas de projet SwiftUI (simulator new_app) pour une demande React Native.

## Finir
7. Résumer : dossier, commande pour relancer (`cd <nom> && npx expo start --ios`), ce que montre l'écran.
"""),
    "ios-swiftui": ("Créer ou modifier une app iOS en SwiftUI (vues, modèles, réseau, persistance).", """# iOS / SwiftUI

- Architecture : `Models/` (structs Codable), `Views/` (une vue par écran), `Services/` (réseau async/await).
- État : `@State`, `@StateObject`/`@Observable`, `@Environment` ; navigation `NavigationStack`.
- Réseau : `URLSession.shared.data(from:)` + `JSONDecoder` ; erreurs affichées à l'utilisateur.
- Persistance : SwiftData ou `UserDefaults` pour les petits réglages.
- Compiler : `xcodebuild -scheme <App> -destination 'platform=iOS Simulator,name=iPhone 16' build`.
"""),
    "api-php": ("Créer une API REST en PHP (PDO/MySQL, JSON, validation, sécurité).", """# API PHP

- Un point d'entrée `index.php` + routeur simple ; réponses `header('Content-Type: application/json')`.
- Base : PDO avec requêtes préparées UNIQUEMENT (jamais de concaténation SQL), `PDO::ERRMODE_EXCEPTION`.
- Validation des entrées (`filter_var`), codes HTTP corrects, erreurs JSON `{"error": "..."}`.
- Mots de passe : `password_hash` / `password_verify`. CORS si besoin.
- Tester : `php -S 127.0.0.1:8080` (start_process) puis curl sur chaque route.
"""),
    "docker": ("Conteneuriser une application (Dockerfile optimisé + docker compose).", """# Docker

- Dockerfile multi-étapes, image slim/alpine, utilisateur non-root, `.dockerignore`.
- Dépendances copiées avant le code (cache), `CMD` explicite, `EXPOSE` du port.
- `compose.yaml` : service app + base de données + volumes + variables d'environnement (`.env`).
- Vérifier : `docker compose up -d --build`, `docker compose ps`, curl sur l'app, `docker compose logs`.
"""),
    "deploiement-vps": ("Déployer une application sur un serveur Linux (VPS) de façon sûre.", """# Déploiement VPS

- Ne JAMAIS exécuter de commande sur le serveur sans l'accord explicite de l'utilisateur.
- Étapes : rsync/git du code, venv/npm install, service systemd (redémarrage auto), reverse proxy Nginx,
  HTTPS avec certbot, pare-feu (ufw : 22, 80, 443).
- Secrets dans un fichier `.env` hors du dépôt. Logs : `journalctl -u app -f`.
- Fournir un script `deploy.sh` idempotent et une checklist de vérification.
"""),
    "base-de-donnees": ("Concevoir un schéma SQL, des migrations et des requêtes performantes.", """# Base de données

- Schéma : clés primaires, clés étrangères, contraintes NOT NULL/UNIQUE, types adaptés, index sur les colonnes filtrées.
- Migrations versionnées (fichiers `001_init.sql`, `002_...sql`) ; jamais de modification manuelle en prod.
- Requêtes : préparées, `EXPLAIN` pour vérifier l'usage des index, pagination par clé.
- Sauvegarde avant toute migration destructive.
"""),
    "script-bash": ("Écrire des scripts Bash robustes (options, erreurs, logs).", """# Script Bash

- En-tête : `#!/usr/bin/env bash` + `set -euo pipefail`.
- Arguments avec `getopts`, aide `-h`, variables entre guillemets, `trap` pour nettoyer.
- Vérifier les dépendances (`command -v`), messages clairs sur stderr, codes de sortie.
- Tester avec `bash -n script.sh` puis un essai réel ; `shellcheck` s'il est installé.
"""),
    "ci-cd": ("Mettre en place une intégration et un déploiement continus (GitHub Actions / GitLab CI) : tests automatiques à chaque envoi, puis déploiement.", """# CI/CD : tests automatiques, puis déploiement

## Quand l'utiliser
- On te demande « CI/CD », « GitHub Actions », « GitLab CI », « intégration continue », « déploiement automatique »,
  « lancer les tests à chaque push ».
- PAS pour : lancer les tests une fois sur ce Mac (fais-le avec run_command), déployer à la main sur un serveur
  (skill deploiement-vps), ni pour un document, un article ou une question générale.

## Avant d'écrire quoi que ce soit
1. Lire le projet : `list_files`, puis le fichier de dépendances (`requirements.txt` / `pyproject.toml`, `package.json`,
   `composer.json`) et la façon dont les tests se lancent aujourd'hui.
2. Lancer ces tests UNE fois sur le Mac. S'ils échouent ici, ils échoueront en CI : le dire et les corriger d'abord.
3. Plateforme : `git remote -v` → github.com = GitHub Actions (`.github/workflows/ci.yml`) ; gitlab = `.gitlab-ci.yml`.
   Pas de dépôt distant : GitHub Actions par défaut, et le dire.

## Modèle GitHub Actions (Python) — à adapter, pas à recopier aveuglément
```yaml
name: CI
on:
  push: { branches: [main] }
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -r requirements.txt
      - run: python -m pytest -q
```
Node : `actions/setup-node@v4` avec `node-version: 20` et `cache: npm`, puis `npm ci`, `npm test`, `npm run build`
(seulement les scripts qui existent dans package.json). PHP : `shivammathur/setup-php@v2`, `composer install`, `vendor/bin/phpunit`.

## Déploiement (seulement si demandé)
- Un job `deploy` séparé, `needs: test`, et `if: github.ref == 'refs/heads/main'` : on ne déploie jamais un code qui échoue.
- Les accès (clé SSH, mot de passe, jeton) vont dans les SECRETS du dépôt : `${{ secrets.NOM }}`. Jamais en clair dans le YAML.

## Pièges fréquents
- Branche `master` et non `main` : vérifier avec `git branch`.
- Des tests qui ont besoin d'une base de données ou d'un fichier `.env` : ajouter un `services:` ou des variables, sinon ils échouent en CI.
- Ne pas ajouter de lint (ruff, eslint) qui n'existe pas déjà dans le projet : la CI échouerait pour du style.

## Vérifier
- YAML valide : `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" .github/workflows/ci.yml`.
- Les commandes du YAML relancées une par une sur le Mac donnent le même résultat.
- Si `act` est installé : `act -j test`.

## Répondre
En quelques lignes : le fichier créé, ce qu'il fait (« à chaque push : installation puis tests »), les secrets à
créer (nom exact et où : Settings › Secrets and variables › Actions) et où voir les exécutions (onglet Actions).
"""),
    # ------------------------------------------------------------------ quality
    "securite": ("Relire un projet pour trouver les failles de sécurité et les corriger.", """# Revue de sécurité

Chercher : injections SQL/commandes, XSS, CSRF, secrets dans le code, mots de passe en clair,
contrôles d'accès manquants, uploads non filtrés, dépendances vulnérables (`pip-audit`, `npm audit`).
Pour chaque problème : fichier:ligne, gravité, exploitation possible, correctif. Corriger les plus graves d'abord.
"""),
    "performance": ("Mesurer puis accélérer du code lent (profilage avant optimisation).", """# Performance

1. Mesurer d'abord : `time`, `cProfile`/`py-spy` (Python), DevTools (web), `EXPLAIN` (SQL).
2. Cibler le point chaud principal ; ne pas optimiser au hasard.
3. Pistes : algorithme/complexité, requêtes N+1, cache, index, I/O en lot, pagination.
4. Re-mesurer et donner le gain chiffré (avant/après).
"""),
    "refactoring": ("Améliorer la structure du code sans changer son comportement.", """# Refactoring

1. S'assurer qu'il existe des tests (sinon en écrire quelques-uns sur le comportement actuel).
2. Petites étapes : renommer, extraire des fonctions, supprimer la duplication, simplifier les conditions.
3. Lancer les tests après chaque étape ; ne jamais mélanger refactoring et nouvelles fonctionnalités.
4. Résumer ce qui a changé et pourquoi.
"""),
    "doc-api": ("Documenter une API (routes, paramètres, exemples curl, OpenAPI).", """# Documentation d'API

- Pour chaque route : méthode, chemin, paramètres, corps, réponses (codes + exemples JSON), erreurs.
- Un exemple `curl` testé par route.
- Si possible un fichier `openapi.yaml` (FastAPI le génère : `/openapi.json`).
- Écrire dans `docs/API.md` ou dans le README.
"""),
}
