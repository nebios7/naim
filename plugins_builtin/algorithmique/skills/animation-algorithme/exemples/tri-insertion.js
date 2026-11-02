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
