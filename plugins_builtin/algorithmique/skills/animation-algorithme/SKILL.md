---
name: animation-algorithme
description: Une simulation visuelle (page HTML autonome) qui exécute un algorithme ou un petit programme pas à pas (tri, recherche, boucle, récursivité, pile, arbre, graphe, liste chaînée) avec son code surligné, ses variables, une explication à chaque étape et les commandes lecture, pause, pas à pas.
---

# Animer un algorithme

## Dans la conversation (le cas normal) : un bloc ```simulation
Quand on te demande de montrer, simuler ou animer un algorithme dans la conversation, sans demander de fichier ni de
page : ta réponse est une phrase courte, puis UN bloc ```simulation qui contient l'objet `const ALGO = { … }` (le même
format que ci-dessous), puis une ou deux phrases pour s'en servir. Naim le joue aussitôt dans la conversation, avec
le moteur : barres qui glissent, code surligné, variables, lecture / pause / pas à pas / vitesse. Aucun fichier,
aucune commande, aucun bloc ```visuel ni ```html fait main.

Exemple complet, juste et vérifié (un tri : suis exactement ce plan) :
```simulation
const ALGO = {
  titre: "Chaque carte trouve sa place",
  sous_titre: "Tri par insertion",
  fichier: "tri_insertion.py",
  langage: "python",
  type: "tri",
  valeurs: [5, 2, 8, 1, 9, 3],
  code: `
def tri_insertion(a):
    for i in range(1, len(a)):
        cle = a[i]
        j = i - 1
        while j >= 0 and a[j] > cle:
            a[j + 1] = a[j]
            a[j] = cle
            j -= 1
    return a`,
  build(a, P) {
    const n = a.length;
    for (let i = 1; i < n; i++) {
      const cle = a[i];
      P(3, `On prend <b>${cle}</b> et on lui cherche sa place parmi les cases de gauche, déjà triées.`, { key: i, ok: P.plage(0, i - 1), vars: { i, cle } });
      let j = i - 1;
      while (j >= 0) {
        const gt = a[j] > cle;
        P(5, gt ? `<b>${a[j]} &gt; ${cle}</b> : ${a[j]} doit passer à droite.` : `<b>${a[j]} ≤ ${cle}</b> : ${cle} est à sa place.`,
          { pair: [j, j + 1], vars: { i, j, cle }, note: `${a[j]} ${gt ? ">" : "≤"} ${cle}` });
        if (!gt) break;
        a[j + 1] = a[j]; a[j] = cle;
        P(7, `On décale : <b>${cle}</b> glisse d'une case vers la gauche.`, { pair: [j, j + 1], swap: true, vars: { i, j, cle } });
        j--;
      }
    }
    P(9, "Toutes les cartes sont à leur place : le tableau est trié.", { ok: P.plage(0, n - 1) });
  },
};
```
Une erreur dans `build` s'affiche en rouge dans la simulation : si l'utilisateur te la montre, redonne le bloc entier
corrigé.

## Une page à garder (seulement si un fichier ou une page est demandé)

La page est faite de deux parties :
- **le moteur** (`moteur.html`, déjà écrit et testé) : barres qui glissent, bras robot, code coloré automatiquement,
  ligne surlignée, variables, compteurs, lecture / pause / pas à pas / vitesse, valeurs de l'utilisateur ;
- **l'algorithme** : un petit fichier `.js` que TU écris. C'est le seul travail.

Tu n'ouvres jamais `moteur.html` et tu n'écris jamais la page à la main.

```bash
T="$HOME/.naim/plugins/algorithmique/skills/animation-algorithme"
cat "$T/exemples/tri-bulles.js"                  # un tri : lis-le d'abord (ou recherche-dichotomique.js pour une recherche)
# write_file <dossier>/tri_insertion.js          # ton algorithme, sur le même plan
python3 "$T/simulation.py" creer tri_insertion.js tri_insertion.html   # la page, puis la vérification
```

`creer` assemble la page puis la vérifie. Il exécute ton algorithme pour de vrai sur tes valeurs. Pour un tri, il essaie
aussi un tableau déjà trié, un tableau inversé, des doublons, une seule case. Pour une recherche, il essaie la
première case, la dernière, le milieu et une valeur absente. Il écrit OK ou FAUX, avec la raison. Tant qu'il y a une
ERREUR ou un FAUX : corrige le fichier `.js` (edit_file), puis relance `creer`. La page n'est finie qu'avec
« La simulation est juste. ».

## Le fichier de l'algorithme
```js
const ALGO = {
  titre: "Une phrase qui donne envie",      // le grand titre
  sous_titre: "Tri par insertion",
  fichier: "tri_insertion.py",              // le nom dans l'onglet du code
  langage: "python",                        // python, c, java, javascript, cobol, pseudo
  type: "tri",                              // "tri", "recherche" ou "autre"
  valeurs: [5, 2, 8, 1, 9, 3],
  code: `
def tri_insertion(a):
    ...`,                                   // le code MONTRÉ, en texte simple, tel que l'élève l'écrirait
  build(a, P) {                             // l'algorithme EXÉCUTÉ, en JavaScript, sur le tableau a
    ...
    P(4, "Une phrase qui explique pourquoi.", { pair: [j, j + 1], vars: { i, j } });
  },
};
```
- `code` : du texte simple, jamais de `<span>` ni de `&lt;`. La couleur est automatique. Les lignes sont
  numérotées à partir de 1, la première ligne non vide étant la ligne 1.
- `build` est du **JavaScript**, même si le code montré est en Python ou en C : `&&` et `||` (jamais `and` /
  `or`), `let` / `const`, des accolades, `Math.floor`. Il modifie `a` comme l'algorithme le fait, pour de vrai.
- `P(ligne, message, options)` enregistre une étape. `ligne` est le numéro de la ligne de `code` qui s'exécute,
  et `message` une phrase courte pour un élève (le HTML `<b>` est permis). Le tableau `a` est photographié tout seul.
  Les options :
  - `pair: [i, j]` : les deux cases regardées (le bras robot les tient), en bleu ; avec `swap: true`, en rouge ;
  - `key: k` : la case mise de côté, en violet (la valeur à insérer, le pivot, le minimum) ;
  - `ok: P.plage(0, i)` : les cases déjà à leur place, en vert ; `found: k` : la case trouvée (recherche) ;
  - `out: [...]` : les cases éliminées, pâles (recherche) ;
  - `vars: { i, j, v }` : les variables affichées sous le code ;
  - `note: "5 > 3"` : un petit calcul au bout de la ligne surlignée ; `pass: "passe 2"` : la ligne d'état ;
  - `c: …`, `s: …` : les deux compteurs (comparaisons et échanges ; d'autres noms avec `compteurs: [...]`).
- Une recherche : `cible: 26` (un champ « cible » apparaît) et `build(a, P, x)` reçoit la valeur cherchée.

## Les règles
- Les étapes viennent de l'exécution réelle de `build` : jamais d'étapes écrites à la main.
- Chaque ligne importante du code a son `P` au bon numéro : relis les numéros avec le code sous les yeux.
- Messages en français, courts : ce qui se passe et pourquoi.

## Autre chose que des barres (pile d'appels, arbre, graphe, liste chaînée, Hanoï…)
Garde le même fichier et le même moteur. Ajoute `type: "autre"` et une fonction `dessiner(etape, zone)` dans
ALGO : elle dessine l'étape dans `zone` (un `div`, par exemple avec `zone.innerHTML = '<svg …>…</svg>'`).
Ce que tu passes dans `P(ligne, message, { dessin: {...} })` arrive dans `etape.extra` :
- **pile d'appels** : `dessin: { pile: ["fact(3)", "fact(2)"] }`, une boîte par appel de bas en haut, celle du dessus surlignée ;
- **arbre / graphe** : nœuds et arêtes en SVG ; `dessin: { courant: x, visites: [...], file: [...] }` ;
- **liste chaînée** : des boîtes reliées par des flèches, et le pointeur courant au-dessus.
Le moteur garde le code surligné, les variables, les messages et les commandes.

## Pour finir
Donne le chemin de la page et dis comment s'en servir : Espace = lecture / pause, flèches = étape par étape,
ses propres valeurs dans le champ du bas. La page s'ouvre toute seule dans le panneau Aperçu de Naim :
n'ouvre pas le navigateur du Mac, sauf si l'utilisateur le demande. Le fichier `.js` reste à côté : on le modifie,
puis on relance `creer`.
