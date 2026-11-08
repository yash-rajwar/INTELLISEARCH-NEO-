import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Imports happen inside the tests on purpose (config must load after other test modules).


class InterruptedUploadTests(unittest.TestCase):
    def test_extracting_rows_become_errors_and_others_are_untouched(self):
        import store

        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(store, "DB", Path(folder) / "test.sqlite3"):
                store.init_v2_db()
                store.save_doc("a" * 32, "busy.txt", ".txt", 5, status="extracting")
                store.save_doc("b" * 32, "done.txt", ".txt", 5, 3, 0, "indexed")
                self.assertEqual(store.mark_interrupted(), 1)
                self.assertEqual(store.upload_doc("a" * 32)["status"], "error")
                self.assertIn("Interrupted", store.upload_doc("a" * 32)["error"])
                self.assertEqual(store.upload_doc("b" * 32)["status"], "indexed")
                self.assertEqual(store.mark_interrupted(), 0)


if __name__ == "__main__":
    unittest.main()
