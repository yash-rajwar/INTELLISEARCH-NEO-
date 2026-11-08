"""V3-specific offline contract tests; neither ES nor Flask server required."""

import sys
import tempfile
import sqlite3
from pathlib import Path
from unittest import TestCase, mock

import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("LEGACY_ENABLED", "true")
from config import PORT, UP_INDEX, V2_INDEX, SOURCES
from search import indices_for, payload, search, fuse_ranked
from es_client import ESFailure


def hit(i, idx="books_passages_phase2e_v1", text="Example excerpt"):
    src = (
        {
            "document_id": "a" * 32,
            "filename": "test.pdf",
            "file_type": ".pdf",
            "page_number": 2,
            "content": text,
            "title": "Test PDF",
        }
        if idx == V2_INDEX
        else {"book_id": "02", "start_line": 42, "content": text, "title": "Frankenstein"}
    )
    return {"_id": str(i), "_index": idx, "_score": 5.0, "_source": src}


class MixedIndexMock:
    def __init__(self, fail_sem=False):
        self.calls = []
        self.fail_sem = fail_sem

    def exists(self, name):
        return name in ("books_passages_phase2e_v1", V2_INDEX)

    def api(self, method, path, **kw):
        self.calls.append((method, path, kw))
        if path.endswith("/_mapping"):
            idx = path.split("/")[0]
            return {
                idx: {
                    "mappings": {
                        "properties": (
                            {"content_semantic": {"type": "semantic_text"}}
                            if idx == "books_passages_phase2e_v1"
                            else {"content": {"type": "text"}}
                        )
                    }
                }
            }
        if path.endswith("/_search"):
            if path == "books_passages_phase2e_v1/_search":
                if self.fail_sem:
                    raise ESFailure("Elasticsearch timed out after 65s")
                rows = [hit("s1")]
            else:
                rows = [hit("lex1", V2_INDEX), hit("s1")]
            return {"took": 5, "hits": {"total": {"value": len(rows)}, "hits": rows}}
        raise AssertionError("Unexpected API call " + path)


class V3ContractTests(TestCase):
    def test_v3_isolation(self):
        self.assertEqual(PORT, 5003)
        self.assertNotEqual(UP_INDEX, V2_INDEX)
        self.assertEqual(SOURCES["uploads_v2"][0], V2_INDEX)

    def test_filter_types_retains_old_and_new_uploads(self):
        class Exists:
            def exists(self, x):
                return True

        self.assertEqual(
            indices_for(Exists(), "all", doc_type=".pdf"),
            ["intellisearch_corpus_v1", UP_INDEX, V2_INDEX],
        )

    def test_native_rrf_payload_has_no_track_total_hits(self):
        for mode in ("weighted", "hybrid"):
            p = payload("question", mode)
            self.assertNotIn("track_total_hits", p)
            self.assertIn("retriever", p)

    def test_rrf_fusion_uses_rank_not_score(self):
        fused = fuse_ranked([hit("a"), hit("b")], [hit("b"), hit("c")], False, 10)
        self.assertEqual(fused[0]["_id"], "b")
        self.assertNotEqual(fused[0]["_score"], 5.0)

    def test_cross_index_hybrid_queries_semantic_indices_only(self):
        fake = MixedIndexMock()
        r = search(fake, "An unfinished creation", "all", "hybrid", size=4)
        requests = [(p, kw["payload"]) for m, p, kw in fake.calls if p.endswith("/_search")]
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0][0], f"books_passages_phase2e_v1,{V2_INDEX}/_search")
        self.assertEqual(requests[1][0], "books_passages_phase2e_v1/_search")
        self.assertIn("query", requests[1][1])
        self.assertNotIn("retriever", requests[1][1])
        self.assertEqual(r["mode_used"], "hybrid")
        self.assertTrue(any(h["type"] == "uploads_v2" for h in r["hits"]))
        self.assertIn(
            "/uploaded-v2/", [h["source_url"] for h in r["hits"] if h["type"] == "uploads_v2"][0]
        )

    def test_cross_index_timeout_is_explicit_keyword_fallback(self):
        fake = MixedIndexMock(fail_sem=True)
        r = search(fake, "An unfinished creation", "all", "weighted", size=4)
        self.assertEqual(r["mode_used"], "keyword fallback")
        self.assertIn("BM25", r["warning"])

    def test_single_semantic_index_uses_semantic_field(self):
        fake = MixedIndexMock()
        r = search(fake, "creation", "passages", "semantic", size=1)
        searches = [kw["payload"] for m, p, kw in fake.calls if p.endswith("/_search")]
        # The semantic search comes first. A second, BM25-only lookup may follow: it is used
        # to tag hits that were found by meaning and not by keyword.
        self.assertIn(len(searches), (1, 2))
        self.assertEqual(searches[0]["query"]["match"]["content_semantic"]["query"], "creation")
        self.assertEqual(r["hits"][0]["source_url"], "/book/02?line=42")

    def test_v2_reader_opens_database_read_only(self):
        import v2_reader

        with tempfile.TemporaryDirectory() as root:
            data = Path(root)
            db = data / "showcase.sqlite3"
            con = sqlite3.connect(db)
            try:
                con.execute(
                    "CREATE TABLE uploads (doc_id TEXT,filename TEXT,file_type TEXT,status TEXT,created_at TEXT)"
                )
                con.execute(
                    "INSERT INTO uploads VALUES (?,?,?,?,?)",
                    ("a" * 32, "original.pdf", ".pdf", "indexed", "2026-10-14"),
                )
                con.commit()
            finally:
                con.close()
            with mock.patch.object(v2_reader, "V2_DATA", data):
                got = v2_reader.v2_docs()
                self.assertEqual(got[0]["filename"], "original.pdf")
                self.assertIsNone(v2_reader.v2_path("invalid"))
                self.assertFalse((data / "uploads").exists())

    def test_invalid_filters_blocked(self):
        with self.assertRaises(ValueError):
            search(MixedIndexMock(), "question", scope="../bad")
        with self.assertRaises(ValueError):
            search(MixedIndexMock(), "question", doc_type=".exe")


class TemplateSmokeTests(TestCase):
    def test_new_templates_render_with_mock_data(self):
        from jinja2 import Environment, FileSystemLoader
        from types import SimpleNamespace
        from config import ROOT, BOOK_NAMES
        from search import SCOPES, MODES

        env = Environment(loader=FileSystemLoader(str(ROOT / "templates")), autoescape=True)
        env.globals.update(
            url_for=lambda name, **kw: "/" + name,
            request=SimpleNamespace(path="/system"),
            get_flashed_messages=lambda **kw: [],
            csrf_token="dummy",
            SCOPES=SCOPES,
            MODES=MODES,
            BOOK_NAMES=BOOK_NAMES,
            has_local_llm=False,
        )
        status = {
            "es_version": "9.5.3",
            "es_error": None,
            "counts": {"books": 5, "passages": 2354, "uploads": 0},
            "inference": {"state": "Mapping configured", "endpoint": ".elser-2-elasticsearch"},
            "ocr": {"ready": False, "detail": "not installed"},
            "ollama": {"configured": False, "note": "not configured"},
            "port": 5003,
        }
        for name, variables in {
            "system.html": {"status": status},
            "demo.html": {
                "cases": [
                    {
                        "id": "F1",
                        "name": "Test",
                        "query": "Creation",
                        "expected": "Frankenstein",
                        "scope": "passages",
                    }
                ]
            },
            "semantic_check.html": {"report": {"ok": True, "message": "one query passed"}},
            "library.html": {"docs": [], "insights": {}, "v2_docs": []},
            "home.html": {
                "counts": {
                    "books": 5,
                    "passages": 2354,
                    "documents": 12,
                    "uploads": 0,
                    "uploads_v2": 0,
                },
                "stats": {"queries": 0, "uploads": 0},
                "error": "",
                "version": "9.5.3",
            },
        }.items():
            with self.subTest(template=name):
                html = env.get_template(name).render(**variables)
                self.assertIn("IntelliSearch", html)
                self.assertIn("</html>", html)

    def test_all_new_html_parses(self):
        from jinja2 import Environment, FileSystemLoader
        from config import ROOT

        env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
        for path in (ROOT / "templates").glob("*.html"):
            with self.subTest(filename=path.name):
                env.parse(path.read_text(encoding="utf-8"))
