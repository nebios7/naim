---
name: visuel
description: Afficher un visuel vivant DANS la conversation (horloge qui avance, compteur, jauge, compte à rebours, petit tableau de bord, mini-calculatrice, graphique de données interactif, carte géographique avec des lieux) avec un bloc ```visuel.
---

# Un visuel dans la conversation

Le visuel s'affiche DANS la conversation, à la place du bloc : pas de fichier, pas d'outil, pas d'Aperçu, jamais de
bloc ```html (il resterait du code). Ta réponse : une phrase courte, puis UN bloc ```visuel, puis rien ou une phrase.

## Une simulation d'algorithme : pas ce bloc
Un tri, une recherche, une boucle, une récursivité à montrer pas à pas : jamais un visuel fait main. C'est un bloc
```simulation avec `const ALGO = { … }` (skill animation-algorithme), joué par le moteur de Naim.

## Un graphe de maths : pas ce bloc
Une courbe, une fonction de x ou de x et y, un gradient, des courbes de niveau, une région, un nuage de points :
jamais un visuel fait main ni make_diagram (Mermaid ne trace pas de fonction). C'est un bloc ```graphe (skill
maths-affichage), calculé et dessiné exactement par Naim, avec un point à déplacer pour f(x, y) :
```graphe
f(x, y) = x^2 + 3y
x : -3..3
y : -2..4
```

## Le bloc
Du HTML (avec son `<style>` et son `<script>`), sans `<html>` ni `<head>` : il est posé dans une page déjà prête, à la
police et aux couleurs de Naim. Fermé par ``` sur sa propre ligne.

- Vivant : ce qui change (l'heure, un compte à rebours) est calculé par le script, jamais écrit en dur.
  `new Date()`, `setInterval(…, 1000)`, `toLocaleTimeString("fr-FR")`, `toLocaleDateString("fr-FR", {weekday: "long", day: "numeric", month: "long", year: "numeric"})`.
- Rien d'extérieur : ni police, ni image, ni fetch (tout est bloqué). Deux bibliothèques sont fournies par Naim,
  rien d'autre : `naimGraphe` (graphiques) et `naimCarte` (cartes), ci-dessous. Icônes : SVG au trait dessinés dans le
  bloc. Jamais d'emoji.

## Un graphique de données (ventes, notes, températures, budget, sondage)
`naimGraphe(élément, option)` : un vrai graphique ECharts, aux couleurs de Naim (orange d'abord), qui suit le mode
clair / sombre, avec valeurs au survol, légende cliquable et animation. Tu écris seulement les données (`option`).
Une div de hauteur fixe, puis le script :
```visuel
<div id="g" style="height: 320px"></div>
<script>
naimGraphe("#g", {
  title: { text: "Ventes 2026" }, tooltip: { trigger: "axis" }, legend: { top: 28 },
  grid: { top: 70, left: 44, right: 16, bottom: 30 },
  xAxis: { type: "category", data: ["Jan", "Fév", "Mar", "Avr"] }, yAxis: { type: "value" },
  series: [{ name: "Boutique", type: "bar", data: [120, 200, 150, 80] },
           { name: "En ligne", type: "line", smooth: true, data: [90, 140, 180, 160] }]
});
</script>
```
- Types : `bar` (comparer), `line` (évolution dans le temps), `pie` avec `radius: ["45%", "70%"]` (parts d'un
  tout, 6 parts au plus), `scatter` (deux mesures), `radar`, `heatmap`, `gauge`, `funnel`, `sankey`.
- Beaucoup de points : `dataZoom: [{ type: "inside" }, { type: "slider" }]` pour zoomer.
- Des données qui changent : garde le graphique (`const c = naimGraphe(...)`) puis `c.setOption({ series: [...] })`.
- Les VRAIES valeurs de l'utilisateur ou de tes recherches, jamais inventées ; l'unité dans le titre ou l'axe.
- Une courbe de fonction mathématique (f(x) = …) : pas ici, c'est le bloc ```graphe.

## Une carte géographique (lieux, trajet, villes, zone)
`naimCarte(élément, [lat, lng], zoom)` : un vrai plan (OpenStreetMap, sombre en mode sombre), qu'on déplace et
zoome ; `naimPoint(carte, [lat, lng], "texte")` : un point orange avec son nom au survol. Leaflet complet derrière
(`L.polyline`, `L.circle`, `L.polygon`, `carte.fitBounds`).
```visuel
<div id="m" style="height: 340px"></div>
<script>
const carte = naimCarte("#m", [48.8566, 2.3522], 12);
naimPoint(carte, [48.8584, 2.2945], "Tour Eiffel");
naimPoint(carte, [48.8606, 2.3376], "Louvre");
L.polyline([[48.8584, 2.2945], [48.8606, 2.3376]], { color: "#d97757", weight: 3 }).addTo(carte);
</script>
```
- Zoom : 5 pays · 10 région · 12 ville · 15 quartier. Plusieurs lieux : `carte.fitBounds([[lat1, lng1], [lat2, lng2]], { padding: [30, 30] })`.
- Des coordonnées justes : celles d'un lieu connu, ou cherchées (web) ; jamais au hasard.

## Le style (sobre et soigné, comme Naim)
- Couleurs de Naim, qui suivent le mode clair / sombre : `var(--text)`, `var(--muted)`, `var(--panel)` (fond de
  carte), `var(--side)`, `var(--line)` (bordures), `var(--brand)` (UNE touche d'accent, orange). Pas de dégradé
  violet, pas de couleurs criardes, pas de grosse ombre.
- Une carte : `background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 28px;`
  centrée (`margin: 0 auto`), largeur raisonnable (`max-width: 360px`) ; un « carré » : `aspect-ratio: 1`.
- Les chiffres : `font-variant-numeric: tabular-nums` (ils ne sautent pas), gros et fins (`font-size: 56px;
  font-weight: 300; letter-spacing: -1px`) ; le texte secondaire petit, `var(--muted)`, première lettre en majuscule.
- De l'air : peu d'éléments, bien alignés.
- Des tailles fixes en px (jamais `vh`, jamais `height: 100%` sur la page) : le visuel ne change pas de hauteur pendant qu'il s'anime.
  Un graphique ou une carte : une div pleine largeur avec sa hauteur (`height: 320px`), sans carte autour.

## Exemple : l'heure dans un carré
```visuel
<div class="c">
  <div class="t" id="t">--:--</div>
  <div class="s" id="s">--</div>
  <div class="d" id="d"></div>
</div>
<style>
  .c { width: 240px; aspect-ratio: 1; margin: 0 auto; display: flex; flex-direction: column; align-items: center;
       justify-content: center; gap: 6px; background: var(--panel); border: 1px solid var(--line); border-radius: 20px; }
  .t { font-size: 56px; font-weight: 300; letter-spacing: -1px; font-variant-numeric: tabular-nums; color: var(--text); }
  .s { font-size: 15px; color: var(--brand); font-variant-numeric: tabular-nums; }
  .d { font-size: 13px; color: var(--muted); }
  .d::first-letter { text-transform: uppercase; }
</style>
<script>
  const tick = () => {
    const n = new Date();
    t.textContent = n.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    s.textContent = String(n.getSeconds()).padStart(2, "0") + " s";
    d.textContent = n.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  };
  tick(); setInterval(tick, 1000);
</script>
```

## Pour finir
« Change la couleur », « plus grand », « ajoute les secondes » : redonne le bloc ```visuel entier, modifié. Un fichier
(logo, affiche, PNG, PDF) demandé explicitement : c'est un autre travail, pas ce bloc.
