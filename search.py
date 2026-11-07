"""Safe Elasticsearch search orchestration. Cross-collection RRF is rank fusion over
separately scoped lexical and semantic searches to avoid querying semantic_text
on unmapped collections. Single-index hybrid uses Elasticsearch native RRF.
"""

from time import perf_counter
from config import SOURCES, BOOK_NAMES
from es_client import ESFailure

MODES = {
    "keyword": "BM25 keyword",
    "semantic": "ELSER semantic",
    "hybrid": "Equal-weight RRF",
    "weighted": "Weighted RRF (BM25 1.0 / ELSER 1.5)",
}
SCOPES = {"all": "All collections", **{k: v[1] for k, v in SOURCES.items()}}


def indices_for(client, scope, book_id="", doc_type=""):
    groups = SOURCES if scope == "all" else {scope: SOURCES[scope]} if scope in SOURCES else {}
    if book_id:
        groups = {k: v for k, v in groups.items() if k in ("passages", "books")}
    if doc_type:
        groups = {k: v for k, v in groups.items() if k in ("uploads", "uploads_v2")}
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
        filters.append({"term": {"file_type": doc_type}})

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


def _display_hits(rows):
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
    elif mode in ("hybrid", "weighted") and set(sem) != set(names):
        # Safe client-side RRF when a union contains lexical-only documents.
        # Every semantic request targets only indices mapped as semantic_text.
        pool = max(50, size)
        lex = client.api(
            "POST",
            ",".join(names) + "/_search",
            payload=payload(q, "keyword", pool, book_id, doc_type),
            timeout=35,
        )
        warning = "Hybrid uses separate lexical and semantic searches across collections; ranks are fused locally. Scores are not comparable to ES _score."
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
    hits = _display_hits(rows)
    total = d.get("hits", {}).get("total", {})
    count = total.get("value", len(hits)) if isinstance(total, dict) else (total or len(hits))
    return {
        "hits": hits,
        "count": count,
        "took": took,
        "elapsed_ms": elapsed,
        "warning": warning,
        "mode_used": mode_used,
        "indices": active,
    }
