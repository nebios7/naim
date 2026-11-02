// Tri à bulles (C) : le modèle à suivre pour un tri. Seul ce fichier change d'un algorithme à l'autre.
const ALGO = {
  titre: "Regarde ce robot transformer le chaos en ordre",
  sous_titre: "Tri à bulles",
  fichier: "bubble_sort.c",
  langage: "c",
  type: "tri",                     // le vérificateur contrôle que le tableau final est trié
  valeurs: [2, 5, 1, 7, 8, 3, 6, 4],
  compteurs: ["COMPARAISONS", "ÉCHANGES"],
  // le code montré, tel quel (texte simple, la couleur est automatique) ; P(ligne, …) pointe sur ces lignes
  code: `
void bubble_sort(int a[], size_t n)
{
  for (size_t i = 0; i + 1 < n; i++) {
    bool swapped = false;
    for (size_t j = 0; j + 1 < n - i; j++) {
      if (a[j] > a[j + 1]) {
        int tmp = a[j];
        a[j] = a[j + 1];
        a[j + 1] = tmp;
        swapped = true;
      }
    }
    if (!swapped) break; // déjà trié
  }
}`,
  // l'algorithme exécuté pour de vrai sur `a` ; P(ligne, message, {…}) enregistre une étape
  build(a, P) {
    const n = a.length;
    let c = 0, s = 0;
    const fini = (i) => P.plage(n - i, n - 1);           // les cases déjà à leur place (à droite)
    for (let i = 0; i + 1 < n; i++) {
      let swapped = false;
      P(3, `<b>Passe ${i + 1}.</b> On fait remonter le plus grand des ${n - i} éléments restants.`,
        { vars: { i, swapped }, ok: fini(i), pass: `passe ${i + 1}` });
      for (let j = 0; j + 1 < n - i; j++) {
        c++;
        const gt = a[j] > a[j + 1];
        P(6, gt ? `<b>${a[j]} &gt; ${a[j + 1]}</b> : mauvais ordre, il faut échanger.` : `<b>${a[j]} ≤ ${a[j + 1]}</b> : déjà dans l'ordre.`,
          { pair: [j, j + 1], vars: { i, j, swapped }, ok: fini(i), c, note: `${a[j]} ${gt ? ">" : "≤"} ${a[j + 1]}`, pass: `passe ${i + 1}` });
        if (gt) {
          const tmp = a[j]; a[j] = a[j + 1]; a[j + 1] = tmp; s++; swapped = true;
          P(9, `On échange : <b>${a[j]}</b> passe à gauche, <b>${a[j + 1]}</b> à droite.`,
            { pair: [j, j + 1], swap: true, vars: { i, j, tmp, swapped }, ok: fini(i), s, pass: `passe ${i + 1}` });
        }
      }
      if (!swapped) {
        P(13, "<b>Aucun échange pendant cette passe</b> : le tableau est trié, on s'arrête.",
          { ok: P.plage(0, n - 1), vars: { i, swapped }, pass: "aucun échange → terminé" });
        return;
      }
    }
    P(15, "Fin des passes : le tableau est trié.", { ok: P.plage(0, n - 1), pass: "terminé" });
  },
};
