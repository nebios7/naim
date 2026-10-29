#!/usr/bin/env python3
"""Which skill each sentence picks, exactly as Naim chooses it (to check a new skill's words before saying it is learnt).

  verifier_skill.py "fais-moi un cours en pdf" "fusionne ces deux pdf" …
  verifier_skill.py --attendu pdf-pro "fais-moi un cours en pdf"     exit code 1 if a sentence picks another skill
"""
import sys
from pathlib import Path

for d in (Path.home() / "Library/Application Support/Naim/app", Path(__file__).resolve().parents[4]):
    if (d / "extensions.py").is_file():
        sys.path.insert(0, str(d))
        break
import extensions as ext  # noqa: E402

args, want = sys.argv[1:], None
if args[:1] == ["--attendu"] and len(args) > 1:
    want, args = args[1], args[2:]
if not args:
    sys.exit(__doc__)
bad = 0
for sentence in args:
    s = ext.match_skill(sentence)
    got = s["name"] if s else "(aucun skill)"
    ok = want is None or got == want
    bad += not ok
    print(f"{'ok ' if ok else 'NON'}  {got:24} ← {sentence}")
if want and bad:
    print(f"\n{bad} phrase(s) ne choisissent pas « {want} » : ajuste ses mots (triggers du plugin.json) ou sa description, puis relance.")
sys.exit(1 if bad else 0)
