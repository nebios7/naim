"""naim-mem: what Naim did, kept across sessions and searchable (SQLite + full-text search, on this Mac only).

Used by capture.py (the hooks: each request, each action, each final answer) and serveur.py (the MCP tools Naim
calls to search it). Database: ~/.naim/naim-mem/memoire.db
"""
import os
import sqlite3
import time
from pathlib import Path

DB = Path(os.environ.get("NAIM_HOME", Path.home() / ".naim")) / "naim-mem" / "memoire.db"


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=5)
    db.execute("""CREATE TABLE IF NOT EXISTS obs (id INTEGER PRIMARY KEY, t REAL, session TEXT, projet TEXT, type TEXT,
                  outil TEXT, titre TEXT, detail TEXT)""")
    db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS obs_fts USING fts5(titre, detail, projet, content='obs',
                  content_rowid='id', tokenize='unicode61 remove_diacritics 2')""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS obs_ai AFTER INSERT ON obs BEGIN
                  INSERT INTO obs_fts(rowid, titre, detail, projet) VALUES (new.id, new.titre, new.detail, new.projet); END""")
    return db


def add(session, projet, type_, outil, titre, detail):
    with connect() as db:
        db.execute("INSERT INTO obs (t, session, projet, type, outil, titre, detail) VALUES (?,?,?,?,?,?,?)",
                   (time.time(), session or "", projet or "", type_, outil or "", titre[:300], (detail or "")[:4000]))


def _fmt(row, long=False):
    id_, t, projet, type_, titre, detail = row
    when = time.strftime("%d/%m/%Y %H:%M", time.localtime(t))
    head = f"#{id_} · {when} · {type_}{' · ' + Path(projet).name if projet else ''} · {titre}"
    return head + (f"\n{detail}" if long and detail else "")


def search(query, limit=10):
    words = [w for w in "".join(c if c.isalnum() else " " for c in query).split() if len(w) > 1]
    if not words:
        return []
    match = " OR ".join(f'"{w}"*' for w in words)
    with connect() as db:
        rows = db.execute("""SELECT o.id, o.t, o.projet, o.type, o.titre, snippet(obs_fts, 1, '«', '»', '…', 18)
                             FROM obs_fts JOIN obs o ON o.id = obs_fts.rowid WHERE obs_fts MATCH ?
                             ORDER BY bm25(obs_fts) LIMIT ?""", (match, int(limit))).fetchall()
    return [_fmt(r, long=True) for r in rows]


def timeline(projet="", days=7, limit=40):
    since = time.time() - float(days) * 86400
    with connect() as db:
        rows = db.execute("""SELECT id, t, projet, type, titre, '' FROM obs WHERE t >= ? AND (? = '' OR projet LIKE ?)
                             AND type != 'action' ORDER BY t DESC LIMIT ?""",
                          (since, projet, f"%{projet}%", int(limit))).fetchall()
    return [_fmt(r) for r in rows]


def detail(id_):
    with connect() as db:
        row = db.execute("SELECT id, t, projet, type, titre, detail FROM obs WHERE id = ?", (int(id_),)).fetchone()
    return _fmt(row, long=True) if row else None


def count():
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM obs").fetchone()[0]
