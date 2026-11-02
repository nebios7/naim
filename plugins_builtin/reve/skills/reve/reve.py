"""Naim's dream from the command line: `reve.py lancer` (dream now, wait, show) or `reve.py voir` (show what waits).
It talks to the running Naim (http://127.0.0.1:8765): the dream itself and the user's answers stay in Naim."""
import json
import os
import sys
import time
import urllib.request

URL = f"http://127.0.0.1:{os.environ.get('NAIM_PORT', '8765')}/api/dream"


def call(body=None):
    req = urllib.request.Request(URL, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def show(r):
    last, props = r.get("last"), r.get("pending") or []
    if last:
        rd = last.get("read") or {}
        print(f"Dernier rêve : {last.get('date_time') or last.get('date')} · {rd.get('moments', 0)} moments relus "
              f"dans {rd.get('conversations', 0)} conversations")
    else:
        print("Naim n'a pas encore rêvé.")
    if not props:
        print("Aucune proposition en attente.")
        return
    print(f"\n{len(props)} proposition(s) en attente :")
    for i, p in enumerate(props, 1):
        what = "Règle à ajouter" if p["kind"] == "regle" else "Fait à retirer de la mémoire"
        print(f"\n{i}. {what} : {p['text']}")
        if p.get("why"):
            print(f"   Pourquoi : {p['why']}")
        for e in p.get("evidence") or []:
            print(f"   L'utilisateur avait dit : « {e['user'][:200]} »")
    print("\nÀ accepter par l'utilisateur : carte de l'accueil, ou Personnaliser › Mémoire › Rêves de la nuit.")


def main():
    cmd = (sys.argv[1:] or ["voir"])[0]
    try:
        if cmd == "lancer":
            call({"op": "run"})
            print("Naim relit ce qui est nouveau…", flush=True)
            time.sleep(2)
            while (r := call())["state"].get("running"):
                time.sleep(5)
            show(r)
        else:
            show(call())
    except OSError as e:
        print(f"Naim ne répond pas sur {URL} ({e}). L'application Naim doit être ouverte.")
        sys.exit(1)


if __name__ == "__main__":
    main()
