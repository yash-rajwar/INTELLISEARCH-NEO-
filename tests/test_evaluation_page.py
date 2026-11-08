"""Tests for the /evaluation page: only the two cited runs, honest caveats, no crash on bad files."""
import json

import evalview


def _row(qid, qtype, expected, rank=1, error=None):
    return {
        "id": qid,
        "type": qtype,
        "split": "dev",
        "question": "Question " + qid,
        "expected_doc": expected,
        "has_gold": bool(expected),
        "status": "error" if error else "ok",
        "error": error,
        "doc_rank": rank if expected else None,
        "passage_rank": rank if expected else None,
        "passage_kind": "gold" if expected else None,
        "wall_ms": 50,
        "took_ms": 20,
        "top_title": "Some document",
    }


def _write_run(folder, stem, with_error=False):
    from eval import metrics

    rows = {
        "keyword": [
            _row("Q01", "plain", "Doc A", rank=1),
            _row("Q02", "typo", "Doc B", rank=3),
            _row("Q03", "unanswerable", None),
        ],
        "semantic": [
            _row("Q01", "plain", "Doc A", rank=2),
            _row("Q02", "typo", "Doc B", rank=None, error="timeout [10s]" if with_error else None),
            _row("Q03", "unanswerable", None),
        ],
    }
    data = {
        "meta": {
            "git_commit": "abc1234",
            "elasticsearch": "9.0.0",
            "timestamp": "2026-11-08T09:00:00",
            "questions_sha256": "f" * 64,
        },
        "summary": {m: metrics.summarise(r) for m, r in rows.items()},
        "results": rows,
    }
    (folder / (stem + ".json")).write_text(json.dumps(data), encoding="utf-8")


def test_only_the_two_cited_runs_are_loaded(tmp_path):
    for stem in ("20261108-085517", "20261108-091348", "20261108-085023", "20261108-023037"):
        _write_run(tmp_path, stem)
    runs = evalview.load_cited_runs(tmp_path)
    assert [r["stem"] for r in runs] == ["20261108-085517", "20261108-091348"]
    assert all(r["found"] for r in runs)


def test_missing_run_is_reported_not_a_crash(tmp_path):
    _write_run(tmp_path, "20261108-085517")
    runs = evalview.load_cited_runs(tmp_path)
    assert runs[0]["found"] is True
    assert runs[1]["found"] is False
    assert "not found" in runs[1]["problem"]


def test_unreadable_file_is_reported_not_a_crash(tmp_path):
    (tmp_path / "20261108-085517.json").write_text("{not json", encoding="utf-8")
    runs = evalview.load_cited_runs(tmp_path)
    assert runs[0]["found"] is False
    assert "could not be read" in runs[0]["problem"]


def test_counts_and_no_answer_rows(tmp_path):
    _write_run(tmp_path, "20261108-085517")
    run = evalview.load_cited_runs(tmp_path)[0]
    assert (run["n_total"], run["n_answerable"], run["n_no_answer"]) == (3, 2, 1)
    assert [u["id"] for u in run["no_answer"]] == ["Q03"]
    assert [b["type"] for b in run["by_type"]] == ["plain", "typo"]


def test_failed_questions_are_listed(tmp_path):
    _write_run(tmp_path, "20261108-085517", with_error=True)
    run = evalview.load_cited_runs(tmp_path)[0]
    assert [(f["mode"], f["id"]) for f in run["failed"]] == [("semantic", "Q02")]


def test_bar_width_is_proportional_and_safe():
    assert evalview._bar_width(10, 20) == evalview.MAX_W // 2
    assert evalview._bar_width(20, 20) == evalview.MAX_W
    assert evalview._bar_width(0, 20) == 0
    assert evalview._bar_width(5, 0) == 0
    assert evalview._bar_width(30, 20) == evalview.MAX_W


def test_page_shows_caveat_and_only_cited_runs():
    import app as appmod

    html = appmod.app.test_client().get("/evaluation").get_data(as_text=True)
    assert "Read this first" in html
    assert "eval-frozen-v2" in html
    assert "<svg" in html
    assert "20261108-085517" in html
    assert "20261108-091348" in html
    for old in ("20261108-085023", "20261108-085236", "20261108-023037"):
        assert old not in html
