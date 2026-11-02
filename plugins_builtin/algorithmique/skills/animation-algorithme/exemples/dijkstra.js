// Plus court chemin de Dijkstra (type "autre") : le modèle pour un GRAPHE. dessiner() place les nœuds, les arêtes et
// leurs poids ; le nœud traité, les nœuds définitifs et les distances changent à chaque étape.
const ALGO = {
  titre: "Toujours le plus proche d'abord",
  sous_titre: "Algorithme de Dijkstra",
  fichier: "dijkstra.py",
  langage: "python",
  type: "autre",
  compteurs: ["NŒUDS DÉFINITIFS"],
  valeurs: [4, 1, 2, 5, 8, 3],                 // les poids des arêtes A-B, A-C, C-B, B-D, C-D, D-E
  code: `
def dijkstra(graphe, depart):
    dist = {n: inf for n in graphe}
    dist[depart] = 0
    fait = set()
    while len(fait) < len(graphe):
        u = min((n for n in graphe if n not in fait), key=dist.get)
        fait.add(u)
        for v, poids in graphe[u]:
            if dist[u] + poids < dist[v]:
                dist[v] = dist[u] + poids
    return dist`,
  build(v, P) {
    const w = [0, 1, 2, 3, 4, 5].map((i) => Math.max(1, Math.round(+v[i] || 1)));
    const aretes = [["A", "B", w[0]], ["A", "C", w[1]], ["C", "B", w[2]], ["B", "D", w[3]], ["C", "D", w[4]], ["D", "E", w[5]]];
    const noeuds = ["A", "B", "C", "D", "E"], dist = {}, fait = [];
    noeuds.forEach((n) => (dist[n] = Infinity));
    const d = (o) => ({ aretes, dist: { ...dist }, fait: fait.slice(), ...o });
    const txt = (x) => (x === Infinity ? "∞" : x);
    P(2, "Au départ, toutes les distances sont inconnues : <b>∞</b>.", { dessin: d({}) });
    dist.A = 0;
    P(3, "Le départ <b>A</b> est à distance <b>0</b> de lui-même.", { vars: { "dist[A]": 0 }, dessin: d({}) });
    while (fait.length < noeuds.length) {
      const u = noeuds.filter((n) => !fait.includes(n)).sort((x, y) => dist[x] - dist[y])[0];
      P(6, `Parmi les nœuds pas encore faits, le plus proche est <b>${u}</b> (distance ${txt(dist[u])}).`, { vars: { u }, dessin: d({ u }) });
      fait.push(u);
      P(7, `<b>${u}</b> est définitif : aucun autre chemin ne peut être plus court.`, { c: fait.length, vars: { u }, dessin: d({ u }) });
      for (const [x, y, p] of aretes) {
        if (x !== u && y !== u) continue;
        const vv = x === u ? y : x;
        if (fait.includes(vv)) continue;
        const mieux = dist[u] + p < dist[vv];
        P(9, mieux ? `Par ${u}, on atteint <b>${vv}</b> en ${dist[u]} + ${p} = <b>${dist[u] + p}</b> : mieux que ${txt(dist[vv])}.`
                    : `Par ${u}, ${vv} coûterait ${dist[u] + p} : pas mieux que <b>${txt(dist[vv])}</b>.`,
          { vars: { u, v: vv, poids: p }, note: `${dist[u]} + ${p} ${mieux ? "<" : "≥"} ${txt(dist[vv])}`, dessin: d({ u, v: vv }) });
        if (mieux) {
          dist[vv] = dist[u] + p;
          P(10, `dist[${vv}] devient <b>${dist[vv]}</b>.`, { vars: { [`dist[${vv}]`]: dist[vv] }, dessin: d({ u, v: vv }) });
        }
      }
    }
    P(11, "Tous les nœuds sont faits : chaque distance est la plus courte depuis A.", { dessin: d({ fini: true }) });
  },
  dessiner(t, zone) {
    const g = t.extra, pos = { A: [60, 130], B: [220, 50], C: [220, 210], D: [380, 130], E: [500, 130] };
    let s = "";
    for (const [x, y, p] of g.aretes) {
      const on = g.u && g.v && ((x === g.u && y === g.v) || (y === g.u && x === g.v));
      const [x1, y1] = pos[x], [x2, y2] = pos[y];
      s += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${on ? "#5cc8ff" : "#3a3a55"}" stroke-width="${on ? 4 : 2.5}"/>`
         + `<rect x="${(x1 + x2) / 2 - 13}" y="${(y1 + y2) / 2 - 12}" width="26" height="22" rx="6" fill="#12121c" stroke="#34344a"/>`
         + `<text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 + 4}" fill="#aab" font-size="13" text-anchor="middle">${p}</text>`;
    }
    for (const [n, [x, y]] of Object.entries(pos)) {
      const fait = g.fait.includes(n), cur = n === g.u && !g.fini, vis = n === g.v;
      const fill = cur ? "#5a3f9e" : fait ? "#1f5a3a" : vis ? "#25506a" : "#1b1b2a";
      const bord = cur ? "#b69cff" : fait ? "#6fe898" : vis ? "#5cc8ff" : "#4b4b86";
      const dv = g.dist[n] === Infinity || g.dist[n] == null ? "∞" : g.dist[n];
      s += `<circle cx="${x}" cy="${y}" r="24" fill="${fill}" stroke="${bord}" stroke-width="2.5"/>`
         + `<text x="${x}" y="${y + 6}" fill="#e8e8f2" font-size="18" font-weight="700" text-anchor="middle">${n}</text>`
         + `<text x="${x}" y="${y + 44}" fill="${fait ? "#6fe898" : "#ffc53d"}" font-size="14" text-anchor="middle" font-family="ui-monospace,Menlo,monospace">${dv}</text>`;
    }
    zone.innerHTML = `<svg viewBox="0 0 560 270" style="width:100%;height:260px">${s}</svg>`;
  },
};
