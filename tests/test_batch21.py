"""Batch 21: related corpus documents. Imports nothing that touches config or the app."""

import json

import pytest

from related import find_document_id, find_related, parse_matches, related_query, sample_chunk_indexes

INDEX = "corpus_index"
DOC_ID = "e71725fa32e892f887308816046c4227"


def fake_api(count=129, known=True):
    calls = []

    def api(method, path, body):
        calls.append((path, body))
        text = json.dumps(body)
        if path.endswith("/_count"):
            return {"count": count}
        if "more_like_this" in text:
            return {"hits": {"hits": [
                {"_score": 4.2, "_source": {"document_id": "z", "filename": "india-dpdp-2023.pdf",
                                            "title": "DPDP Act", "page_number": 3, "content": "x" * 600}},
                {"_score": 1.0, "_source": {"document_id": "y", "filename": "unknown.pdf", "content": "y"}},
            ]}}
        if "chunk_index" in text:
            return {"hits": {"hits": [{"_source": {"content": "passage %d" % i}} for i in range(3)]}}
        if not known:
            return {"hits": {"hits": []}}
        return {"hits": {"hits": [
            {"_source": {"document_id": "other", "filename": "india-it-act-2000.pdf.bak"}},
            {"_source": {"document_id": DOC_ID, "filename": "india-it-act-2000.pdf"}},
        ]}}

    api.calls = calls
    return api


def test_document_is_found_by_exact_filename_only():
    api = fake_api()
    assert find_document_id(api, INDEX, "india-it-act-2000.pdf") == DOC_ID
    assert find_document_id(fake_api(known=False), INDEX, "india-it-act-2000.pdf") is None


def test_sampling_spreads_through_the_document():
    assert sample_chunk_indexes(0) == []
    assert sample_chunk_indexes(4) == [0, 1, 2, 3]
    spread = sample_chunk_indexes(129)
    assert spread[0] == 0 and spread[-1] == 128 and len(spread) == 6
    assert spread == sorted(set(spread))


def test_query_excludes_the_document_itself_and_groups_by_document():
    q = related_query(DOC_ID, ["a", "b"])
    assert q["query"]["bool"]["must_not"] == [{"term": {"document_id": DOC_ID}}]
    assert q["collapse"] == {"field": "document_id"}
    assert q["query"]["bool"]["must"][0]["more_like_this"]["like"] == ["a", "b"]


def test_matches_are_mapped_trimmed_and_unknown_files_survive():
    api = fake_api()
    matches = find_related(api, INDEX, "india-it-act-2000.pdf", {"india-dpdp-2023.pdf": "india-dpdp-2023"})
    assert matches[0]["id"] == "india-dpdp-2023" and matches[0]["page"] == 3
    assert len(matches[0]["passage"]) == 450
    assert matches[1]["id"] == "" and matches[1]["title"] == "unknown.pdf"
    assert parse_matches({}, {}) == []


def test_not_indexed_and_no_passages_give_plain_errors():
    with pytest.raises(ValueError, match="not found"):
        find_related(fake_api(known=False), INDEX, "india-it-act-2000.pdf", {})
    with pytest.raises(ValueError, match="No passages"):
        find_related(fake_api(count=0), INDEX, "india-it-act-2000.pdf", {})
