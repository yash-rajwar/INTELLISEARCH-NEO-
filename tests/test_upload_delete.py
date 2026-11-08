import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Imports happen inside the tests on purpose (see test_chunker_caps.py).

GOOD_ID = "a" * 32


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.content = b"x"

    def json(self):
        return self._body


class FakeSession:
    def __init__(self):
        self.calls = []

    def head(self, url, timeout=None):
        return FakeResponse(200)

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return FakeResponse(200, {"deleted": 3})


class DeleteUploadTests(unittest.TestCase):
    def test_delete_targets_one_document_only(self):
        from es_client import ES

        session = FakeSession()
        client = ES(password="x", session=session)
        self.assertEqual(client.delete_upload_chunks(GOOD_ID), 3)
        method, url, kw = session.calls[-1]
        self.assertEqual(method, "POST")
        self.assertIn("_delete_by_query", url)
        self.assertEqual(kw["json"], {"query": {"term": {"document_id": GOOD_ID}}})

    def test_bad_document_id_is_refused(self):
        from es_client import ES, ESFailure

        session = FakeSession()
        client = ES(password="x", session=session)
        for bad in ("", "*", "../x", "A" * 32):
            with self.assertRaises(ESFailure):
                client.delete_upload_chunks(bad)
        self.assertEqual(session.calls, [])

    def test_remove_upload_clears_local_records(self):
        import store

        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(store, "DB", Path(folder) / "test.sqlite3"):
                store.init_v2_db()
                store.save_doc(GOOD_ID, "a.txt", ".txt", 10, 1)
                store.save_insights(GOOD_ID, "Other", ["x"])
                store.remember_hash("h1", GOOD_ID)
                store.remove_upload(GOOD_ID)
                self.assertIsNone(store.upload_doc(GOOD_ID))
                self.assertIsNone(store.get_insights(GOOD_ID))
                self.assertIsNone(store.find_hash("h1"))


if __name__ == "__main__":
    unittest.main()
