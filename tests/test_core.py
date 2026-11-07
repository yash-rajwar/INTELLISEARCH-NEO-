import sys
import unittest
from pathlib import Path
from io import BytesIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from search import payload, indices_for, search
from extractors import text_pages, make_chunks
from config import SOURCES
from es_client import ES


class MockES:
    def exists(self, x):
        return x in [z[0] for z in SOURCES.values()]

    def api(self, m, p, **kw):
        if p.endswith("/_mapping"):
            n = p.split("/")[0]
            return {
                n: {
                    "mappings": {
                        "properties": {
                            "content_semantic": {"type": "semantic_text"}
                            if n != "demo_documents"
                            else {"type": "text"}
                        }
                    }
                }
            }
        if p.endswith("/_search"):
            return {
                "took": 3,
                "hits": {
                    "total": {"value": 1},
                    "hits": [
                        {
                            "_id": "01-1-22",
                            "_index": "books_passages_phase2e_v1",
                            "_score": 0.72,
                            "_source": {
                                "title": "A Novel",
                                "book_id": "01",
                                "start_line": 1,
                                "content": "A passage",
                            },
                        }
                    ],
                },
            }
        raise AssertionError(p)


class CoreTests(unittest.TestCase):
    def test_weighted_format(self):
        p = payload("question", "weighted")
        r = p["retriever"]["rrf"]["retrievers"]
        self.assertEqual([x["weight"] for x in r], [1.0, 1.5])
        self.assertEqual(
            r[1]["retriever"]["standard"]["query"]["match"]["content_semantic"]["query"], "question"
        )

    def test_semantic_query(self):
        p = payload("creature", "semantic", book_id="02")
        self.assertEqual(p["query"]["bool"]["filter"][0]["term"]["book_id"], "02")

    def test_lexical_search(self):
        r = search(MockES(), "question", scope="passages", mode="keyword")
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["hits"][0]["source_url"], "/book/01?line=1")

    def test_bad_filters(self):
        with self.assertRaises(ValueError):
            search(MockES(), "q", book_id="../../")
        with self.assertRaises(ValueError):
            search(MockES(), "q", scope="nonsense")

    def test_chunking(self):
        chunks = make_chunks(
            [{"page": 4, "text": ("human creature " * 400)}], target=300, overlap=50
        )
        self.assertTrue(len(chunks) > 1)
        self.assertTrue(all(c["page_number"] == 4 for c in chunks))

    def test_text_extraction(self):
        pages, n = text_pages(b"\xef\xbb\xbfHello world!", ".txt")
        self.assertEqual(n, 0)
        self.assertIn("Hello", pages[0]["text"])

    def test_docx_extraction(self):
        from docx import Document

        b = BytesIO()
        d = Document()
        d.add_paragraph("Hello semantic document")
        d.save(b)
        pages, n = text_pages(b.getvalue(), ".docx")
        self.assertIn("Hello semantic document", pages[0]["text"])

    def test_empty_pdf_fails(self):
        with self.assertRaises(Exception):
            text_pages(b"junk", ".pdf")

    def test_bundled_pdf_page_links(self):
        path = Path(__file__).resolve().parents[1] / "samples" / "sample_two_page_brief.pdf"
        pages, n = text_pages(path.read_bytes(), ".pdf")
        self.assertEqual(n, 2)
        self.assertIn("North Archive, room 17", pages[1]["text"])
        self.assertEqual(make_chunks(pages)[-1]["page_number"], 2)

    def test_bulk_writes_only_showcase_index(self):
        import json
        from config import UP_INDEX

        class FakeWriter(ES):
            def __init__(self):
                self.upload_semantic = False
                self.records = []

            def exists(self, index):
                return index == UP_INDEX

            def api(self, m, p, **kw):
                self.records.append((m, p, kw))
                return {"errors": False}

        fake = FakeWriter()
        fake.bulk_upload("abc", [{"document_id": "abc", "content": "example"}], semantic=False)
        actions = [
            json.loads(l)["index"]
            for m, p, kw in fake.records
            for i, l in enumerate(kw["raw"].decode().splitlines())
            if i % 2 == 0
        ]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["_index"], UP_INDEX)


if __name__ == "__main__":
    unittest.main()
