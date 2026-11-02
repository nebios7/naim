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
      T.forEach(function (t) { used[t.line] = 1; if (!t.msg) c.sans_message = (c.sans_message || 0) + 1; });
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
    print("\nLa simulation est juste." if good else "\nCorrige build() dans le fichier de l'algorithme puis relance.")
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
