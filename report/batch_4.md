# IntelliSearch NEO — Batch 4: Warm Retrieval Performance and Storage

**Evidence date:** 10 November 2026  
**Branch:** `v4-upgrade`  
**Status:** Warm-query latency, baseline index storage, and five Docker memory snapshots measured. Cold-start test deliberately omitted.  
**Platform:** Elasticsearch 9.2.0 in single-node Docker, Flask application container `intellisearch`, Windows PowerShell 5.1 on host.

## 1. Objective

Measure the observed latency of BM25 lexical, ELSER sparse semantic, and native reciprocal-rank-fusion (RRF) hybrid retrieval using the same source index and query workload. Record index storage and operational measurements for the internship report. These measurements describe the test environment, not guaranteed performance on deployment infrastructure.

## 2. Setup and controls

- **Benchmark index:** `intellisearch_corpus_v1`, read-only, with 7,102 searchable parent chunks from 18 public source documents.
- **Questions:** 36 frozen questions (`report/questions_frozen.csv`), including 32 answerable and 4 unanswerable. SHA-256 `7503f9ade1db1ea8fbb7ee2f0e2d8acf29320c73d043adea6a4becb98e77990f`.
- **Retrieval modes:** `bm25` maps to application `keyword`; `elser` maps to `semantic`; `hybrid` maps to the application's `hybrid` RRF search.
- **Top-k:** 10 displayed results per search.
- **Benchmark design:** three warm-up searches per mode, excluded from statistics, followed by five repetitions of all 36 questions for each mode. Thus 180 measured requests per mode, 540 overall.
- **Execution:** temporary script `/tmp/b4_perf.py` inside `intellisearch`, environment override `CORPUS_INDEX=intellisearch_corpus_v1`. Actual retrieval calls the application's `search()` method; it checks index selection and excludes fallback or failed requests from the clean-results claim.
- **Timing:** client time uses `time.perf_counter()` around the complete application `search()` call; Elasticsearch `took` is taken from the returned search result. For application semantic/hybrid modes, client timing may incorporate auxiliary search processing, not solely Elasticsearch core query execution.
- **Percentiles:** p50 is the median; p95 uses nearest-rank indexing of sorted measurements. No random query order or seed was used; each mode ran its 36 questions in frozen file order for five repetitions.

## 3. Method

1. Confirmed the baseline index count (7,102 searchable chunks), source index override, frozen question count, and frozen-file hash before measurements.
2. Executed three untimed-for-summary warm-up requests per mode.
3. Executed five passes of the same 36 questions for each retrieval mode using the real application search pathway, recording client and Elasticsearch search time plus status for every request in `report/results/b4_latency.csv`.
4. Collected five `docker stats --no-stream` snapshots: one before the workload, three labelled samples taken by a scheduled background job, and one after the workload. Reviewed the resulting `report/results/b4_memory.txt` output; sampling times were not captured, so the three labelled samples cannot be conclusively aligned to individual search modes.
5. Queried Elasticsearch primary store bytes through `/{index}/_stats/store` and parent chunk count through `/{index}/_count`; saved to `report/results/b4_index_size.txt`.
6. Omitted restart-dependent cold-start measurements to avoid interfering with the ongoing evaluation environment. No new ingestion was initiated during the benchmark.

## 4. Verified latency results

All reported time values are milliseconds. There were **540 successful queries and 0 failed/fallback queries**.

| Mode | Successful/attempted | Client p50 | Client p95 | Client min | Client max | ES `took` p50 | ES `took` p95 | ES `took` min | ES `took` max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BM25 | 180/180 | 4.6 | 6.3 | 3.0 | 8.9 | 2.0 | 3.0 | 0.0 | 3.0 |
| ELSER | 180/180 | 15.7 | 18.5 | 10.3 | 23.3 | 5.0 | 7.0 | 4.0 | 12.0 |
| Hybrid RRF | 180/180 | 19.2 | 23.4 | 12.6 | 28.5 | 8.0 | 12.0 | 5.0 | 17.0 |

**Median latency overhead versus BM25:** ELSER +11.1 ms (3.41× BM25); Hybrid RRF +14.6 ms (4.17× BM25). **p95 overhead versus BM25:** ELSER +12.2 ms (2.94×); Hybrid RRF +17.1 ms (3.71×). These ratios compare measured quantiles, not per-question paired differences.

### Console output excerpt

```text
Index: intellisearch_corpus_v1 Questions: 36 Repeats: 5
Questions SHA256: 7503f9ade1db1ea8fbb7ee2f0e2d8acf29320c73d043adea6a4becb98e77990f
Parent chunk count: 7102
MODE bm25 warmups=3
  completed repetition 5 / 5
MODE elser warmups=3
  completed repetition 5 / 5
MODE hybrid warmups=3
  completed repetition 5 / 5
RESULTS /tmp/b4_latency.csv
bm25 180/180 4.6/6.3/3.0/8.9 2.0/3.0/0.0/3.0
elser 180/180 15.7/18.5/10.3/23.3 5.0/7.0/4.0/12.0
hybrid 180/180 19.2/23.4/12.6/28.5 8.0/12.0/5.0/17.0
FAILED_OR_FALLBACK 0 TOTAL 540
```

## 5. Index storage and ingestion evidence

The **primary-shard storage** of the evaluated baseline index was **29,833,278 bytes**, approximately **28.45 MiB**, containing **7,102 parent chunks**. The measured ratio was **4,200.69 primary-store bytes per parent chunk**. This is an index-level storage ratio, not an amount of text stored per chunk; semantic indexing may add internal storage overhead. It excludes replica storage and does not account for all cluster-level disk usage.

The Batch 3 v2 dry-run reported 7,102 planned chunks and the v3 dry-run 6,641 planned chunks. One interrupted v3 ingestion log reported processing 754 chunks of a single TXT document in 350.3 seconds (approximately 2.2 chunks/second), followed by a KeyboardInterrupt during a later operation. That isolated observed rate is **not** a completed end-to-end ingestion benchmark and is not directly comparable with the current warm query latency measurements. The full v2 and v3 ingestion throughput comparison was unavailable at the evidence cutoff.

## 6. Docker memory observations and cold-start status

The following values were transcribed from five `docker stats --no-stream` snapshots saved to `report/results/b4_memory.txt`. These are **sampled container working-set-style usage figures as reported by Docker**, not application-only memory allocation, machine-wide RAM use, or a measured peak. The three labelled samples were collected by a background job initiated before the benchmark. Their exact timing relative to individual BM25, ELSER, and hybrid queries was not logged.

| Snapshot | `intellisearch` memory | `es01` memory | `es01` memory limit | `es01` memory % | `es01` CPU % |
|---|---:|---:|---:|---:|---:|
| Before | 95.11 MiB | 5.767 GiB | 6 GiB | 96.12% | 2.48% |
| Sample 1 | 95.38 MiB | 5.787 GiB | 6 GiB | 96.45% | 2.15% |
| Sample 2 | 95.38 MiB | 5.788 GiB | 6 GiB | 96.46% | 7.26% |
| Sample 3 | 95.36 MiB | 5.787 GiB | 6 GiB | 96.45% | 2.22% |
| After | 95.36 MiB | 5.787 GiB | 6 GiB | 96.45% | 5.78% |

**Observed:** Across these snapshots, the application container ranged from **95.11 to 95.38 MiB**. Elasticsearch ranged from **5.767 to 5.788 GiB**, or **96.12% to 96.46% of its configured 6 GiB container memory limit**. Its highest *sampled* CPU percentage was **7.26%**. These readings show that the Elasticsearch container was already operating near its configured memory limit during the sampling window. They do **not** establish an out-of-memory event, a true workload peak, a memory leak, or a causal relationship between memory occupancy and search latency. Docker-reported usage can include file cache and other accounted memory; the underlying Elasticsearch JVM heap and native ELSER model allocations were **not separated** in this test.

**Operational implication:** High container-level memory occupancy is a deployment consideration. Future capacity testing should measure JVM heap, native inference allocation, cache pressure, and sustained concurrent workload separately before setting production resource limits.

The optional cold-start test was **not performed** because it required restarting Elasticsearch. All Batch 4 latency results are **warm-query** measurements.

## 7. Observations and limitations

- **Observed:** All 540 retrieval requests completed in their requested modes against the baseline index with no recorded fallback or failure.
- **Observed:** BM25 produced the lowest observed median and p95 client time; hybrid RRF produced the highest among the three modes under this benchmark protocol.
- **Observed:** The baseline index primary-store size was 29,833,278 bytes for 7,102 parent chunks.
- **Observed:** Elasticsearch container memory remained at 96.12%–96.46% of its 6 GiB configured limit across five sampled snapshots; no out-of-memory failure was observed.
- **Hypothesis:** Added semantic inference/search and RRF work contribute to hybrid overhead, but this benchmark does not isolate each operation causally.
- **Limitations:** One machine and one single-node Elasticsearch deployment, sequential mode execution rather than randomized interleaving, cached/warm searches, 36 questions repeated five times, limited concurrency, no confidence intervals, no cold-start timings, non-time-stamped and non-continuous memory snapshots, no separate JVM/native/cache memory attribution. Re-evaluate latency on the intended deployment hardware before capacity planning.

## 8. Key takeaways

1. **F-B4-01–03:** Each search mode completed 180/180 measured queries with zero fallback or failure.
2. **F-B4-04–06:** Client p50 values were BM25 4.6 ms, ELSER 15.7 ms, and hybrid 19.2 ms; respective p95 values were 6.3, 18.5 and 23.4 ms.
3. **F-B4-07:** Relative to BM25, hybrid median client time increased by 14.6 ms (4.17×).
4. **F-B4-08:** Baseline primary-shard storage was 29,833,278 bytes across 7,102 parent chunks.
5. **F-B4-09–11:** Five Docker snapshots showed Elasticsearch using 5.767–5.788 GiB (96.12%–96.46% of its 6 GiB memory limit) and the Flask application using 95.11–95.38 MiB; cold-start was not measured.

## 9. Screenshots and evidence

| Suggested screenshot | Caption | Evidence |
|---|---|---|
| `report/screenshots/b4_01_latency_results.png` | Warm retrieval latency results | Summary table showing per-mode quantiles and 540 clean queries |
| `report/screenshots/b4_02_docker_stats.png` | Docker memory during performance test | Raw `docker stats` sample with resource usage, after redacting identifiers |
| `report/screenshots/b4_03_indices_size.png` | Baseline index primary storage | `_stats/store` size and parent count |

Screenshot files were not supplied at the evidence cutoff; filenames above are suggested only, not claims that screenshots exist.

## 10. FACTS

| ID | Fact | Value | Source |
|---|---|---|---|
| F-B4-01 | Questions, repeats, warmups | 36 × 5; 3 warm-ups per mode | `report/results/b4_latency.csv`; benchmark console output in §4 |
| F-B4-02 | Successful measured searches | 540/540; 180/180 each mode | `report/results/b4_latency.csv`; console §4 |
| F-B4-03 | Failed or fallback | 0 | `report/results/b4_latency.csv`; console §4 |
| F-B4-04 | Client p50 BM25 / ELSER / hybrid | 4.6 / 15.7 / 19.2 ms | `report/results/b4_latency.csv`; console §4 |
| F-B4-05 | Client p95 BM25 / ELSER / hybrid | 6.3 / 18.5 / 23.4 ms | `report/results/b4_latency.csv`; console §4 |
| F-B4-06 | ES `took` p50 BM25 / ELSER / hybrid | 2 / 5 / 8 ms | `report/results/b4_latency.csv`; console §4 |
| F-B4-07 | Hybrid versus BM25 client p50 | +14.6 ms, 4.17× | Calculated from F-B4-04 |
| F-B4-08 | Baseline index store / parent chunks / ratio | 29,833,278 bytes / 7,102 / 4,200.69 bytes per chunk | `report/results/b4_index_size.txt` |
| F-B4-09 | Elasticsearch memory observed, five snapshots | 5.767–5.788 GiB; 96.12%–96.46% of 6 GiB container limit | `report/results/b4_memory.txt`; §6 |
| F-B4-11 | Flask application memory observed, five snapshots | 95.11–95.38 MiB | `report/results/b4_memory.txt`; §6 |
| F-B4-12 | Elasticsearch highest sampled CPU utilization | 7.26% (sample 2); not a measured peak | `report/results/b4_memory.txt`; §6 |
| F-B4-13 | Cold-start experiment | Not performed | §6 |
| F-B4-10 | Frozen question file SHA-256 | `7503f9ade1db1ea8fbb7ee2f0e2d8acf29320c73d043adea6a4becb98e77990f` | Benchmark console §4 |

## 11. Feeds report chapters

Performance results; performance and retrieval-quality trade-offs; deployment and operational considerations; limitations; future evaluation and capacity planning. No new licence-tier or purchase recommendation is made on latency data alone.
