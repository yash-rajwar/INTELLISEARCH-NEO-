"""Read-only source text access for uploaded documents and original cleaned books."""

import re
from config import BOOKS_DIR, UPLOADS, BOOK_FILES, BOOK_NAMES, DATA, V2_DATA
from store import upload_doc, all_docs
from extractors import text_pages
from v2_reader import v2_docs, v2_doc, v2_path


def choices():
    items = [{"id": "book:" + bid, "name": f"Book · {title}"} for bid, title in BOOK_NAMES.items()]
    for item in all_docs():
        if item["status"] == "indexed":
            items.append({"id": "upload:" + item["doc_id"], "name": "Upload · " + item["filename"]})
    for item in v2_docs():
        if item["status"] == "indexed" and v2_path(item["doc_id"]):
            items.append(
                {
                    "id": "upload-v2:" + item["doc_id"],
                    "name": "V2 (read-only) · " + item["filename"],
                }
            )
    return items


def read_source(ref):
    if ref.startswith("book:"):
        bid = ref[5:]
        if bid not in BOOK_FILES:
            raise ValueError("Unknown book selection.")
        path = BOOKS_DIR / BOOK_FILES[bid]
        if not path.is_file():
            raise ValueError("Clean source book not present on disk.")
        return {
            "id": ref,
            "title": BOOK_NAMES[bid],
            "text": path.read_text(encoding="utf-8-sig")[:160000],
            "link": "/book/" + bid,
        }
    if ref.startswith("upload:") and re.fullmatch(r"upload:[0-9a-f]{32}", ref):
        doc_id = ref[7:]
        item = upload_doc(doc_id)
        if not item or item["status"] != "indexed":
            raise ValueError("Unknown or unindexed uploaded document.")
        path = UPLOADS / (doc_id + item["file_type"])
        if not path.is_file():
            raise ValueError("Uploaded source no longer exists.")
        cache = DATA / "extracted" / f"{doc_id}.txt"
        if cache.exists():
            txt = cache.read_text(encoding="utf-8")
        else:
            pages, _ = text_pages(path.read_bytes(), item["file_type"], ocr=False)
            txt = "\n\n".join(p["text"] for p in pages)
        return {
            "id": ref,
            "title": item["filename"],
            "text": txt[:160000],
            "link": "/uploaded/" + doc_id,
        }
    if ref.startswith("upload-v2:") and re.fullmatch(r"upload-v2:[0-9a-f]{32}", ref):
        doc_id = ref[10:]
        item = v2_doc(doc_id)
        path = v2_path(doc_id)
        if not item or item["status"] != "indexed" or not path:
            raise ValueError("V2 upload not found or no longer available.")
        cache = V2_DATA / "extracted" / f"{doc_id}.txt"
        if cache.is_file():
            txt = cache.read_text(encoding="utf-8")
        else:
            pages, _ = text_pages(path.read_bytes(), item["file_type"])
            txt = "\n\n".join(p["text"] for p in pages)
        return {
            "id": ref,
            "title": item["filename"],
            "text": txt[:160000],
            "link": "/uploaded-v2/" + doc_id,
        }
    raise ValueError("Select a document from the available library.")
