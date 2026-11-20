const ALGO = {
  titre: "Chaque appel attend le suivant",
  sous_titre: "Récursivité : factorielle",
  fichier: "factorielle.py",
  langage: "python",
  type: "autre",
  valeurs: [5],                  // n (l'élève peut mettre 1 à 8)
  compteurs: ["APPELS"],
  code: `
def factorielle(n):
    if n <= 1:
        return 1
    return n * factorielle(n - 1)

print(factorielle(5))`,
  build(a, P) {
    const n0 = Math.max(0, Math.min(8, Math.floor(Number(a[0]) || 0)));
    const pile = [];                // les appels en cours, du premier (en bas) au dernier (en haut)
    let appels = 0;
    const D = (fin) => ({ pile: pile.map((f) => ({ ...f })), fin: fin === undefined ? null : fin });
    P("print(factorielle(5))", `Le programme demande <b>factorielle(${n0})</b>.`, { vars: { n: n0 }, dessin: D(), c: 0 });
    // la vraie récursion : chaque appel de f est un appel de factorielle, avec sa propre case
    function f(n) {
      appels += 1;
      pile.push({ n, etat: "appel", val: null });
      const moi = pile[pile.length - 1];
      P("def factorielle(n):", `On appelle <b>factorielle(${n})</b> : une nouvelle case s'empile, avec son propre n = ${n}.`,
        { vars: { n }, dessin: D(), c: appels });
      const base = n <= 1;
      P("if n <= 1:", base ? `<b>${n} ≤ 1</b> : c'est le cas de base, on peut répondre tout de suite.`
                           : `<b>${n} &gt; 1</b> : il faut d'abord connaître factorielle(${n - 1}).`,
        { vars: { n }, note: `${n} <= 1 → ${base ? "vrai" : "faux"}`, dessin: D(), c: appels });
      if (base) {
        moi.etat = "rend"; moi.val = 1;
        P("return 1", `factorielle(${n}) renvoie <b>1</b> : sa case se dépile.`, { vars: { n }, dessin: D(), c: appels });
        pile.pop();
        return 1;
      }
      moi.etat = "attend";
      P("return n * factorielle(n - 1)", `factorielle(${n}) se met en attente : elle appelle factorielle(${n - 1}).`,
        { vars: { n }, dessin: D(), c: appels });
      const r = f(n - 1);
      moi.etat = "rend"; moi.val = n * r;
      P("return n * factorielle(n - 1)", `factorielle(${n - 1}) a renvoyé ${r} : factorielle(${n}) calcule <b>${n} × ${r} = ${n * r}</b>.`,
        { vars: { n, r }, note: `${n} * ${r} = ${n * r}`, dessin: D(), c: appels });
      pile.pop();
      return n * r;
    }
    const res = f(n0);
    P("print(factorielle(5))", `Toutes les cases sont dépilées : on affiche <b>${res}</b>.`, { vars: { resultat: res }, dessin: D(res), c: appels });
  },
  dessiner(t, zone) {
    const e = t.extra, W = 520, H = 250, m = 40, top = 44, bas = H - 14;
    // la hauteur d'une case vient du nombre de cases : la pile tient toujours dans le cadre
    const nb = Math.max(1, e.pile.length), gap = 6;
    const hb = Math.min(34, (bas - top - gap * (nb - 1)) / nb);
    const fs = Math.max(11, Math.min(15, hb * 0.45));
    let s = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:260px;font-family:system-ui,sans-serif">`;
    s += `<text x="${m}" y="24" font-size="12" fill="#aab">pile d'appels (le dernier appel est en haut)</text>`;
    if (e.fin !== null) {
      s += `<rect x="${W / 2 - 120}" y="${H / 2 - 30}" width="240" height="60" rx="8" fill="#1f5a3a" stroke="#6fe898" stroke-width="2"/>`;
      s += `<text x="${W / 2}" y="${H / 2 + 7}" text-anchor="middle" font-size="20" font-weight="700" fill="#e8e8f2">résultat : ${e.fin}</text>`;
    }
    e.pile.forEach((f, k) => {
      const y = bas - (k + 1) * hb - k * gap, cy = y + hb / 2, actif = k === e.pile.length - 1;
      const col = f.etat === "rend" ? ["#1f5a3a", "#6fe898"] : actif ? ["#25506a", "#5cc8ff"] : ["#1b1b2a", "#34344a"];
      s += `<rect x="${m}" y="${y}" width="${W - 2 * m}" height="${hb}" rx="8" fill="${col[0]}" stroke="${col[1]}" stroke-width="2"/>`;
      s += `<text x="${m + 14}" y="${cy + fs * 0.35}" font-size="${fs}" font-weight="700" fill="#e8e8f2">factorielle(${f.n})</text>`;
      const droite = f.etat === "rend" ? `renvoie ${f.val}` : f.etat === "attend" ? `attend factorielle(${f.n - 1})` : `n = ${f.n}`;
      s += `<text x="${W - m - 14}" y="${cy + fs * 0.35}" text-anchor="end" font-size="${fs}" fill="${f.etat === "rend" ? "#6fe898" : f.etat === "attend" ? "#aab" : "#5cc8ff"}">${droite}</text>`;
    });
    s += `</svg>`;
    zone.innerHTML = s;
  },
};
