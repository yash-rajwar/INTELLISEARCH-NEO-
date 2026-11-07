# Progress ledger

_Last updated: 2026-11-07 by session 2_

## Status board
| WP | Title | Status | Commit | Notes |
|----|-------|--------|--------|-------|
| 00 | Safety net (branch, tests, .gitignore) | done | ad86be4 | venv is Python 3.12.10 |
| 16a | Formatting-only commit | done | 84cbce0 | ruff format, 15 files |
| 16b (part) | Unused imports, pymupdf import | done | 83e65b1, c5f2687 | rest of 16b later |
| 01 | Portable configuration | done | 263c443, a3d7711, bbb1d5e | settings.py, BOOKS_DIR, LEGACY_ENABLED off by default, preflight table; 49 tests pass |
| 02 | App factory, server, secrets, logging | not started | | next; trimmed plan in Decisions |
| 03 | ES client hardening and caching | not started | | include ELSER warm-up |
| 05 | Chunker v2 and dynamic limits | not started | | |
| 04 | Ingestion CLI and corpus index | not started | | must be re-runnable on the office computer |
| 06 | Upload pipeline | not started | | |
| 07 | Search service, grouping, modes, pagination | not started | | |
| 08 | Evaluation harness | not started | | |
| 14a | UI level U1 | not started | | |
| 15 | System, license and health page | not started | | |
| 09 | Neighbour context | not started | | |
| 11 | Fuzzy mode and highlighting | not started | | |
| 12 | Ask / RAG improvements | not started | | |
| 10 | Optional Elastic Rerank | not started | | |
| 14b | UI level U2 | not started | | |

## Environment facts (confirmed)
- Laptop: Windows, 8 GB RAM, x86_64, 4 CPUs; Python 3.12.10 venv in .\venv
- Elasticsearch 9.0.0 (Lucene 10.1.0), single node, Docker (es01); Kibana 9.0.0 (container stopped)
- License: trial, active, expires 2026-12-07 08:02 UTC; eligible_to_start_trial=false is expected
- ELSER endpoint .elser-2-elasticsearch exists (min allocations 0; endpoint chunking sentence, 250, overlap 1)
- ELSER needs about 2.0 GiB native memory. .wslconfig sets WSL memory 5GB, swap 4GB. xpack.ml.max_machine_memory_percent=50, so total_ml_memory is 2460mb
- ELSER works on the laptop after a forced stop of the failed deployment: direct _infer cold start 27.6 s; semantic search over zz_elser_probe warm 0.6 s (took 476 ms). Scales to zero when idle. Cause of the earlier failure not identified (CPU has avx/avx2/sse4_2, OOMKilled=false). One early probe search hung 15 min
- Kibana Dev Tools times out at about 30 s; use curl with --max-time and JSON in a file
- pip needs the PostgreSQL CA variable cleared (SSL_CERT_FILE, REQUESTS_CA_BUNDLE, CURL_CA_BUNDLE, PIP_CERT)
- es01 is published on 0.0.0.0:9200 (rebind to 127.0.0.1 later)
- Scratch index zz_elser_probe has 2 docs; delete at the end with the user's yes
- Corpus index name and counts: not created yet

## [VERIFY] results
- ELSER answers a query: CONFIRMED (_infer 27.6 s cold; semantic search 0.6 s warm)
- Weighted RRF weight accepted: ?
- Semantic highlight inside rrf: ?
- linear / text_similarity_reranker / .rerank-v1 on 9.0.0: ?

## Decisions
- 2026-11-07: demo is on the office computer; build and rehearse on the laptop; fresh Elasticsearch plus its own trial must be set up on the office computer
- 2026-11-07: WP-05 before WP-04
- 2026-11-07: legacy collections hidden unless LEGACY_ENABLED=true
- 2026-11-07: git add by file name, not -A
- WP-02 plan: no blueprint split; persistent secret.key; rotating logs; ES client at import time; fix store.init_db connection close; add tests; waitress optional

## Open problems
- Plan an ELSER warm-up before the demo (cold start is slow); first deployment failure unexplained
- Later commits not pushed to GitHub (intentional)
- Q&A guide, reports and slides need updating after the code changes

## Next 3 steps
1. WP-02 (trimmed), then WP-03 with an ELSER warm-up
2. WP-05, WP-04, then the corpus and frozen evaluation questions
3. Rehearse a fresh install on the office computer; delete zz_elser_probe at the end (with the user's yes)