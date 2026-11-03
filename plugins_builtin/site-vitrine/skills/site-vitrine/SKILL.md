---
name: site-vitrine
description: Site vitrine ou landing page pour un commerce, un artisan, un cabinet, une association, un restaurant, un salon — à partir d'un modèle sobre et éditorial, vérifié (pas un gabarit « fait par une IA »).
---

# Site vitrine et landing page

Le modèle vérifié est dans ce skill : `$HOME/.naim/plugins/site-vitrine/skills/site-vitrine/modele.html`. C'est une
page complète, sobre et éditoriale : bandeau, ouverture avec grande photo, repères, prestations et tarifs, à propos,
galerie, avis, infos pratiques, appel final. Elle s'adapte au téléphone, et le clavier et le mouvement réduit sont
prévus.

**Ne réécris pas la page de zéro.** Copie le modèle, puis change le contenu section par section avec edit_file. C'est
plus beau, et bien plus rapide que de générer 900 lignes.

```bash
cp "$HOME/.naim/plugins/site-vitrine/skills/site-vitrine/modele.html" <dossier>/index.html
```

## Les étapes
1. **Copie le modèle** (commande ci-dessus).
2. **Remplace les textes** du lieu de l'exemple (Maison Ardoise, céramique, Nantes) par ceux de l'utilisateur : nom,
   métier, ville et quartier, prestations et prix, horaires, adresse, téléphone, e-mail. Un edit_file par section.
   Garde la structure, les classes et le style.
3. **Ce que tu ne sais pas** (prix, horaires, téléphone, avis) : mets des valeurs plausibles **et dis-le clairement
   dans ta réponse** (« les prix et horaires sont des exemples : donne-moi les vrais »). N'invente jamais un nombre de
   clients, une note sur 5 ou des années d'expérience.
4. **L'ambiance** : change seulement les trois couleurs de `:root` (`--papier`, `--encre`, `--accent`) avec une ligne
   du tableau ci-dessous. Si tu changes les polices, change le lien Google Fonts et `--titre` / `--texte`.
5. **Les photos** : si l'utilisateur a donné des photos, copie-les dans le dossier et remplace le `<span>` du cadre par
   `<img src="photo.jpg" alt="description précise">`. Sinon, **laisse les cadres** avec leur légende « Photo : … »
   adaptée au métier (« Photo : la façade du salon »). N'utilise jamais de liens d'images au hasard (Unsplash,
   picsum…) : ils cassent et tombent à côté du sujet.
6. **Regarde le résultat** (look_at, écran par écran avec page=2, 3…) et corrige ce qui ne va pas.

## Ambiances (les trois couleurs de :root)
| Métier | --papier | --encre | --accent | Titres / texte |
|---|---|---|---|---|
| Artisan, céramique, atelier | #f5f1ea | #1f1c18 | #a4502c | Fraunces / Instrument Sans |
| Coiffure, beauté, soins | #f4efe9 | #231f1d | #8c5a4a | Fraunces / Instrument Sans |
| Restaurant, café, cave | #f3eee4 | #1d1a16 | #7a2e1f | Fraunces / Instrument Sans |
| Cabinet (avocat, médecin, architecte) | #f6f6f3 | #15191d | #2f4a5c | Newsreader / Instrument Sans |
| Sport, coach, studio | #f2f2ef | #121212 | #c2410c | Archivo / Archivo |
| Nature, fleuriste, bio | #f1f0e8 | #1c211b | #4d6a3a | Fraunces / Instrument Sans |

## Ce qui fait « page générée par une IA » — à ne jamais faire
- Dégradés roses ou violets, fond en dégradé derrière le titre, effet « verre ».
- Titre centré du type « Votre [métier] de confiance à [ville] » ou « Sublimez votre beauté ».
- Icônes émoji ou smileys pour les services, cartes toutes identiques avec une icône ronde.
- Chiffres inventés (« 5000+ clients satisfaits », « 15 ans d'expérience »), étoiles et avatars à initiales.
- Plus de trois couleurs, des ombres partout, des coins très arrondis, des boutons en dégradé.
- Les phrases creuses (« une expérience unique », « passion et expertise ») : écris des faits précis sur le lieu.

## Une landing page de produit ou d'application
Même modèle : l'ouverture présente le produit (une phrase claire et une capture d'écran dans le cadre). Les
prestations deviennent les fonctions, avec leur prix si l'utilisateur en a. Les infos pratiques deviennent la FAQ ou
le contact. Pour une scène 3D dans la page, ajoute-la à partir du skill threejs-3d.
