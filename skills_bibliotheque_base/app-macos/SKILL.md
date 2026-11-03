---
name: app-macos
description: Créer une vraie application Mac (SwiftUI) qui se compile, s'installe dans Applications et se lance — sans projet Xcode.
---

# Application Mac en SwiftUI (sans Xcode)

N'écris JAMAIS de projet Xcode à la main (`.xcodeproj`, `project.pbxproj`) : c'est illisible et ça échoue toujours.
On compile avec le script de ce skill, qui fabrique un paquet Swift puis l'application `.app`.

## Règles des commandes (à respecter à la lettre)
- Utilise UNIQUEMENT les 3 commandes ci-dessous (copier le modèle, compiler, installer). N'écris JAMAIS toi-même
  un `.app`, un `Info.plist`, un `cp` vers Applications ou un `codesign` : le script le fait, et ces commandes sont refusées.
- Lis TOUT ce que le script affiche. Il dit toujours le résultat :
  `✓ application créée`, `✓ installée : <chemin>`, `✓ lancée` — ou `ERREURS DE COMPILATION` / `ÉCHEC …` avec la raison.
  Pas de « ✓ lancée » dans la sortie = l'app n'est PAS lancée : ne dis jamais le contraire.
- Si le script échoue, relance-le une fois avec ` 2>&1` à la fin pour voir le message complet, puis corrige.

## Emplacements
- Sources : `apps/<Nom>/<Nom>App.swift` dans le dossier du projet ouvert (le script affiche le chemin complet : `→ sources : …`).
- Application installée : **`/Applications/<Nom>.app`** (le dossier Applications du Mac, visible dans le Finder et le
  Launchpad). Si le Mac le refuse, le script utilise `~/Applications/<Nom>.app` et l'écrit. Donne à l'utilisateur
  le chemin EXACT de la ligne `✓ installée : …`, jamais un chemin deviné.
- Relancer plus tard : `open "/Applications/<Nom>.app"` (le script l'affiche à la fin).

## Design (une app qui ressemble à une vraie app Mac)
Le modèle est déjà soigné : GARDE sa structure et son style, change seulement le contenu.
- Mise en page : barre latérale (`NavigationSplitView`) avec la liste, détail à droite ; barre d'outils avec
  « Actualiser » (`arrow.clockwise`) ; recherche dans la barre latérale ; bandeau d'état en bas après une action.
- Détail : une carte d'en-tête (grande icône dans un carré arrondi coloré, titre, sous-titre, pastille d'état
  « En ligne » verte), puis des sections `Carte(titre:symbole:)` : une section = une tâche (imprimer, réglages, infos).
- Icônes SF Symbols partout (`printer`, `doc`, `wifi`, `folder`, `gearshape`, `info.circle`…), jamais d'emoji.
- Un seul bouton principal par section (`.borderedProminent`, `.controlSize(.large)`), désactivé tant qu'il manque
  quelque chose ; pendant l'action, un `ProgressView` à sa place.
- États vides avec `ContentUnavailableView` (icône, titre, une phrase qui dit quoi faire).
- Couleurs du système (`.tint`, `.secondary`, `Color(nsColor: .controlBackgroundColor)`) : l'app suit le mode
  sombre/clair. Coins arrondis 12 à 16, marges 16 à 24, pas de texte collé aux bords.
- Les commandes du Mac passent par `await lancerAsync(...)` : la fenêtre ne se fige jamais.
- Jamais de données inventées (pas de fausses imprimantes) : tout ce qui s'affiche vient d'une vraie commande.
- Pas de `Picker(.segmented)` pour une liste d'éléments, pas de « - » entre des boutons, pas de longue colonne de
  boutons : utilise la liste de gauche et les sections.

## Méthode
1. Pars TOUJOURS du modèle qui compile déjà (fenêtre, choix d'un fichier, liste, bouton, commande du Mac) :
   `mkdir -p apps/<Nom> && cp ~/.naim/skills/app-macos/modele.swift apps/<Nom>/<Nom>App.swift`
   puis lis-le (read_file) et ADAPTE-le avec edit_file : renomme `MonApp` et « Mon application », change
   `Element` (ce qu'on liste), `charger()` (d'où viennent les données) et `DetailView` (les sections et leurs actions).
   Garde `choisirFichier()`, `lancer()` et `lancerAsync()` telles quelles.
   - Imprimantes : `lpstat -a` liste celles du Mac ; celles du réseau (même non ajoutées) :
     `/usr/bin/ippfind -T 3 _ipp._tcp` (une URL `ipp://…` par ligne) ; en ajouter une : `/usr/sbin/lpadmin -p <nom> -E -v <url> -m everywhere`.
   - Pas de `DocumentGroup` ni de `FileDocument` : une simple `WindowGroup` suffit.
   - Toute variable utilisée dans la vue doit être déclarée en `@State private var … = …` en haut de `ContentView`.
   - PAS d'UIKit (c'est iOS). Ne redéfinis jamais un type qui existe déjà.
2. Compiler (≈ 10 s) :
   `bash ~/.naim/skills/app-macos/build_app.sh <Nom> apps/<Nom>`
   - S'il y a des erreurs : lis la PREMIÈRE erreur (fichier:ligne), corrige seulement elle, relance. 5 essais au plus,
     puis explique ce qui bloque.
3. Installer dans Applications et lancer (quand l'utilisateur veut l'app, c'est-à-dire presque toujours) :
   `bash ~/.naim/skills/app-macos/build_app.sh <Nom> apps/<Nom> --install --open`
   → la sortie doit contenir `✓ installée : /Applications/<Nom>.app` et `✓ lancée`.
4. Vérifier le rendu : `bash ~/.naim/skills/app-macos/capture_app.sh <Nom>` puis look_at sur l'image indiquée.
   Compare avec la section Design (barre latérale, carte d'en-tête, sections, icônes) ; si c'est vide, tassé ou
   brut, corrige le code, relance build_app.sh … --install --open, et recapture.

## Répondre
Ce que fait l'app (2 ou 3 lignes), où elle est (le chemin EXACT de `✓ installée : …`), et qu'elle est lancée
(seulement si la sortie dit `✓ lancée`). Ajoute la commande pour la relancer.
Ne dis pas « ouvrez Xcode » : l'utilisateur veut une application prête.
