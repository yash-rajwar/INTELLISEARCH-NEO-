"""Offline regression suite: intentionally needs no Flask server or live Elasticsearch."""

import sys
import unittest
from pathlib import Path

import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("LEGACY_ENABLED", "true")
from intelligence import classify, summarize, compare_texts, explain, evidence_reply
from extractors import text_pages
from ocr import available
from config import PORT, UP_INDEX
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]


class V2Tests(unittest.TestCase):
    def test_index_and_port_isolation(self):
        self.assertEqual(PORT, 5003)
        self.assertEqual(UP_INDEX, "intellisearch_showcase_chunks_v3")

    def test_category_and_tags(self):
        c = classify(
            "Research experiment: the study used evidence and analysis of data. Research methodology."
        )
        self.assertEqual(c["category"], "Research")
        self.assertTrue(c["tags"])

    def test_summary_is_extractive(self):
        text = "The team recorded a clear signal during the experiment. The signal changed after the second inspection. Researchers documented their results for later review."
        s = summarize(text, 2)
        self.assertEqual(len(s["sentences"]), 2)
        self.assertTrue(all(x in text for x in s["sentences"]))

    def test_compare(self):
        r = compare_texts(
            "Staff review records monthly in Sector 7.", "Staff review records weekly in Sector 7."
        )
        self.assertTrue(r["overlap_pct"] > 0)
        self.assertIn("monthly", r["left_only"])
        self.assertIn("weekly", r["right_only"])

    def test_explanation_does_not_claim_model_attribution(self):
        e = explain(
            "blue lantern archive", "The archive recorded blue lantern safety checks", "semantic"
        )
        self.assertIn("archive", e["matched"])
        self.assertIn("not an attribution", e["disclaimer"])

    def test_evidence_citations(self):
        hits = [
            {
                "index": "books_20",
                "id": "abc",
                "title": "Sample",
                "passage": "A scientific experiment concluded with the archive inspection. The staff reported its findings.",
                "source_url": "/book/01?line=1",
            }
        ]
        e = evidence_reply("scientific archive inspection", hits)
        self.assertEqual(e[0]["citation"], 1)
        self.assertIn("/context/books_20/abc", e[0]["context_url"])

    def test_pdf_ocr_sample_contains_no_selectable_text(self):
        path = ROOT / "samples" / "sample_scanned_memo.pdf"
        with self.assertRaisesRegex(ValueError, "OCR"):
            text_pages(path.read_bytes(), ".pdf")

    def test_templates_parse(self):
        env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
        for p in (ROOT / "templates").glob("*.html"):
            env.parse(p.read_text(encoding="utf-8"))

    def test_example_comparison_files(self):
        a = (ROOT / "samples" / "sample_comparison_policy_A.txt").read_text()
        b = (ROOT / "samples" / "sample_comparison_policy_B.txt").read_text()
        self.assertIn("monthly", a)
        self.assertIn("weekly", b)

    def test_ocr_status_does_not_require_tesseract(self):
        status, message = available()
        self.assertIsInstance(status, bool)
        self.assertIsInstance(message, str)

    def test_existing_search_tests_are_still_run_separately(self):
        self.assertTrue((ROOT / "tests" / "test_core.py").exists())


if __name__ == "__main__":
    unittest.main()
