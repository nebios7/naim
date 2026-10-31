"""Read Naim's recent conversations and print a short, factual digest to write the improvement report from.

    python3 analyse.py [--jours 7] [--max 40]     the digest of the last days
    python3 analyse.py --conv <id>                the steps of one conversation, in short
    python3 analyse.py --rapport <rapport.html>   the PDF (pdf-pro) in ~/Documents/Naim/Fichiers, and the report kept:
                                                  the next digest lists what it proposed

Nothing is changed: it only reads ~/Library/Application Support/Naim/conversations.
"""
import argparse
import collections
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

CONVS = Path.home() / "Library/Application Support/Naim/conversations"
REPORTS = Path.home() / ".naim/rapports-amelioration"
OUT = Path.home() / "Documents/Naim/Fichiers"
PDFPRO = Path.home() / ".naim/plugins/pdf-pro/skills/pdf-pro/pdfpro.py"
# the user says the reply was not what they wanted
UNHAPPY = re.compile(r"\b(nul+e?|pourri|moche|pas (bon|joli|ce que|demand)|ne marche|marche pas|fonctionne pas|toujours pas|"
                     r"encore une fois|erreur|bug|il a pas|il n'a pas|j'ai pas demand|oubli\w*|trop long|c'est long|lent|"
                     r"incomplet|n'importe quoi|faux|refai[st]|recommence)\b", re.I)
FAILED = re.compile(r"^(error|refused|denied|blocked|not allowed)|exit code [1-9]", re.I)
STOP = set("avec pour dans mais plus tout tous toute faire fais fait mon mes ton tes son ses une des les est sont que qui "
           "quoi comment cette elle ils nous vous moi toi sur par pas peux veux bien aussi alors donc comme salut bonjour bonsoir "
           "naim merci coucou".split())


def load(days, most):
    since = datetime.datetime.now().timestamp() - days * 86400
    out = []
    for f in sorted(CONVS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.stat().st_mtime < since or len(out) >= most:
            break
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if any(m.get("role") == "user" for m in d.get("messages", [])):
            out.append(d)
    return out


def words(text):
    return {w for w in re.findall(r"[a-zà-ÿ]{4,}", text.lower()) if w not in STOP}


def when(ms):
    return datetime.datetime.fromtimestamp(ms / 1000) if ms else None


def digest(convs, days):
    errors, skills, slow, unhappy, ratings, firsts = collections.Counter(), collections.Counter(), [], [], [], []
    hours = collections.Counter()
    total_tools = 0
    for d in convs:
        msgs, title = d.get("messages", []), (d.get("title") or "")[:70]
        first = next((m for m in msgs if m.get("role") == "user"), None)
        if first:
            firsts.append((d["id"], title, words(first.get("content") or ""), when(first.get("time"))))
            t = when(first.get("time"))
            if t:
                hours[f"{['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim'][t.weekday()]} {t.hour}h"] += 1
        asked = title
        for i, m in enumerate(msgs):
            if m.get("role") == "user":
                asked = (m.get("content") or "").strip().replace("\n", " ")[:70] or asked
            if m.get("role") == "user" and i > 1 and UNHAPPY.search(m.get("content") or ""):
                unhappy.append(f"{d['id']} « {title} » : « {(m.get('content') or '').strip()[:140]} »")
            if m.get("role") != "assistant":
                continue
            if m.get("rating") is not None:
                ratings.append((m["rating"], d["id"], title))
            steps = m.get("steps") or []
            calls, wasted, failed = collections.Counter(), 0, 0
            for s in steps:
                if s.get("type") == "event" and str(s.get("text", "")).startswith("Skill utilisé"):
                    skills[s["text"].split(":", 1)[-1].strip()] += 1
                if s.get("type") != "tool":
                    continue
                total_tools += 1
                key = s.get("name", "") + json.dumps(s.get("args"), sort_keys=True, ensure_ascii=False)
                calls[key] += 1
                wasted += calls[key] > 1  # the same call again, same arguments
                res = str(s.get("result") or s.get("output") or "")
                if FAILED.search(res[:200]):
                    failed += 1
                    prog = ""
                    if s.get("name") == "run_command":  # which command: « python3 pdfpro.py », « convert_document »
                        cmd = str((s.get("args") or {}).get("command", "")).split()
                        prog = " " + " ".join(Path(c).name for c in cmd[:2] if not c.startswith("-"))[:40]
                    errors[f"{s.get('name')}{prog} : {re.sub(r'[0-9a-f]{8,}|/[^ ]+', '…', res.strip().splitlines()[0])[:110]}"] += 1
            st = m.get("stats") or {}
            if steps:
                slow.append((st.get("total") or 0, len([s for s in steps if s.get("type") == "tool"]), failed, wasted,
                             st.get("reason"), d["id"], asked))

    # the same kind of request in several conversations: a skill or an automation to make
    groups, seen = [], set()
    for i, (cid, title, w, t) in enumerate(firsts):
        if cid in seen or len(w) < 3:  # « salut », « ça va ? » : not a request
            continue
        same = [(cid, title, t)] + [(c2, t2, h2) for c2, t2, w2, h2 in firsts[i + 1:]
                                    if c2 not in seen and len(w & w2) / max(1, len(w | w2)) >= 0.34]
        if len(same) >= 2:
            seen.update(c for c, _, _ in same)
            groups.append(same)

    L = [f"# Digest des conversations de Naim : {len(convs)} conversations, {days} derniers jours, {total_tools} outils lancés", ""]
    L.append("## Les plus longues (durée, outils, échecs, appels refaits, fin)")
    for tot, n, f, w, why, cid, title in sorted(slow, reverse=True)[:8]:
        L.append(f"- {tot / 60:.0f} min · {n} outils · {f} échecs · {w} refaits · fin {why or '?'} · {cid} « {title} »")
    L += ["", "## Erreurs d'outils qui reviennent"]
    L += [f"- {n}× {e}" for e, n in errors.most_common(10)] or ["- aucune"]
    L += ["", "## Quand l'utilisateur n'était pas content (son message suivant)"]
    L += [f"- {u}" for u in unhappy[:10]] or ["- rien de repéré"]
    bad = [f"- {cid} « {t} »" for r, cid, t in ratings if r < 0]
    L += ["", f"## Notes données : {sum(r > 0 for r, _, _ in ratings)} Bon, {sum(r == 0 for r, _, _ in ratings)} Correct, {len(bad)} Mauvais"] + bad
    L += ["", "## Demandes qui reviennent (candidates à un skill ou une automatisation)"]
    for g in groups[:8]:
        times = ", ".join(t.strftime("%a %d/%m %Hh") for _, _, t in g if t)
        L.append(f"- {len(g)}× : " + " | ".join(f"« {t} »" for _, t, _ in g[:4]) + (f" — le {times}" if times else ""))
    if not groups:
        L.append("- aucune")
    L += ["", "## Skills utilisés", "- " + (", ".join(f"{s} ({n})" for s, n in skills.most_common(15)) or "aucun")]
    L += ["", "## Moments des demandes", "- " + ", ".join(f"{h} ({n})" for h, n in hours.most_common(6))]
    old = sorted(REPORTS.glob("*.html"))[-3:] if REPORTS.exists() else []
    L += ["", "## Déjà proposé dans les rapports précédents (ne le repropose pas tel quel : dis s'il a été fait)"]
    for r in old:
        props = [re.sub(r"<[^>]+>", "", p).strip() for p in re.findall(r'class="prop"[^>]*>(.*?)</h3>', r.read_text(errors="replace"), re.S)]
        L.append(f"- {r.stem} : " + (" ; ".join(p[:90] for p in props[:8]) or "(aucune proposition lisible)"))
    if not old:
        L.append("- aucun rapport précédent")
    L += ["", "Détail d'une conversation : python3 analyse.py --conv <id>"]
    return "\n".join(L)


def one(cid):
    f = CONVS / f"{cid}.json"
    if not f.exists():
        return f"error: conversation {cid} introuvable"
    d = json.loads(f.read_text())
    L = [f"# « {d.get('title')} » ({d.get('mode')})"]
    for m in d.get("messages", []):
        if m.get("role") == "user":
            L.append(f"\nUTILISATEUR : {(m.get('content') or '').strip()[:400]}")
            continue
        for s in m.get("steps") or []:
            if s.get("type") == "tool":
                res = str(s.get("result") or s.get("output") or "").strip().replace("\n", " ")
                L.append(f"  {s.get('name')} {json.dumps(s.get('args'), ensure_ascii=False)[:140]} → {res[:120]}")
            elif s.get("type") == "event":
                L.append(f"  ({s.get('text')})")
        st = m.get("stats") or {}
        L.append(f"NAIM ({(st.get('total') or 0) / 60:.0f} min, fin {st.get('reason')}) : {(m.get('content') or '').strip()[:500]}")
    return "\n".join(L)[:12000]


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--jours", type=int, default=7)
    a.add_argument("--max", type=int, default=40)
    a.add_argument("--conv")
    a.add_argument("--rapport")
    o = a.parse_args()
    if o.rapport:
        src, day = Path(o.rapport).expanduser().resolve(), datetime.date.today().isoformat()
        REPORTS.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, REPORTS / f"{day}.html")
        OUT.mkdir(parents=True, exist_ok=True)
        pdf = OUT / f"Rapport-amelioration-{day}.pdf"
        r = subprocess.run([sys.executable, str(PDFPRO), "render", str(src), str(pdf)], capture_output=True, text=True, timeout=180)
        if r.returncode or not pdf.exists():
            sys.exit(f"error: PDF non fait ({(r.stderr or r.stdout).strip()[-300:]}) ; le rapport est gardé dans {REPORTS}")
        print(f"ok: PDF : {pdf} — rapport gardé dans {REPORTS / (day + '.html')}. Regarde le PDF avec look_at.")
    elif o.conv:
        print(one(o.conv))
    else:
        convs = load(o.jours, o.max)
        print(digest(convs, o.jours) if convs else f"Aucune conversation ces {o.jours} derniers jours : essaie --jours 30.")


if __name__ == "__main__":
    main()
