---
name: mods
description: Créer, changer ou enlever un mod de la fenêtre de Naim (un bandeau au-dessus de la zone de message, un bouton sous elle, un toast, une réaction à chaque message), écrit dans ~/.naim/mods/<nom>/.
---

# Les mods : changer ta propre fenêtre

Un mod est un petit dossier `~/.naim/mods/<nom>/` (nom en minuscules, avec des tirets) que la fenêtre de Naim charge
toute seule. Il ne touche jamais au programme de Naim : pour l'enlever, l'utilisateur tape `/mods off <nom>`.

## Les fichiers

- `mod.json` : `{ "description": "<ce qu'il fait, une phrase>", "version": "1.0" }`
- `mod.js` : le code, en JavaScript du navigateur. Il reçoit l'objet `naim` :
  - `naim.band(id, html, { tone })` (html = du texte HTML ou un élément créé avec `document.createElement`) : un bandeau d'une ligne au-dessus de la zone de message, avec un bouton
    « Masquer » à droite (déjà fourni : ne le refais pas). `tone` : `"ok"` (vert), `"warn"` (orange), `"alert"` (rouge),
    rien = gris. Rappelle-le pour le mettre à jour ; `null` l'enlève ; `{ hideable: false }` sans « Masquer ».
    Donne-lui du texte sur une ligne (des `<span>`, pas de `<div>` ni de style de cadre : le bandeau a déjà le sien,
    à la largeur de la zone de message). Il renvoie la zone du texte, pour y attacher des clics. Sépare les infos par ` · ` (ex. `Limites 5 h 42 % · 7 jours 18 %`).
    Pour colorer seulement un chiffre ou un mot (plus lisible qu'une ligne toute colorée) : `<b class="ok">11 %</b>`,
    `class="warn"` ou `class="alert"` ; `<b>` seul = en clair. Ex. : `Limites 5 h <b class="ok">11 %</b> (reprise 23:50)`.
  - `naim.button(id, { label, title, onClick })` : un bouton dans la ligne sous la zone de message (`null` l'enlève).
  - `naim.toast(texte)` : un court message en bas de la fenêtre.
  - `naim.on("send", (texte) => …)` : à chaque message envoyé ; `naim.on("reply", (texte) => …)` : à chaque réponse finie.
  - `naim.send(texte)` : envoyer un message à Naim.
  - `naim.store.get(clé, défaut)` / `naim.store.set(clé, valeur)` : garder une valeur d'une ouverture à l'autre.
  - `fetch("/api/...")` marche pour lire ce que Naim sait déjà (ex. `/api/status`).
  - `naim.panel(id, { title, icon })` : un onglet à lui dans le panneau de droite (à côté de Fichiers, Aperçu) ;
    il renvoie la zone où mettre le contenu. `icon` : `"chart"`, `"shield"`, `"activity"`… `naim.show(id)` l'ouvre.
  - `naim.chart` : des graphiques tout faits, aux couleurs de Naim, qui renvoient un élément à ajouter (`zone.append(…)`) :
    `bars(données, { title })`, `line(données, { title })`, `donut(données, { title })` avec données =
    `[{ label, value }]` ou `[[label, valeur]]` ; `stat("Messages", 42, { hint, tone })` (un grand chiffre) ;
    `table(lignes, { head: [...] })`. Ne dessine jamais un graphique à la main : utilise-les.
  - `await naim.stats(jours)` : les statistiques déjà calculées (rien n'est envoyé ailleurs) :
    `jours` = `[{ jour, messages, reponses, outils, fichiers }]`, `conversations`, `modes` ({chat, agent}),
    `outils` = `[[nom, nombre]]` (les plus utilisés), `temps_reponse_median_s`, `premier_mot_median_s`.
  - `await naim.security()` : en lecture seule (un mod ne change JAMAIS la sécurité) : `permissions`
    ({screen, accessibility} de l'app), `autorisations` (modes auto…), `commandes_interdites`, `plugins_hooks`
    (`[{ nom, hooks_allumes }]`), `actions_30_jours` ({ bloquees, refusees, refusees_par_toi }).
- `mod.css` (facultatif) : le style. Utilise les couleurs de Naim : `var(--text)`, `var(--muted)`, `var(--line)`,
  `var(--panel)`, `var(--hover)` ; elles suivent le thème clair ou sombre.

## Inventer un autre affichage

Le bandeau, le bouton et le toast suffisent souvent. Pour autre chose (un panneau sur le côté, une fenêtre flottante,
un badge sur un bouton), crée tes propres éléments avec `document.createElement` et leur style dans `mod.css`, avec
les couleurs de Naim, et donne-leur toujours un bouton « Masquer » (ou une croix en trait fin) qui les cache.

## Règles

- Icônes en traits fins (SVG `stroke="currentColor"`), jamais d'emoji. Pas de doublon d'une info déjà affichée.
- Pas de `setInterval` plus fréquent qu'une fois par seconde ; pas de réseau vers l'extérieur sans que l'utilisateur
  l'ait demandé.
- Échappe tout texte venu d'ailleurs avant de le mettre dans `html` (ou utilise `textContent`).

## Méthode

1. Écris les fichiers avec write_file dans `~/.naim/mods/<nom>/` (crée le dossier).
2. Relis `mod.js` : syntaxe valide (`node --check ~/.naim/mods/<nom>/mod.js` si node est là).
3. Dis à l'utilisateur de taper `/mods reload` (le mod apparaît tout de suite), et comment l'enlever : « Masquer »
   sur le bandeau (`/mods show <nom>` le remet), ou `/mods off <nom>` pour l'éteindre (ses fichiers restent,
   `/mods on <nom>` le remet).

## Exemple : un bandeau qui compte les messages de la journée

`mod.js` :
```js
const today = () => new Date().toISOString().slice(0, 10);
const show = () => {
  const c = naim.store.get("count", { day: today(), n: 0 });
  if (c.day !== today()) { c.day = today(); c.n = 0; }
  naim.band("compteur", `Aujourd'hui : ${c.n} message${c.n > 1 ? "s" : ""}`, { tone: c.n > 50 ? "warn" : "" });
  return c;
};
naim.on("send", () => { const c = show(); c.n++; naim.store.set("count", c); show(); });
show();
```

## Exemple complet : un panneau de statistiques et de sécurité

`mod.js` :
```js
const zone = naim.panel("tableau", { title: "Statistiques", icon: "chart" });
const fill = async () => {
  const [st, sec] = await Promise.all([naim.stats(30), naim.security()]);
  const total = (k) => st.jours.reduce((a, j) => a + j[k], 0);
  const row = document.createElement("div");
  row.style.cssText = "display:flex;gap:8px;flex-wrap:wrap";
  row.append(naim.chart.stat("Messages", total("messages"), { hint: "30 jours" }),
             naim.chart.stat("Conversations", st.conversations),
             naim.chart.stat("Réponse médiane", (st.temps_reponse_median_s ?? "–") + " s"));
  const p = sec.permissions || {};
  zone.replaceChildren(
    row,
    naim.chart.bars(st.jours.map((j) => [j.jour, j.messages]), { title: "Messages par jour" }),
    naim.chart.donut(st.outils.slice(0, 6), { title: "Outils les plus utilisés" }),
    naim.chart.table([
      ["Enregistrement de l'écran", p.screen ? "oui" : "non"],
      ["Accessibilité", p.accessibility ? "oui" : "non"],
      ["Actions refusées (30 j)", (sec.actions_30_jours.refusees || 0) + (sec.actions_30_jours.bloquees || 0)],
    ], { head: ["Sécurité", ""] }));
};
naim.on("reply", fill);
fill();
naim.button("ouvrir", { label: "Statistiques", onClick: () => naim.show("tableau") });
```

