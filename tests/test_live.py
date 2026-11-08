"""Live smoke tests against the real cluster and corpus.

Run:  $env:RUN_LIVE = "1" ; python -m pytest -q -m live
Without RUN_LIVE=1 they are skipped. Imports happen inside the tests (config import order).
Where a test says "observed", the expectation comes from a real run on 2026-11-08.
"""

import pytest

pytestmark = pytest.mark.live

DPDP = "Digital Personal Data Protection"


def _es():
    from config import ES_PASSWORD
    from es_client import ES

    if not ES_PASSWORD:
        pytest.skip("ES_PASSWORD is not set")
    return ES(password=ES_PASSWORD)


def _search(mode, query, size=8):
    from es_client import ESFailure
    from search import search

    try:
        return search(_es(), query, "corpus", mode, size=size)
    except ESFailure as exc:
        text = str(exc).lower()
        if "timed out" in text or "408" in text:
            pytest.skip("ELSER timed out (cold start); warm it up and retry")
        raise


def test_cluster_is_version_9():
    assert _es().probe().startswith("9.")


def test_corpus_size():
    from config import CORPUS_INDEX

    es = _es()
    count = es.api("POST", CORPUS_INDEX + "/_count", payload={}, timeout=30)["count"]
    assert count >= 7000
    agg = es.api("POST", CORPUS_INDEX + "/_search", timeout=30,
                 payload={"size": 0, "aggs": {"d": {"cardinality": {"field": "document_id"}}}})
    assert agg["aggregations"]["d"]["value"] == 18


def test_keyword_finds_the_data_protection_act():
    titles = [h["title"] for h in _search("keyword", "Data Principal", 5)["hits"][:5]]
    assert any(DPDP in t for t in titles)


def test_hybrid_finds_the_data_principal_definition():
    question = "What is the person whose personal data is collected called?"
    titles = [h["title"] for h in _search("hybrid", question, 5)["hits"][:5]]
    assert any(DPDP in t for t in titles)  # observed: rank 1


def test_fuzzy_deta_finds_data_or_date():
    import re

    hits = _search("fuzzy", "deta", 8)["hits"]
    text = " ".join((h.get("passage") or "").lower() for h in hits)
    assert re.search(r"\b(data|date)\b", text)  # observed: 2 passages each in the top 8


def test_semantic_highlight_works_inside_rrf():
    from config import CORPUS_INDEX, ES_URL

    es = _es()
    base = {"standard": {"query": {"match": {"content": "personal data"}}}}
    sem = {"standard": {"query": {"semantic": {"field": "content_semantic", "query": "personal data"}}}}
    body = {"size": 2, "_source": ["title"],
            "retriever": {"rrf": {"retrievers": [base, sem], "rank_window_size": 20}},
            "highlight": {"fields": {"content_semantic": {"number_of_fragments": 1}}}}
    r = es.s.request("POST", ES_URL + "/" + CORPUS_INDEX + "/_search", json=body, timeout=90)
    if r.status_code == 408:
        pytest.skip("ELSER timed out (cold start)")
    assert r.status_code == 200
    assert any("content_semantic" in (h.get("highlight") or {}) for h in r.json()["hits"]["hits"])
