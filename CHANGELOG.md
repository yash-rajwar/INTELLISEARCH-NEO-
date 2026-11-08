# Changelog

Built from the commit messages on the `v4-upgrade` branch. `git log` has the detail.

## V4 (November 2026)

### Foundations
- Code formatted with ruff (no logic changes); unused imports removed; `pymupdf` import.
- Settings module that reads the environment and `.env`; `BOOKS_DIR` replaces the old folder-layout assumption.
- `LEGACY_ENABLED` switch: legacy collections are hidden unless it is on.
- Persistent secret key, file logging, Elasticsearch client created at import, SQLite connection closed.
- Elasticsearch client with retries, longer ELSER warm-up, keep-alive ping, cached counts and status reporting.

### Corpus and ingestion
- Chunker v2, Elasticsearch client, ingestion CLI and a corpus smoke test.
- Corpus index of 18 public documents (7,102 passages); downloader, `corpus/manifest.csv` and `corpus/ATTRIBUTION.md`.

### Search
- Results grouped by document, query words highlighted, loading note, contrast fixes, security headers.
- Fuzzy keyword mode (BM25 with typo tolerance, no ELSER call), a fifth method on the Search page with a
  documented rule and explanation text. `/compare` still shows four modes.
- Weighted RRF fused locally, because Elasticsearch 9.0.0 rejects the weighted retriever format.
- File-type filter accepts `pdf` and `.pdf` and includes the corpus.
- "Found by meaning" label and "Show more results".
- Neighbouring passages in source context for corpus results.
- Corpus originals served by the app; source links with page anchors; query-word overlap line;
  standing no-answer note; mode labels.
- `LOG_QUERIES` switch; highlighted passages.

### Uploads
- Uploads without silent truncation, ELSER on by default, duplicate detection by content hash.
- Delete uploaded documents; failed uploads are cleaned up.
- Upload runs in the background. The library shows `indexing...`, then `indexed` or `error`, and refreshes
  itself. A restart marks unfinished uploads as interrupted. Delete is refused while a file is still being
  indexed. The duplicate check happens when the file is submitted.

### Documents
- Corpus documents in Summarize and Compare, whole-document summaries, aligned passages.
- Corpus PDFs over 200 pages can be summarized and compared (corpus files up to 1,000 pages; uploads keep
  the 200-page limit).

### Compare methods, Ask, System
- Compare methods page: status chip per method (ok, slow, fallback, failed, skipped), agreement markers
  (found by both, only by meaning, only by keywords) and a summary sentence.
- Ask page checks, Ollama status, citation validation and an evidence notice.
- System page: licence, ELSER, corpus counts, a Test now button and a diagnostics report.

### Interface
- Licence chip in the top bar and presenter mode.
- Grouped navigation (five groups), skip link, page titles, sidebar that fits short screens.
- Startup banner no longer carries the V3 label.

### Evaluation
- Evaluation harness with metrics, runner and report writer; question set v2 (36 questions with
  source-verified gold spans, tag `eval-frozen-v2`); development run and one test run.
- `/evaluation` page: reads saved files only, shows the two cited runs with caveats, hits/questions tables
  and bars.

### Documentation
- README, changelog, demo guide, office setup guide, cluster facts, evaluation notes, progress ledger,
  traceability note.

## V3

Original showcase front end over the legacy indexes. See `git log`.
