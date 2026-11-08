import unittest

# Imports happen inside the tests on purpose (config must load after other test modules).


def make_hit(index, key):
    return {
        "_index": index,
        "_id": key,
        "_score": 1.0,
        "_source": {
            "content": "passage " + key,
            "title": "Title " + key,
            "filename": key + ".pdf",
            "document_id": key,
            "file_type": "pdf",
        },
    }


class FakeClient:
    """Pretends to be Elasticsearch: BM25 finds only 'a'; the hybrid/semantic side finds 'a' and 'b'."""

    def __init__(self, lexical_fails=False):
        from config import CORPUS_INDEX

        self.index = CORPUS_INDEX
        self.lexical_fails = lexical_fails
        self.calls = []

    def exists(self, name):
        return True

    def api(self, method, path, payload=None, timeout=None, raw=None):
        from es_client import ESFailure

        self.calls.append(path)
        if path.endswith("/_mapping"):
            name = path[: -len("/_mapping")]
            return {name: {"mappings": {"properties": {"content_semantic": {"type": "semantic_text"}}}}}
        payload = payload or {}
        if "retriever" in payload:
            hits = [make_hit(self.index, "a"), make_hit(self.index, "b")]
        elif "content_semantic" in str(payload.get("query", "")):
            hits = [make_hit(self.index, "b"), make_hit(self.index, "a")]
        else:
            if self.lexical_fails:
                raise ESFailure("lexical lookup failed")
            hits = [make_hit(self.index, "a")]
        return {"took": 1, "hits": {"total": {"value": len(hits)}, "hits": hits}}


class MeaningTagTests(unittest.TestCase):
    def test_hybrid_tags_only_hits_missing_from_keyword_results(self):
        from search import search

        r = search(FakeClient(), "some question", "corpus", "hybrid", size=5)
        by_id = {h["id"]: h for h in r["hits"]}
        self.assertFalse(by_id["a"]["meaning_only"])
        self.assertTrue(by_id["b"]["meaning_only"])

    def test_keyword_mode_has_no_tag(self):
        from search import search

        r = search(FakeClient(), "some question", "corpus", "keyword", size=5)
        self.assertNotIn("meaning_only", r["hits"][0])

    def test_failed_keyword_lookup_means_no_tags(self):
        from search import search

        r = search(FakeClient(lexical_fails=True), "some question", "corpus", "hybrid", size=5)
        self.assertTrue(r["hits"])
        self.assertTrue(all("meaning_only" not in h for h in r["hits"]))


class PaginationTests(unittest.TestCase):
    def test_result_limit(self):
        from search import result_limit

        self.assertEqual(result_limit(None), 30)
        self.assertEqual(result_limit("abc"), 30)
        self.assertEqual(result_limit("60"), 60)
        self.assertEqual(result_limit("5"), 30)
        self.assertEqual(result_limit("99999"), 150)


if __name__ == "__main__":
    unittest.main()
