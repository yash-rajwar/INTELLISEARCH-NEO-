"""Read-only smoke test of the corpus index: counts per file, then BM25, semantic and RRF.

    python scripts\\smoke_corpus.py
It never writes. The first semantic query can take ~30 s if ELSER is cold.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from es_http import ESFailure, ESHttp  # noqa: E402
from settings import load_settings  # noqa: E402

QUESTIONS = [
    (
        "different words (meaning)",
        "What should an organisation do when attackers get into its network?",
    ),
    ("exact term", "ClientHello"),
    ("different words (legal)", "how can a citizen ask the government for records"),
]
FIELDS = ["title", "filename", "page_number", "start_line", "content"]


def where(src):
    if src.get("page_number"):
        return f"p.{src['page_number']}"
    if src.get("start_line"):
        return f"lines {src['start_line']}-{src.get('end_line')}"
    return ""


def show(es, index, label, body):
    body = {"size": 3, "_source": FIELDS, **body}
    try:
        res = es.request("POST", f"{index}/_search", json=body, timeout=120, retries=0)
    except ESFailure as exc:
        print(f"  {label:9} FAILED: {exc}")
        return
    hits = res["hits"]["hits"]
    print(f"  {label:9} {res.get('took')} ms")
    for h in hits:
        s = h["_source"]
        snippet = " ".join(s.get("content", "").split())[:90]
        print(f"     - {s.get('title', '?')[:45]} {where(s)} | {snippet}")


def main():
    cfg = load_settings()
    es = ESHttp(cfg)
    index = cfg.corpus_index
    agg = es.request(
        "POST",
        f"{index}/_search",
        timeout=30,
        json={"size": 0, "aggs": {"f": {"terms": {"field": "filename", "size": 50}}}},
    )
    total = es.request("POST", f"{index}/_count", timeout=30)["count"]
    print(f"{index}: {total} chunks")
    for b in agg["aggregations"]["f"]["buckets"]:
        print(f"  {b['key']:34} {b['doc_count']}")
    for kind, q in QUESTIONS:
        print(f"\nQ ({kind}): {q}")
        bm25 = {"match": {"content": q}}
        sem = {"semantic": {"field": "content_semantic", "query": q}}
        show(es, index, "BM25", {"query": bm25})
        show(es, index, "ELSER", {"query": sem})
        show(
            es,
            index,
            "RRF",
            {
                "retriever": {
                    "rrf": {
                        "retrievers": [{"standard": {"query": bm25}}, {"standard": {"query": sem}}],
                        "rank_window_size": 50,
                        "rank_constant": 60,
                    }
                }
            },
        )


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
