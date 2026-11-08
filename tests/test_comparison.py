import unittest

from comparison import annotate


def hit(title, rank, **extra):
    row = {"title": title, "rank": rank, "passage": "Passage from " + title, "has_context": False}
    row.update(extra)
    return row


def entry(titles, ms=40, mode_used="keyword"):
    hits = [hit(t, i + 1) for i, t in enumerate(titles)]
    result = {"hits": hits, "elapsed_ms": ms, "count": len(hits), "mode_used": mode_used}
    return {"result": result, "error": ""}


class AnnotateTests(unittest.TestCase):
    def test_markers_and_sentence(self):
        outputs = {"keyword": entry(["A", "B", "C"]), "semantic": entry(["B", "D"], mode_used="semantic")}
        summary = annotate(outputs)
        self.assertTrue(summary["comparable"])
        self.assertEqual(summary["meaning_only"], ["D"])
        self.assertEqual(summary["keyword_only"], ["A", "C"])
        keyword_hits = outputs["keyword"]["result"]["hits"]
        self.assertEqual([h["marker"] for h in keyword_hits], ["keyword", "both", "keyword"])
        self.assertEqual(outputs["semantic"]["result"]["hits"][1]["marker"], "meaning")
        self.assertIn("1 document that keyword search did not", summary["sentence"])
        self.assertIn("2 documents that semantic search did not", summary["sentence"])

    def test_same_documents(self):
        outputs = {"keyword": entry(["A", "B"]), "semantic": entry(["B", "A"], mode_used="semantic")}
        summary = annotate(outputs)
        self.assertIn("same documents", summary["sentence"])
        self.assertEqual(outputs["keyword"]["result"]["hits"][0]["marker"], "both")

    def test_failed_semantic_gives_no_markers_and_no_crash(self):
        outputs = {"keyword": entry(["A"]), "semantic": {"result": None, "error": "timed out"}}
        summary = annotate(outputs)
        self.assertFalse(summary["comparable"])
        self.assertEqual(outputs["semantic"]["status"], "failed")
        self.assertNotIn("marker", outputs["keyword"]["result"]["hits"][0])
        self.assertTrue(summary["note"])

    def test_skipped_status(self):
        outputs = {"hybrid": {"result": None, "error": "Skipped to avoid repeated ELSER timeouts."}}
        annotate(outputs)
        self.assertEqual(outputs["hybrid"]["status"], "skipped")

    def test_fallback_is_flagged_and_not_compared(self):
        outputs = {
            "keyword": entry(["A"]),
            "semantic": entry(["A"], mode_used="keyword fallback"),
        }
        summary = annotate(outputs)
        self.assertEqual(outputs["semantic"]["status"], "fallback")
        self.assertFalse(summary["comparable"])
        self.assertIn("fell back", summary["note"])

    def test_slow_status_label(self):
        outputs = {"semantic": entry(["A"], ms=4500, mode_used="semantic")}
        annotate(outputs)
        self.assertEqual(outputs["semantic"]["status"], "slow")
        self.assertEqual(outputs["semantic"]["status_label"], "slow, 4.5 s")

    def test_empty_outputs(self):
        self.assertFalse(annotate({})["comparable"])


class CompareTemplateTests(unittest.TestCase):
    def render(self, outputs, summary):
        from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

        from config import ROOT

        stub = DictLoader({"base.html": "{% block content %}{% endblock %}", "_filters.html": ""})
        env = Environment(
            loader=ChoiceLoader([stub, FileSystemLoader(str(ROOT / "templates"))]),
            autoescape=True,
        )
        env.globals.update(
            url_for=lambda name, **kw: "/" + name,
            MODES={"keyword": "Keyword", "semantic": "Semantic", "hybrid": "Hybrid", "weighted": "Weighted"},
        )
        return env.get_template("compare.html").render(q="test", scope="corpus", outputs=outputs, summary=summary)

    def test_markers_status_and_escaping(self):
        outputs = {
            "keyword": entry(["A", "<b>B</b>"]),
            "semantic": entry(["<b>B</b>", "D"], mode_used="semantic"),
            "hybrid": {"result": None, "error": "Skipped to avoid repeated ELSER timeouts."},
        }
        summary = annotate(outputs)
        html = self.render(outputs, summary)
        self.assertIn("Only found by meaning", html)
        self.assertIn("Found by both", html)
        self.assertIn("skipped", html)
        self.assertIn("Retry this comparison", html)
        self.assertIn("&lt;b&gt;B&lt;/b&gt;", html)
        self.assertNotIn("<b>B</b>", html)

    def test_renders_without_summary(self):
        outputs = {"keyword": entry(["A"])}
        html = self.render(outputs, None)
        self.assertIn("Passage from A", html)


if __name__ == "__main__":
    unittest.main()
