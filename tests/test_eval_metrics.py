import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval import metrics
from eval.run_eval import load_questions


def hit(title, text="", passage=""):
    return {"title": title, "text": text, "passage": passage}


class SpanTests(unittest.TestCase):
    def test_exact_match_ignores_case_and_line_breaks(self):
        chunk = "The Procedure and\nsafeguards subject to which blocking may be carried out"
        self.assertEqual(
            metrics.match_kind(chunk, "procedure and safeguards subject to which"), "exact"
        )

    def test_fuzzy_match_handles_hyphenation_for_long_spans(self):
        chunk = (
            "(3) The subscriber or intermediary or any person in-\ncharge of the computer resource "
            "shall, when called upon, extend all facilities and technical assistance"
        )
        gold = "subscriber or intermediary or any person in charge of the computer resource shall extend all facilities"
        self.assertEqual(metrics.match_kind(chunk, gold), "fuzzy")

    def test_short_spans_never_match_fuzzily(self):
        self.assertIsNone(metrics.match_kind("the quick brown fox", "the fox brown quick dog"))

    def test_empty_gold_span_matches_nothing(self):
        self.assertIsNone(metrics.match_kind("anything", ""))


class RankTests(unittest.TestCase):
    def test_doc_rank_counts_distinct_documents(self):
        hits = [hit("A"), hit("A"), hit("B"), hit("C")]
        self.assertEqual(metrics.first_doc_rank(hits, ["B"]), 2)

    def test_any_of_several_expected_documents_counts(self):
        hits = [hit("A"), hit("C")]
        self.assertEqual(metrics.first_doc_rank(hits, ["x", "c"]), 2)

    def test_missing_document_gives_none(self):
        self.assertIsNone(metrics.first_doc_rank([hit("A")], ["B"]))

    def test_passage_match_uses_full_text_and_reports_rank(self):
        hits = [hit("A", text="nothing here"), hit("B", text="the answer is forty two")]
        self.assertEqual(metrics.first_passage_match(hits, "answer is forty two"), (2, "exact"))

    def test_percentile_is_nearest_rank(self):
        self.assertEqual(metrics.percentile([300, 100, 200], 50), 200)
        self.assertEqual(metrics.percentile([300, 100, 200], 95), 300)
        self.assertIsNone(metrics.percentile([], 50))


class SummaryTests(unittest.TestCase):
    def test_counts_and_unscored_failures(self):
        def row(status, expected, gold, doc_rank, passage_rank, wall, kind=None):
            return {
                "status": status, "expected_doc": expected, "has_gold": gold, "doc_rank": doc_rank,
                "passage_rank": passage_rank, "passage_kind": kind, "wall_ms": wall,
                "took_ms": None if wall is None else wall // 10,
            }  # fmt: skip

        rows = [
            row("ok", "A", True, 1, 2, 100, "exact"),
            row("ok", "A", False, 4, None, 300),
            row("failed", "A", True, None, None, None),
            row("ok", "", False, None, None, 200),
        ]
        s = metrics.summarise(rows)
        self.assertEqual(
            (s["questions"], s["not_answered"], s["doc_n"], s["passage_n"]), (4, 1, 2, 1)
        )
        self.assertEqual((s["doc_hit@1"], s["doc_hit@3"], s["doc_hit@5"]), (1, 1, 2))
        self.assertEqual((s["passage_hit@1"], s["passage_hit@3"]), (0, 1))
        self.assertEqual(s["mrr"], 0.5)
        self.assertEqual((s["wall_p50"], s["wall_p95"]), (200, 300))


class LoaderTests(unittest.TestCase):
    def test_loader_filters_by_split_and_checks_columns(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            good = Path(tmp) / "q.csv"
            good.write_text(
                'id,split,type,question,expected_doc\nQ1,dev,keyword,"a, b",Doc\nQ2,test,long,c,Doc\n',
                encoding="utf-8",
            )
            self.assertEqual([r["id"] for r in load_questions(good, "dev")], ["Q1"])
            self.assertEqual(len(load_questions(good, "all")), 2)
            bad = Path(tmp) / "bad.csv"
            bad.write_text("id,question\nQ1,x\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                load_questions(bad)


if __name__ == "__main__":
    unittest.main()
