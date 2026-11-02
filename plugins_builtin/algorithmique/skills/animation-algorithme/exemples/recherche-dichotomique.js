// Recherche dichotomique (Python) : le modèle à suivre pour une recherche (une valeur cherchée, des cases éliminées).
const ALGO = {
  titre: "Couper le tableau en deux, encore et encore",
  sous_titre: "Recherche dichotomique",
  fichier: "recherche.py",
  langage: "python",
  type: "recherche",               // le vérificateur contrôle la case trouvée (ou l'absence)
  valeurs: [3, 8, 12, 17, 21, 26, 30, 34, 41],
  cible: 26,                       // affiche le champ « cible » ; build la reçoit en 3e argument
  trie_avant: true,                // « Mélanger » garde un tableau trié
  compteurs: ["COMPARAISONS", "ÉTAPES"],
  code: `
def recherche(a, x):
    g, d = 0, len(a) - 1
    while g <= d:
        m = (g + d) // 2
        if a[m] == x:
            return m
        elif a[m] < x:
            g = m + 1
        else:
            d = m - 1
    return -1`,
  build(a, P, x) {
    let g = 0, d = a.length - 1, c = 0, s = 0;
    const hors = () => a.map((_, k) => k).filter((k) => k < g || k > d);   // les cases éliminées
    P(2, `On cherche <b>${x}</b> entre la case <b>${g}</b> et la case <b>${d}</b>.`, { vars: { x, g, d }, out: hors() });
    while (g <= d) {
      const m = Math.floor((g + d) / 2); s++;
      P(4, `Le milieu de ${g}..${d} est la case <b>${m}</b> (valeur ${a[m]}).`, { key: m, vars: { x, g, d, m }, out: hors(), s });
      c++;
      if (a[m] === x) {
        P(6, `<b>${a[m]} = ${x}</b> : trouvé à la case <b>${m}</b> !`, { found: m, vars: { x, g, d, m }, out: hors(), c, note: "trouvé", pass: `trouvé en ${s} étapes` });
        return m;
      }
      if (a[m] < x) {
        g = m + 1;
        P(8, `<b>${a[m]} &lt; ${x}</b> : la cible est à droite, on élimine la moitié gauche.`, { pair: [m, m], vars: { x, g, d, m }, out: hors(), c, note: `${a[m]} < ${x}` });
      } else {
        d = m - 1;
        P(10, `<b>${a[m]} &gt; ${x}</b> : la cible est à gauche, on élimine la moitié droite.`, { pair: [m, m], vars: { x, g, d, m }, out: hors(), c, note: `${a[m]} > ${x}` });
      }
    }
    P(11, `Plus aucune case possible : <b>${x}</b> n'est pas dans le tableau.`, { vars: { x, g, d }, out: hors(), pass: "absent → -1" });
    return -1;
  },
};
