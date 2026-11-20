"""Visual simulations of an algorithm: the engine (moteur.html) is fixed and tested, only the algorithm changes.

    python3 simulation.py creer <algo.js> <page.html>    the page = the engine + this algorithm, then checked
    python3 simulation.py verifier <algo.js | page.html> runs the algorithm on several inputs and says what is wrong

<algo.js> defines `const ALGO = {titre, sous_titre, fichier, langage, type, valeurs, code, build(a, P) {...}}`
(see exemples/). The check runs it for real (node, or the JavaScript built into macOS): syntax, line numbers,
an end, and for a sort a sorted array, for a search the right cell, on its values and on harder ones.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "moteur.html"
START, END = "// ==== ALGO ====", "// ==== FIN ALGO ===="

HARNESS = r"""
var __res = {cases: [], warnings: [], fatal: null};
// what is drawn outside its <svg viewBox> is cut off on the page: say which element, where, and the frame
function outside(html) {
  var m = /<svg[^>]*viewBox="\s*(-?[\d.]+)[\s,]+(-?[\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/.exec(html);
  if (!m) return '';
  var x0 = +m[1], y0 = +m[2], W = +m[3], H = +m[4], re = /<(\w+)\b([^>]*)>/g, t, bad = [];
  while ((t = re.exec(html)) && bad.length < 3) {
    if (/^(svg|g|defs|style|marker|linearGradient|stop|tspan)$/i.test(t[1])) continue;
    var at = {}, ar = /([\w-]+)="(-?[\d.]+)"/g, q;
    while ((q = ar.exec(t[2]))) at[q[1]] = +q[2];
    var xs = ['x', 'cx', 'x1', 'x2'].filter(function (k) { return k in at; }).map(function (k) { return at[k]; });
    var ys = ['y', 'cy', 'y1', 'y2'].filter(function (k) { return k in at; }).map(function (k) { return at[k]; });
    if ('width' in at && 'x' in at) xs.push(at.x + at.width);
    if ('height' in at && 'y' in at) ys.push(at.y + at.height);
    var r = at.r || 0, out = xs.some(function (v) { return v - r < x0 - 1 || v + r > x0 + W + 1; }) || ys.some(function (v) { return v - r < y0 - 1 || v + r > y0 + H + 1; });
    if (out) bad.push('<' + t[1] + ' ' + t[2].trim().slice(0, 60) + '>');
  }
  return bad.length ? 'le dessin sort du cadre viewBox="' + m[1] + ' ' + m[2] + ' ' + W + ' ' + H + '" et sera coupé : ' + bad.join(', ')
    + '. Calcule les positions à partir de ce qu\'il y a à montrer : une échelle tirée des valeurs (x = marge + (v - min) / (max - min) * (largeur - 2 * marge)), '
    + 'une taille de case tirée du nombre de cases (h = hauteur utile / nombre), pour que tout reste dedans.' : '';
}
// two texts on top of each other, or two boxes that cut each other (neither inside the other), cannot be read
function overlaps(html) {
  var num = function (a, k, d) { var q = new RegExp('(?:^|\\s)' + k + '="(-?[\\d.]+)"').exec(a); return q ? +q[1] : d; };
  var texts = [], rects = [], re = /<text\b([^>]*)>([\s\S]*?)<\/text>/g, t;
  while ((t = re.exec(html))) {
    var a = t[1], str = t[2].replace(/<[^>]+>/g, '').replace(/&\w+;/g, '_').trim();
    if (!str) continue;
    var fs = num(a, 'font-size', 14), w = str.length * fs * 0.56, x = num(a, 'x', 0), y = num(a, 'y', 0);
    var anc = (/text-anchor="(\w+)"/.exec(a) || [])[1];
    var x0 = anc === 'middle' ? x - w / 2 : anc === 'end' ? x - w : x;
    texts.push({x0: x0, x1: x0 + w, y0: y - fs * 0.78, y1: y + fs * 0.22, s: str});
  }
  var rr = /<rect\b([^>]*)>/g;
  while ((t = rr.exec(html))) {
    var b = t[1], rw = num(b, 'width', 0), rh = num(b, 'height', 0);
    if (rw > 0 && rh > 0) rects.push({x0: num(b, 'x', 0), y0: num(b, 'y', 0), x1: num(b, 'x', 0) + rw, y1: num(b, 'y', 0) + rh});
  }
  var inter = function (p, q) { return Math.max(0, Math.min(p.x1, q.x1) - Math.max(p.x0, q.x0)) * Math.max(0, Math.min(p.y1, q.y1) - Math.max(p.y0, q.y0)); };
  var area = function (p) { return (p.x1 - p.x0) * (p.y1 - p.y0); };
  for (var i = 0; i < texts.length; i++) for (var j = i + 1; j < texts.length; j++) {
    if (inter(texts[i], texts[j]) > 0.25 * Math.min(area(texts[i]), area(texts[j])))
      return 'les textes « ' + texts[i].s.slice(0, 30) + ' » et « ' + texts[j].s.slice(0, 30) + ' » se chevauchent : donne à chaque texte sa place (une ligne, une case, un côté).';
  }
  var inside = function (p, q) { return p.x0 >= q.x0 - 1 && p.x1 <= q.x1 + 1 && p.y0 >= q.y0 - 1 && p.y1 <= q.y1 + 1; };
  for (var i2 = 0; i2 < rects.length; i2++) for (var j2 = i2 + 1; j2 < rects.length; j2++) {
    var P1 = rects[i2], Q1 = rects[j2];
    if (inter(P1, Q1) > 4 && !inside(P1, Q1) && !inside(Q1, P1))
      return 'deux cases se coupent (x=' + Math.round(P1.x0) + ' y=' + Math.round(P1.y0) + ' et x=' + Math.round(Q1.x0) + ' y=' + Math.round(Q1.y0) + ') : une case est soit à côté d\'une autre, soit entièrement dedans.';
  }
  return '';
}
try {
  if (typeof ALGO === 'undefined') throw new Error("ALGO n'est pas défini : le fichier doit commencer par « const ALGO = { … } ».");
  if (typeof ALGO.build !== 'function') throw new Error("ALGO.build(a, P) manque : c'est la fonction qui exécute l'algorithme.");
  var lines = codeLines(ALGO);
  if (!lines.length) throw new Error("ALGO.code est vide : mets le code montré, en texte simple.");
  if (/<span|&lt;|&gt;|&amp;/.test(ALGO.code)) throw new Error("ALGO.code contient du HTML (<span>, &lt;…) : écris le code en texte simple, la couleur est automatique.");
  var vals = (ALGO.valeurs || [5, 2, 8, 1, 9, 3]).slice();
  var nums = vals.filter(function (v) { return typeof v === 'number'; }).length === vals.length;
  var inputs = [[vals, ALGO.cible]];
  if (ALGO.type === 'tri' && nums) {
    inputs.push([vals.slice().sort(function (x, y) { return x - y; })], [vals.slice().sort(function (x, y) { return y - x; })],
                [[3, 1, 3, 2, 1, 2]], [[7]], [[2, 1]]);
  }
  if (ALGO.type === 'recherche') {
    var s = vals.slice();
    [s[0], s[s.length - 1], s[Math.floor(s.length / 2)]].forEach(function (x) { inputs.push([s, x]); });
    var absent = nums ? Math.max.apply(null, s) + 1 : '§';
    inputs.push([s, absent]);
  }
  var used = {};
  inputs.forEach(function (inp) {
    var v = inp[0], x = inp[1], c = {valeurs: v, cible: x, ok: true, pourquoi: ''};
    try {
      var T = makeTrace(ALGO, v, x), last = T[T.length - 1];
      c.etapes = T.length; c.fin = last.a;
      T.forEach(function (t, k) {
        used[t.line] = 1; if (!t.msg) c.sans_message = (c.sans_message || 0) + 1;
        // a value that does not exist shown to the student (« 5 × null », « i = undefined »): the algorithm is wrong there
        var shown = [t.msg, t.note].concat(Object.keys(t.vars || {}).map(function (n) { return n + ' = ' + t.vars[n]; })).join(' | ');
        var bad = /\b(undefined|NaN|null)\b|\[object Object\]/.exec(shown.replace(/<[^>]+>/g, ''));
        if (bad && c.ok) { c.ok = false; c.pourquoi = 'étape ' + (k + 1) + ' : on montre « ' + bad[0] + ' » à l\'élève (' + shown.replace(/<[^>]+>/g, '').slice(0, 140) + ') : une valeur n\'est pas encore calculée ou mal passée'; }
      });
      if (ALGO.type === 'tri') {
        var want = v.slice().sort(function (p, q) { return p - q; });
        if (ALGO.ordre === 'decroissant') want.reverse();
        if (JSON.stringify(last.a) !== JSON.stringify(want)) { c.ok = false; c.pourquoi = 'tableau final ' + JSON.stringify(last.a) + ' au lieu de ' + JSON.stringify(want); }
      }
      if (ALGO.type === 'recherche') {
        var present = v.indexOf(x) >= 0;
        if (present && (last.found === null || v[last.found] !== x)) { c.ok = false; c.pourquoi = x + ' est dans le tableau mais la dernière étape ne le montre pas trouvé (found: case)'; }
        if (!present && last.found !== null) { c.ok = false; c.pourquoi = x + " n'est pas dans le tableau mais la dernière étape dit trouvé"; }
      }
    } catch (e) { c.ok = false; c.pourquoi = String(e && e.message || e); }
    __res.cases.push(c);
  });
  if (typeof ALGO.dessiner === 'function') {  // the drawing is tried on every step: an error there breaks the page too
    var TD = makeTrace(ALGO, vals, ALGO.cible), drawn = 0;
    for (var di = 0; di < TD.length && di < 400; di++) {
      var zone = {innerHTML: '', textContent: '', style: {}, children: [], appendChild: function (e) { this.children.push(e); return e; },
                  querySelector: function () { return null; }, querySelectorAll: function () { return []; }};
      try { ALGO.dessiner(TD[di], zone); }
      catch (e) { __res.dessin = 'dessiner() plante à l\'étape ' + (di + 1) + ' : ' + String(e && e.message || e)
                  + " (elle ne reçoit que l'étape : ce que tu passes dans P(…, { dessin: {…} }) arrive dans etape.extra)"; break; }
      if (zone.innerHTML || zone.children.length) drawn++;
      if (!__res.dessin && zone.innerHTML) { var off = outside(String(zone.innerHTML)) || overlaps(String(zone.innerHTML)); if (off) __res.dessin = 'à l\'étape ' + (di + 1) + ', ' + off; }
    }
    if (!__res.dessin && !drawn) __res.dessin = "dessiner() ne dessine rien : remplis zone.innerHTML (un <svg …>…</svg>)";
  } else if (ALGO.type === 'autre') {
    __res.warnings.push('type "autre" sans dessiner(etape, zone) : ce sont des barres qui seront montrées');
  }
  var never = [];
  lines.forEach(function (l, i) { if (!used[i + 1] && /[A-Za-z0-9]/.test(l) && !/^\s*(\/\/|#|\*>)/.test(l) && l.trim().length > 2 && !/^\s*[{}]\s*$/.test(l)) never.push(i + 1); });
  if (never.length > lines.length / 2) __res.warnings.push('lignes jamais surlignées : ' + never.join(', ') + ' (des P(ligne, …) manquent, ou les numéros sont décalés)');
} catch (e) { __res.fatal = String(e && e.message || e); }
var __out = JSON.stringify(__res);
if (typeof process !== 'undefined' && typeof console !== 'undefined') console.log(__out);
__out;
"""


def _here(p):
    """A path written relative to the work folder, even when the folder's own name was repeated in it."""
    p = Path(os.path.expanduser(p))
    if p.is_absolute() or p.exists():
        return p
    parts = p.parts
    if len(parts) > 1 and parts[0] == Path.cwd().name and Path(*parts[1:]).parent.exists():
        return Path(*parts[1:])
    return p


def algo_text(path):
    """The algorithm block, from an algo .js file or from a page made with this engine."""
    t = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".html", ".htm"):
        if START not in t:
            sys.exit(f"{path.name} n'a pas été faite avec le moteur (pas de bloc « {START} »). "
                     "Écris un fichier algo .js puis : simulation.py creer algo.js page.html")
        return t.split(START, 1)[1].split(END, 1)[0].strip("\n")
    return t


def engine_trace():
    t = ENGINE.read_text(encoding="utf-8")
    return t.split('<script id="trace">', 1)[1].split("</script>", 1)[0]


def run_js(code):
    """Run a script: node if it is there, else the JavaScript built into macOS. Returns (stdout, stderr, ok)."""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "simulation-verif.js"
        f.write_text(code, encoding="utf-8")
        node = shutil.which("node")
        cmd = [node, str(f)] if node else ["osascript", "-l", "JavaScript", str(f)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return "", "l'algorithme tourne sans fin (plus de 60 s) : vérifie la condition de fin des boucles", False
        return r.stdout, r.stderr.replace(str(f), "algo"), r.returncode == 0


def check(path):
    """Print the report; True when the simulation is right."""
    algo = algo_text(path)
    out, err, ok = run_js(algo + "\n" + engine_trace() + "\n" + HARNESS)
    line = out.strip().splitlines()[-1] if out.strip() else ""
    try:
        res = json.loads(line)
    except ValueError:
        m = re.search(r"algo:(\d+)", err) or re.search(r"(\d+):\d+", err)
        where = f" (ligne {m.group(1)} du fichier de l'algorithme)" if m else ""
        msg = next((l for l in err.splitlines() if re.search(r"Error|Erreur", l)), err.strip()[-400:])
        print(f"ERREUR de syntaxe JavaScript{where} : {msg.strip()}")
        print("Rappel : build() est du JavaScript (&& et ||, pas and/or ; let/const ; accolades), "
              "le code montré est du texte simple dans ALGO.code.")
        return False
    if res["fatal"]:
        print(f"ERREUR : {res['fatal']}")
        return False
    good = True
    for c in res["cases"]:
        what = f"valeurs {c['valeurs']}" + (f", cible {c['cible']}" if c.get("cible") is not None else "")
        if c["ok"]:
            print(f"OK   {what} → {c.get('etapes')} étapes, fin {c.get('fin')}")
        else:
            good = False
            print(f"FAUX {what} → {c['pourquoi']}")
        if c.get("sans_message"):
            print(f"     {c['sans_message']} étape(s) sans message : chaque P(ligne, message) explique ce qui se passe")
    if res.get("dessin"):
        good = False
        print(f"FAUX dessin → {res['dessin']}")
    for w in res["warnings"]:
        print(f"À revoir : {w}")
    print("\nLa simulation est juste." if good else "\nCorrige build()" + (" ou dessiner()" if res.get("dessin") else "")
          + " dans le fichier de l'algorithme puis relance.")
    return good


def create(algo_path, page):
    algo = algo_path.read_text(encoding="utf-8")
    if START in algo:
        algo = algo_text(algo_path)
    t = ENGINE.read_text(encoding="utf-8")
    head, rest = t.split(START, 1)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(head + START + "\n" + algo.strip("\n") + "\n" + END + rest.split(END, 1)[1], encoding="utf-8")
    print(f"Page créée : {page.resolve()}")
    return check(page)


def main():
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == "creer":
        src = _here(a[1])
        if not src.exists():
            sys.exit(f"Fichier introuvable : {src}")
        sys.exit(0 if create(src, _here(a[2])) else 1)
    if len(a) == 2 and a[0] == "verifier":
        src = _here(a[1])
        if not src.exists():
            sys.exit(f"Fichier introuvable : {src}")
        sys.exit(0 if check(src) else 1)
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
