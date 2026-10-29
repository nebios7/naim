"""Mods: small changes to Naim's own window (a band above the message box, a button, a panel), written by the user or
by Naim itself in ~/.naim/mods/<nom>/ (mod.json, mod.js, mod.css). The window loads the switched-on ones at startup;
/mods lists them, /mods off <nom> switches one off without deleting anything."""
import json
import re

import extensions as ext

DIR = ext.HOME / "mods"
OFF = DIR / ".eteints.json"  # the names switched off by the user (a mod's own files are never touched)
MAX_FILE = 200_000


def _off():
    try:
        return set(json.loads(OFF.read_text()))
    except (OSError, ValueError):
        return set()


def listing(with_code=False):
    """Every mod with its description and state; with_code adds mod.js and mod.css for the window to load."""
    off, out = _off(), []
    for d in sorted(DIR.iterdir()) if DIR.is_dir() else []:
        if not d.is_dir() or d.name.startswith(".") or not (d / "mod.js").is_file() and not (d / "mod.css").is_file():
            continue
        try:
            meta = json.loads((d / "mod.json").read_text())
        except (OSError, ValueError):
            meta = {}
        m = {"name": d.name, "description": str(meta.get("description", ""))[:300], "version": str(meta.get("version", "")),
             "enabled": d.name not in off, "path": str(d)}
        if with_code and m["enabled"]:
            for f in ("mod.js", "mod.css"):
                p = d / f
                m[f.split(".")[1]] = p.read_text(errors="replace")[:MAX_FILE] if p.is_file() else ""
        out.append(m)
    return out


def switch(name, enabled):
    if not re.fullmatch(r"[\w.-]+", name or "") or not (DIR / name).is_dir():
        return {"error": f"mod inconnu : {name}"}
    off = _off()
    (off.discard if enabled else off.add)(name)
    DIR.mkdir(parents=True, exist_ok=True)
    OFF.write_text(json.dumps(sorted(off)))
    return {"ok": True, "name": name, "enabled": enabled}


def stats(convs, days=30):
    """Ready-made statistics for a mod to show (read from the saved conversations, nothing sent anywhere):
    per day, the messages, answers, tools and files changed; the most used tools; the answer times."""
    import collections
    import time
    since = (time.time() - days * 86400) * 1000
    day = lambda ms: time.strftime("%Y-%m-%d", time.localtime(ms / 1000))
    per = collections.OrderedDict((day((time.time() - k * 86400) * 1000), {"messages": 0, "reponses": 0, "outils": 0, "fichiers": 0})
                                  for k in range(days - 1, -1, -1))
    tools, modes, times, ttft, convs_n = collections.Counter(), collections.Counter(), [], [], 0
    for f in convs.glob("*.json") if convs.is_dir() else []:
        try:
            c = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        seen = False
        for m in c.get("messages") or []:
            t = m.get("time") or 0
            if t < since or m.get("_greet"):
                continue
            d = per.get(day(t))
            if d is None:
                continue
            seen = True
            if m.get("role") == "user":
                d["messages"] += 1
                continue
            d["reponses"] += 1
            for s in m.get("steps") or []:
                if s.get("type") == "tool":
                    d["outils"] += 1
                    tools[s.get("name") or "?"] += 1
            d["fichiers"] += len(m.get("changes") or [])
            st = m.get("stats") or {}
            if st.get("total"):
                times.append(st["total"])
            if m.get("ttft") is not None:
                ttft.append(m["ttft"])
        if seen:
            convs_n += 1
            modes[c.get("mode") or "chat"] += 1
    mid = lambda xs: round(sorted(xs)[len(xs) // 2], 1) if xs else None
    return {"jours": [{"jour": k, **v} for k, v in per.items()], "conversations": convs_n, "modes": dict(modes),
            "outils": tools.most_common(12), "temps_reponse_median_s": mid(times), "premier_mot_median_s": mid(ttft),
            "periode_jours": days}


def security(settings, convs, plugin_list, perms):
    """What protects this Mac, for a mod to show (read only: a mod never changes any of it): the app's macOS
    permissions, the approval modes, the plugins whose hooks run, and the actions refused or asked in 30 days."""
    import collections
    import time
    since = (time.time() - 30 * 86400) * 1000
    seen = collections.Counter()
    for f in convs.glob("*.json") if convs.is_dir() else []:
        try:
            c = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        for m in c.get("messages") or []:
            if (m.get("time") or 0) < since:
                continue
            for s in m.get("steps") or []:
                r = str(s.get("result") or "")
                kind = ("bloquees" if r.startswith("blocked") else "refusees" if r.startswith("refused") else
                        "refusees_par_toi" if r.startswith("denied") else None)
                if kind:
                    seen[kind] += 1
    keys = ("auto_yes", "auto_writes", "auto_commands", "auto_mcp", "auto_computer", "power")
    return {"permissions": perms, "autorisations": {k: bool(settings.get(k)) for k in keys if k in settings},
            "commandes_interdites": len(settings.get("blocked") or []),
            "plugins_hooks": [{"nom": p.get("name"), "hooks_allumes": not p.get("hooks_off")} for p in plugin_list
                              if p.get("hooks") and p.get("enabled", True)],
            "actions_30_jours": dict(seen)}
