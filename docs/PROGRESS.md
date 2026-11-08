# Progress ledger

_Last updated: 2026-11-07 by session 2_

## Status board
| WP | Title | Status | Commit | Notes |
|----|-------|--------|--------|-------|
| 00 | Safety net (branch, tests, .gitignore) | done | ad86be4 | venv is Python 3.12.10 |
| 16a | Formatting-only commit | done | 84cbce0 | ruff format, 15 files |
| 16b (part) | Unused imports, pymupdf import | done | 83e65b1, c5f2687 | rest of 16b later |
| 01 | Portable configuration | done | 263c443, a3d7711, bbb1d5e | settings.py, BOOKS_DIR, LEGACY_ENABLED off by default, preflight |
| 02 | Secret key, logging, ES client at import, sqlite close | done | 8698909 | no app factory, no waitress (decided: not needed for the demo) |
| 03 | ES client hardening, corpus source, warm-up, status | done | b829771, 8efd1e3, 6c8c477 | retries, /warmup, keep-alive ping, elser/license/corpus in /api/status; 66 tests pass |
| 05 | Chunker v2 and dynamic limits | not started | | corpus already built; re-chunking needs re-indexing, measure first |
| 04 | Ingestion CLI and corpus index | not started | | must match the existing corpus (fields below) |
| 06 | Upload pipeline | not started | | |
| 07 | Search service, grouping, modes, pagination | not started | | known issues listed below |
| 08 | Evaluation harness | not started | | |
| 14a | UI level U1 | not started | | |
| 15 | System, license and health page | partly | | /api/status has the data; template not updated |
| 09-12, 14b | Stretch work | not started | | |

## Environment facts (confirmed)
- Laptop: Windows, 8 GB RAM, x86_64, 4 CPUs; Python 3.12.10 venv in .\venv
- Elasticsearch 9.0.0, single node, Docker (es01); Kibana 9.0.0 (container stopped)
- License: trial, active, expires 2026-12-07 08:02 UTC (per-cluster)
- ELSER: works after a forced stop of the failed deployment. Direct _infer cold 27.6 s, warm 0.06 s. Scales to zero when idle. One warm-up call returned 408 after 2 min while "starting"; app now waits up to 280 s and pings every 120 s. Cause of the first failure not identified
- Corpus intellisearch_corpus_v1: 7,102 chunks by _count (_cat showed 15,732, probably including hidden ELSER sub-documents); content_semantic is semantic_text with .elser-2-elasticsearch. Fields: title, filename, document_id, page_number, chunk_index, collection, file_type (stored as "pdf", no dot), content, content_hash, created_at. First seen document: India IT Act 2000
- OCR not ready (Tesseract language data missing); Ollama not configured: both optional, not part of the demo
- Kibana Dev Tools times out at about 30 s; use curl with --max-time and JSON in a file
- pip needs the PostgreSQL CA variables cleared (SSL_CERT_FILE, REQUESTS_CA_BUNDLE, CURL_CA_BUNDLE, PIP_CERT)
- es01 is published on 0.0.0.0:9200 (rebind to 127.0.0.1 later)
- Scratch index zz_elser_probe; delete at the end with the user's yes
- Backup: git bundle at ..\intellisearch-backup.bundle (copy it to another disk)

## [VERIFY] results
- ELSER answers a query: CONFIRMED
- Weighted RRF weight accepted on 9.0.0: ? (check with /compare on the corpus)
- Semantic highlight inside rrf: ?
- linear / text_similarity_reranker / .rerank-v1 on 9.0.0: ?

## Decisions
- 2026-11-07: build and rehearse on the laptop; push to GitHub at the end
- 2026-11-07: legacy collections hidden unless LEGACY_ENABLED=true
- 2026-11-07: git add by file name, not -A
- 2026-11-07: corpus is an always-on source and the default scope

## Open problems
- Demo machine: the user cannot visit the office before Monday; the laptop is assumed (unconfirmed)
- Corpus hits have no source link (originals are not served by the app)
- Document-type filter expects ".pdf" but the corpus stores "pdf"
- Later commits not pushed to GitHub (intentional)
- Q&A guide, reports and slides need updating after the code changes

## Next 3 steps
1. Check /compare on the corpus (all four modes) and list the corpus documents
2. Frozen evaluation questions and harness (WP-08) with k/N results saved to a file
3. WP-07 fixes (filters, source info), UI polish, demo script
## Session 3 update (2026-11-08)
- Weighted RRF fused locally; file-type filter fixed; doc-hit scoring matches filenames (fdf8399, bb9ad5f)
- Question set v2: 36 questions with source-verified gold spans (tag eval-frozen-v2)
- Saved-evaluation page at /evaluation (works without Elasticsearch)
- Corpus originals served at /corpus-file/<name>; search cards and source context link to them with page anchors
- Query-word overlap line and standing no-answer note; score-based no-answer detection tested and rejected
- Dev run 20261108-085517 (N=20 answerable): all modes 18/20 doc hit@1; passage hit@1 keyword 10, semantic 6, hybrid 9, weighted 8
- Test run 20261108-091348, run once (N=12 answerable; semantic 11 because Q03 timed out with ELSER HTTP 408): doc hit@1 keyword 10/12, semantic 8/11, hybrid 10/12, weighted 10/12; passage hit@5 keyword 4/12, semantic 7/11, hybrid 6/12, weighted 6/12
- Finding: no mode wins consistently; ranking flipped between dev and test; small N
- Chunking checked: median about 1,250 to 1,340 characters, max 1,399, no oversize; many standards chunks end on headings or footers (page footers appear inside RFC chunks)
- Open: change the default elastic password, rebind es01 to 127.0.0.1, delete zz_elser_probe (with a yes), corpus manifest and licences, update Q&A guide and slides
