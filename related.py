"""Related documents for the corpus index, using Elasticsearch more-like-this.

The corpus stores document_id as a hash, not the manifest id, so the document is found by
its filename. Several of its passages (spread through the document) are used as the
"like" text, and the document itself is excluded. This compares shared vocabulary only.
"""

SOURCE_FIELDS = ["document_id", "filename", "title", "page_number", "content"]


def find_document_id(api, index, filename):
    """The stored document_id for a manifest filename, or None if it is not indexed."""
    body = {
        "size": 5,
        "_source": ["document_id", "filename"],
        "query": {
            "bool": {
                "should": [{"term": {"filename": filename}}, {"match_phrase": {"filename": filename}}],
                "minimum_should_match": 1,
            }
        },
    }
    for row in api("POST", index + "/_search", body).get("hits", {}).get("hits", []):
        source = row.get("_source") or {}
        if source.get("filename") == filename and source.get("document_id"):
            return source["document_id"]
    return None


def sample_chunk_indexes(count, wanted=6):
    """Chunk numbers spread evenly through a document of `count` passages."""
    if count <= 0:
        return []
    if count <= wanted:
        return list(range(count))
    return sorted({round(i * (count - 1) / (wanted - 1)) for i in range(wanted)})


def sample_texts(api, index, document_id, indexes):
    if not indexes:
        return []
    body = {
        "size": max(1, len(indexes)),
        "_source": ["content"],
        "query": {
            "bool": {
                "filter": [{"term": {"document_id": document_id}}, {"terms": {"chunk_index": indexes}}]
            }
        },
    }
    rows = api("POST", index + "/_search", body).get("hits", {}).get("hits", [])
    texts = [(row.get("_source") or {}).get("content", "")[:1500] for row in rows]
    return [t for t in texts if t.strip()]


def related_query(document_id, texts, size=8):
    return {
        "size": size,
        "_source": SOURCE_FIELDS,
        "collapse": {"field": "document_id"},
        "query": {
            "bool": {
                "must": [
                    {
                        "more_like_this": {
                            "fields": ["content"],
                            "like": texts,
                            "min_term_freq": 2,
                            "min_doc_freq": 2,
                            "max_query_terms": 40,
                        }
                    }
                ],
                "must_not": [{"term": {"document_id": document_id}}],
            }
        },
    }


def parse_matches(response, by_filename):
    matches = []
    for row in response.get("hits", {}).get("hits", []):
        source = row.get("_source") or {}
        filename = source.get("filename") or ""
        matches.append(
            {
                "id": by_filename.get(filename, ""),
                "title": source.get("title") or filename or "Document",
                "filename": filename,
                "page": source.get("page_number"),
                "passage": (source.get("content") or "")[:450],
                "score": row.get("_score"),
            }
        )
    return matches


def find_related(api, index, filename, by_filename, size=8):
    """api(method, path, body) -> dict. Raises ValueError with a plain message when it cannot work."""
    document_id = find_document_id(api, index, filename)
    if not document_id:
        raise ValueError("This document was not found in the corpus index.")
    count = api("POST", index + "/_count", {"query": {"term": {"document_id": document_id}}}).get("count", 0)
    texts = sample_texts(api, index, document_id, sample_chunk_indexes(count))
    if not texts:
        raise ValueError("No passages could be read for this document.")
    response = api("POST", index + "/_search", related_query(document_id, texts, size))
    return parse_matches(response, by_filename)
