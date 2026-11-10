"""IntelliSearch NEO Batch 2: evidence-based chunk-level evaluation.

Uses the existing application's search() function for every retrieval mode.
Run from /app with python /tmp/report_eval.py ... inside the app container.
The Elasticsearch index is read only. No app modules or questions are modified.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from config import ES_PASSWORD
from es_client import ES
from search import search

MODES = {"bm25": "keyword", "elser": "semantic", "hybrid": "hybrid"}
COLS = ["id", "split", "type", "mode", "status", "error", "first_relevant_rank",
        "p5", "p10", "recall10", "mrr", "ndcg10", "top1", "doc_p5", "doc_p10",
        "doc_hit10", "top1_score", "latency_ms_client", "es_took_ms", "split_span_flag"]
REMAP = str.maketrans({"\u2018":"'", "\u2019":"'", "\u201c":'"', "\u201d":'"',
                       "\u2010":"-", "\u2011":"-", "\u2012":"-", "\u2013":"-", "\u2014":"-", "\u2212":"-"})


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = s.replace("\u00ad", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    s = re.sub(r"(?<=\w)-[ \t]*\r?\n[ \t]*(?=\w)", "", s)
    return " ".join(s.translate(REMAP).lower().split())


def get_chunks(client, index, filename):
    """Read all parent chunks for one filename using a bounded scroll, no ES writes."""
    response = client.api("POST", f"{index}/_search?scroll=2m", payload={
        "size": 500, "sort": ["_doc"], "_source": ["filename", "chunk_index", "content", "document_id"],
        "query": {"term": {"filename": filename}}
    }, timeout=45)
    sid = response.get("_scroll_id")
    chunks = []
    try:
        while True:
            hits = response.get("hits", {}).get("hits", [])
            if not hits:
                break
            for h in hits:
                src = h.get("_source", {})
                chunks.append({"id": h["_id"], "order": src.get("chunk_index"),
                               "doc_id": src.get("document_id"), "text": norm(src.get("content"))})
            response = client.api("POST", "/_search/scroll", payload={"scroll": "2m", "scroll_id": sid})
            sid = response.get("_scroll_id", sid)
    finally:
        if sid:
            try:
                client.api("DELETE", "/_search/scroll", payload={"scroll_id": [sid]})
            except Exception:
                pass
    chunks.sort(key=lambda c: (str(c["doc_id"]), c["order"] if isinstance(c["order"], int) else -1, c["id"]))
    return chunks


def relevant_set(chunks, gold):
    gold = norm(gold)
    exact, split = set(), set()
    if not gold:
        return exact, split
    for c in chunks:
        if gold in c["text"]:
            exact.add(c["id"])
    for a, b in zip(chunks, chunks[1:]):
        if (a["doc_id"] != b["doc_id"] or not isinstance(a["order"], int)
                or not isinstance(b["order"], int) or b["order"] != a["order"] + 1):
            continue
        left = a["text"]
        combined = left + " " + b["text"]
        pos = combined.find(gold)
        if pos < 0:
            continue
        end = pos + len(gold)
        left_count = max(0, min(end, len(left)) - pos)
        right_start = len(left) + 1
        right_count = max(0, end - max(pos, right_start))
        if left_count >= len(gold) * .30:
            split.add(a["id"])
        if right_count >= len(gold) * .30:
            split.add(b["id"])
    return exact | split, split - exact


def git_rev():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def averages(rows):
    # Both failed and fallback questions are excluded from means AND counted explicitly.
    valid = [r for r in rows if r["status"] == "ok" and r["p5"] is not None]
    output = {"n": len(valid), "questions": len(rows),
              "failed_or_fallback": sum(r["status"] != "ok" for r in rows)}
    for metric in ("p5", "p10", "recall10", "mrr", "ndcg10", "top1", "doc_p5", "doc_p10", "doc_hit10"):
        output[metric] = round(statistics.mean(r[metric] for r in valid), 3) if valid else None
    for fld in ("latency_ms_client", "es_took_ms"):
        vals = [r[fld] for r in rows if r["status"] == "ok" and isinstance(r[fld], (float,int))]
        if vals:
            vals.sort()
            output[fld + "_p50"] = round(statistics.median(vals))
            output[fld + "_p95"] = round(vals[min(len(vals)-1, math.ceil(.95*len(vals))-1)])
        else:
            output[fld + "_p50"] = output[fld + "_p95"] = None
    return output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", required=True)
    ap.add_argument("--index", default="intellisearch_corpus_v1")
    ap.add_argument("--modes", default="bm25,elser,hybrid")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--split", choices=("all", "dev", "test"), default="all")
    ap.add_argument("--ids", default="", help="Comma-separated IDs for dry run")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.k != 10:
        ap.error("This fixed evaluation protocol requires --k 10")
    modes = [m.strip() for m in args.modes.split(",")]
    if not modes or any(m not in MODES for m in modes):
        ap.error("Valid modes: bm25,elser,hybrid")
    question_bytes = Path(args.questions).read_bytes()
    questions = list(csv.DictReader(question_bytes.decode("utf-8-sig").splitlines()))
    ids = set(args.ids.split(",")) if args.ids else None
    questions = [q for q in questions if (args.split == "all" or q["split"] == args.split)
                 and (ids is None or q["id"] in ids)]
    if not questions:
        ap.error("No questions selected")
    if not ES_PASSWORD:
        raise SystemExit("ES_PASSWORD not loaded via project config; refusing to prompt or log it")
    client = ES(password=ES_PASSWORD)
    es_version = client.probe()
    by_doc = {}
    relevant = {}
    split_flags = {}
    for q in questions:
        fname = q.get("expected_doc", "").strip()
        if not fname:
            continue
        if fname not in by_doc:
            by_doc[fname] = get_chunks(client, args.index, fname)
        if not by_doc[fname]:
            raise SystemExit(f"COVERAGE GATE FAILED: {fname} has no chunks in {args.index}")
        r, split = relevant_set(by_doc[fname], q.get("gold_span", ""))
        if not r:
            raise SystemExit(f"GOLD GATE FAILED: {q['id']} has zero matching chunks in {fname}")
        relevant[q["id"]] = r
        split_flags[q["id"]] = bool(split)
    prefix = Path(args.out)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    top10 = {}
    for mode in modes:
        for q in questions:
            t0 = time.perf_counter()
            status, err, hits, es_took = "ok", "", [], None
            try:
                res = search(client, q["question"], "corpus", MODES[mode], size=10)
                hits = res.get("hits", [])[:10]
                es_took = res.get("took")
                if res.get("mode_used") != MODES[mode]:
                    status, err = "fallback", str(res.get("warning", ""))[:180]
                if res.get("indices") != [args.index]:
                    status, err = "wrong_index", str(res.get("indices"))[:180]
            except Exception as exc:
                status, err = "failed", f"{type(exc).__name__}: {str(exc)[:150]}"
            elapsed = round((time.perf_counter()-t0)*1000)
            top10.setdefault(q["id"], {})[mode] = [{
                "rank": i+1, "chunk_id": h.get("id", ""), "source_doc": h.get("filename", ""),
                "score": h.get("score"), "snippet": (h.get("text") or "")[:200]
            } for i,h in enumerate(hits)]
            row = {"id": q["id"], "split": q["split"], "type": q["type"],
                   "mode": mode, "status": status, "error": err,
                   "first_relevant_rank": None, "p5": None, "p10": None,
                   "recall10": None, "mrr": None, "ndcg10": None, "top1": None,
                   "doc_p5": None, "doc_p10": None, "doc_hit10": None,
                   "top1_score": hits[0].get("score") if hits else None,
                   "latency_ms_client": elapsed, "es_took_ms": es_took,
                   "split_span_flag": split_flags.get(q["id"], False)}
            if status == "ok" and q["id"] in relevant:
                rel = relevant[q["id"]]
                relbits = [int(h.get("id") in rel and h.get("filename") == q["expected_doc"]) for h in hits]
                ranks = [i+1 for i,x in enumerate(relbits) if x]
                first = ranks[0] if ranks else None
                dcg = sum(v/math.log2(i+2) for i,v in enumerate(relbits))
                ideal = sum(1/math.log2(i+2) for i in range(min(10,len(rel))))
                docs = [int(h.get("filename") == q["expected_doc"]) for h in hits]
                row.update(first_relevant_rank=first,
                           p5=sum(relbits[:5])/5, p10=sum(relbits[:10])/10,
                           recall10=len({h.get("id") for h in hits if h.get("id") in rel})/len(rel),
                           mrr=1/first if first else 0, ndcg10=dcg/ideal if ideal else 0,
                           top1=relbits[0] if relbits else 0,
                           doc_p5=sum(docs[:5])/5, doc_p10=sum(docs[:10])/10,
                           doc_hit10=int(any(docs)))
            rows.append(row)
            print(f"{q['id']:>3} {mode:6} {status:12} rank={str(row['first_relevant_rank']):>4} client_ms={elapsed}",flush=True)
    with open(str(prefix)+"_per_question.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLS)
        writer.writeheader()
        writer.writerows(rows)
    summary = []
    for mode in modes:
        mode_rows = [r for r in rows if r["mode"] == mode]
        for label, sub in (("all",mode_rows),
                           ("dev",[r for r in mode_rows if r["split"]=="dev"]),
                           ("test",[r for r in mode_rows if r["split"]=="test"])):
            summary.append({"group":label,"mode":mode,**averages(sub)})
        for typ in sorted({r["type"] for r in mode_rows if r["type"] != "unanswerable"}):
            summary.append({"group":"type:"+typ,"mode":mode,
                            **averages([r for r in mode_rows if r["type"]==typ])})
    with open(str(prefix)+"_summary.csv", "w", encoding="utf-8", newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    Path(str(prefix)+"_top10.json").write_text(json.dumps(top10,indent=2,ensure_ascii=False),encoding="utf-8")
    manifest={"git_commit":git_rev(),"index":args.index,"es_version":es_version,
              "modes":modes,"application_mode_mapping":MODES,"questions_sha256":hashlib.sha256(question_bytes).hexdigest(),
              "questions_count":len(questions),"split":args.split,"ids":args.ids,
              "rrf_parameters":{"rank_constant":60,"rank_window_size":50},
              "timestamp_utc":datetime.now(timezone.utc).isoformat(),
              "strict_definition":"expected filename AND normalized gold span in chunk or qualifying adjacent split",
              "failed_or_fallback_count":sum(r['status']!='ok' for r in rows),
              "split_span_questions":sum(split_flags.values())}
    Path(str(prefix)+"_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print("\nSUMMARY (answerable only; no failed/fallback scores)",flush=True)
    for item in summary:
        if item["group"] in ("all","dev","test"):
            print(item["group"],item["mode"],"n",item["n"],"fail",item["failed_or_fallback"],"MRR",item["mrr"],"Recall10",item["recall10"],flush=True)
    print("OUTPUT_PREFIX",prefix,flush=True)
    if manifest["failed_or_fallback_count"]:
        print("WARNING: FAILED OR FALLBACK REQUESTS; DO NOT REPORT A CLEAN COMPARISON",flush=True)

if __name__ == "__main__":
    main()
