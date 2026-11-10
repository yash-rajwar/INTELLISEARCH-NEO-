# IntelliSearch NEO | Batch 2: Retrieval Evaluation

**Evaluation date:** 10 November 2026  
**Project:** IntelliSearch NEO  
**Git branch:** `v4-upgrade`  
**Elasticsearch index:** `intellisearch_corpus_v1`  
**Search implementation:** application `search()` in `search.py`; BM25=`keyword`, ELSER=`semantic`, hybrid=`hybrid` (RRF).  
**Status:** Main evaluation executed and results captured. Further manual review of per-question evidence and screenshot capture remain outstanding.

## Objective

Compare lexical BM25, ELSER semantic retrieval, and hybrid reciprocal-rank fusion against a reproducible, fixed set of questions over the indexed public-document corpus. Distinguish answer-passage retrieval metrics from document-level retrieval and avoid making unsupported general-performance claims.

## Preparation and provenance

- Question CSV: `report/questions_frozen.csv`, copied byte-for-byte from `eval/questions_draft.csv`.
- Frozen SHA-256: `7503F9ADE1DB1EA8FBB7EE2F0E2D8ACF29320C73D043ADEA6A4BECB98E77990F`.
- Total 36 questions: 32 answerable and 4 intentionally unanswerable.
- Split: dev 22 (20 answerable + 2 unanswerable), test 14 (12 answerable + 2 unanswerable).
- Types: keyword 11, conceptual 11, long 5, typo 5, unanswerable 4.
- Gold-span verification: 32/32 spans found in the expected indexed document, 0 missing; no split-only spans observed under the implemented adjacent-chunk rule.
- Three tentative spans confirmed using surrounding indexed context: Q05 (NIST CSF's six functions), Q16 (TCP SYN and initial sequence numbers), and Q32 (NASA systems engineering spanning design through retirement). These are substantive contextual confirmations, not merely string checks.
- Runtime: Docker application container `intellisearch`, Python 3.12.16, Flask 3.1.3, requests 2.34.2.
- Application search modes confirmed: `keyword`, `semantic`, `hybrid`, `weighted`, `fuzzy`; only the first three evaluated here.

## Method

The evaluator called the project's existing search logic, rather than implementing alternative query pathways. Each of the 36 frozen questions was run in BM25, ELSER, and hybrid modes with top-*k*=10; this produced 108 mode/question executions. The main comparison uses only the 32 answerable questions for passage-relevance metrics. Four unanswerable questions were run but should be assessed separately for overconfident retrieval, not counted as ordinary misses.

Reported metrics are Precision@5, Precision@10, Recall@10, mean reciprocal rank (MRR), and nDCG@10. Do not interpret the reported Recall@10 as necessarily identical to the proportion of questions with any relevant hit: some questions have multiple gold-matching chunks. Scores are within-query/mode ranking outputs and raw search scores must not be compared across modes.

### Main evaluation (answerable questions, n=32)

| Metric | BM25 | ELSER | Hybrid RRF |
|---|---:|---:|---:|
| Precision@5 | 0.119 | **0.125** | 0.119 |
| Precision@10 | 0.078 | 0.081 | **0.084** |
| Recall@10 | 0.625 | 0.688 | **0.695** |
| MRR | 0.380 | 0.344 | **0.399** |
| nDCG@10 | 0.435 | 0.429 | **0.470** |
| Reported failures/fallbacks | 0 | 0 | 0 |

**Observed:** Hybrid ranks highest in overall Recall@10, MRR, and nDCG@10; ELSER ranks highest in Precision@5. The margins are modest, and the set is small.

### Split-level results (answerable only)

| Split | Mode | n | MRR | Recall@10 |
|---|---|---:|---:|---:|
| Dev | BM25 | 20 | 0.538 | 0.800 |
| Dev | ELSER | 20 | 0.431 | 0.750 |
| Dev | Hybrid | 20 | **0.544** | **0.812** |
| Test | BM25 | 12 | 0.117 | 0.333 |
| Test | ELSER | 12 | **0.200** | **0.583** |
| Test | Hybrid | 12 | 0.158 | 0.500 |

**Observed:** On the held-out test subset, ELSER outranks the other modes on both reported MRR and Recall@10, unlike the overall ranking. This difference must be preserved in the final internship report. Do not tune RRF using these test results.

## Dry-run sanity check

Three diagnostic answerable questions (Q01, Q05, Q16) were executed across all three modes before the main run. Nine executions succeeded, with no reported fallback or failure.

| Question | BM25 first relevant rank | ELSER first relevant rank | Hybrid first relevant rank |
|---|---:|---:|---:|
| Q01: Data Fiduciary | Not found in top 10 | Not found in top 10 | Not found in top 10 |
| Q05: NIST CSF core functions | 1 | 2 | 1 |
| Q16: TCP connection setup | 10 | 2 | 3 |

**Observed:** Q16 was retrieved earlier by ELSER and hybrid than by BM25 in this diagnostic run. Q01 was not retrieved in the top 10 in any mode, despite its gold span being verified in the index. These observations justify examining retrieval failure examples, not assuming missing documents.

## Evidence and reproducibility

The following files were produced on the user's Windows PC under `report/results/`:

1. `b2_gold_check.json`: normalized gold-span verification output.
2. `b2_dry_summary.csv` and `b2_dry_per_question.csv`: three-question diagnostic.
3. `b2_main_per_question.csv`: main per-question results across modes.
4. `b2_main_summary.csv`: main grouped metrics.
5. `b2_main_top10.json`: top-ten retrieved results and supporting snippets.
6. `b2_main_manifest.json`: run metadata and reproducibility details.

Main run command:

```powershell
docker exec intellisearch python /tmp/report_eval.py --questions /tmp/questions_frozen.csv --index intellisearch_corpus_v1 --modes bm25,elser,hybrid --k 10 --split all --out /tmp/b2_main
```

**Evidence status:** User supplied terminal output confirming execution, summary metrics, and copies of the four main evidence files. This report does not independently re-open the full CSV/JSON evidence, so group-by-type scores, document-level metrics, unanswerable top-score statistics, and per-mode p50/p95 latencies are **not yet verified here**. These must be read from the actual evidence files before their numerical values are published. Do not fill them by estimation.

## Observations, interpretations and limitations

- **Observed:** 108 retrieval executions completed with zero evaluator-reported failures/fallbacks.
- **Observed:** Full gold-span presence verification succeeded for 32/32 answerable questions; three tentative spans were contextually reviewed.
- **Observed:** Hybrid has the best overall MRR (0.399), while ELSER has the best test MRR (0.200). The overall winner and held-out test winner differ.
- **Hypothesis:** Semantic retrieval is useful when question wording diverges from source language, as suggested by the Q16 diagnostic. Additional examples and query-level analysis are required for a stronger claim.
- **Limitation:** Public-domain and public-document sample, small manually composed question set; results should not be generalized to classified, operational, or entirely different corpora.
- **Limitation:** Some gold spans can appear in more than one chunk; strict relevance metrics should consider all verified matching chunks. Exact treatment is evaluator-specific, and full evidence should be reviewed.
- **Limitation:** The evaluated retrieval modes and results are conditional on the observed Elasticsearch 9.2.0 setup and active ELSER endpoint/licensing at test time.
- **Limitation:** The executed test split should remain held out. Avoid parameter tuning or repeated hypothesis-driven changes using test scores.
- **Limitation:** No causal inference from nine dry-run comparisons or 32 answerable queries; no significance tests or confidence intervals were computed.

## Evidence statements for report chapters

- **F-B2-01:** The 36-item frozen evaluation set contained 32 answerable and four unanswerable questions; SHA-256 recorded above.
- **F-B2-02:** Gold spans were found in the expected indexed documents for all 32 answerable items; three flagged items were confirmed against surrounding indexed context.
- **F-B2-03:** Main run evaluated 36 questions across BM25, ELSER and hybrid RRF, with zero reported failures/fallbacks.
- **F-B2-04:** Overall hybrid MRR=0.399, nDCG@10=0.470, Recall@10=0.695; ELSER Precision@5=0.125.
- **F-B2-05:** Test-set ELSER MRR=0.200 and Recall@10=0.583, both highest among the three tested modes on that subset.
- **F-B2-06:** Diagnostic Q16 first relevant rank improved from BM25 rank 10 to ELSER rank 2, while Q01 was absent from all top-ten diagnostic result lists.

## Remaining Batch 2 closure items

- Review `b2_main_per_question.csv` / `b2_main_top10.json` for three representative examples, and check unanswerable-question behavior and metric definitions.
- Record latency p50/p95 from available evidence if valid; otherwise mark it as deferred.
- Capture reproducibility screenshots where possible; do not fabricate them.
- Update `docs/PROGRESS.md`; stage and commit only Batch 2-specific files after reviewing `git status` and the diff.
- GitHub push was previously blocked by `403` because the active credential belonged to another GitHub account. Commit locally if still blocked, and report remote state accurately.
