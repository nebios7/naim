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


def start(port, settings):
    if STATE["running"]:
        return STATE
    STATE.update(running=True, started=time.strftime("%H:%M"), finished=None, current="", results=[])
    threading.Thread(target=_run, args=(port, settings), daemon=True, name="naim-check").start()
    return STATE


def report():
    """The state as text (for the Admin screen)."""
    r = STATE["results"]
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
