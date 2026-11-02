// Produit de deux matrices 2×2 (type "autre") : le modèle pour une GRILLE. dessiner() est libre : ici trois grilles
// A × B = C, la ligne de A et la colonne de B lues en couleur, la case de C qui se remplit.
const ALGO = {
  titre: "Ligne fois colonne, case par case",
  sous_titre: "Produit de matrices",
  fichier: "produit.py",
  langage: "python",
  type: "autre",
  compteurs: ["MULTIPLICATIONS"],              // le moteur compte ce que build passe en c
  valeurs: [1, 2, 3, 4, 5, 6, 7, 8],          // A = [[1,2],[3,4]], B = [[5,6],[7,8]] ; l'élève peut en mettre d'autres
  code: `
def produit(A, B):
    n = len(A)
    C = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            for k in range(n):
                C[i][j] += A[i][k] * B[k][j]
    return C`,
  build(a, P) {
    const v = a.slice(0, 8).concat([0, 0, 0, 0, 0, 0, 0, 0]).slice(0, 8);
    const A = [[v[0], v[1]], [v[2], v[3]]], B = [[v[4], v[5]], [v[6], v[7]]], C = [[null, null], [null, null]];
    let mult = 0;
    const snap = (o) => ({ A, B, C: C.map((r) => r.slice()), ...o });
    P(3, "On prépare C, vide : chaque case sera <b>une ligne de A fois une colonne de B</b>.", { dessin: snap({}) });
    for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) {
      C[i][j] = 0;
      P(5, `Case C[${i}][${j}] : la <b>ligne ${i}</b> de A et la <b>colonne ${j}</b> de B.`, { vars: { i, j }, dessin: snap({ i, j }) });
      for (let k = 0; k < 2; k++) {
        C[i][j] += A[i][k] * B[k][j]; mult++;
        P(7, `${A[i][k]} × ${B[k][j]} = <b>${A[i][k] * B[k][j]}</b>, on l'ajoute : C[${i}][${j}] vaut maintenant <b>${C[i][j]}</b>.`,
          { c: mult, vars: { i, j, k }, note: `+ ${A[i][k]}×${B[k][j]}`, dessin: snap({ i, j, k }) });
      }
    }
    P(8, "Les quatre cases sont calculées : voilà C = A × B.", { dessin: snap({ fini: true }) });
  },
  dessiner(t, zone) {
    const d = t.extra, S = 46, G = 6;
    const grille = (M, x0, nom, on) => {
      let s = `<text x="${x0 + S + G / 2}" y="22" fill="#aab" font-size="14" text-anchor="middle" font-family="ui-monospace,Menlo,monospace">${nom}</text>`;
      M.forEach((r, i) => r.forEach((val, j) => {
        const st = on(i, j), x = x0 + j * (S + G), y = 40 + i * (S + G);
        const fill = st === "k" ? "#5a3f9e" : st === "lit" ? "#25506a" : st === "ok" ? "#1f5a3a" : "#1b1b2a";
        const bord = st === "k" ? "#b69cff" : st === "lit" ? "#5cc8ff" : st === "ok" ? "#6fe898" : "#34344a";
        s += `<rect x="${x}" y="${y}" width="${S}" height="${S}" rx="8" fill="${fill}" stroke="${bord}" stroke-width="2"/>`
           + `<text x="${x + S / 2}" y="${y + S / 2 + 7}" fill="#e8e8f2" font-size="19" font-weight="700" text-anchor="middle">${val == null ? "" : val}</text>`;
      }));
      return s;
    };
    const has = (x) => x !== undefined;
    let s = grille(d.A, 20, "A", (i, j) => has(d.i) && i === d.i ? (j === d.k ? "k" : "lit") : "")
          + `<text x="140" y="96" fill="#aab" font-size="26" text-anchor="middle">×</text>`
          + grille(d.B, 170, "B", (i, j) => has(d.j) && j === d.j ? (i === d.k ? "k" : "lit") : "")
          + `<text x="290" y="96" fill="#aab" font-size="26" text-anchor="middle">=</text>`
          + grille(d.C, 320, "C", (i, j) => has(d.i) && i === d.i && j === d.j && !d.fini ? "lit" : d.C[i][j] != null ? "ok" : "");
    zone.innerHTML = `<svg viewBox="0 0 440 160" style="width:100%;height:250px;margin-top:10px">${s}</svg>`;
  },
};
