import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Imports of extractors/store happen inside the tests on purpose: they load
# config, and other test files set environment variables before config loads.


class UploadLimitTests(unittest.TestCase):
    def test_long_text_is_not_cut_off(self):
        from extractors import make_chunks

        # about 420,000 characters; the old cap was 270,000
        text = "alpha " * 70000 + "ENDMARKER"
        chunks = make_chunks([{"page": None, "text": text}])
        self.assertGreater(len(chunks), 120)
        self.assertIn("ENDMARKER", chunks[-1]["content"])

    def test_too_many_passages_is_refused(self):
        import extractors

        # A tiny limit keeps the test fast; the logic is the same.
        with mock.patch.object(extractors, "MAX_PASSAGES", 5):
            with self.assertRaises(ValueError):
                extractors.make_chunks([{"page": None, "text": "word " * 2000}])

    def test_short_text_gives_one_passage(self):
        from extractors import make_chunks

        chunks = make_chunks([{"page": 1, "text": "A short sentence."}])
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["page_number"], 1)

    def test_duplicate_hash_lookup(self):
        import store

        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(store, "DB", Path(folder) / "test.sqlite3"):
                store.init_v2_db()
                self.assertIsNone(store.find_hash("abc"))
                store.remember_hash("abc", "doc1")
                self.assertEqual(store.find_hash("abc")["doc_id"], "doc1")
                store.forget_hash("doc1")
                self.assertIsNone(store.find_hash("abc"))


if __name__ == "__main__":
    unittest.main()