# IntelliSearch NEO — Batch 5: Enterprise Capability Assessment, Failure Analysis and Recommendations

**Evidence date:** 10 November 2026  
**Repository branch:** `v4-upgrade`  
**Baseline revision:** `5e05779` (Batch 4 report committed)  
**Status:** Evidence-based desktop assessment completed; no new Elasticsearch queries or tests conducted in this batch.  
**Platform:** Flask + Elasticsearch 9.2.0, single-node Docker deployment; 30-day trial of paid Elastic capabilities.

## 1. Objective

Assess the demonstrated value and limitations of Elasticsearch's BM25 lexical search, Elastic Learned Sparse EncodeR (ELSER), inference endpoint and `semantic_text` integration, and native reciprocal-rank-fusion (RRF) hybrid retrieval. Interpret measurable retrieval quality against search latency, operational capacity, and licensing considerations. This is technical evidence for an organizational decision, **not a procurement recommendation**.

## 2. Evidence and methodology

- Source index: `intellisearch_corpus_v1` containing **7,102 searchable parent chunks from 18 public documents**, without modifying any existing corpus indexes for this assessment.
- Frozen question set: `report/questions_frozen.csv`, **36 questions** (**32 answerable**, four intentionally unanswerable), with **22 dev / 14 test**, corresponding to 20/12 answerable. SHA-256: `7503F9ADE1DB1EA8FBB7EE2F0E2D8ACF29320C73D043ADEA6A4BECB98E77990F`.
- Results: `report/results/b2_main_per_question.csv`, `b2_main_summary.csv`, and `b2_main_top10.json`, from existing application `search()` calls using BM25, ELSER and hybrid RRF at top-10.
- Performance: `report/results/b4_latency.csv`, `b4_memory.txt`, `b4_index_size.txt`, and `report/batch_4.md`; the same baseline index was used.
- Chunking: `report/batch_3.md` and `report/results/b3_chunk_count_comparison.csv`. Chunker v3 was evaluated structurally by dry run; a complete controlled v3 retrieval-quality comparison was **not** available at cutoff.
- Relevance: reported rank means the first **gold-span-matching chunk** in the expected document. A retrieved document or related paragraph that lacks the frozen gold span is **not** counted as a strict success. Qualitative explanations below are hypotheses, not proven root causes. Retrieved snippets were truncated to 200 characters in `b2_main_top10.json`; the display excerpts here are illustrative portions of that stored evidence.

## 3. Retrieval effectiveness: measured findings

| Retrieval method | Answerable n | Recall@10 | MRR | nDCG@10 |
|---|---:|---:|---:|---:|
| BM25 | 32 | 0.625 | 0.380 | 0.435 |
| ELSER | 32 | 0.688 | 0.344 | 0.429 |
| Hybrid RRF | 32 | **0.695** | **0.399** | **0.470** |

**Observed:** Hybrid led on the aggregate MRR and nDCG@10 in this set and had the highest displayed Recall@10. The differences are exploratory: there are only 32 answerable questions, and the original relevance standard is strict chunk-level matching rather than graded human judgments. The hybrid's Recall@10 advantage over ELSER is **0.007** (rounded source metrics), not a substantial proven advantage.

### Concrete retrieval contrasts

| Question | Type | BM25 first gold rank | ELSER first gold rank | Hybrid first gold rank | Observation |
|---|---|---:|---:|---:|---|
| Q06, `HelloRetryRequest` | keyword, test | Miss | 3 | 7 | ELSER and hybrid found the specified RFC 8446 gold span; lexical top-10 did not. |
| Q28, `characterisitcs of trustworty AI` | typo, dev | Miss | 5 | 3 | Semantic/hybrid succeeded despite spelling errors; BM25 missed strict gold span. |
| Q10, `least privilege` | keyword, test | 10 | Miss | Miss | BM25 found the precise NIST 800-53 gold span while ELSER and hybrid returned related passages. |
| Q26, `Concent Manger single point of contact` | typo, dev | 1 | Miss | 8 | BM25 ranked the strict match first despite misspellings; semantic retrieval did not find it within 10. |
| Q15, PUT-like resource replacement question | conceptual, dev | 6 | 1 | 1 | ELSER and hybrid ranked the exact gold passage first, an example of query–source vocabulary mismatch. |

**Interpretation:** No single retrieval mode dominates every question. The existence of typo wins and losses in both directions precludes claiming ELSER is a universally reliable spell-corrector. Search and relevance behavior is highly question-dependent.

## 4. Failure analysis: five cases from saved top-10 evidence

### Q13: National-security exception under the Indian RTI Act (conceptual, dev)

- **Question:** When can a government office refuse to share information because of national security?
- **Expected document:** `india-rti-2005.pdf`; **gold span:** `prejudicially affect the sovereignty and integrity of India`.
- **Strict first-gold ranks:** BM25 miss / ELSER miss / hybrid miss.
- **Top three BM25 results:** all NIST SP 800-53 sections, with excerpts beginning `NIST SP 800-53, REV. 5 ... SECURITY AND PRIVACY CONTROLS ...`.
- **Top three ELSER results:** NIST 800-171 on information resources; NIST 800-53 ODNI insider-threat reference; NIST 800-53 integrity terminology.
- **Top three hybrid results:** NIST 800-53 national insider-threat reference, national cyberspace strategy, and control agreement description.
- **Hypothesis:** The phrase “national security” biased retrieval toward cybersecurity documents instead of the intended RTI statutory exception. The specific legal clause was not surfaced within the strict top-10.

### Q14: TLS confidentiality and message integrity (conceptual, test)

- **Question:** How does the protocol stop others from listening in or altering messages?
- **Expected document:** `rfc-8446.txt`; **gold span:** `prevent eavesdropping, tampering, and message forgery`.
- **Strict first-gold ranks:** BM25 miss / ELSER miss / hybrid miss.
- **Top three BM25 results:** RFC 8446 traffic-secret/forward-secrecy paragraph; RFC 9110 protocol-version semantics; RFC 9110 intermediary description.
- **Top three ELSER results:** RFC 9110 partial-message handling; RFC 9110 message semantics; NIST 800-53 pre/post-transmission confidentiality and integrity control.
- **Top three hybrid results:** three RFC 9110 passages about conformance, protocol versions, and message semantics.
- **Hypothesis:** Generic question vocabulary (“the protocol”, “messages”) may be insufficiently discriminative across TLS, HTTP and security-control documents. BM25 did retrieve a relevant TLS paragraph, but not the strict gold passage.

### Q18: Frankenstein's reaction to the creature (conceptual, test)

- **Question:** How did Victor react when the creature he built came alive?
- **Expected document:** `gutenberg-frankenstein.txt`; **gold span:** `breathless horror and disgust filled my heart`.
- **Strict first-gold ranks:** BM25 miss / ELSER miss / hybrid miss.
- **Top three BM25 results:** a Victor/Elizabeth conversation from Frankenstein; a Sherlock Holmes excerpt; a Frankenstein account of writings and poems.
- **Top three ELSER results:** three Frankenstein passages, including a William-related conversation, Victor's strange laughter, and a later apology.
- **Top three hybrid results:** Frankenstein's Victor/Elizabeth conversation, Victor's strange laughter, and William-related conversation.
- **Hypothesis:** Several passages refer to Victor's emotions without describing the creation scene, producing plausible topic matches but missing the exact event and gold sentence. Document-level apparent relevance masks a strict passage failure.

### Q27: Misspelled electronic-record authentication (typo, test)

- **Question:** `digitel signiture authentcation of electronic record`.
- **Expected document:** `india-it-act-2000.pdf`; **gold span:** `authentication of any electronic record by a subscriber by means of an electronic method or procedure`.
- **Strict first-gold ranks:** BM25 miss / ELSER 10 / hybrid 9.
- **Top three BM25 results:** same Act's asymmetric cryptosystem and hash-function paragraph; subscriber public key; electronic-record originator provision.
- **Top three ELSER results:** electronic-record receipt-location clause; asymmetric cryptosystem paragraph; electronic-signature authentication technique.
- **Top three hybrid results:** asymmetric cryptosystem paragraph; subscriber public-key paragraph; receipt-location clause.
- **Hypothesis:** Query misspellings and many near-neighbor legal definitions drew high ranks to related clauses while the frozen gold sentence was retrieved only at ranks 9–10 by semantic/hybrid methods.

### Q30: Misspelled RTI written request (typo, test)

- **Question:** `how to make a requst for informashun in writting`.
- **Expected document:** `india-rti-2005.pdf`; **gold span:** `shall make a request in writing or through electronic means`.
- **Strict first-gold ranks:** BM25 miss / ELSER miss / hybrid miss.
- **Top three BM25 results:** Pride and Prejudice social encounter; NASA contractor/technical-team planning; another Pride and Prejudice conversation.
- **Top three ELSER results:** NIST 800-53 heading; NIST CSF 2.0 online resources; NIST 800-53 no-writable-storage requirement.
- **Top three hybrid results:** NIST 800-53 heading; Pride and Prejudice passage; NIST CSF online resources.
- **Hypothesis:** Multiple severe spelling errors together with generic terms reduced lexical overlap and semantic specificity. No evaluated mode recovered the strict gold passage in top-10; a separate fuzzy BM25 mode exists in the app but was not benchmarked in Batch 2.

## 5. Elastic capabilities actually assessed

| Capability | Use in prototype | Observed evidence | Self-managed licensing: current published information | Operational caution |
|---|---|---|---|---|
| BM25 lexical retrieval | `search.py` keyword mode over extracted text | Recall@10 0.625; p50 client 4.6 ms | Included in Elastic's free-and-open search offering | Weak on some paraphrases and typos, but stronger on some exact legal passages. |
| ELSER sparse semantic model on local ML node | `.elser-2-elasticsearch` for semantic ranking | Recall@10 0.688; p50 15.7 ms; both gains and losses against BM25 | Elastic's **self-managed Platinum** plan lists ELSER on ML nodes; Enterprise includes Platinum | Model memory, inference throughput and licence eligibility should be verified for the target deployment. |
| Inference endpoint | Model-backed query and ingestion inference | ELSER deployment observed started; semantic queries succeeded | Appropriate inference/model entitlement required; tied to model and deployment path, not universally a single tier | Do not assume all cloud/external inference paths share the same entitlement or cost. |
| `semantic_text` mapping | `content_semantic` field automatically invokes sparse embedding pipeline | Mapping and live semantic queries verified in Batches 1–2 | Elastic says the field mapping can be added without a special licence, but **index/reindex operations using an inference endpoint can fail without the appropriate licence** | Distinguish mapping support from paid model-backed inference. |
| Native RRF hybrid retriever | Fuse BM25 and ELSER ranked results | Recall@10 0.695, MRR 0.399, nDCG@10 0.470; p50 client 19.2 ms | Elastic's pricing FAQ groups the full ESRE suite, including hybrid RRF, with **Platinum or Enterprise**. Precise feature-specific entitlement for this version should be reconfirmed before procurement. | Hybrid increases latency and does not eliminate all failures. |

**Licensing source notes (accessed 10 November 2026):**

1. Official self-managed plans: https://www.elastic.co/pricing/self-managed (Platinum includes ELSER on Elastic ML nodes; Enterprise includes Platinum).
2. Official pricing FAQ: https://www.elastic.co/pricing/faq (full ESRE suite described under Platinum or Enterprise).
3. Official `semantic_text` documentation: https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/semantic-text (mapping permitted regardless of licence; inference calls require appropriate entitlement).
4. Official Elastic feature/subscription matrix: https://www.elastic.co/subscriptions (verify the applicable contractual version and feature tiers with vendor).

These are **published product descriptions**, not a substitute for checking the exact licence, support terms, air-gapped deployment rights or future pricing with Elastic. No claim is made that every hybrid capability is *Enterprise-only*.

## 6. Performance and operational considerations

| Metric | BM25 | ELSER | Hybrid RRF |
|---|---:|---:|---:|
| Successful warm searches | 180/180 | 180/180 | 180/180 |
| Client p50 (ms) | 4.6 | 15.7 | 19.2 |
| Client p95 (ms) | 6.3 | 18.5 | 23.4 |
| Elasticsearch `took` p50 (ms) | 2 | 5 | 8 |
| Elasticsearch `took` p95 (ms) | 3 | 7 | 12 |

- Across all **540** measured warm searches, **zero fallback or failure** was recorded.
- Hybrid p50 was **14.6 ms higher (4.17×)** than BM25, on the tested system and workload.
- Elasticsearch primary store used **29,833,278 bytes**, or **4,200.69 bytes per searchable parent chunk** across 7,102 chunks. This includes underlying indexed storage, not just extracted text.
- Five Docker stats snapshots showed Elasticsearch memory ranging **5.767–5.788 GiB**, against a **6 GiB** container limit (**96.12%–96.46%**); the Flask container ranged **95.11–95.38 MiB**. This does **not** by itself establish a leak or an imminent failure.
- A full cold-start/restart experiment was deliberately **not performed**. The project used a single-node environment. Therefore availability, sustained concurrent throughput, tail latency under production load and sizing on a target environment remain unmeasured.
- Chunker v2's 18-document dry run produced 7,102 chunks; v3's dry run produced **6,641**, a **6.49% decrease**. This is a structural segmentation result, not demonstrated accuracy improvement or measured storage savings.

## 7. Limitations and risks

1. Only **32 answerable gold-span questions**, including **12 answerable test questions**; the dev/test split is too small for broad generalization or a robust significance claim.
2. All 18 corpus documents are public materials, rather than real deployment data. No assessment of sensitive or restricted data is implied.
3. Gold spans were designed by one evaluator; binary exact-span matching can count meaningfully related results as strict misses. One gold sentence is not a graded human relevance assessment.
4. The corpus contains duplicate statutory material and PDF page headers/footers; repeated content may influence rankings. The effect was not isolated experimentally.
5. The project ran on one machine in Docker under a time-limited paid-feature trial. Timings and memory usage are environment-dependent; security accreditation and target deployment compatibility were not assessed.
6. Only the existing baseline corpus was used for retrieval and latency tests. The v3 chunker dry run is not comparable to a full semantic ingestion/retrieval evaluation.
7. Unanswerable questions were included in the frozen 36-question set but the headline retrieval-quality averages are for 32 answerable cases; this report does not claim measured answer abstention accuracy.
8. Licensing details may change; use the current official feature matrix, vendor proposal and exact contract for any purchasing decision. Reuse or redistribution rights of some documents, including Indian legislation sources, were not fully verified.

## 8. Evidence-linked recommendations (not procurement conclusions)

- **R1 (F-B5-01, F-B5-02):** Test hybrid RRF as a candidate default where higher relevance warrants a measured latency increase. Include BM25-only fallback because BM25 won individual questions (Q10, Q26).
- **R2 (F-B5-03):** Add an explicit fuzzy-BM25 route or suggestion mechanism for repeated-misspelled queries, then evaluate on a larger frozen typo set; the existing application has a fuzzy mode but it was not part of this controlled comparison.
- **R3 (F-B5-04):** Build a larger independently annotated, graded-relevance test suite; preserve exact-span metrics as one strict secondary view. Review problem cases manually.
- **R4 (F-B5-05):** Inspect retrieval query disambiguation for ambiguous legal/security questions (Q13, Q14) and passage/window selection for near-miss cases (Q18, Q27).
- **R5 (F-B5-06):** Repeat throughput and memory measurements, cold-start and concurrency tests on the actual target hardware before defining capacity or service objectives.
- **R6 (F-B5-07):** Finish a controlled v2-v3 retrieval comparison before asserting the effect of chunker v3 on relevance or storage.
- **R7 (F-B5-08):** Obtain written confirmation of subscription/licence entitlement, deployment model, support, offline usage and total cost before any procurement decision.

## 9. Key findings for the final abstract and conclusion

1. A reproducible 18-document public corpus contained **7,102 searchable parent chunks** (F-B5-01).
2. The frozen set comprised **36 questions**, **32 answerable**, **4 unanswerable**, with 12 answerable test questions (F-B5-01).
3. On the answerable set, hybrid RRF achieved **Recall@10 0.695, MRR 0.399, nDCG@10 0.470** (F-B5-02).
4. BM25 and ELSER each won individual questions; no method achieved universal strict success (F-B5-03).
5. All **540** warm benchmark requests succeeded without fallback; median client latencies were **4.6/15.7/19.2 ms** for BM25/ELSER/hybrid (F-B5-04).
6. Peak sampled Elasticsearch memory was **5.788 GiB of 6 GiB**, and this alone does not diagnose a leak (F-B5-05).
7. Chunker v3 planned **461 fewer chunks** (6.49%) but full retrieval effects remained unverified (F-B5-06).
8. Self-managed ELSER on Elastic ML nodes was listed within the Platinum offering, which highlights the need to distinguish feature-specific eligibility from an assumption that all tested functions are Enterprise-exclusive (F-B5-08).

## 10. Screenshots

No new screenshot captured in this read-only assessment batch. Previously captured mapping, inference, latency and index views, where available, are referenced by their parent batch files; absence of a screenshot is not evidence that a test occurred.

## 11. FACTS registry

| ID | Evidence | Verified value | Source |
|---|---|---|---|
| F-B5-01 | Corpus/questions | 18 public documents; 7,102 parent chunks; 36 questions, 32 answerable, four unanswerable; 12 answerable test | `report/batch_1.md`; `report/questions_frozen.csv`; `report/batch_2.md` |
| F-B5-02 | Strict answerable retrieval, n=32 | BM25 Recall@10=.625 MRR=.380 nDCG@10=.435; ELSER .688/.344/.429; hybrid .695/.399/.470 | `report/results/b2_main_summary.csv` |
| F-B5-03 | Example first gold ranks | Q06: -/3/7; Q10: 10/-/-; Q13: -/-/-; Q14: -/-/-; Q18: -/-/-; Q26: 1/-/8; Q27: -/10/9; Q28: -/5/3; Q30: -/-/- | `report/results/b2_main_per_question.csv`; `report/results/b2_main_top10.json`; `report/questions_frozen.csv` |
| F-B5-04 | Warm client p50/p95 (ms), 180 each | BM25 4.6/6.3; ELSER 15.7/18.5; hybrid 19.2/23.4; 540/540 successes | `report/results/b4_latency.csv`; `report/batch_4.md` |
| F-B5-05 | Memory | ES 5.767–5.788 GiB, 6 GiB limit; app 95.11–95.38 MiB; five snapshots | `report/results/b4_memory.txt` |
| F-B5-06 | Chunking v2 vs v3 dry run | 7,102 vs 6,641; 461 fewer; 6.49%; v3 retrieval effect unverified | `report/batch_3.md`; `report/results/b3_chunk_count_comparison.csv` |
| F-B5-07 | Baseline index size | 29,833,278 primary-store bytes; 4,200.69 bytes per parent chunk | `report/results/b4_index_size.txt` |
| F-B5-08 | Published licensing guidance | Self-managed Platinum includes ELSER on Elastic ML nodes; `semantic_text` mapping is not equivalent to unrestricted model-backed inference; vendor contract confirmation needed | https://www.elastic.co/pricing/self-managed ; https://www.elastic.co/pricing/faq ; https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/semantic-text |
| F-B5-09 | Study scope | Single node, trial licence, frozen gold-span method, no cold-start or production concurrency test | `report/batch_1.md` through `report/batch_4.md` |

## 12. Feeds final internship report chapters

Enterprise capability assessment; failure and error analysis; retrieval quality–latency trade-offs; operational observations; limitations; evidence-based recommendations; conclusion and proposed future work.

**Handover:** Batch 1–5 Markdown reports collectively contain the measured evidence for final report assembly. The evaluation results relate only to the public-corpus prototype under the stated conditions. No licence purchase, military-system deployment or security endorsement is implied.
