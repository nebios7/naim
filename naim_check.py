"""« Vérifier Naim » : real requests through the running app, one per behaviour that matters, in a temporary folder.

Nothing leaves the Mac (emails are simulated), nothing is remembered (automatic memory off for these requests), the
temporary folder is deleted at the end. Each case says what it checked; the report lists what works and what broke.
Run it before publishing a version: the problems are found here, not while using Naim.
"""
import json
import shutil
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import mailer

STATE = {"running": False, "started": None, "finished": None, "current": "", "results": []}
CASE_TIMEOUT = 420


def _ask(port, settings, folder, message, mode="chat", history=None):
    """One request like the app sends it; returns what Naim did."""
    s = dict(settings, mode=mode, project=str(folder), memory_auto=False, think=False)
    body = {"message": message, "mode": mode, "model": s.get("model") or "naim", "think": False, "settings": s,
            "history": history or [], "project": str(folder), "auto_yes": True}
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    out = {"tools": [], "text": "", "errors": [], "files": []}
    t = time.time()
    with urllib.request.urlopen(req, timeout=CASE_TIMEOUT) as r:
        for line in r:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            ty = e.get("type")
            if ty == "tool":
                out["tools"].append(e.get("name"))
            elif ty == "token":
                out["text"] += e.get("text") or ""
            elif ty == "answer":
                out["text"] = e.get("text") or out["text"]
            elif ty == "error":
                out["errors"].append(e.get("text"))
            elif ty == "deliverables":
                out["files"] = [f.get("path") for f in e.get("files") or []]
    out["secs"] = round(time.time() - t)
    return out


def _cases(folder):
    write = {"write_file", "creer_fichier", "edit_file", "multi_edit", "delete_file", "move_file"}
    lesson_hist = [{"role": "user", "content": "c'est quoi une variable en Python ?"},
                   {"role": "assistant", "content": "Une variable est un nom qui désigne une valeur, par exemple x = 5."}]
    return [
        ("Salut", "chat", "salut", None,
         lambda o: (o["text"].strip() and not o["tools"] and "je suis naim" not in o["text"].lower(),
                    "répond, sans outil et sans se présenter")),
        ("Merci", "chat", "merci", lesson_hist,
         lambda o: (o["text"].strip() and not o["tools"] and len(o["text"]) < 500,
                    "répond court, sans outil ni fichier")),
        ("Leçon", "chat", "Explique les boucles for en Python avec un exemple", None,
         lambda o: ("```" in o["text"] and not (set(o["tools"]) & write),
                    "explique dans la conversation avec du code, sans créer de fichier")),
        ("Schéma", "chat", "Fais-moi un schéma des étapes pour préparer un café", None,
         lambda o: ("```mermaid" in o["text"] and len(o["tools"]) <= 4, "dessine un schéma dans la réponse, sans boucle")),
        ("PDF", "chat", "Fais-moi un PDF d'une demi-page sur l'histoire du café", None,
         lambda o: ("creer_fichier" in o["tools"] and any(folder.glob("*.pdf")), "crée un vrai PDF dans le dossier")),
        ("E-mail", "chat", "Envoie-moi rapport.pdf par mail en pièce jointe", None,
         lambda o: ("send_email" in o["tools"] and any(m["attachments"] for m in (mailer.SIMULATED or [])),
                    "envoie vraiment (envoi simulé) avec la pièce jointe, sans l'annoncer seulement")),
        ("Agent : programme", "agent", "Crée hello.py qui affiche Bonjour, lance-le et dis-moi la sortie", None,
         lambda o: ((folder / "hello.py").exists() and "run_command" in o["tools"] and "bonjour" in o["text"].lower(),
                    "crée le fichier, le lance et donne la vraie sortie")),
        ("Agent : remarque", "agent", "merci par contre tu n'es pas obligé de me faire trois excel",
         [{"role": "user", "content": "fais-moi un tableau excel des pièces"},
          {"role": "assistant", "content": "Fichiers Excel créés : pieces.xlsx, pieces_2.xlsx, pieces_3.xlsx."}],
         lambda o: (len(list(folder.glob("pieces*.xlsx"))) <= 1, "comprend la remarque et retire les fichiers en trop")),
    ]


def _prepare(folder):
    import chatfiles
    chatfiles._make(folder / "rapport.pdf", "# Rapport\n\nUn court rapport de test.")
    for n in ("pieces.xlsx", "pieces_2.xlsx", "pieces_3.xlsx"):
        chatfiles._make(folder / n, "Date;Pièce\n01/01/2026;Courrier")


def _run(port, settings):
    folder = Path(tempfile.mkdtemp(prefix="naim-verif-"))
    mailer.SIMULATED = []
    try:
        _prepare(folder)
        for name, mode, msg, hist, check in _cases(folder):
            STATE["current"] = name
            try:
                o = _ask(port, settings, folder, msg, mode, hist)
                ok, what = check(o)
                STATE["results"].append({"name": name, "ok": bool(ok), "what": what, "secs": o["secs"],
                                         "tools": o["tools"], "answer": o["text"].strip()[:300], "errors": o["errors"]})
            except Exception as e:  # noqa: BLE001 — one case failing must not stop the others
                STATE["results"].append({"name": name, "ok": False, "what": "", "secs": 0, "tools": [],
                                         "answer": "", "errors": [f"{type(e).__name__}: {e}"]})
    finally:
        mailer.SIMULATED = None
        shutil.rmtree(folder, ignore_errors=True)
        STATE.update(running=False, finished=time.strftime("%H:%M"), current="")
        try:
            _save()
            learn(STATE["results"])
        except Exception as e:  # noqa: BLE001 — saving or learning must never break Naim
            print(f"vérification : enregistrement impossible ({e})", flush=True)


def start(port, settings):
    if STATE["running"]:
        return STATE
    STATE.update(running=True, started=time.strftime("%H:%M"), finished=None, current="", results=[])
    threading.Thread(target=_run, args=(port, settings), daemon=True, name="naim-check").start()
    return STATE


def report():
    """The state as text (for the Admin screen)."""
    r = STATE["results"]
    if not STATE["started"] and (last := last_saved()):
        n_ok = sum(x["ok"] for x in last["results"])
        return (f"Dernière vérification : {last['date']} — {n_ok}/{len(last['results'])} cas réussis.\n"
                + "\n".join(f"{'OK    ' if x['ok'] else 'ÉCHEC '} {x['name']} : {x['what']}" for x in last["results"])
                + (f"\n\n{lessons()}" if lessons() else ""))
    if not STATE["started"]:
        return ("Aucune vérification lancée depuis l'ouverture de Naim.\n"
                "Clique d'abord sur « Vérifier Naim » : 8 essais réels (salut, leçon, schéma, PDF, e-mail simulé, programme, "
                "remarque), 10 à 20 minutes. N'utilise pas Naim pendant ce temps, puis reviens ici.")
    lines = []
    for x in r:
        lines.append(f"{'OK    ' if x['ok'] else 'ÉCHEC '} {x['name']} ({x['secs']} s) : {x['what']}")
        if not x["ok"]:
            lines.append(f"        outils : {', '.join(x['tools']) or 'aucun'}")
            if x["errors"]:
                lines.append(f"        erreur : {x['errors'][0][:200]}")
            if x["answer"]:
                lines.append(f"        réponse : {x['answer'][:200]}")
    n_ok = sum(x["ok"] for x in r)
    head = (f"Vérification en cours (lancée à {STATE['started']}) : {len(r)}/8 cas faits, en ce moment « {STATE['current']} ». "
            "Clique à nouveau pour voir la suite." if STATE["running"]
            else f"Vérification terminée à {STATE['finished']} : {n_ok}/{len(r)} cas réussis.")
    return head + ("\n\n" + "\n".join(lines) if lines else "")


# ============================================================================ automatic check and lessons
import extensions as ext  # noqa: E402

REPORTS = ext.HOME / "verification"
LESSONS = ext.HOME / "lecons.md"


def _save():
    REPORTS.mkdir(parents=True, exist_ok=True)
    data = {"date": time.strftime("%Y-%m-%d %H:%M"), "results": STATE["results"]}
    (REPORTS / (time.strftime("%Y-%m-%d_%H%M") + ".json")).write_text(json.dumps(data, ensure_ascii=False, indent=1))


def last_saved():
    """The latest report kept on disk: {date, results} or None."""
    files = sorted(REPORTS.glob("*.json")) if REPORTS.exists() else []
    try:
        return json.loads(files[-1].read_text()) if files else None
    except (OSError, ValueError):
        return None


def learn(results):
    """Level 2: for each failed case, one short rule in ~/.naim/lecons.md (read by Naim in Chat and Agent).
    One rule per case, replaced when the case fails again; a case that passes again loses its rule. Code is never touched."""
    import re
    import llamacpp
    rules = {}
    if LESSONS.exists():
        for m in re.finditer(r"^- \*\*(.+?)\*\* : (.+)$", LESSONS.read_text(), re.M):
            rules[m.group(1)] = m.group(2)
    for x in results:
        if x["ok"]:
            rules.pop(x["name"], None)
            continue
        ask = (f"Un essai automatique de l'assistant Naim a échoué.\nEssai : {x['name']}\nAttendu : {x['what']}\n"
               f"Outils utilisés : {', '.join(x['tools']) or 'aucun'}\nRéponse donnée : {x['answer'][:400]}\n"
               f"Erreurs : {'; '.join(x['errors'])[:300]}\n\nÉcris UNE seule règle courte (25 mots au plus), à l'impératif, "
               "en français, que Naim devra suivre pour réussir ce genre de demande la prochaine fois. Rien d'autre.")
        try:
            out = llamacpp.chat([{"role": "user", "content": ask}], stream=False,
                                options={"slot": llamacpp.bg_slot(), "num_predict": 80, "temperature": 0.2, "num_ctx": 8192})
            rule = re.sub(r"\s+", " ", (out.get("content") or "").strip().strip('"«» '))[:220]
        except Exception:  # noqa: BLE001
            rule = ""
        if rule:
            rules[x["name"]] = rule
    if rules:
        LESSONS.write_text("# Leçons de mes vérifications (écrites par Naim)\n\nRègles tirées des essais ratés. "
                           "Tu peux corriger ou effacer ce fichier.\n\n"
                           + "\n".join(f"- **{k}** : {v}" for k, v in rules.items()) + "\n")
    elif LESSONS.exists():
        LESSONS.write_text("# Leçons de mes vérifications (écrites par Naim)\n\nAucune : tous les essais réussissent.\n")


def lessons():
    """The rules, for Naim's instructions ('' when there are none)."""
    try:
        t = LESSONS.read_text()
    except OSError:
        return ""
    lines = [l for l in t.splitlines() if l.startswith("- **")]
    return ("Leçons de tes vérifications précédentes (suis-les) :\n" + "\n".join(lines)) if lines else ""


def start_auto(port, get_settings, busy, last_activity):
    """Level 1: once a day, when the Mac has been idle for 30 min (no conversation, nothing running), the check runs
    by itself; the report waits for the next opening of Naim."""
    def loop():
        time.sleep(600)
        while True:
            try:
                s = get_settings()
                last = last_saved()
                age = (time.time() - time.mktime(time.strptime(last["date"], "%Y-%m-%d %H:%M"))) if last else 1e9
                idle = time.time() - last_activity() >= 1800 and not busy()
                if s.get("self_check", True) is not False and age >= 20 * 3600 and idle and not STATE["running"]:
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} vérification automatique (Mac inactif)", flush=True)
                    start(port, s)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(300)
    threading.Thread(target=loop, daemon=True, name="naim-auto-check").start()
