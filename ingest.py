"""Ingestion CLI (WP-04): files -> chunks -> intellisearch_corpus_v1.

    python ingest.py --path corpus\\files --tier 1 --dry-run
    python ingest.py --path corpus\\files --tier 1
    python ingest.py --path corpus\\files --only nist-800-61r3,rfc-8446 --replace

Re-running is safe: a document whose chunks are all present is skipped; a document
that was interrupted half-way is cleaned and re-indexed. Writes ONLY to the corpus index.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from settings import load_settings

from chunking import chunk_lines, chunk_pages, chunk_text, strip_gutenberg
from chunking3 import chunk_pages_v3
from es_http import ESFailure, ESHttp
from health import warm_up
from mappings import ensure_corpus_index

EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
RETRY_ITEM_STATUS = {408, 429, 500, 502, 503, 504}
CHUNKER_VERSION = 2  # 2 = chunker v2 (default), 3 = chunker v3; set by --chunker

# stem -> (title, collection, tier). Unknown files get a title from the filename.
KNOWN = {
    "nist-800-61r3": ("NIST SP 800-61 Rev. 3: Incident Response", "standards", 1),
    "nist-csf-2": ("NIST Cybersecurity Framework 2.0", "standards", 1),
    "nist-ai-rmf-1": ("NIST AI Risk Management Framework 1.0", "standards", 1),
    "india-dpdp-2023": ("Digital Personal Data Protection Act, 2023 (India)", "legal", 1),
    "india-it-act-2000": ("Information Technology Act, 2000 (India)", "legal", 1),
    "india-rti-2005": ("Right to Information Act, 2005 (India) with DoPT Guide", "legal", 1),
    "rfc-9110": ("RFC 9110: HTTP Semantics", "rfc", 1),
    "rfc-8446": ("RFC 8446: TLS 1.3", "rfc", 1),
    "nist-800-53r5": ("NIST SP 800-53 Rev. 5: Security and Privacy Controls", "standards", 2),
    "nasa-se-handbook": ("NASA Systems Engineering Handbook", "standards", 2),
    "nist-800-171r3": ("NIST SP 800-171 Rev. 3: Protecting CUI", "standards", 3),
    "rfc-9293": ("RFC 9293: Transmission Control Protocol", "rfc", 3),
    "gutenberg-art-of-war": ("The Art of War (Sun Tzu, tr. Giles)", "books", 3),
    "gutenberg-pride-and-prejudice": ("Pride and Prejudice (Jane Austen)", "books", 3),
    "gutenberg-frankenstein": ("Frankenstein (Mary Shelley)", "books", 3),
    "gutenberg-sherlock-holmes": ("The Adventures of Sherlock Holmes (Conan Doyle)", "books", 3),
    "gutenberg-dracula": ("Dracula (Bram Stoker)", "books", 3),
    "gutenberg-alice": ("Alice's Adventures in Wonderland (Lewis Carroll)", "books", 3),
}


# ---------------------------------------------------------------- extraction
def extract_pdf(data: bytes, cfg):
    import pymupdf

    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        if doc.needs_pass:
            raise ValueError("encrypted PDF")
        pages = []
        for i in range(len(doc)):
            text = doc[i].get_text().replace("\x00", "")
            if text.strip():
                pages.append((i + 1, text))
        n = len(doc)
    finally:
        doc.close()
    if not pages:
        raise ValueError("no extractable text (scanned PDF? OCR is not used by this CLI)")
    chunker = chunk_pages_v3 if CHUNKER_VERSION == 3 else chunk_pages
    return chunker(
        pages, cfg.chunk_target_chars, cfg.chunk_overlap_chars, cfg.max_chunks_per_doc
    ), n


def extract_text(data: bytes, cfg):
    text = data.decode("utf-8-sig", errors="replace").replace("\x00", "")
    body, first_line = strip_gutenberg(text)
    if not body.strip():
        raise ValueError("empty text file")
    return chunk_lines(
        body, first_line, cfg.chunk_target_chars, cfg.chunk_overlap_chars, cfg.max_chunks_per_doc
    ), None


def extract_docx(data: bytes, cfg):
    from docx import Document
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph

    doc = Document(io.BytesIO(data))
    parts, headings, pos = [], [], 0  # headings: (char offset, text)
    for elem in doc.element.body.iterchildren():
        line = ""
        if elem.tag == qn("w:p"):
            para = Paragraph(elem, doc)
            line = para.text.strip()
            if line and (para.style.name or "").lower().startswith(("heading", "title")):
                headings.append((pos, line[:200]))
        elif elem.tag == qn("w:tbl"):
            rows = []
            for row in elem.findall(qn("w:tr")):
                cells = [
                    " ".join(x for x in c.itertext() if x.strip()) for c in row.findall(qn("w:tc"))
                ]
                if cells:
                    rows.append(" | ".join(cells))
            line = "\n".join(rows)
        if line:
            parts.append(line)
            pos += len(line) + 1
    if not parts:
        raise ValueError("DOCX does not contain readable text")
    chunks = chunk_text(
        "\n".join(parts), cfg.chunk_target_chars, cfg.chunk_overlap_chars, cfg.max_chunks_per_doc
    )
    for c in chunks:
        c.section = next((h for off, h in reversed(headings) if off <= c.start_char), None)
    return chunks, None


EXTRACTORS = {".pdf": extract_pdf, ".txt": extract_text, ".md": extract_text, ".docx": extract_docx}


# ------------------------------------------------------------------ bulk I/O
def build_rows(index, meta, chunks, semantic, created_at):
    rows = []
    for c in chunks:
        src = {
            "document_id": meta["document_id"],
            "content_hash": meta["content_hash"],
            "collection": meta["collection"],
            "filename": meta["filename"],
            "title": meta["title"],
            "file_type": meta["file_type"],
            "chunk_index": c.chunk_index,
            "created_at": created_at,
            "content": c.text,
        }
        for key in ("page_number", "start_line", "end_line"):
            if getattr(c, key, None) is not None:
                src[key] = getattr(c, key)
        if getattr(c, "section", None):
            src["section"] = c.section
        if semantic:
            src["content_semantic"] = c.text
        cid = f"{meta['document_id']}_{c.chunk_index:05d}"
        rows.append(
            (
                cid,
                json.dumps({"index": {"_index": index, "_id": cid}}),
                json.dumps(src, ensure_ascii=False),
            )
        )
    return rows


def bulk_index(es, rows, *, batch_size, timeout, max_attempts=3, sleep=time.sleep):
    """Send rows in small batches; retry failed items. Returns (ok_count, failures)."""
    ok, failures = 0, []
    for i in range(0, len(rows), batch_size):
        pending = rows[i : i + batch_size]
        for attempt in range(1, max_attempts + 1):
            body = ("\n".join(f"{a}\n{s}" for _, a, s in pending) + "\n").encode("utf-8")
            errors = {}
            try:
                res = es.request("POST", "_bulk", ndjson=body, timeout=timeout)
                for it in res.get("items", []):
                    d = it.get("index", {})
                    if d.get("error"):
                        errors[d["_id"]] = (d.get("status", 500), str(d["error"])[:300])
                ok += len(pending) - len(errors)
            except ESFailure as exc:
                errors = {cid: (exc.status or 500, str(exc)[:300]) for cid, _, _ in pending}
            keep = []
            for row in pending:
                if row[0] in errors:
                    status, msg = errors[row[0]]
                    if status in RETRY_ITEM_STATUS and attempt < max_attempts:
                        keep.append(row)
                    else:
                        failures.append({"_id": row[0], "status": status, "error": msg})
            pending = keep
            if not pending:
                break
            sleep(2**attempt)
    return ok, failures


# --------------------------------------------------------------- orchestration
def select_files(root: Path, tiers, only):
    files = sorted(p for p in root.rglob("*") if p.is_file())
    chosen, skipped = [], []
    for p in files:
        if p.suffix.lower() not in EXTENSIONS:
            skipped.append((p.name, "unsupported file type"))
            continue
        known = KNOWN.get(p.stem)
        if only and not any(p.stem == o or p.stem.endswith("-" + o) for o in only):
            continue
        if not only and tiers and (known is None or known[2] not in tiers):
            continue
        chosen.append(p)
    return chosen, skipped


def count_docs(es, index, field, value):
    return es.request(
        "POST", f"{index}/_count", json={"query": {"term": {field: value}}}, timeout=30
    ).get("count", 0)


def delete_docs(es, index, field, value):
    es.request(
        "POST",
        f"{index}/_delete_by_query?refresh=true&conflicts=proceed",
        json={"query": {"term": {field: value}}},
        timeout=120,
    )


def main(argv=None, es=None, settings=None, out=print, sleep=time.sleep) -> int:
    ap = argparse.ArgumentParser(description="Ingest documents into the corpus index.")
    ap.add_argument("--path", required=True, help="folder with documents")
    ap.add_argument("--collection", default=None, help="override collection (default: automatic)")
    ap.add_argument(
        "--tier", default="", help="comma list of tiers, e.g. 1 or 1,2 (known corpus files)"
    )
    ap.add_argument("--only", default="", help="comma list of file names without extension")
    ap.add_argument("--semantic", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument(
        "--chunker", type=int, choices=(2, 3), default=2,
        help="PDF chunker: 2 = current (default), 3 = cleaned passages (use with --index)",
    )
    ap.add_argument(
        "--index", default=None,
        help="write to this intellisearch_corpus* index instead of CORPUS_INDEX",
    )
    ap.add_argument(
        "--batch-size", type=int, default=10, help="chunks per bulk request (default 10)"
    )
    ap.add_argument(
        "--replace", action="store_true", help="delete older chunks of the same filename first"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="show the plan; do not touch Elasticsearch"
    )
    args = ap.parse_args(argv)

    global CHUNKER_VERSION
    cfg = settings or load_settings()
    if args.index:
        if dataclasses.is_dataclass(cfg):
            cfg = dataclasses.replace(cfg, corpus_index=args.index)
        else:
            cfg = cfg._replace(corpus_index=args.index)
    index = cfg.corpus_index
    if args.chunker == 3 and index == "intellisearch_corpus_v1":
        out("Refusing: chunker 3 must not write into intellisearch_corpus_v1. "
            "Use --index intellisearch_corpus_v2.")
        return 2
    CHUNKER_VERSION = args.chunker
    out(f"Chunker v{args.chunker}, index {index}")
    if not index.startswith("intellisearch_corpus"):
        out(f"Refusing to write to {index!r}: only intellisearch_corpus* indexes may be written.")
        return 2
    root = Path(args.path)
    if not root.is_dir():
        out(f"Folder not found: {root}")
        return 2
    tiers = {int(t) for t in args.tier.split(",") if t.strip()}
    only = [o.strip() for o in args.only.split(",") if o.strip()]
    files, skipped = select_files(root, tiers, only)
    for name, why in skipped:
        out(f"SKIP {name}: {why}")
    if not files:
        out("No matching files.")
        return 2

    t_start = time.monotonic()
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    err_dir = cfg.data_dir / "ingest"
    summary = {
        "index": index,
        "semantic": args.semantic,
        "documents": 0,
        "chunks": 0,
        "skipped": 0,
        "failed": 0,
        "per_document": [],
    }
    errors_log = []

    if not args.dry_run:
        es = es or ESHttp(cfg)
        try:
            out(
                f"Elasticsearch {es.request('GET', '/', timeout=8).get('version', {}).get('number')} reachable"
            )
            if ensure_corpus_index(es, cfg, args.semantic):
                out(f"Created index {index}")
            es.request("POST", f"{index}/_refresh", timeout=30)
            if args.semantic:
                out("Warming up ELSER (first run can take ~30 s) ...")
                out(f"ELSER ready after {warm_up(es, cfg.es_inference_id):.1f}s")
        except ESFailure as exc:
            out(f"FATAL: {exc}")
            return 2

    total_chunks_done, sem_seconds = 0, 0.0
    for n, path in enumerate(files, 1):
        known = KNOWN.get(path.stem)
        title = known[0] if known else path.stem.replace("-", " ").replace("_", " ").title()
        collection = args.collection or (known[1] if known else "uploads")
        label = f"[{n}/{len(files)}] {path.name}"
        try:
            data = path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            chunks, pages = EXTRACTORS[path.suffix.lower()](data, cfg)
        except Exception as exc:  # one bad file (corrupt, too many chunks, ...) never stops the run
            out(f"{label}: FAILED {exc}")
            summary["failed"] += 1
            errors_log.append({"file": path.name, "stage": "extract", "error": str(exc)[:300]})
            continue
        meta = {
            "document_id": sha[:32],
            "content_hash": sha,
            "collection": collection,
            "filename": path.name,
            "title": title,
            "file_type": path.suffix.lower().lstrip("."),
        }
        expected = len(chunks)
        if args.dry_run:
            out(
                f"{label}: {expected} chunks"
                + (f", {pages} pages" if pages else "")
                + (f" (~{expected} ELSER calls)" if args.semantic else "")
            )
            summary["documents"] += 1
            summary["chunks"] += expected
            continue
        try:
            have = count_docs(es, index, "document_id", meta["document_id"])
            if have == expected and not args.replace:
                out(f"{label}: already indexed ({have} chunks), skipped")
                summary["skipped"] += 1
                continue
            if args.replace:
                delete_docs(es, index, "filename", path.name)
            elif have:  # interrupted earlier: clean, then redo
                out(f"{label}: found {have} of {expected} chunks (interrupted run), re-indexing")
                delete_docs(es, index, "document_id", meta["document_id"])
            else:
                other = count_docs(es, index, "filename", path.name)
                if other:
                    out(
                        f"{label}: NOTE another version of this filename is indexed; use --replace to remove it"
                    )
            t0 = time.monotonic()
            rows = build_rows(index, meta, chunks, args.semantic, created_at)
            ok, failures = bulk_index(
                es,
                rows,
                batch_size=args.batch_size,
                timeout=160 if args.semantic else 60,
                sleep=sleep,
            )
        except ESFailure as exc:
            out(f"{label}: FAILED {exc}")
            summary["failed"] += 1
            errors_log.append({"file": path.name, "stage": "index", "error": str(exc)[:300]})
            continue
        secs = time.monotonic() - t0
        sem_seconds += secs
        total_chunks_done += ok
        for f in failures:
            errors_log.append({"file": path.name, "stage": "bulk", **f})
        if failures:
            summary["failed"] += 1
        summary["documents"] += 1
        summary["chunks"] += ok
        summary["per_document"].append(
            {
                "file": path.name,
                "chunks": ok,
                "failed_chunks": len(failures),
                "seconds": round(secs, 1),
            }
        )
        rate = total_chunks_done / sem_seconds if sem_seconds else 0
        left = sum(1 for _ in files[n:])  # documents still to do
        out(
            f"{label}: {ok}/{expected} chunks in {secs:.1f}s ({ok / secs if secs else 0:.1f}/s); "
            f"overall {rate:.1f} chunks/s, {left} file(s) left"
        )

    if not args.dry_run:
        try:
            es.request("POST", f"{index}/_refresh", timeout=60)
        except ESFailure as exc:
            out(f"WARNING: final refresh failed: {exc}")
    summary["seconds"] = round(time.monotonic() - t_start, 1)
    summary["chunks_per_second"] = (
        round(total_chunks_done / sem_seconds, 2) if sem_seconds else None
    )
    if not args.dry_run:
        err_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (err_dir / f"summary-{stamp}.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        if errors_log:
            with open(err_dir / "ingest_errors.jsonl", "a", encoding="utf-8") as fh:
                fh.writelines(json.dumps(e) + "\n" for e in errors_log)
            out(f"{len(errors_log)} problem(s) written to {err_dir / 'ingest_errors.jsonl'}")
    out("SUMMARY " + json.dumps({k: v for k, v in summary.items() if k != "per_document"}))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
