import unittest

# Imports happen inside the tests on purpose (config must load after other test modules).


class Recorder:
    def __init__(self):
        self.calls = []

    def exists(self, name):
        return True

    def api(self, method, path, payload=None, timeout=None, raw=None):
        self.calls.append((path, payload))
        return {"took": 1, "hits": {"total": {"value": 0}, "hits": []}}


class FuzzyModeTests(unittest.TestCase):
    def test_fuzzy_is_listed_and_adds_fuzziness_only_for_itself(self):
        from search import MODES, payload

        self.assertIn("fuzzy", MODES)
        self.assertEqual(payload("recieve", "fuzzy")["query"]["multi_match"]["fuzziness"], "AUTO")
        self.assertNotIn("fuzziness", payload("recieve", "keyword")["query"]["multi_match"])

    def test_fuzzy_search_is_one_bm25_request_and_never_touches_elser(self):
        from search import search

        rec = Recorder()
        result = search(rec, "recieve", "corpus", "fuzzy")
        self.assertEqual(result["mode_used"], "fuzzy")
        searches = [p for path, p in rec.calls if path.endswith("/_search")]
        self.assertEqual(len(searches), 1)
        self.assertIn("fuzziness", searches[0]["query"]["multi_match"])
        self.assertNotIn("content_semantic", str(searches[0]["query"]))
        self.assertFalse(any(path.endswith("/_mapping") for path, _ in rec.calls))


if __name__ == "__main__":
    unittest.main()
