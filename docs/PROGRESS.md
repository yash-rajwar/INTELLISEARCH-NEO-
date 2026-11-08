# Progress ledger

_Last updated: 2026-11-08_

## Status board
| Item | Title | Status | Commit | Notes |
|------|-------|--------|--------|-------|
| WP-00 | Safety net (branch, tests, .gitignore) | done | ad86be4 | venv is Python 3.12.10 |
| WP-16a | Formatting-only commit | done | 84cbce0 | ruff format, 15 files |
| WP-16b (part) | Unused imports, pymupdf import | done | 83e65b1, c5f2687 | rest of 16b later |
| WP-01 | Portable configuration | done | 263c443, a3d7711, bbb1d5e | settings.py, BOOKS_DIR, LEGACY_ENABLED off by default, preflight |
| WP-02 | Secret key, logging, ES client at import, sqlite close | done | 8698909 | no app factory, no waitress (decided: not needed for the demo) |
| WP-03 | ES client hardening, corpus source, warm-up, status | done | b829771, 8efd1e3, 6c8c477 | retries, /warmup, keep-alive ping, /api/status |
| WP-05 | Chunker v2 | done | see git log | chunking.py; corpus chunks: median about 1,250 to 1,340 characters, max 1,399 |
| WP-04 | Ingestion CLI and corpus index | done | see git log | intellisearch_corpus_v1: 7,102 passages, 18 documents |
| WP-06 | Upload pipeline (hash, replace, delete) | done | see git log | uploads index intellisearch_showcase_chunks_v3 |
| WP-07 | Search service, grouping, modes | done | fdf8399, bb9ad5f (fixes) | weighted RRF fused locally; file-type filter fixed |
| WP-08 | Evaluation harness and question set v2 | done | see git log | eval/run_eval.py, 36 questions, tag eval-frozen-v2 |
| WP-11 | Fuzzy mode and highlighting | done | f80db95 | LOG_QUERIES switch also added |
| WP-12 | Ask page checks and citation validation | done | 3d1f6da | |
| Batch 11 (WP-15) | /system page: licence, ELSER, corpus counts, Test now, diagnostics report | done | 3d2d4b6 | sysview.py |
| Batch 12a | Long-document summaries and aligned passages | done | see git log | longdoc.py |
| Batch 12b | Corpus documents in Summarize and Compare | done | 6ad0b85 | corpus:<id>, text cache in data/extracted |
| Docs | Demo guide | done | 86c96c3 | docs/DEMO.md, figures still to be re-checked |
| Batch 13 | Compare methods page: status chips and markers | done | d4ed62f | Found by both / Only found by meaning / Only found by keywords |
| Batch 14 | Long PDFs (max_pages) | done | d764c5f | corpus files up to 1,000 pages; uploads keep the 200-page limit |
| Batch 15 | Navigation rewrite (base.html) | done | 8df402c | five nav groups, skip link |
| Batch 16 | /evaluation page shows only the two cited runs | done | 1144d95, a322352 | 16c (route test in a separate process): see git log |
| Batch 17 | Startup banner text, this ledger | done | see git log | |
| WP-10 | Optional Elastic Rerank | tested and rejected | | The endpoint exists, but the model could not be loaded on this cluster (Model definition truncated), and ELSER already uses most of the 2,460 MB machine-learning memory. ENABLE_RERANK stays off. The development-split gate was never reached |
| WP-09 | Neighbour context | partly | ef0a2cf, a71a39b | Display and the CONTEXT_NEIGHBOURS setting exist. Not built: one mget per page, and the passage-hit-with-neighbours metric |
| WP-14a | UI level U1 | partly | 8df402c | navigation, layout, demo step bar done; full U1 checklist not reviewed; U3 not started |
| Batch 18 | README, CHANGELOG, demo guide, traceability note | done | 227c378 | |
| Batch 19 | Loopback guard, inline header on corpus files, CONTEXT_NEIGHBOURS | done | a71a39b | 19b fixed an import-order problem in the new test |
| Batch 20 | Compare runs its methods in two parallel phases | done | see git log | parallel.py |
| Batch 21 | Related documents for the corpus, corpus list in the library, X-Frame-Options DENY | done | see git log | related.py; shared vocabulary, not meaning |
| Batch 22 | Ask: clickable citations, copy button, Ollama status, OLLAMA settings from .env | done | see git log | Ollama is not part of the demo |
| Batch 23 | Header tests, live smoke tests, pinned requirements, CI file | done | dab1e06 | live tests: 5 passed, 1 skipped (ELSER cold) |
| Batch 24 | Demo page corpus examples and step bar, system page V4 label and rerank line | done | see git log | |
| Batch 25 | Documentation update, docs/ARCHITECTURE.md | done | see git log | |
| WP-18 | Security hygiene | partly | see git log | headers checked by tests; loopback guard; repeat the secret scan before any push |
| WP-16 (rest) | Type hints, docstrings, single DB initialiser, caching | not done | | reported as not done |
| WP-17 (rest) | docker-compose file, scripts, screenshots, user guide, test report | not done | | reported as not done |

Status values: not started, in progress, done, deferred, partly.

## Environment facts (confirmed)
- Laptop: Windows, 8 GB RAM, x86_64, 4 CPUs; Python 3.12.10 venv in .\venv
- Elasticsearch 9.0.0, single node, Docker (es01, volume elastic-stack_esdata); Kibana 9.0.0 (container stopped). Health yellow (one replica cannot be assigned on a single node): harmless
- Licence: trial, active, expires 2026-12-07 08:02 UTC (per cluster)
- ELSER (.elser-2-elasticsearch, field content_semantic): first call after idle about 30 s; warm calls well under 1 s; a warm call can still time out (HTTP 408 seen once). App waits up to 280 s and pings every 120 s. English only
- Live check, query "What is the person whose personal data is collected called?" (scope corpus), warm latencies: keyword 69 ms, semantic 241 ms, hybrid 497 ms, weighted 414 ms
- Corpus intellisearch_corpus_v1: 7,102 passages by _count (_cat showed a larger number, probably hidden ELSER sub-documents), 18 documents; file_type stored as "pdf" (no dot)
- Corpus text cache data/extracted is not in git: on a new machine run python warm_corpus_text.py first (about 2 minutes), otherwise the first click on SP 800-53 takes about 80 s
- OCR not ready (Tesseract language data missing); Ollama not configured: both optional, not part of the demo
- Machine-learning memory on this cluster: about 2,460 MB, of which ELSER uses about 2,100 MB. Do not start extra model deployments before the demo
- Kibana Dev Tools times out at about 30 s; use curl with --max-time and JSON in a file
- pip needs the PostgreSQL CA variables cleared (SSL_CERT_FILE, REQUESTS_CA_BUNDLE, CURL_CA_BUNDLE, PIP_CERT)
- es01 is published on 0.0.0.0:9200 (see Open problems)
- Scratch index zz_elser_probe; delete only with the user's explicit yes
- Backup: git bundle at ..\intellisearch-backup.bundle (copy it to another disk)

## [VERIFY] results
- ELSER answers a query: CONFIRMED
- Weighted RRF weight accepted on 9.0.0: NO, the weighted retriever format is rejected (HTTP 400); weighted RRF is fused locally
- Semantic highlight inside rrf: CONFIRMED on 9.0.0 (live check 2026-11-08; fragments can be long)
- text_similarity_reranker / .rerank-v1 on 9.0.0: the endpoint exists and the licence is trial, but the model fails to load (Model definition truncated). linear retriever: not checked

## Decisions
- 2026-11-07: build and rehearse on the laptop; push to GitHub at the end
- 2026-11-07: legacy collections hidden unless LEGACY_ENABLED=true
- 2026-11-07: git add by file name, not -A
- 2026-11-07: corpus is an always-on source and the default scope
- No app factory, no waitress
- Related documents for the corpus: built (batch 21). It compares shared vocabulary (more-like-this), not meaning
- Rerank (WP-10): tried on the demo laptop on 2026-11-08 and rejected (the model could not be loaded)
- Compare runs keyword and semantic together, then hybrid and weighted together; after an ELSER timeout hybrid and weighted are labelled skipped
- Compare markers: top results of keyword and semantic search are compared by document title; a fallback is flagged and not compared
- /evaluation shows only the two cited runs (dev 20261108-085517, test 20261108-091348); other saved runs stay on disk but are not shown
- The test split (tag eval-frozen-v2) was run once and is never run again
- Present from the laptop unless the office machine already has Elasticsearch tested
- Ollama (local AI answers) is dropped from the demo: the office computer does not have it. The Ask page shows cited evidence only

## Evaluation (cited runs, hits/questions, never percentages)
Development split, run 20261108-085517, N=20 answerable:

| Metric | keyword | semantic | hybrid | weighted |
|---|---|---|---|---|
| Document hit@1 | 18/20 | 18/20 | 18/20 | 18/20 |
| Passage hit@1 | 10/20 | 6/20 | 9/20 | 8/20 |
| Passage hit@5 | 15/20 | 16/20 | 16/20 | 16/20 |

Test split, run 20261108-091348, run once, N=12 answerable (semantic N=11: Q03 hit HTTP 408):

| Metric | keyword | semantic | hybrid | weighted |
|---|---|---|---|---|
| Document hit@1 | 10/12 | 8/11 | 10/12 | 10/12 |
| Passage hit@1 | 2/12 | 0/11 | 1/12 | 1/12 |
| Passage hit@5 | 4/12 | 7/11 | 6/12 | 6/12 |

Finding: no mode wins consistently, the order changed between the splits, and differences of one or two questions are within noise. Full tables, MRR, rejected experiments and limits: docs/EVALUATION.md.
Not cited (older runs with a since-fixed scoring bug, and an old 23-question draft): 20261108-085023, 20261108-085236, 20261108-023037. A separate dev-only fuzzy run is in eval/results_fuzzy.

## Open problems
- After the demo: rebind es01 to 127.0.0.1 and change the default elastic password. Do not recreate the container before the demo
- Delete zz_elser_probe (needs the user's explicit yes)
- Corpus manifest and licences: three Indian government documents have unverified reuse terms
- docs/DEMO.md figures need re-checking against the eval JSON (typo counts, latencies)
- Manual UI checks not yet reported: sidebar fit at the demo screen size, Tab shows the skip link, Summarize time on SP 800-53 (over 20 s means do not demo it live), aligned passages in Compare documents on corpus documents
- ELSER can time out even when warm: open the warm-up page before presenting
- Later commits are not pushed to GitHub (intentional)
- ruff reported 192 findings at the last check (35 auto-fixable); CI therefore runs the tests only. Clean up after the demo
- Q&A guide, reports and slides need updating after the code changes

## Next 3 steps
1. Slides (about 7, real hits/questions counts, legacy results kept separate from this evaluation) and the Q&A guide
2. The manual checks in the open problems list, then two timed rehearsals from a cold ELSER with a backup recording
3. Tag demo-2026-11-09 after the rehearsals pass; after the demo: rebind es01, change the password, push to a private repository
