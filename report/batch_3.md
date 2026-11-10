# IntelliSearch NEO: Batch 3 — Chunking v2 versus v3

**Evidence cutoff:** 10 November 2026  
**Repository branch:** `v4-upgrade`  
**Study:** Exploratory internship evaluation of Elasticsearch-based lexical, semantic, and hybrid retrieval using public documents.  
**Status:** **Preliminary chunking comparison completed; full v3 semantic ingestion and controlled retrieval comparison not verified at cutoff.**

## 1. Objective and scope

Assess whether the improved PDF chunker changes corpus segmentation and, where evidence is available, retrieval quality. The comparison uses the same 18 public source documents and the frozen 36-question evaluation set from Batch 2. Chunker v2 is implemented in `chunking.py`; chunker v3 is implemented in `chunking3.py`. The initial report guide described a v1-versus-v2 comparison; repository inspection showed that **v2-versus-v3** is the actual available comparison, so these implementation labels are used throughout.

This report distinguishes *verified indexed data*, *local extraction dry-run outputs*, and *retrieval evaluation*. No v3 retrieval metric is estimated or imputed.

## 2. Experimental setup and controls

- **Elasticsearch:** 9.2.0, single-node Docker instance (`es01`); app container `intellisearch`.
- **Baseline index:** `intellisearch_corpus_v1`, with **7,102 searchable parent chunks** across 18 source documents, measured in Batch 1. The v2 dry-run yielded 7,102 chunks with matching per-file counts, consistent with a v2 baseline; the matching counts do not independently prove the original build history.
- **Candidate index:** `intellisearch_corpus_v3_eval`, a separate index; baseline index was not overwritten.
- **Configuration:** both local dry runs used the installed ingestion settings, with `--chunker 2` or `--chunker 3` and `--dry-run`. The command `ingest.py --path corpus/files --chunker 3 --index intellisearch_corpus_v3_eval` was used for real v3 ingestion.
- **Frozen questions:** `report/questions_frozen.csv`, 36 questions: 32 answerable and 4 unanswerable; SHA-256 `7503F9ADE1DB1EA8FBB7EE2F0E2D8ACF29320C73D043ADEA6A4BECB98E77990F`.
- **Retrieval methods:** BM25 (`keyword`), ELSER (`semantic`), and default hybrid RRF (`hybrid`) through the application's `search()` function, top 10.
- **Important index control:** the evaluator's `--index` selects the index for loading gold chunks; the application search index is selected separately through `CORPUS_INDEX`. A v3 run must set **both** `CORPUS_INDEX=intellisearch_corpus_v3_eval` and `--index intellisearch_corpus_v3_eval`.

## 3. Implementation differences

**Chunker v2:** `chunking.py` produces sentence-aware chunks up to the configured character target with overlap; PDFs are processed page-by-page. It retains repeated page furniture unless separately removed by extraction.

**Chunker v3:** `chunking3.py` cleans recurring PDF headers, footers, and page numbers; joins PDF pages into a continuous text stream; avoids ending a passage on a heading; and favors sentence starts near overlap positions. The same `chunk_lines()` route is used for TXT files under both `--chunker` options in the observed ingestion implementation, so TXT segmentation is unchanged in this comparison. V3 is not a single-variable experiment: several PDF segmentation choices change together.

## 4. Measured chunk counts

Both dry runs reported **18 documents, zero extraction failures**. V2 produced 7,102 proposed chunks; v3 produced 6,641 proposed chunks, a **net reduction of 461 chunks (6.49%)**. Means per document were 394.56 (v2) and 368.94 (v3), respectively. The v3 figure is a **dry-run result**, not an assertion of completed indexing.

| Source document | v2 chunks | v3 dry-run chunks | v3 − v2 | Reduction (%) |
|---|---:|---:|---:|---:|
| gutenberg-alice.txt | 136 | 136 | 0 | 0.00 |
| gutenberg-art-of-war.txt | 279 | 279 | 0 | 0.00 |
| gutenberg-dracula.txt | 754 | 754 | 0 | 0.00 |
| gutenberg-frankenstein.txt | 381 | 381 | 0 | 0.00 |
| gutenberg-pride-and-prejudice.txt | 664 | 664 | 0 | 0.00 |
| gutenberg-sherlock-holmes.txt | 503 | 503 | 0 | 0.00 |
| india-dpdp-2023.pdf | 62 | 64 | +2 | -3.23 |
| india-it-act-2000.pdf | 129 | 124 | -5 | 3.88 |
| india-rti-2005.pdf | 206 | 205 | -1 | 0.49 |
| nasa-se-handbook.pdf | 827 | 761 | -66 | 7.98 |
| nist-800-171r3.pdf | 261 | 234 | -27 | 10.34 |
| nist-800-53r5.pdf | 1602 | 1349 | -253 | 15.79 |
| nist-800-61r3.pdf | 108 | 97 | -11 | 10.19 |
| nist-ai-rmf-1.pdf | 111 | 103 | -8 | 7.21 |
| nist-csf-2.pdf | 67 | 62 | -5 | 7.46 |
| rfc-8446.txt | 326 | 326 | 0 | 0.00 |
| rfc-9110.pdf | 468 | 418 | -50 | 10.68 |
| rfc-9293.pdf | 218 | 181 | -37 | 16.97 |
| **Total** | **7,102** | **6,641** | **-461** | **6.49** |

The largest absolute reduction was for **NIST SP 800-53 Rev. 5** (253 fewer). The largest proportional PDF reduction was **RFC 9293** (16.97%). The DPDP Act produced two *additional* chunks under v3. Thus v3 does not uniformly reduce chunks for every document.

## 5. Baseline chunk-quality indicators

A read-only `scripts/chunk_report.py intellisearch_corpus_v1` inspection reported the following for selected v2-indexed documents. They describe surface properties of chunks and must not be treated as verified semantic boundary errors.

| Document | v2 chunks | Chunks beginning with lowercase letter | Chunks without listed terminal punctuation |
|---|---:|---:|---:|
| NASA Systems Engineering Handbook | 827 | 407 | 199 |
| NIST SP 800-53 Rev. 5 | 1,602 | 812 | 294 |
| RFC 9110 | 468 | 235 | 199 |

These findings motivate inspection of page continuity, headings, and sentence boundaries under v3. Comparable **v3 indexed chunk-length distributions (mean/median/p95), boundary counts, and side-by-side snippets were not captured before the cutoff**. Do not report them as completed.

## 6. Retrieval baseline from Batch 2 (v2 index only)

The 36-question set (32 answerable, 4 unanswerable) was evaluated on `intellisearch_corpus_v1` with 3 modes, with **108 reported searches and no reported failed/fallback requests**. Strict answer-span metrics for the 32 answerable questions are:

| Metric | BM25 | ELSER | Hybrid RRF |
|---|---:|---:|---:|
| Precision@5 | 0.119 | **0.125** | 0.119 |
| Precision@10 | 0.078 | 0.081 | **0.084** |
| Recall@10 | 0.625 | 0.688 | **0.695** |
| MRR | 0.380 | 0.344 | **0.399** |
| nDCG@10 | 0.435 | 0.429 | **0.470** |

On the 12-answerable-question held-out test subset, ELSER led on MRR (0.200) and Recall@10 (0.583), while hybrid scored 0.158 and 0.500 and BM25 scored 0.117 and 0.333, respectively. These **baseline numbers must not be represented as v3 outcomes**.

## 7. Partial v3 ingestion and evaluation status

The separate v3 index was created and semantic indexing was observed progressing. The last user-supplied polling logs showed approximately **3,971** chunks in one monitor at 12:51:45 and **4,051** in a separate monitor at 12:51:58. The user then closed terminal windows. These are incomplete snapshots from different polling times, **not a final indexed total**, and the completion or survival of the ingestion process after terminal closure was not established.

During an earlier duplicate-worker incident, two ingestion processes were observed; the duplicate was subsequently stopped and one original process remained. A separate unbuffered ingestion run processed `gutenberg-dracula.txt` (754/754 chunks in 350.3 seconds, approximately 2.2 chunks/s) but ended with a `KeyboardInterrupt` during a later bulk request. This measured document throughput is **not an end-to-end ingestion rate for the complete corpus**. The ingestion CLI may resume by skipping complete documents and reindexing interrupted documents, but a final successful summary was not supplied.

A premature v3 evaluation correctly aborted with `COVERAGE GATE FAILED: india-dpdp-2023.pdf has no chunks`; there is no valid completed v3 evaluation to compare with the baseline. The v3 retriever's index selection was separately verified by printing `CORPUS_INDEX` and `SOURCES['corpus'][0]` under the environment override, both of which selected `intellisearch_corpus_v3_eval`.

**Not completed / not claimed:** full 18-document v3 indexing validation; v3 Precision/Recall/MRR/nDCG; strict gold-span boundary comparison; paired v2/v3 question-level changes; representative v3 passage samples; complete ingestion elapsed time and rate; definitive index storage comparison.

## 8. Interpretation and limitations

**Observed:** For these 18 source files with the same local settings, v3's extraction/chunking dry run reduced the total planned parent chunk count by 6.49%. This result is driven by PDF handling, not a change to text-file chunking. Baseline v2 retrieval quality was measured separately in Batch 2.

**Hypotheses, not demonstrated outcomes:** Cleaner boundaries and the removal of repetitive page furniture may improve passage coherence, reduce redundant retrieval hits, or affect semantic indexing workload. They could also remove context or alter ranking. These effects cannot be determined from chunk counts alone.

The corpus is limited to 18 public documents. The query set is small and manually designed. V3 changes multiple PDF processing features at once, so any future observed retrieval change cannot be uniquely attributed to a single feature. Indexing was interrupted/incomplete at evidence cutoff; no statistical claim about relevance improvement is warranted.

## 9. Conclusions and follow-up validation

Chunker v3 **demonstrated lower planned chunk counts** for this corpus, notably on larger technical PDFs, while keeping the same 18 source files in the dry-run processing scope. **No measured improvement in retrieval accuracy has yet been established.** A controlled v2–v3 retrieval comparison remains pending rather than being replaced with an estimated score.

When resources permit: verify an uninterrupted ingestion `SUMMARY` with zero failures; verify exactly 6,641 parent chunks and the same 18 filenames; collect comparable chunk statistics and gold-span boundary counts; evaluate v3 once with both `CORPUS_INDEX` and `--index` set to `intellisearch_corpus_v3_eval`; compare per-question and aggregate metrics against the already-frozen Batch 2 baseline. Do not modify the frozen questions or tune the test split post hoc.

## 10. Evidence and reproducibility

Local evidence paths supplied or generated during this batch:

- `report/results/b3_chunk_count_comparison.csv` — PDF-by-PDF counts from the two local dry-run outputs.
- `report/results/b3_chunk_stats_v2.txt` — read-only baseline chunk inspection.
- `report/results/b2_main_summary.csv`, `b2_main_per_question.csv`, `b2_main_top10.json`, `b2_main_manifest.json` — measured v2 retrieval baseline.
- `report/questions_frozen.csv` — unchanged question set, SHA-256 above.
- Source modules: `chunking.py`, `chunking3.py`, `ingest.py`, `search.py`, `report/eval.py`.

**Reproduction commands (not executed during report preparation):**

```powershell
# Extraction counts only, without indexing
docker exec intellisearch python ingest.py --path corpus/files --chunker 2 --index intellisearch_corpus_v1 --dry-run
docker exec intellisearch python ingest.py --path corpus/files --chunker 3 --index intellisearch_corpus_v3_eval --dry-run

# Only after confirmed complete v3 indexing: full evaluation
docker exec -e CORPUS_INDEX=intellisearch_corpus_v3_eval intellisearch python /tmp/report_eval.py --questions /tmp/questions_frozen.csv --index intellisearch_corpus_v3_eval --modes bm25,elser,hybrid --k 10 --split all --out /tmp/b3_chunk_v3
```

## 11. Evidence facts for final report assembly

- **F-B3-01:** 18 identical source documents available for both local dry-run chunker modes.
- **F-B3-02:** v2 output 7,102 chunks; v3 dry-run 6,641; absolute reduction 461, relative reduction 6.49%.
- **F-B3-03:** 11 PDFs have different chunk counts; 7 TXT files retain identical counts.
- **F-B3-04:** NIST 800-53r5: 1,602 → 1,349 (-253; 15.79%); RFC 9293: 218 → 181 (-37; 16.97%).
- **F-B3-05:** India DPDP Act: 62 → 64 (+2); optimization not uniformly reductive.
- **F-B3-06:** Baseline (v2) hybrid Recall@10 0.695, MRR 0.399, nDCG@10 0.470 on 32 answerable questions; v3 retrieval results unavailable.
- **F-B3-07:** Final successful v3 semantic ingestion and matched v2/v3 evaluation were not verified at cutoff.
