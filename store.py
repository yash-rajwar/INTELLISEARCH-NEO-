"""SQLite metadata for uploads and search history. No production databases touched."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from config import DATA, DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS uploads (
 doc_id TEXT PRIMARY KEY, filename TEXT NOT NULL, file_type TEXT NOT NULL,
 file_bytes INTEGER NOT NULL, chunks INTEGER NOT NULL DEFAULT 0,
 pages INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL,
 semantic_status TEXT NOT NULL DEFAULT 'none', error TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS searches (
 id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT NOT NULL,
 scope TEXT NOT NULL, mode TEXT NOT NULL, hits INTEGER NOT NULL,
 elapsed_ms INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_date ON searches(created_at);
"""


def init_db():
    DATA.mkdir(parents=True, exist_ok=True)
    with db() as c:  # db() commits and then closes; "with sqlite3.connect()" never closes
        c.executescript(SCHEMA)


@contextmanager
def db():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_doc(
    doc_id, filename, ext, size, chunks=0, pages=0, status="pending", semantic="none", error=""
):
    with db() as c:
        c.execute(
            """INSERT INTO uploads(doc_id,filename,file_type,file_bytes,chunks,pages,status,semantic_status,error,created_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(doc_id) DO UPDATE SET chunks=excluded.chunks,pages=excluded.pages,status=excluded.status,
                     semantic_status=excluded.semantic_status,error=excluded.error""",
            (doc_id, filename, ext, size, chunks, pages, status, semantic, error[:900], now()),
        )


def upload_doc(doc_id):
    with db() as c:
        item = c.execute("SELECT * FROM uploads WHERE doc_id=?", (doc_id,)).fetchone()
    return dict(item) if item else None


def all_docs():
    with db() as c:
        return [
            dict(x) for x in c.execute("SELECT * FROM uploads ORDER BY created_at DESC").fetchall()
        ]


def log_query(q, scope, mode, hits, ms, status):
    with db() as c:
        c.execute(
            "INSERT INTO searches(query,scope,mode,hits,elapsed_ms,status,created_at) VALUES(?,?,?,?,?,?,?)",
            (q[:500], scope, mode, hits, ms, status, now()),
        )


def dashboard():
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM searches").fetchone()[0]
        docs = c.execute(
            "SELECT COUNT(*) FROM uploads WHERE status IN ('indexed','lexical')"
        ).fetchone()[0]
        avg = c.execute('SELECT AVG(elapsed_ms) FROM searches WHERE status="ok"').fetchone()[0] or 0
        methods = [
            dict(x)
            for x in c.execute(
                "SELECT mode,COUNT(*) AS n FROM searches GROUP BY mode ORDER BY n DESC"
            ).fetchall()
        ]
        recent = [
            dict(x)
            for x in c.execute(
                "SELECT query,scope,mode,elapsed_ms,hits,status,created_at FROM searches ORDER BY id DESC LIMIT 12"
            ).fetchall()
        ]
    return {
        "queries": total,
        "uploads": docs,
        "avg_ms": round(avg),
        "methods": methods,
        "recent": recent,
    }


V2_SCHEMA = """
CREATE TABLE IF NOT EXISTS insights (
 doc_id TEXT PRIMARY KEY, category TEXT NOT NULL, tags TEXT NOT NULL,
 ocr_pages INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bookmarks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, index_name TEXT NOT NULL, hit_id TEXT NOT NULL,
 title TEXT NOT NULL, query TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(index_name,hit_id));
"""


def init_v2_db():
    init_db()
    with db() as c:
        c.executescript(V2_SCHEMA)


def save_insights(doc_id, category, tags, ocr_pages=0):
    import json

    with db() as c:
        c.execute(
            "INSERT INTO insights(doc_id,category,tags,ocr_pages,created_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(doc_id) DO UPDATE SET category=excluded.category,tags=excluded.tags,ocr_pages=excluded.ocr_pages",
            (doc_id, category, json.dumps(tags[:8]), ocr_pages, now()),
        )


def get_insights(doc_id):
    import json

    with db() as c:
        r = c.execute("SELECT * FROM insights WHERE doc_id=?", (doc_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["tags"] = json.loads(d["tags"])
    return d


def all_insights():
    import json

    with db() as c:
        rows = c.execute("SELECT * FROM insights").fetchall()
    return {r["doc_id"]: {**dict(r), "tags": json.loads(r["tags"])} for r in rows}


def add_bookmark(index_name, hit_id, title, query):
    with db() as c:
        c.execute(
            "INSERT OR IGNORE INTO bookmarks(index_name,hit_id,title,query,created_at) VALUES(?,?,?,?,?)",
            (index_name, hit_id, title[:180], query[:500], now()),
        )


def remove_bookmark(bookmark_id):
    with db() as c:
        c.execute("DELETE FROM bookmarks WHERE id=?", (bookmark_id,))


def bookmarks():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM bookmarks ORDER BY id DESC LIMIT 200")]


def recent_queries(limit=12):
    with db() as c:
        return [
            r["query"]
            for r in c.execute(
                "SELECT query FROM searches WHERE status=? ORDER BY id DESC LIMIT ?", ("ok", limit)
            )
        ]
