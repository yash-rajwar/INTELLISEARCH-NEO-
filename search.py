"""Safe Elasticsearch search orchestration. Cross-collection RRF is rank fusion over
separately scoped lexical and semantic searches to avoid querying semantic_text
on unmapped collections. Single-index hybrid uses Elasticsearch native RRF.
"""

from time import perf_counter
from config import SOURCES, BOOK_NAMES
from es_client import ESFailure

MODES = {
    "keyword": "Keyword (BM25)",
    "semantic": "Semantic (ELSER, meaning-based)",
    "hybrid": "Hybrid (keyword + semantic, RRF)",
    "weighted": "Weighted hybrid (BM25 1.0 / ELSER 1.5, fused locally)",
}
SCOPES = {"all": "All collections", **{k: v[1] for k, v in SOURCES.items()}}


def indices_for(client, scope, book_id="", doc_type=""):
    groups = SOURCES if scope == "all" else {scope: SOURCES[scope]} if scope in SOURCES else {}
    if book_id:
        groups = {k: v for k, v in groups.items() if k in ("passages", "books")}
    if doc_type:
        groups = {k: v for k, v in groups.items() if k in ("uploads", "uploads_v2", "corpus")}
    return [v[0] for v in groups.values() if client.exists(v[0])]


def payload(query, mode, size=12, book_id="", doc_type="", semantic_available=True):
    qlex = {
        "multi_match": {
            "query": query,
            "fields": ["content^2", "title^2", "author", "text", "body", "summary"],
            "type": "best_fields",
        }
    }
    qsem = {"match": {"content_semantic": {"query": query}}}
    filters = []
    if book_id:
        filters.append({"term": {"book_id": book_id}})
    if doc_type:
        filters.append({"terms": {"file_type": [doc_type, doc_type.lstrip(".")]}})

    def apply(q):
        return {"bool": {"must": [q], "filter": filters}} if filters else q

    p = {"size": size, "_source": {"excludes": ["content_semantic"]}, "track_total_hits": True}
    if mode == "keyword" or not semantic_available:
        p["query"] = apply(qlex)
    elif mode == "semantic":
        p["query"] = apply(qsem)
    else:
        a = {"standard": {"query": apply(qlex)}}
        b = {"standard": {"query": apply(qsem)}}
        subs = (
            [{"retriever": a, "weight": 1.0}, {"retriever": b, "weight": 1.5}]
            if mode == "weighted"
            else [a, b]
        )
        p.pop(
            "track_total_hits", None
        )  # RRF retriever disallows track_total_hits in some versions.
        p["retriever"] = {
            "rrf": {"retrievers": subs, "rank_constant": 60, "rank_window_size": max(50, size)}
        }
    return p


def semantic_indexes(client, index_names):
    result = []
    for name in index_names:
        try:
            info = client.api("GET", f"{name}/_mapping", timeout=10)
            props = info[name]["mappings"].get("properties", {})
            if props.get("content_semantic", {}).get("type") == "semantic_text":
                result.append(name)
        except (KeyError, ESFailure, TypeError):
            continue
    return result


def fuse_ranked(lex, sem, weighted=False, cap=12):
    """Ranks from different models are never compared by raw _score."""
    fused = {}
    for hits, weight in ((lex, 1.0), (sem, 1.5 if weighted else 1.0)):
        for rank, h in enumerate(hits, 1):
            key = (h.get("_index"), h.get("_id"))
            if None in key:
                continue
            item = fused.setdefault(key, {"hit": dict(h), "score": 0.0})
            item["score"] += weight / (60.0 + rank)
    out = []
    for item in sorted(fused.values(), key=lambda x: -x["score"])[:cap]:
        h = item["hit"]
        h["_score"] = item["score"]
        out.append(h)
    return out


_STOP = set("a an and are as at be by can do does for from how i in is it of on or the to what when where which who why with you my should must".split())


def overlap_note(query, passage):
    """Count how many distinct query words appear in the passage. Facts only, no confidence claim."""
    import re

    words = []
    for w in re.findall(r"[a-z0-9]+", (query or "").lower()):
        if w not in _STOP and len(w) > 1 and w not in words:
            words.append(w)
    if not words:
        return ""
    text = (passage or "").lower()
    found = sum(1 for w in words if w in text)
    return f"{found} of {len(words)} query words appear in this passage"


def highlight_html(text, query):
    """Escape the text, then wrap query words in <mark>. Never marks up raw text."""
    import re

    from markupsafe import Markup, escape

    text = text or ""
    words = []
    for w in re.findall(r"[A-Za-z0-9]+", query or ""):
        if w.lower() not in _STOP and len(w) > 1 and w.lower() not in [x.lower() for x in words]:
            words.append(w)
    if not words:
        return escape(text)
    words.sort(key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)
    parts = []
    last = 0
    for m in pattern.finditer(text):
        parts.append(escape(text[last : m.start()]))
        parts.append(Markup("<mark>") + escape(m.group(0)) + Markup("</mark>"))
        last = m.end()
    parts.append(escape(text[last:]))
    return Markup("").join(parts)


def _display_hits(rows, query=""):
    result = []
    for rank, hit in enumerate(rows, 1):
        src = hit.get("_source") or {}
        index = str(hit.get("_index", ""))
        typ = next((k for k, (name, _) in SOURCES.items() if name == index), "other")
        book = str(src.get("book_id") or "")
        filename = str(src.get("filename") or src.get("source_file") or "")
        chunk = str(
            src.get("content") or src.get("text") or src.get("body") or src.get("summary") or ""
        )
        title = str(src.get("title") or filename or BOOK_NAMES.get(book) or "Untitled result")
        startline = src.get("start_line")
        page = src.get("page_number")
        doc_id = str(src.get("document_id") or "")
        if typ in ("uploads", "uploads_v2") and doc_id:
            base = "/uploaded/" if typ == "uploads" else "/uploaded-v2/"
            source_url = (
                base
                + doc_id
                + (f"#page={page}" if page and filename.lower().endswith(".pdf") else "")
            )
        elif typ == "corpus" and filename:
            from urllib.parse import quote

            source_url = "/corpus-file/" + quote(filename) + (
                f"#page={page}" if page and filename.lower().endswith(".pdf") else ""
            )
        elif book in BOOK_NAMES:
            source_url = (
                "/book/"
                + book
                + (f"?line={startline}" if isinstance(startline, int) and startline > 0 else "")
            )
        else:
            source_url = ""
        result.append(
            {
                "rank": rank,
                "id": str(hit.get("_id") or ""),
                "index": index,
                "type": typ,
                "title": title,
                "filename": filename,
                "document_id": doc_id,
                "overlap": overlap_note(query, chunk),
                "author": str(src.get("author") or ""),
                "passage": chunk[:750],
                "text": chunk,  # full chunk, used by the evaluation harness
                "score": hit.get("_score"),
                "book_id": book,
                "page": page,
                "start_line": startline,
                "section": str(src.get("section") or ""),
                "file_type": str(src.get("file_type") or ""),
                "source_url": source_url,
                "has_context": bool(hit.get("_id")),
            }
        )
    return result


def group_hits(hits):
    """Group chunk hits by document. A group's rank is the rank of its best chunk."""
    groups = {}
    for h in hits:
        key = (h.get("index"), h.get("document_id") or h.get("filename") or h.get("title"))
        g = groups.get(key)
        if g is None:
            g = {
                "title": h.get("title"),
                "type": h.get("type"),
                "file_type": h.get("file_type"),
                "best": h,
                "hits": [],
                "pages": [],
            }
            groups[key] = g
        g["hits"].append(h)
        page = h.get("page")
        if page and page not in g["pages"]:
            g["pages"].append(page)
    out = []
    for rank, g in enumerate(groups.values(), 1):
        g["rank"] = rank
        g["pages"].sort()
        out.append(g)
    return out


def search(client, q, scope="all", mode="keyword", book_id="", doc_type="", size=12):
    if not q.strip() or len(q) > 500:
        raise ValueError("Enter a query of up to 500 characters.")
    if mode not in MODES or scope not in SCOPES:
        raise ValueError("Invalid search mode or collection.")
    if book_id and book_id not in BOOK_NAMES:
        raise ValueError("Invalid book filter.")
    if doc_type and doc_type not in (".pdf", ".docx", ".txt"):
        raise ValueError("Invalid document filter.")
    names = indices_for(client, scope, book_id, doc_type)
    if not names:
        return {
            "hits": [],
            "count": 0,
            "took": 0,
            "elapsed_ms": 0,
            "warning": "No indexed documents for these filters.",
            "mode_used": mode,
            "indices": [],
        }
    sem = semantic_indexes(client, names) if mode != "keyword" else []
    warning = ""
    active = names
    if mode == "semantic":
        active = sem
        if not active:
            return {
                "hits": [],
                "count": 0,
                "took": 0,
                "elapsed_ms": 0,
                "warning": "No semantic index is available in this collection. Choose BM25.",
                "mode_used": mode,
                "indices": [],
            }
        if len(sem) < len(names):
            warning = "Some collections have no semantic field and were excluded. Use BM25 to include all."
    started = perf_counter()
    d = {}
    took = 0
    lex_keys = None  # keys of the BM25 results, used for the 'found by meaning' tag
    if mode in ("hybrid", "weighted") and not sem:
        mode_used = "keyword fallback"
        warning = "No ELSER-capable indices are present; showing BM25 results rather than calling this hybrid."
        d = client.api(
            "POST",
            ",".join(names) + "/_search",
            payload=payload(q, "keyword", size, book_id, doc_type),
            timeout=35,
        )
        rows = d.get("hits", {}).get("hits", [])
        took = d.get("took", 0)
    elif (mode == "weighted" and sem) or (
        mode in ("hybrid", "weighted") and set(sem) != set(names)
    ):
        # Safe client-side RRF when a union contains lexical-only documents.
        # Every semantic request targets only indices mapped as semantic_text.
        pool = max(50, size)
        lex = client.api(
            "POST",
            ",".join(names) + "/_search",
            payload=payload(q, "keyword", pool, book_id, doc_type),
            timeout=35,
        )
        lex_keys = {(h.get("_index"), h.get("_id")) for h in lex.get("hits", {}).get("hits", [])}
        warning = (
            "Weighted RRF (BM25 1.0, ELSER 1.5) is fused locally because this Elasticsearch version rejects weighted retrievers. Scores are fusion scores, not ES _score."
            if mode == "weighted"
            else "Hybrid uses separate lexical and semantic searches across collections; ranks are fused locally. Scores are not comparable to ES _score."
        )
        try:
            semantic = client.api(
                "POST",
                ",".join(sem) + "/_search",
                payload=payload(q, "semantic", pool, book_id, doc_type),
                timeout=65,
            )
            rows = fuse_ranked(
                lex.get("hits", {}).get("hits", []),
                semantic.get("hits", {}).get("hits", []),
                mode == "weighted",
                size,
            )
            took = lex.get("took", 0) + semantic.get("took", 0)
            mode_used = mode
        except ESFailure as err:
            rows = lex.get("hits", {}).get("hits", [])[:size]
            took = lex.get("took", 0)
            warning = "ELSER search failed; showing BM25 only. Reason: " + str(err)[:180]
            mode_used = "keyword fallback"
        d = {"hits": {"hits": rows, "total": {"value": len(rows)}}, "took": took}
    else:
        mode_used = mode
        p = payload(q, mode, size, book_id, doc_type)
        try:
            d = client.api(
                "POST",
                ",".join(active) + "/_search",
                payload=p,
                timeout=65 if mode != "keyword" else 35,
            )
        except ESFailure as err:
            if mode in ("hybrid", "weighted"):
                d = client.api(
                    "POST",
                    ",".join(names) + "/_search",
                    payload=payload(q, "keyword", size, book_id, doc_type),
                    timeout=35,
                )
                mode_used = "keyword fallback"
                warning = "Hybrid unavailable. BM25 results shown instead: " + str(err)[:180]
            else:
                raise
        rows = d.get("hits", {}).get("hits", [])
        took = d.get("took", 0)
    elapsed = round((perf_counter() - started) * 1000)
    hits = _display_hits(rows, q)
    if mode_used in ("semantic", "hybrid", "weighted"):
        keys = lex_keys
        if keys is None:
            keys = lexical_keys(client, names, q, book_id, doc_type, max(50, size))
        if keys is not None:
            for row, h in zip(rows, hits):
                h["meaning_only"] = (row.get("_index"), row.get("_id")) not in keys
    total = d.get("hits", {}).get("total", {})
    count = total.get("value", len(hits)) if isinstance(total, dict) else (total or len(hits))
    return {
        "hits": hits,
        "groups": group_hits(hits),
        "count": count,
        "took": took,
        "elapsed_ms": elapsed,
        "warning": warning,
        "mode_used": mode_used,
        "indices": active,
    }


def lexical_keys(client, names, q, book_id, doc_type, pool):
    """Keys of the top BM25 results. Returns None if that lookup fails (then no tags are shown)."""
    try:
        d = client.api(
            "POST",
            ",".join(names) + "/_search",
            payload=payload(q, "keyword", pool, book_id, doc_type),
            timeout=35,
        )
        return {(h.get("_index"), h.get("_id")) for h in d.get("hits", {}).get("hits", [])}
    except (ESFailure, KeyError, TypeError, AttributeError):
        return None


def result_limit(raw, default=30, maximum=150):
    """How many passages to fetch. Accepts the ?n= value; anything odd gives the default."""
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max(default, min(n, maximum))
