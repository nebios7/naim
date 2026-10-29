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
