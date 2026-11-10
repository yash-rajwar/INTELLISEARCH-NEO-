# Batch 1 — Environment and Evaluation Readiness

**Status:** EVIDENCE COMPLETE; SCREENSHOTS AND GIT HANDOFF PENDING  
**Date:** 2026-11-10  
**Baseline Git commit:** `2503794`  
**Branch:** `v4-upgrade`  
**Elasticsearch:** `9.2.0`  
**Project:** IntelliSearch NEO

## 1. Objective

Establish the deployed environment, the scope of the indexed public-document corpus, and the availability of Elasticsearch's trial-enabled semantic retrieval capabilities. Check whether the document coverage needed for a later BM25, ELSER, and hybrid RRF evaluation is present, without changing the original corpus or application code.

## 2. Setup

- Project: IntelliSearch NEO, a Flask and Elasticsearch search prototype.
- Repository branch: `v4-upgrade`; baseline commit: `2503794`. The working tree already contained changes to `config.py`, `corpus/ATTRIBUTION.md`, `corpus/manifest.csv` and untracked `Dockerfile`, `ml.json`. These changes were not modified as part of this batch.
- Platform: Windows PowerShell with Docker. Docker Engine/CLI version reported: `29.9.2`. Host Python and project `venv` both reported `3.13.15`; the checked `venv` did not contain `requests`, `Flask`, `elasticsearch`, or `python-dotenv` at the time of inspection. The application's successful Flask responses came from an earlier running Docker container. Dependencies were not installed or changed.
- Containers observed: `es01` (Elasticsearch Docker image `9.2.0`) and `intellisearch` (Flask app). Both containers were observed to have exited with code `255` at different points; `es01` was restarted and then answered authenticated Kibana API requests. The cause of the exits was not determined.
- Cluster: `docker-cluster`, single node. A live health check reported `yellow`; 47 active primary/total active shards, zero unassigned primary shards, and one unassigned replica shard. The allocation explanation identified `same_shard` for the showcase index replica, because the existing primary was on the only node.
- Main evaluation corpus index: `intellisearch_corpus_v1`; supplementary index: `intellisearch_showcase_chunks_v3` (not used for the Batch 1 coverage gate).
- Retrieval modes planned for later batches: `bm25`, `elser`, and `hybrid` (RRF). No retrieval quality metrics were collected in Batch 1.
- Chunker attribution: `docs/PROGRESS.md` states chunker v2 was completed and lists 7,102 passages, but does not conclusively establish which chunker generated each index. **Not independently verified.**

## 3. Method

1. Inspected the Git branch, baseline commit, existing working-tree state, container images, and installed Python environment.
2. Inspected Elasticsearch startup logs; then queried live health, licence, index inventory, mapping, inference endpoint, and trained-model deployment using authenticated Kibana Dev Tools.
3. Queried `intellisearch_corpus_v1/_count` and an aggregation on the `filename` field. Compared returned filenames against the 18-entry `corpus/manifest.csv` inventory and the 14 filenames referenced in the evaluation plan.
4. Exported `report/results/b1_corpus_inventory.csv` from the verified aggregation counts and manifest metadata. The CSV records filename, tier, format, source bytes, and indexed chunk count.
5. Measured source text length with Elasticsearch scripted aggregations over the `content` field: `avg` for mean, and percentiles at 50 and 95. Percentiles are approximate aggregation estimates rather than exact order statistics.
6. Inspected index mappings to identify `content`, `filename`, `document_id`, `chunk_index`, and `content_semantic`. No ingestion, deletion, mapping updates, or index resets were performed.

## 4. Results

### 4.1 Environment, licence and model

| Item | Observed result |
|---|---|
| Elasticsearch version | 9.2.0 |
| Docker version | 29.9.2 |
| Cluster health | yellow |
| Nodes / data nodes | 1 / 1 |
| Active shards / primary shards | 47 / 47 |
| Unassigned shards / unassigned primary shards | 1 / 0 |
| Active shards percentage | 97.91666666666666% |
| Licence | trial, active |
| ELSER inference ID | `.elser-2-elasticsearch` |
| Model ID | `.elser_model_2_linux-x86_64` |
| Model deployment state | started |
| Model allocation | fully_allocated; 1 of 1 target |
| Deployment threads per allocation | 1 |
| Inference count / failure count | 55 / 0 |
| Inference endpoint sentence chunking | max chunk size 250, overlap 1; these are inference settings, not evidence of the application's chunker version |

The model statistics showed ELSER operational at the time queried; historical application logs also showed warm-ups and successful HTTP responses. The endpoint's existence alone would not have demonstrated deployment readiness, so both were checked.

### 4.2 Index counts and mapping

| Index | `_cat/indices` docs.count | Store size | Health |
|---|---:|---:|---|
| `intellisearch_corpus_v1` | 15,732 | 28.4mb | green |
| `intellisearch_showcase_chunks_v3` | 495 | 886.9kb | yellow |

The main index's `_count` API returned **7,102** source-searchable Elasticsearch documents/chunks. The `filename` aggregation also totalled **7,102**, covering **18 distinct filenames**. This differs from `_cat/indices` `docs.count` of **15,732**. Additional Lucene documents associated with semantic indexing are a **hypothesis** for the discrepancy, not a verified cause. All corpus and retrieval-evaluation denominators in this report use the verified `_count` result, 7,102.

Mapping evidence:

| Purpose | Field | Mapping type |
|---|---|---|
| Chunk text | `content` | `text` |
| Semantic content | `content_semantic` | `semantic_text` (ELSER endpoint) |
| Filename | `filename` | `keyword` |
| Source ID | `document_id` | `keyword` |
| Chunk order | `chunk_index` | `integer` |
| Page number | `page_number` | `integer` |
| Collection | `collection` | `keyword` |

### 4.3 Corpus inventory and coverage

The inventory uses the 18 manifest rows and actual per-filename Elasticsearch aggregation counts. Full manifest metadata (including each source file's size in bytes) is in `report/results/b1_corpus_inventory.csv`.

| Tier | Filename | Indexed chunks |
|---|---|---:|
| 1 | nist-800-61r3.pdf | 108 |
| 1 | nist-csf-2.pdf | 67 |
| 1 | nist-ai-rmf-1.pdf | 111 |
| 1 | india-dpdp-2023.pdf | 62 |
| 1 | india-it-act-2000.pdf | 129 |
| 1 | india-rti-2005.pdf | 206 |
| 1 | rfc-9110.pdf | 468 |
| 1 | rfc-8446.txt | 326 |
| 2 | nist-800-53r5.pdf | 1,602 |
| 2 | nasa-se-handbook.pdf | 827 |
| 3 | nist-800-171r3.pdf | 261 |
| 3 | rfc-9293.pdf | 218 |
| 3 | gutenberg-art-of-war.txt | 279 |
| 3 | gutenberg-pride-and-prejudice.txt | 664 |
| 3 | gutenberg-frankenstein.txt | 381 |
| 3 | gutenberg-sherlock-holmes.txt | 503 |
| 3 | gutenberg-dracula.txt | 754 |
| 3 | gutenberg-alice.txt | 136 |
| **Total** | **18 distinct filenames** | **7,102** |

**Coverage gate: PASS, 14/14 documents present** in `intellisearch_corpus_v1`. All 14 `expected_doc` filenames referenced by the planned 36-question evaluation set have at least one indexed chunk; none are missing. This proves document presence only. Whether the exact 32 answerable questions' `gold_span` texts occur in indexed chunks must be tested in Batch 2. Reuse terms for the three Indian government acts are unverified; their use here was for an internal demonstration.

### 4.4 Chunk length (source `content`, characters)

| Statistic | Value | Method |
|---|---:|---|
| Mean | 1,195.772599267812 | Elasticsearch scripted `avg` |
| 50th percentile (estimated) | 1,295.4836508268372 | Elasticsearch scripted `percentiles` |
| 95th percentile (estimated) | 1,393.524643711143 | Elasticsearch scripted `percentiles` |
| Population | 7,102 chunks | `_count` and aggregation hits.total |

For presentation, rounded values are **mean 1,195.773**, **estimated p50 1,295.484**, and **estimated p95 1,393.525** characters. The two percentile figures are estimates and must not be described as exact median / exact p95.

### 4.5 Representative raw API evidence

```json
{"cluster_name":"docker-cluster","status":"yellow","number_of_nodes":1,"number_of_data_nodes":1,"active_primary_shards":47,"active_shards":47,"unassigned_shards":1,"unassigned_primary_shards":0,"active_shards_percent_as_number":97.91666666666666}
{"license":{"status":"active","type":"trial"}}
{"count":7102,"_shards":{"total":1,"successful":1,"skipped":0,"failed":0}}
{"model_id":".elser_model_2_linux-x86_64","deployment_stats":{"state":"started","allocation_status":{"allocation_count":1,"target_allocation_count":1,"state":"fully_allocated"}},"inference_stats":{"inference_count":55,"failure_count":0}}
{"mean_chunk_length":{"value":1195.772599267812}}
{"chunk_lengths":{"values":{"50.0":1295.4836508268372,"95.0":1393.524643711143}}}
```

*The last four objects are concise extracts of separate user-run API results, not literal complete responses. No credentials or internal connection addresses are retained.*

## 5. Observations

- **Observed:** The single-node cluster was `yellow`, with no unassigned primary shards. The only unassigned shard was the showcase index's replica; its allocation explanation reported `same_shard`.
- **Observed:** The licence API reported `trial` and `active`, and ELSER deployment statistics reported `started` and `fully_allocated`.
- **Observed:** The main index uses `semantic_text` on `content_semantic` and the ELSER inference endpoint.
- **Observed:** All 18 manifest filenames have indexed content; all 14 required evaluation filenames are present.
- **Observed:** Container exit code 255 occurred during earlier environment checks, but live Elasticsearch verification subsequently succeeded. Root cause not established.
- **Hypothesis:** Hidden/internal documents produced by `semantic_text` indexing could account for the difference between CAT `docs.count` and searchable `_count`; this was not independently measured.
- **Hypothesis:** The corpus likely uses chunker v2 because the progress ledger documents v2 completion alongside the 7,102-passage corpus; index-specific chunker provenance was not confirmed.

## 6. Limitations

- No search relevance metrics have been computed yet; gold-span coverage and scoring are Batch 2 tasks.
- Only one local cluster was evaluated; observed timings and capacities cannot be generalized to other hardware.
- The tested environment uses a time-limited paid-tier trial. Commercial use or procurement decisions are outside this report.
- Application-container exit code 255 was not explained, and persistent application availability was not demonstrated.
- Per-index chunker provenance remains unverified.
- The percentile aggregation gives estimates, not exact percentiles.
- Three Indian government acts were retained for an internal prototype; reuse terms were not independently verified.

## 7. Key takeaways

- **F-B1-01, F-B1-02:** Elasticsearch 9.2.0 was accessible; the paid-tier trial licence was active.
- **F-B1-03, F-B1-04:** ELSER was deployed and fully allocated, with 55 inferences and 0 reported failures at measurement time.
- **F-B1-05, F-B1-06:** The main index contained 7,102 searchable chunks across 18 documents; the 14-document evaluation coverage gate passed.
- **F-B1-07:** Source content averaged 1,195.773 characters per chunk, with estimated p50 1,295.484 and p95 1,393.525 characters.
- **F-B1-08:** The single-node cluster was yellow because a replica could not be allocated beside its primary; no primary shards were unassigned.

## 8. Screenshots

**Capture/availability to verify before final commit.** Do not claim screenshots exist until each file is saved locally. Crop any personal details, credentials, host addresses and unrelated content.

| File | Caption | What it proves |
|---|---|---|
| `b1_01_docker_ps.png` | Docker containers and images | Relevant runtime containers and versioned image |
| `b1_02_cluster_health.png` | Live cluster health | Single-node yellow status and no missing primaries |
| `b1_03_license_trial.png` | Trial licence | Trial type and active status |
| `b1_04_indices_list.png` | Index inventory | Index names, source counts and sizes |
| `b1_05_elser_endpoint.png` | ELSER endpoint | Sparse-embedding endpoint configuration |

## 9. FACTS

| ID | What | Verified value | Evidence source |
|---|---|---|---|
| F-B1-01 | Elasticsearch version | `9.2.0` | Console/log evidence in §2 and §4.1 |
| F-B1-02 | Licence type/status | `trial` / `active` | Live `_license` result, §4.5 |
| F-B1-03 | ELSER endpoint and model | `.elser-2-elasticsearch` / `.elser_model_2_linux-x86_64` | Live `_inference` and model stats, §4.1 |
| F-B1-04 | ELSER deployment | `started`; `fully_allocated` (1/1); 55 inference calls, 0 failures | Live model stats, §4.5 |
| F-B1-05 | Main corpus | 18 documents, 7,102 searchable chunks | `results/b1_corpus_inventory.csv`, §4.3; live `_count` |
| F-B1-06 | Required document coverage | PASS: 14/14; missing 0 | `results/b1_corpus_inventory.csv`, §4.3 and evaluation plan |
| F-B1-07 | Chunk lengths | mean 1,195.772599267812; estimated p50 1,295.4836508268372; estimated p95 1,393.524643711143 characters | Live scripted aggregations, §4.4–4.5 |
| F-B1-08 | Cluster health | yellow; nodes 1; active primary shards 47; unassigned shards 1, primary 0 | Live `_cluster/health` and allocation explanation, §4.5 |
| F-B1-09 | CAT reported main index | 15,732 docs.count; 28.4mb store; green | Live `_cat/indices`, §4.2 |
| F-B1-10 | CAT reported showcase index | 495 docs.count; 886.9kb store; yellow | Live `_cat/indices`, §4.2 |
| F-B1-11 | Corpus chunker provenance | Not independently verified; progress ledger states v2 completed | `docs/PROGRESS.md`, §2, §5 |
| F-B1-12 | Index mapping | `content` text; `content_semantic` semantic_text; `filename` keyword; `chunk_index` integer | Live `_mapping`, §4.2 |

## 10. Feeds report chapters

- Project architecture and technology environment
- Corpus composition, ingestion and indexing
- Search implementation and enterprise trial capability setup
- Evaluation prerequisites and methodological limitations
- Environment verification appendix

## Batch 2 handoff

**Evaluate index:** `intellisearch_corpus_v1`. The 14-document presence coverage gate passed. Bring `questions_draft.csv`, this Batch 1 report/FACTS, the application's retrieval functions, and `es_client.py`. Before running any quality metrics, verify every answerable question's `gold_span` against indexed `content` and freeze the corrected question file. Preserve existing Git changes and do not overwrite either existing index.
