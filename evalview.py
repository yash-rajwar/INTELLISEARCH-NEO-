"""Prepare the two cited evaluation runs for the /evaluation page.

Reads the saved JSON files in eval/results only, so it works without
Elasticsearch. Plain Python (no Flask), so it can be tested on its own.

Only the runs listed in CITED_RUNS are shown. They are the runs cited in
docs/EVALUATION.md. Older or exploratory runs stay on disk but are not shown.
"""
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "eval" / "results"

CITED_RUNS = (
    {"stem": "20261108-085517", "label": "Development split", "anchor": "dev"},
    {"stem": "20261108-091348", "label": "Test split (run once, frozen)", "anchor": "test"},
)

# Chart layout in SVG units. Each mode gets one row with two bars (hit@1, hit@5).
ROW_H = 48
CHART_TOP = 30
BAR_H = 14
BAR_X = 110
MAX_W = 300
CHART_W = BAR_X + MAX_W + 70


def _bar_width(hits, total):
    """Bar length for hits out of total. Zero questions gives zero length."""
    if not total:
        return 0
    return round(MAX_W * min(hits, total) / total)


def _chart(summary):
    """Numbers for the inline SVG bars: passage hit@1 and hit@5 for each mode."""
    rows = []
    for i, (mode, s) in enumerate(summary.items()):
        total = s.get("passage_n") or 0
        top = CHART_TOP + i * ROW_H
        bars = []
        for j, (key, tag, css) in enumerate(
            (("passage_hit@1", "@1", "b1"), ("passage_hit@5", "@5", "b5"))
        ):
            hits = s.get(key) or 0
            width = _bar_width(hits, total)
            bars.append(
                {
                    "tag": tag,
                    "css": css,
                    "y": top + j * (BAR_H + 4),
                    "width": width,
                    "text": "%s/%s" % (hits, total),
                    "text_x": BAR_X + width + 6,
                    "aria": "%s passage hit%s: %s of %s" % (mode, tag, hits, total),
                }
            )
        rows.append({"mode": mode, "label_y": top + BAR_H + 4, "bars": bars})
    return {
        "rows": rows,
        "width": CHART_W,
        "height": CHART_TOP + len(rows) * ROW_H,
        "bar_x": BAR_X,
        "max_w": MAX_W,
        "bar_h": BAR_H,
    }


def _by_type(results, first):
    """One summary table per question type (the 'unanswerable' type is shown separately)."""
    from eval import metrics

    blocks = []
    for t in sorted({r.get("type") for r in first if r.get("type")}):
        if t == "unanswerable":
            continue
        count = sum(1 for r in first if r.get("type") == t and r.get("expected_doc"))
        modes = {
            m: metrics.summarise([r for r in rows if r.get("type") == t])
            for m, rows in results.items()
        }
        blocks.append({"type": t, "count": count, "modes": modes})
    return blocks


def _no_answer(results, first):
    """For questions with no answer in the corpus: what each mode still returned on top."""
    out = []
    for r in first:
        if r.get("expected_doc"):
            continue
        tops = {}
        for m, rows in results.items():
            row = next((x for x in rows if x.get("id") == r.get("id")), None)
            tops[m] = (row or {}).get("top_title") or "no result"
        out.append({"id": r.get("id"), "question": r.get("question"), "tops": tops})
    return out


def _failed(results):
    """Questions that did not run (for example an Elasticsearch timeout)."""
    out = []
    for m, rows in results.items():
        for r in rows:
            if r.get("error"):
                out.append({"mode": m, "id": r.get("id"), "error": str(r["error"])[:200]})
    return out


def load_run(spec, folder):
    """Build the page data for one cited run. Never raises for a missing or bad file."""
    path = Path(folder) / (spec["stem"] + ".json")
    view = dict(spec, found=False, problem="was not found in eval/results")
    if not path.is_file():
        return view
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        results = data["results"]
        summary = data["summary"]
    except (OSError, ValueError, KeyError) as exc:
        view["problem"] = "could not be read (%s)" % type(exc).__name__
        return view

    meta = data.get("meta") or {}
    first = next(iter(results.values()), [])
    answerable = sum(1 for r in first if r.get("expected_doc"))
    view.update(
        found=True,
        timestamp=str(meta.get("timestamp", "")),
        git=str(meta.get("git_commit", "")),
        elasticsearch=str(meta.get("elasticsearch", "")),
        questions_hash=str(meta.get("questions_sha256") or "")[:12],
        n_total=len(first),
        n_answerable=answerable,
        n_no_answer=len(first) - answerable,
        summary=summary,
        chart=_chart(summary),
        by_type=_by_type(results, first),
        no_answer=_no_answer(results, first),
        failed=_failed(results),
    )
    return view


def load_cited_runs(folder=None):
    """The two cited runs, in order (development, then test)."""
    folder = Path(folder) if folder else RESULTS_DIR
    return [load_run(spec, folder) for spec in CITED_RUNS]
