const ALGO = {
  titre: "Tant que c'est vrai, on recommence",
  sous_titre: "Boucle while",
  fichier: "boucle_while.py",
  langage: "python",
  type: "autre",
  valeurs: [10, 20, 2],          // x de départ, limite, pas (l'élève peut changer : 0, 7, 3…)
  compteurs: ["TOURS"],
  code: `
x = 10
limite = 20
pas = 2
tours = 0
while x < limite:
    tours += 1
    x += pas
    print(x)
print("fini :", tours, "tours")`,
  build(a, P) {
    let x = a[0];
    const limite = a[1], pas = a[2], depart = a[0];
    let tours = 0;
    const sortie = [], passes = [x];
    const D = (cond) => ({ x, limite, pas, tours, depart, cond, sortie: sortie.slice(), passes: passes.slice() });
    P("x = 10", `x part de <b>${x}</b>.`, { vars: { x }, dessin: D(null) });
    P("limite = 20", `La boucle s'arrêtera quand x atteindra <b>${limite}</b>.`, { vars: { x, limite }, dessin: D(null) });
    P("pas = 2", `À chaque tour, x avance de <b>${pas}</b>.`, { vars: { x, limite, pas }, dessin: D(null) });
    P("tours = 0", "Le compteur de tours commence à 0.", { vars: { x, limite, pas, tours }, dessin: D(null), c: 0 });
    while (true) {
      const vrai = x < limite;
      P("while x < limite:", vrai ? `<b>${x} &lt; ${limite}</b> est vrai : on entre dans la boucle.`
                                  : `<b>${x} &lt; ${limite}</b> est faux : on sort de la boucle.`,
        { vars: { x, limite, pas, tours }, note: `${x} < ${limite} → ${vrai ? "vrai" : "faux"}`, dessin: D(vrai), c: tours });
      if (!vrai) break;
      if (tours >= 12) {  // pas nul ou négatif : la vraie boucle ne s'arrêterait jamais
        P("while x < limite:", `x n'atteint jamais ${limite} : cette boucle tournerait <b>sans fin</b>. On l'arrête ici.`,
          { vars: { x, limite, pas, tours }, dessin: D(true), c: tours });
        return;
      }
      tours += 1;
      P("tours += 1", `Un tour de plus : <b>tours = ${tours}</b>.`, { vars: { x, limite, pas, tours }, dessin: D(true), c: tours });
      x += pas;
      passes.push(x);
      P("x += pas", `x avance de ${pas} : <b>x = ${x}</b>.`, { vars: { x, limite, pas, tours }, note: `x = ${x - pas} + ${pas}`, dessin: D(true), c: tours });
      sortie.push(String(x));
      P("print(x)", `On affiche <b>${x}</b>, puis on remonte tester la condition.`, { vars: { x, limite, pas, tours }, dessin: D(true), c: tours });
    }
    sortie.push(`fini : ${tours} tours`);
    P('print("fini :", tours, "tours")', `La boucle a tourné <b>${tours} fois</b>. Le programme continue après elle.`,
      { vars: { x, limite, pas, tours }, dessin: D(false), c: tours });
  },
  dessiner(t, zone) {
    const e = t.extra, W = 520, H = 250, m = 40;
    // l'échelle vient des valeurs : tout reste dans le cadre, quelles que soient x, limite et pas
    const lo = Math.min(0, e.depart, ...e.passes), hi = Math.max(e.limite, ...e.passes) || 1;
    const X = (v) => m + (v - lo) / ((hi - lo) || 1) * (W - 2 * m);
    const ty = 120;
    const condCol = e.cond === null ? ["#1b1b2a", "#34344a", "#aab"] : e.cond ? ["#1f5a3a", "#6fe898", "#e8e8f2"] : ["#4a1d26", "#e5566c", "#e8e8f2"];
    const condTxt = e.cond === null ? "x < limite ?" : `${e.x} < ${e.limite}  →  ${e.cond ? "vrai" : "faux"}`;
    let s = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:260px;font-family:system-ui,sans-serif">`;
    // la condition, en haut : verte quand on entre, rouge quand on sort
    s += `<rect x="${W / 2 - 110}" y="14" width="220" height="40" rx="8" fill="${condCol[0]}" stroke="${condCol[1]}" stroke-width="2"/>`;
    s += `<text x="${W / 2}" y="40" text-anchor="middle" font-size="17" font-weight="700" fill="${condCol[2]}">${condTxt}</text>`;
    // l'axe et ses graduations
    s += `<line x1="${m}" y1="${ty}" x2="${W - m}" y2="${ty}" stroke="#34344a" stroke-width="2"/>`;
    const step = Math.max(1, Math.ceil((hi - lo) / 10));
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
      s += `<line x1="${X(v)}" y1="${ty - 5}" x2="${X(v)}" y2="${ty + 5}" stroke="#34344a" stroke-width="2"/>`;
      s += `<text x="${X(v)}" y="${ty + 32}" text-anchor="middle" font-size="11" fill="#aab">${v}</text>`;
    }
    // la limite : la ligne d'arrivée
    s += `<line x1="${X(e.limite)}" y1="${ty - 44}" x2="${X(e.limite)}" y2="${ty + 8}" stroke="#ffc53d" stroke-width="2" stroke-dasharray="5 4"/>`;
    s += `<text x="${X(e.limite)}" y="${ty - 50}" text-anchor="middle" font-size="12" font-weight="700" fill="#ffc53d">limite ${e.limite}</text>`;
    // les valeurs déjà prises par x, reliées par des sauts
    e.passes.slice(0, -1).forEach((v, k) => {
      const a = X(v), b = X(e.passes[k + 1]);
      s += `<path d="M ${a} ${ty - 6} Q ${(a + b) / 2} ${ty - 34} ${b} ${ty - 6}" fill="none" stroke="#5a3f9e" stroke-width="2"/>`;
      s += `<circle cx="${a}" cy="${ty}" r="5" fill="#5a3f9e"/>`;
    });
    // x maintenant
    const cx = X(e.x);
    s += `<circle cx="${cx}" cy="${ty}" r="16" fill="#25506a" stroke="#5cc8ff" stroke-width="2"/>`;
    s += `<text x="${cx}" y="${ty + 5}" text-anchor="middle" font-size="13" font-weight="700" fill="#e8e8f2">x</text>`;
    s += `<text x="${cx}" y="${ty + 54}" text-anchor="middle" font-size="15" font-weight="700" fill="#5cc8ff">x = ${e.x}</text>`;
    // la sortie du programme, en bas : ce que print a affiché
    s += `<rect x="${m}" y="184" width="${W - 2 * m}" height="56" rx="8" fill="#171724" stroke="#2c2c40" stroke-width="2"/>`;
    s += `<text x="${m + 12}" y="201" font-size="11" fill="#aab">sortie</text>`;
    const out = e.sortie.slice(-6).join("   ");
    s += `<text x="${m + 12}" y="226" font-size="15" font-family="ui-monospace,Menlo,monospace" style="white-space:pre" fill="#7ee0a0">${out || "(rien encore)"}</text>`;
    s += `</svg>`;
    zone.innerHTML = s;
  },
};
