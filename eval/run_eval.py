"""Run the question set against the live search and write a report.

Example:
    python -m eval.run_eval --modes keyword,semantic,hybrid,weighted --split dev

It calls the same search() function as the web app, so there is no second copy of the query code.
"""

import argparse
import csv
import getpass
import hashlib
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from config import ES_PASSWORD
from es_client import ES, ESFailure
from eval import metrics
from search import MODES, search

ROOT = Path(__file__).resolve().parents[1]
CSV_FIELDS = [
    "mode", "id", "type", "split", "status", "doc_rank", "passage_rank", "passage_kind",
    "wall_ms", "took_ms", "top_title", "top_score", "error", "question", "expected_doc",
]  # fmt: skip


def load_questions(path, split="all"):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    needed = {"id", "split", "type", "question", "expected_doc"}
    if not rows or not needed <= set(rows[0]):
        raise SystemExit(f"{path} must have the columns: {', '.join(sorted(needed))}")
    return [r for r in rows if split == "all" or r["split"] == split]


def run_mode(client, questions, mode, scope, size):
    results = []
    for q in questions:
        expected = [d.strip() for d in (q.get("expected_doc") or "").split("|") if d.strip()]
        gold = (q.get("gold_span") or "").strip()
        row = {
            "id": q["id"], "type": q["type"], "split": q["split"], "question": q["question"],
            "expected_doc": " | ".join(expected), "has_gold": bool(gold), "status": "ok",
            "error": "", "doc_rank": None, "passage_rank": None, "passage_kind": None,
            "wall_ms": None, "took_ms": None, "top_title": "", "top_score": None,
        }  # fmt: skip
        started = time.perf_counter()
        try:
            result = search(client, q["question"], scope, mode, size=size)
        except (ESFailure, ValueError) as exc:
            row["status"] = "failed"
            row["error"] = str(exc)[:200]
            results.append(row)
            continue
        row["wall_ms"] = round((time.perf_counter() - started) * 1000)
        row["took_ms"] = result.get("took")
        if result.get("mode_used") != mode:  # the app fell back to another mode
            row["status"] = "fallback"
            row["error"] = str(result.get("warning", ""))[:200]
        hits = result["hits"]
        if hits:
            row["top_title"] = hits[0]["title"]
            row["top_score"] = hits[0]["score"]
        row["doc_rank"] = metrics.first_doc_rank(hits, expected)
        if gold:
            row["passage_rank"], row["passage_kind"] = metrics.first_passage_match(hits, gold)
        results.append(row)
    return results


def git_commit():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def environment(client):
    info = {"git_commit": git_commit()}
    for name, call in (
        ("elasticsearch", client.probe),
        ("license", client.license_info),
        ("elser_endpoint", client.get_inference),
        ("corpus", client.corpus_status),
    ):
        try:
            info[name] = call()
        except ESFailure as exc:
            info[name] = "unavailable: " + str(exc)[:100]
    return info


def warm_up(client):
    print("Warming up ELSER ... ", end="", flush=True)
    try:
        print(f"{client.warm_up()} ms")
    except ESFailure as exc:
        print("failed:", str(exc)[:150])


HEAD = [
    "| Mode | doc hit@1 | doc hit@3 | doc hit@5 | passage hit@1 | passage hit@3 | passage hit@5 | MRR | not answered | latency p50 / p95 ms |",
    "|---|---|---|---|---|---|---|---|---|---|",
]  # fmt: skip


def fmt(s):
    mrr = "n/a" if s["mrr"] is None else f"{s['mrr']:.3f}"
    latency = "n/a" if s["wall_p50"] is None else f"{s['wall_p50']} / {s['wall_p95']}"
    d, p = s["doc_n"], s["passage_n"]
    cells = [
        f"{s['doc_hit@1']}/{d}", f"{s['doc_hit@3']}/{d}", f"{s['doc_hit@5']}/{d}",
        f"{s['passage_hit@1']}/{p}", f"{s['passage_hit@3']}/{p}", f"{s['passage_hit@5']}/{p}",
        mrr, f"{s['not_answered']}/{s['questions']}", latency,
    ]  # fmt: skip
    return " | ".join(cells)


def table(title, by_mode):
    lines = [f"### {title}", "", *HEAD]
    for mode, rows in by_mode.items():
        lines.append(f"| {mode} | {fmt(metrics.summarise(rows))} |")
    return "\n".join(lines) + "\n"


def write_reports(out_dir, meta, results):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    summary = {mode: metrics.summarise(rows) for mode, rows in results.items()}
    payload = {"meta": meta, "summary": summary, "results": results}
    (out / f"{stamp}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with open(out / f"{stamp}.csv", "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for mode, rows in results.items():
            for row in rows:
                writer.writerow({"mode": mode, **row})

    first = next(iter(results.values()))
    types = sorted({r["type"] for r in first})
    splits = sorted({r["split"] for r in first})
    lines = [
        "# IntelliSearch evaluation run",
        "",
        f"- Date: {meta['timestamp']}",
        f"- Git commit: {meta['git_commit']}",
        f"- Question file: {meta['questions_file']} (sha256 {meta['questions_sha256'][:16]}...), split: {meta['split']}, questions: {meta['question_count']}",
        f"- Scope: {meta['scope']}, results per query: {meta['size']}",
        f"- Elasticsearch: {meta['elasticsearch']}",
        f"- License: {meta['license']}",
        f"- ELSER endpoint: {meta['elser_endpoint']}",
        f"- Corpus: {meta['corpus']}",
        "",
        table("All selected questions", results),
    ]
    for t in types:
        lines.append(
            table(
                f"Question type: {t}",
                {m: [r for r in rows if r["type"] == t] for m, rows in results.items()},
            )
        )
    for s in splits:
        lines.append(
            table(
                f"Split: {s}",
                {m: [r for r in rows if r["split"] == s] for m, rows in results.items()},
            )
        )
    unanswerable = [r["id"] for r in first if not r["expected_doc"]]
    if unanswerable:
        lines += [
            "### Questions with no answer in the corpus",
            "",
            "The top result each mode would show:",
            "",
        ]
        for qid in unanswerable:
            lines.append(f"- {qid}: {next(r['question'] for r in first if r['id'] == qid)}")
            for mode, rows in results.items():
                row = next(r for r in rows if r["id"] == qid)
                score = "" if row["top_score"] is None else f" (score {row['top_score']:.3f})"
                lines.append(f"  - {mode}: {row['top_title'] or 'no result'}{score}")
        lines.append("")
    fuzzy = sum(s["fuzzy_matches"] for s in summary.values())
    lines += [
        "### Interpretation and limits",
        "",
        "This is a small, hand-built question set over public documents. It is exploratory and not a benchmark, "
        "and it says nothing about performance on other documents. Document hits count distinct documents. "
        "Passage hits need a gold span, so their N is smaller. "
        f"{fuzzy} passage match(es) across all modes used the word-overlap fallback instead of an exact match. "
        "'Not answered' counts failures and runs where the app fell back to another mode; those are not scored as misses. "
        "Questions with no answer still return a top result, which is what the table above shows.",
        "",
    ]
    (out / f"{stamp}.md").write_text("\n".join(lines), encoding="utf-8")
    return [out / f"{stamp}{ext}" for ext in (".json", ".csv", ".md")]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the evaluation questions against the search.")
    parser.add_argument("--questions", default=str(ROOT / "eval" / "questions.csv"))
    parser.add_argument("--modes", default="keyword,semantic,hybrid,weighted")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="all")
    parser.add_argument("--scope", default="corpus")
    parser.add_argument("--size", type=int, default=10)
    parser.add_argument("--out", default=str(ROOT / "eval" / "results"))
    parser.add_argument("--no-warmup", action="store_true")
    args = parser.parse_args(argv)

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    bad = [m for m in modes if m not in MODES]
    if bad:
        raise SystemExit(
            "Unknown mode(s): " + ", ".join(bad) + ". Choose from: " + ", ".join(MODES)
        )
    questions = load_questions(args.questions, args.split)
    if not questions:
        raise SystemExit("No questions match that split.")
    if args.split == "test":
        print("Reminder: the test split should be run once, at the very end.")

    client = ES(password=ES_PASSWORD or getpass.getpass("Elasticsearch password (elastic user): "))
    meta = environment(client)
    meta.update(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        questions_file=str(args.questions),
        questions_sha256=hashlib.sha256(Path(args.questions).read_bytes()).hexdigest(),
        split=args.split, scope=args.scope, size=args.size, question_count=len(questions),
        modes=modes,
    )  # fmt: skip
    if not args.no_warmup and any(m != "keyword" for m in modes):
        warm_up(client)
    results = {}
    for mode in modes:
        print(f"Running {len(questions)} questions in mode: {mode}", flush=True)
        results[mode] = run_mode(client, questions, mode, args.scope, args.size)
    for path in write_reports(args.out, meta, results):
        print("Wrote", path)


if __name__ == "__main__":
    main()
