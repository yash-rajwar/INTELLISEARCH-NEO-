"""Corpus index mapping as code (WP-03). Never deletes anything."""

from __future__ import annotations

from es_http import ESFailure


def corpus_mapping(inference_id: str, semantic: bool = True) -> dict:
    props = {
        "document_id": {"type": "keyword"},
        "content_hash": {"type": "keyword"},
        "collection": {"type": "keyword"},
        "filename": {"type": "keyword"},
        "title": {"type": "text", "fields": {"raw": {"type": "keyword", "ignore_above": 256}}},
        "file_type": {"type": "keyword"},
        "section": {"type": "keyword"},
        "page_number": {"type": "integer"},
        "start_line": {"type": "integer"},
        "end_line": {"type": "integer"},
        "chunk_index": {"type": "integer"},
        "created_at": {"type": "date"},
        "content": {"type": "text"},
    }
    if semantic:
        props["content_semantic"] = {"type": "semantic_text", "inference_id": inference_id}
    return {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},  # single-node demo
        "mappings": {"dynamic": "strict", "properties": props},
    }


def has_semantic_field(es, index: str) -> bool:
    props = es.mapping(index).get(index, {}).get("mappings", {}).get("properties", {})
    return props.get("content_semantic", {}).get("type") == "semantic_text"


def ensure_corpus_index(es, settings, semantic: bool = True) -> bool:
    """Create the corpus index if missing. Returns True if it was created."""
    index = settings.corpus_index
    if es.exists(index):
        if semantic and not has_semantic_field(es, index):
            raise ESFailure(
                f"Index {index} exists but has no semantic_text field; "
                "choose another CORPUS_INDEX or ingest with --no-semantic"
            )
        return False
    es.request("PUT", index, json=corpus_mapping(settings.es_inference_id, semantic), timeout=30)
    es.invalidate()
    return True
