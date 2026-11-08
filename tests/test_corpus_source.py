import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Imports happen inside the tests on purpose (config must load after other test modules).

MANIFEST = "id,title,filename\ndemo-doc,Demo Document,demo-doc.txt\nbad-doc,Bad,../evil.txt\n"


def make_corpus(folder, body):
    (folder / "corpus" / "files").mkdir(parents=True)
    (folder / "corpus" / "manifest.csv").write_text(MANIFEST, encoding="utf-8")
    (folder / "corpus" / "files" / "demo-doc.txt").write_text(body, encoding="utf-8")


class CorpusSourceTests(unittest.TestCase):
    def test_corpus_document_is_read_cached_and_linked(self):
        import documents

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            make_corpus(root, "The organization shall keep audit logs for incident response.")
            with mock.patch.object(documents, "ROOT", root), mock.patch.object(documents, "DATA", root / "data"):
                result = documents.read_source("corpus:demo-doc")
                self.assertEqual(result["title"], "Demo Document")
                self.assertIn("audit logs", result["text"])
                self.assertEqual(result["link"], "/corpus-file/demo-doc.txt")
                self.assertTrue((root / "data" / "extracted" / "corpus-demo-doc.txt").is_file())
                self.assertIn("audit logs", documents.read_source("corpus:demo-doc")["text"])

    def test_unknown_ids_and_unsafe_filenames_are_refused(self):
        import documents

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            make_corpus(root, "text")
            with mock.patch.object(documents, "ROOT", root), mock.patch.object(documents, "DATA", root / "data"):
                for ref in ("corpus:missing", "corpus:../evil", "corpus:bad-doc"):
                    with self.assertRaises(ValueError):
                        documents.read_source(ref)

    def test_long_text_is_no_longer_cut_at_160000_characters(self):
        import documents

        body = ("Audit logs support incident response. " * 5000)[:180000]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            make_corpus(root, body)
            with mock.patch.object(documents, "ROOT", root), mock.patch.object(documents, "DATA", root / "data"):
                self.assertGreater(len(documents.read_source("corpus:demo-doc")["text"]), 160000)

    def test_catalog_is_empty_without_a_manifest(self):
        import documents

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            with mock.patch.object(documents, "ROOT", Path(tmp)):
                self.assertEqual(documents.corpus_catalog(), {})


if __name__ == "__main__":
    unittest.main()
