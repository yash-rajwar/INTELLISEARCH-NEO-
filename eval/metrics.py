"""Pure scoring functions for the evaluation harness. No Elasticsearch, no files."""

import math
import re

TOKEN = re.compile(r"\w+", re.UNICODE)
FUZZY_MIN_WORDS = 8  # shorter spans must match exactly, so common words cannot match by luck


def normalise(text):
    """Lower-case and collapse all whitespace, so PDF line breaks do not matter."""
    return " ".join(str(text or "").lower().split())


def match_kind(chunk_text, gold_span):
    """Return "exact", "fuzzy" or None.

    exact: the normalised gold span is inside the normalised chunk.
    fuzzy: for OCR or hyphenation differences. At least 80% of the span's distinct words
           appear in the chunk (a bag-of-words check), and only for spans of 8+ distinct words.
    """
    gold = normalise(gold_span)
    if not gold:
        return None
    chunk = normalise(chunk_text)
    if gold in chunk:
        return "exact"
    gold_words = set(TOKEN.findall(gold))
    if len(gold_words) < FUZZY_MIN_WORDS:
        return None
    chunk_words = set(TOKEN.findall(chunk))
    if len(gold_words & chunk_words) / len(gold_words) >= 0.8:
        return "fuzzy"
    return None


def distinct_docs(hits):
    """Document titles in rank order, each document once."""
    seen = set()
    ordered = []
    for hit in hits:
        key = normalise(hit.get("title"))
        if key and key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def first_doc_rank(hits, expected_docs):
    """1-based rank (among distinct documents) of the first expected document, or None."""
    wanted = {normalise(doc) for doc in expected_docs if doc}
    seen = []
    for hit in hits:
        ident = hit.get("filename") or hit.get("title") or ""
        if ident not in seen:
            seen.append(ident)
        keys = {normalise(hit.get("title") or ""), normalise(hit.get("filename") or "")}
        if keys & wanted:
            return seen.index(ident) + 1
    return None


def first_passage_match(hits, gold_span, limit=10):
    """(rank, kind) of the first chunk that contains the gold span, or (None, None)."""
    for rank, hit in enumerate(hits[:limit], 1):
        kind = match_kind(hit.get("text") or hit.get("passage"), gold_span)
        if kind:
            return rank, kind
    return None, None


def reciprocal_rank(rank):
    return 1.0 / rank if rank else 0.0


def percentile(values, p):
    """Nearest-rank percentile. Returns None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def summarise(rows):
    """Counts for one mode. Failed or fallback rows are not scored; they are reported."""
    ok = [r for r in rows if r["status"] == "ok"]
    answerable = [r for r in ok if r["expected_doc"]]
    gold = [r for r in answerable if r["has_gold"]]
    out = {
        "questions": len(rows),
        "not_answered": len(rows) - len(ok),
        "doc_n": len(answerable),
        "passage_n": len(gold),
    }
    for k in (1, 3, 5):
        out[f"doc_hit@{k}"] = sum(1 for r in answerable if r["doc_rank"] and r["doc_rank"] <= k)
        out[f"passage_hit@{k}"] = sum(
            1 for r in gold if r["passage_rank"] and r["passage_rank"] <= k
        )
    out["mrr"] = (
        round(sum(reciprocal_rank(r["passage_rank"]) for r in gold) / len(gold), 3)
        if gold
        else None
    )
    out["fuzzy_matches"] = sum(1 for r in gold if r.get("passage_kind") == "fuzzy")
    for key, field in (("wall", "wall_ms"), ("took", "took_ms")):
        values = [r[field] for r in ok if r.get(field) is not None]
        out[f"{key}_p50"] = percentile(values, 50)
        out[f"{key}_p95"] = percentile(values, 95)
    return out
