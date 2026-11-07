# Progress ledger

_Last updated: 2026-11-07 by session 1_

## Status board
| WP | Title | Status | Commit | Notes |
|----|-------|--------|--------|-------|
| 00 | Safety net (branch, tests, .gitignore) | done | ad86be4 | venv is Python 3.12.10; 32/32 tests pass |
| 16a | Formatting-only commit | done | 84cbce0 | ruff format, 15 files |
| 16b (part) | Unused imports, pymupdf import | done | 83e65b1, c5f2687 | |
| 01 | Portable configuration | not started | | next |
| 02 | App factory, server, secrets, logging | not started | | |
| 03 | ES client hardening and caching | not started | | |
| 05 | Chunker v2 and dynamic limits | not started | | |
| 04 | Ingestion CLI and corpus index | not started | | |
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
- Elasticsearch version: 9.0.0 (Lucene 10.1.0), single node, Docker (es01), Kibana 9.0.0
- License: trial, active, issued 2026-11-07 08:02 UTC, expires 2026-12-07 08:02 UTC; eligible_to_start_trial=false (expected)
- ELSER endpoint .elser-2-elasticsearch exists; adaptive allocations min 0 (scales to zero, slow first query); its own chunking: sentence, max 250, overlap 1
- Docker memory limit: 3.77 GiB total (es01 uses ~1.5 GiB, kibana ~0.6 GiB). Probably too low for ELSER
- First ELSER request via Kibana Dev Tools timed out (Kibana 30 s gateway limit). Use curl with --max-time
- Python venv: 3.12.10 in .\venv. A system variable points pip at a missing PostgreSQL CA bundle; clear SSL_CERT_FILE / REQUESTS_CA_BUNDLE / CURL_CA_BUNDLE / PIP_CERT in the window before pip install
- Scratch index zz_elser_probe exists (1 test document); delete at the end of the ELSER checks
- Corpus index name and counts: not created yet

## [VERIFY] results
- ELSER answers a query: NOT YET CONFIRMED
- Weighted RRF `weight` accepted: ?
- Semantic highlight inside rrf: ?
- linear / text_similarity_reranker available on 9.0.0: ?

## Decisions
- 2026-11-07: build and rehearse on the laptop, push to GitHub, install on the office computer later
- 2026-11-07: ledger order for WP-05 before WP-04 (the ingest CLI needs the chunker)

## Open problems
- ELSER first-call timeout and low Docker memory (see above)
- Elasticsearch container is published on 0.0.0.0:9200; rebind to 127.0.0.1 later (not urgent)

## Next 3 steps
1. Raise Docker memory, finish the ELSER probe (count, search timing)
2. WP-01 portable configuration (settings.py, no hardcoded paths)
3. WP-02 app factory, waitress, persistent secret
