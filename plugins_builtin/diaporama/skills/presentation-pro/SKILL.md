---
name: presentation-pro
description: Faire une présentation PowerPoint (.pptx) professionnelle — diaporama, slides, exposé, soutenance, pitch — avec un thème de couleurs choisi pour le sujet, des diapositives variées (grands chiffres, étapes, comparaison, graphiques natifs, tableau, citation), des notes d'orateur, un aperçu de chaque diapositive vérifié avant de livrer ; lire ou modifier un PowerPoint existant sans le refaire.
---

# Présentation pro (PowerPoint)

Tu écris le PLAN de la présentation en JSON ; l'outil fabrique le vrai PowerPoint (texte modifiable, graphiques
natifs, notes), une image de chaque diapositive et le contrôle du texte. Ne code pas la présentation toi-même.

```bash
D="$HOME/.naim/plugins/diaporama/skills/presentation-pro"; PY="$HOME/.naim/docs-venv/bin/python"
"$PY" "$D/diapo.py" faire plan.json presentation.pptx      # le PowerPoint + presentation-apercu/diapo-N.png + le contrôle
"$PY" "$D/diapo.py" lire  existante.pptx                  # le texte de chaque diapositive (titres, tableaux, notes)
"$PY" "$D/diapo.py" modifier existante.pptx changements.json nouvelle.pptx
"$PY" "$D/diapo.py" themes                                # les thèmes de couleurs
```

## 1. Avant d'écrire : le fond
- **Le contenu vient de la source** : un document joint, un cours, un texte collé (read_file) — ses idées, ses
  chiffres, ses mots. Un sujet seul : ce que tu sais de sûr ; un sujet pointu ou récent : une recherche web d'abord.
- **Pour qui, pour quoi** : un exposé en classe, une soutenance, un pitch, une réunion. À l'oral : peu de mots,
  beaucoup de visuel ; à lire seul : un peu plus de texte.
- **La taille** : environ une diapositive pour 1 min 30 à 2 min de parole. Sans indication : 8 à 12 diapositives.
- **Le fil** : le message principal tôt, puis les parties (une idée par diapositive), puis la conclusion avec ce
  qu'il faut retenir ou faire.

## 2. Le plan (plan.json)
```json
{
  "theme": "sante",
  "police": "",
  "titre": "Le cœur",
  "diapositives": [
    {"type": "titre", "titre": "Le cœur, une pompe vitale", "sous_titre": "Anatomie et fonctionnement", "auteur": "Léa Martin", "date": "Novembre 2026",
     "notes": "Ce que je dis à l'oral sur cette diapositive."},
    {"type": "points", "titre": "Les quatre cavités", "points": [
       {"titre": "Oreillette droite", "texte": "Reçoit le sang des veines caves", "icone": "home"}],
     "chiffre": {"valeur": "70", "label": "battements par minute"}},
    {"type": "chiffres", "titre": "En chiffres", "chiffres": [{"valeur": "5 L", "label": "par minute", "detail": "au repos"}], "source": "Source : …"},
    {"type": "etapes", "titre": "Le cycle cardiaque", "etapes": [{"titre": "Remplissage", "texte": "Les oreillettes se remplissent"}]},
    {"type": "graphique", "titre": "Fréquence selon l'effort", "graphique": "colonnes", "categories": ["Repos", "Course"],
     "series": [{"nom": "bpm", "valeurs": [70, 150]}], "unite": "bpm", "commentaire": "×2 entre le repos et la course"},
    {"type": "comparaison", "titre": "Deux circulations", "gauche": {"titre": "Petite", "points": ["Vers les poumons"]},
     "droite": {"titre": "Grande", "points": ["Vers le corps"]}},
    {"type": "tableau", "titre": "Valeurs normales", "colonnes": ["Mesure", "Valeur"], "lignes": [["Fréquence", "60-100 bpm"]]},
    {"type": "deux_colonnes", "titre": "…", "gauche": {"titre": "…", "points": ["…"]}, "droite": {"image": "schema.png"}},
    {"type": "image", "titre": "…", "image": "photo.jpg", "legende": "Source : …"},
    {"type": "citation", "texte": "…", "auteur": "…"},
    {"type": "section", "titre": "Partie 2 : le fonctionnement"},
    {"type": "conclusion", "titre": "À retenir", "points": ["…", "…", "…"], "contact": "lea.martin@…"}
  ]
}
```
- **Les types** : `titre`, `section`, `points` (icône + titre + texte, 2 à 6 ; avec `image` ou `chiffre` à droite),
  `chiffres` (2 à 4 grands chiffres), `etapes` (3 à 6, une frise numérotée), `graphique`, `comparaison`,
  `tableau`, `deux_colonnes`, `image`, `citation`, `conclusion`. Chaque diapositive peut avoir `notes` et `pied`.
- **Graphiques** (natifs : modifiables dans PowerPoint) : `colonnes`, `barres`, `lignes`, `aire`, `empile`,
  `camembert`, `anneau` ; `categories` + `series` (un ou plusieurs `{"nom", "valeurs"}`) ; `unite` ; `commentaire`
  (la leçon du graphique, en une phrase, à droite).
- **Icônes** (au trait) : home, user, book, brain, bulb, target, star, spark, bolt, shield, lock, globe, map, calendar,
  chart, list, check, warn, wave, activity, thermo, tool, phone, search, eye, chat,
  code, image, play, layers, folder, mail2, settings, hand, sun, moon, plan, test.
- **Thème** : choisis-le pour le SUJET (`diapo.py themes`) : ardoise (business), foret (nature), corail (marketing),
  ocean (tech, eau), terre (histoire), prune (art, luxe), graphite (sobre), sante (médecine), soleil (éducation).
  Ou tes couleurs : `"theme": {"primaire": "1F2A44", "clair": "E9EDF5", "accent": "F2A541", "texte": "1F2A44", "doux": "6B7385"}`
  (une couleur domine, un accent vif ; les couleurs d'une marque si l'utilisateur en donne). `"police": "georgia"`
  pour des titres à empattement (histoire, littérature, élégant).

## 3. Une bonne présentation
- **Varie** : jamais deux fois de suite le même type ; alterne chiffres, étapes, comparaison, graphique, points.
- **Chaque diapositive a un visuel** (icônes, grand chiffre, graphique, image, frise) : pas de diapositive de texte seul.
- **Peu de mots** : un titre court qui dit le message (« Le débit double à l'effort », pas « Graphique »), sans point
  final ; des points de 3 à 10 mots ; le détail va dans les `notes` (ce que l'orateur dit).
- **Des chiffres vrais**, avec leur source sur la diapositive (`source`) quand ils viennent d'un document ou du web.
- **Images** : un fichier qui existe (téléchargé avant, skill des images, ou fourni par l'utilisateur), chemin complet.

## 4. Vérifier, puis livrer (obligatoire)
1. `diapo.py faire` affiche les PROBLÈMES : un texte qui déborde, deux diapositives pareilles à la suite.
   Corrige le plan (raccourcis, partage en deux diapositives), refais.
2. **Regarde les aperçus** avec look_at (`…-apercu/diapo-1.png`, puis les autres) : texte coupé, éléments qui se
   touchent, diapositive vide ou trop pleine, contraste. Corrige le plan et refais seulement si un défaut se voit.
3. Livre : le chemin du .pptx et, en 2 lignes, le fil de la présentation. Ne recopie pas les diapositives en texte.

## 5. Un PowerPoint qui existe déjà
- **Le lire** : `diapo.py lire fichier.pptx` (le texte de chaque diapositive, ses tableaux, ses notes).
- **Le modifier sans le refaire** (corriger un mot, un chiffre, des notes, enlever ou déplacer une diapositive) :
  écris `changements.json`, puis `diapo.py modifier ancien.pptx changements.json nouveau.pptx` (garde l'original) :
```json
[
  {"remplacer": {"diapo": 3, "ancien": "2025", "nouveau": "2026"}},
  {"notes": {"diapo": 2, "texte": "Insister sur le ventricule gauche."}},
  {"deplacer": [9, 2]},
  {"supprimer": 10}
]
```
  (`diapo` 0 ou absent dans `remplacer` : dans toute la présentation ; le style du texte est gardé.)
- Le refaire entièrement seulement si l'utilisateur veut une nouvelle mise en page : lis-le d'abord, puis fais un
  nouveau plan avec son contenu.

## 6. En PDF
Le PowerPoint fait, une version PDF : les aperçus sont déjà les pages ; pour un PDF propre, ouvre le .pptx dans
Keynote ou PowerPoint seulement si l'utilisateur le demande (Fichier → Exporter en PDF). Sinon, le skill pdf-pro.
