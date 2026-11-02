// Théorème de Pythagore (type "autre") : le modèle pour une CONSTRUCTION GÉOMÉTRIQUE. dessiner() construit la figure
// étape par étape (triangle, carrés sur les côtés, hypoténuse), à l'échelle des valeurs de l'élève.
const ALGO = {
  titre: "Deux carrés font le troisième",
  sous_titre: "Théorème de Pythagore",
  fichier: "pythagore.py",
  langage: "python",
  type: "autre",
  compteurs: [],                                // pas de compteur ici
  valeurs: [3, 4],                              // les deux côtés de l'angle droit
  code: `
from math import sqrt

def hypotenuse(a, b):
    a2 = a * a
    b2 = b * b
    c2 = a2 + b2
    c = sqrt(c2)
    return c`,
  build(v, P) {
    const a = Math.abs(+v[0] || 3), b = Math.abs(+v[1] || 4), r = (x) => Math.round(x * 100) / 100;
    P(3, `Un triangle rectangle, de côtés <b>a = ${a}</b> et <b>b = ${b}</b> autour de l'angle droit.`, { vars: { a, b }, dessin: { a, b, etape: 0 } });
    P(4, `Le carré construit sur a a pour aire <b>${a} × ${a} = ${a * a}</b>.`, { vars: { a, b, a2: a * a }, dessin: { a, b, etape: 1 } });
    P(5, `Le carré construit sur b a pour aire <b>${b} × ${b} = ${b * b}</b>.`, { vars: { a2: a * a, b2: b * b }, dessin: { a, b, etape: 2 } });
    P(6, `Pythagore : le carré sur l'hypoténuse vaut la somme des deux : <b>${a * a} + ${b * b} = ${a * a + b * b}</b>.`,
      { vars: { a2: a * a, b2: b * b, c2: a * a + b * b }, note: `${a * a} + ${b * b}`, dessin: { a, b, etape: 3 } });
    const c = Math.sqrt(a * a + b * b);
    P(7, `Son côté est la racine carrée : <b>c = √${a * a + b * b} ≈ ${r(c)}</b>.`, { vars: { c2: a * a + b * b, c: r(c) }, dessin: { a, b, etape: 4, c: r(c) } });
    P(8, `L'hypoténuse mesure <b>${r(c)}</b>.`, { vars: { c: r(c) }, dessin: { a, b, etape: 4, c: r(c) } });
  },
  dessiner(t, zone) {
    const { a, b, etape, c } = t.extra, k = 110 / Math.max(a, b), A = a * k, B = b * k;
    const O = [0, 0], X = [B, 0], Y = [0, -A];                         // angle droit en O, b horizontal, a vertical
    const pts = [], pt = (p) => p.map((v) => v.toFixed(1)).join(",");
    const carre = (p, q, coul, aire, on) => {        // carré construit vers l'extérieur du triangle sur le segment p→q
      const dx = q[0] - p[0], dy = q[1] - p[1], r = [q[0] + dy, q[1] - dx], s = [p[0] + dy, p[1] - dx];
      pts.push(p, q, r, s);
      const mx = (p[0] + r[0]) / 2, my = (p[1] + r[1]) / 2;
      return on ? `<polygon points="${pt(p)} ${pt(q)} ${pt(r)} ${pt(s)}" fill="${coul}2e" stroke="${coul}" stroke-width="2"/>`
        + `<text x="${mx}" y="${my + 6}" fill="${coul}" font-size="18" font-weight="700" text-anchor="middle">${aire}</text>` : "";
    };
    const s = carre(O, Y, "#5cc8ff", a * a, etape >= 1) + carre(X, O, "#b69cff", b * b, etape >= 2)
      + carre(Y, X, "#3cc46e", a * a + b * b, etape >= 3)
      + `<polygon points="${pt(O)} ${pt(X)} ${pt(Y)}" fill="#1b1b2a" stroke="#e8e8f2" stroke-width="2.5" stroke-linejoin="round"/>`
      + `<path d="M12,0 v-12 h-12" fill="none" stroke="#aab" stroke-width="1.5"/>`
      + `<text x="8" y="${-A / 2 + 5}" fill="#5cc8ff" font-size="14">a = ${a}</text>`          // dans le triangle, le long des côtés
      + `<text x="${B / 2 - 14}" y="-8" fill="#b69cff" font-size="14" text-anchor="middle">b = ${b}</text>`
      + (etape >= 4 ? `<text x="${B / 2 + 10}" y="${-A / 2 - 6}" fill="#ffc53d" font-size="15" font-weight="700">c ≈ ${c}</text>` : "");
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]), m = 24;  // le cadre suit la figure : rien n'est coupé
    const x0 = Math.min(...xs) - m, y0 = Math.min(...ys) - m, w = Math.max(...xs) - x0 + m, h = Math.max(...ys) - y0 + m;
    zone.innerHTML = `<svg viewBox="${x0} ${y0} ${w} ${h}" style="width:100%;height:260px">${s}</svg>`;
  },
};
