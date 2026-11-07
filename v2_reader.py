"""Optional, strictly read-only view of V2's local uploads.
Never opens V2 SQLite in write mode and never modifies V2 files or index.
"""

import re
import sqlite3
from config import V2_DATA


def v2_docs():
    path = V2_DATA / "showcase.sqlite3"
    if not path.is_file():
        return []
    try:
        # mode=ro makes it impossible to create/migrate/modify the V2 database.
        con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)
        con.row_factory = sqlite3.Row
        try:
            return [
                dict(x)
                for x in con.execute("SELECT * FROM uploads ORDER BY created_at DESC LIMIT 300")
            ]
        finally:
            con.close()
    except (sqlite3.Error, OSError):
        return []


def v2_doc(doc_id):
    if not re.fullmatch(r"[0-9a-f]{32}", doc_id):
        return None
    return next((d for d in v2_docs() if d["doc_id"] == doc_id), None)


def v2_path(doc_id):
    item = v2_doc(doc_id)
    if not item:
        return None
    if item["file_type"] not in (".pdf", ".txt", ".docx"):
        return None
    path = V2_DATA / "uploads" / (doc_id + item["file_type"])
    return path if path.is_file() else None
