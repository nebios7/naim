"""Sort the tasks shared by Naim users before a training run. Ratings are never trusted on their own.

Usage (project owner):
  hf download redhamohamed/naim-feedback --repo-type dataset --local-dir ~/naim-feedback
  python3 tools/curate_feedback.py ~/naim-feedback/data
Then read ~/.naim/apprentissage/communaute/echantillon.md; add the ids you reject to exclus.txt (same folder,
one per line) and run it again.
The accepted tasks become training steps in ~/.naim/apprentissage/dataset/communaute_steps.jsonl, which
prepare_v3.py adds to the training data.

Filters, in order:
 1. deletion requests: every task of an installation that asked for deletion is dropped
 2. duplicates and malformed tasks
 3. safety: prompt-injection attempts, destructive or exfiltration commands
 4. rating vs objective signals (finished, plan done, verified, few errors):
      Bon + success      -> accepted          Bon + failure      -> dropped (contradiction)
      Correct + success  -> accepted          Correct + failure  -> dropped (neutral rating, failed task)
      Mauvais + failure  -> kept as negative  Mauvais + success  -> to review
 5. reliability per installation: >30 % contradictions (5+ tasks) -> all its tasks dropped
 6. cap: one installation may not exceed 5 % of the accepted tasks (min 3)
 7. manual exclusions from exclus.txt
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import learning  # noqa: E402  (to build training steps exactly like the app does)

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "data").expanduser()
OUT = learning.BASE / "communaute"  # user data: kept outside the code repository
OUT.mkdir(parents=True, exist_ok=True)
EXCLUDED = OUT / "exclus.txt"
DANGER = re.compile(r"(?i)(ignore (all |the )?(previous|prior) instructions|oublie (toutes )?tes instructions|system prompt|"
                    r"rm\s+-rf\s+(/|~)(\s|$)|:\(\)\s*\{|mkfs|dd\s+if=|curl[^|\n]*\|\s*(ba|z)?sh|wget[^|\n]*\|\s*(ba|z)?sh|"
                    r"\.ssh/id_|/etc/shadow|base64\s+-d[^|\n]*\|\s*(ba)?sh)")


def load():
    items, deleted = [], set()
    for f in sorted(SRC.glob("submissions-*.jsonl")):
        for line in f.read_text().splitlines():
            try:
                items.append(json.loads(line))
            except ValueError:
                pass
    for f in SRC.glob("deletions*.jsonl"):
        for line in f.read_text().splitlines():
            try:
                deleted.add(json.loads(line)["install"])
            except (ValueError, KeyError):
                pass
    return items, deleted


def success(sig):
    return (sig.get("outcome") == "answer" and not sig.get("todos_left") and sig.get("verified") is not False
            and (sig.get("errors") or 0) <= max(2, (sig.get("steps") or 0) // 4))


def failure(sig):
    return sig.get("outcome") in ("loop", "max_steps", "error", "stopped") or sig.get("verified") is False


def main():
    items, deleted = load()
    excluded = set(EXCLUDED.read_text().split()) if EXCLUDED.exists() else set()
    stats = Counter(total=len(items))
    uniq = {}
    for it in items:
        if it.get("install") in deleted:
            stats["supprimées à la demande"] += 1
        elif it.get("id") in uniq:
            stats["doublons"] += 1
        elif it.get("id") in excluded:
            stats["exclues à la main"] += 1
        elif DANGER.search(json.dumps(it.get("messages", []), ensure_ascii=False)):
            stats["refusées (sécurité)"] += 1
        else:
            uniq[it["id"]] = it
    accepted, negatives, review = [], [], []
    per_install = defaultdict(lambda: [0, 0])  # [tasks, contradictions]
    for it in uniq.values():
        sig, r = it.get("signals") or {}, it.get("rating")
        per_install[it["install"]][0] += 1
        if r == 1 and success(sig):
            accepted.append(it)
        elif r == 1:
            per_install[it["install"]][1] += 1
            stats["« Bon » contredits par les signaux"] += 1
        elif r == 0:  # Correct: neutral, learned only when the task really succeeded
            if success(sig):
                accepted.append(it)
            else:
                stats["« Correct » sur une tâche échouée"] += 1
        elif r == -1 and (failure(sig) or not success(sig)):
            negatives.append(it)
        else:
            per_install[it["install"]][1] += 1
            review.append(it)
    suspicious = {i for i, (n, bad) in per_install.items() if n >= 5 and bad / n > 0.30}
    stats["installations peu fiables"] = len(suspicious)
    accepted = [it for it in accepted if it["install"] not in suspicious]
    cap = max(3, int(0.05 * max(len(accepted), 1)) + 1)
    random.Random(7).shuffle(accepted)
    kept, count = [], Counter()
    for it in accepted:
        if count[it["install"]] < cap:
            kept.append(it)
            count[it["install"]] += 1
        else:
            stats["au-delà du plafond par installation"] += 1

    def dump(name, rows):
        with open(OUT / name, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    dump("acceptes.jsonl", kept)
    dump("negatifs.jsonl", negatives)
    dump("a_revoir.jsonl", review)
    steps = [ex for it in kept for ex in learning._steps({**it, "task": it.get("task", "")})]
    learning.DATASET.mkdir(parents=True, exist_ok=True)
    dump_path = learning.DATASET / "communaute_steps.jsonl"
    with open(dump_path, "w", encoding="utf-8") as f:
        for ex in steps:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    sample = random.Random(1).sample(kept, min(30, len(kept)))
    lines = ["# Échantillon à vérifier avant l'entraînement", "",
             "Ajoute l'identifiant d'une tâche douteuse dans `exclus.txt` (même dossier), puis relance le script.", ""]
    for it in sample:
        final = next((m.get("content") for m in reversed(it["messages"]) if m.get("role") == "assistant" and m.get("content")), "")
        lines += [f"## `{it['id']}`", f"**Demande** : {it.get('task', '')[:300]}", f"**Outils** : {', '.join(it.get('tools', []))}",
                  f"**Signaux** : {it.get('signals')}", "", "**Réponse finale** :", "", (final or "")[:800], ""]
    (OUT / "echantillon.md").write_text("\n".join(lines))
    report = [f"- {k} : {v}" for k, v in stats.items()] + [
        f"- **acceptées pour l'entraînement : {len(kept)}** ({len(steps)} exemples d'étapes)",
        f"- négatives gardées pour plus tard : {len(negatives)}", f"- à revoir (« Mauvais » sur une tâche réussie) : {len(review)}",
        f"- plafond par installation : {cap} tâches"]
    (OUT / "rapport.md").write_text("# Tri des tâches partagées\n\n" + "\n".join(report) + "\n")
    print("\n".join(report))
    print(f"\nÉtapes d'entraînement : {dump_path}\nÉchantillon à vérifier : {OUT / 'echantillon.md'}")


if __name__ == "__main__":
    main()
