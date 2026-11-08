# Evaluation

This document reports how the four search modes behaved on a small, hand-checked question set. It does **not** claim that any mode is better than another. The sample is small and the rankings changed between the two splits.

## Setup

- Corpus: `intellisearch_corpus_v1`, 7,102 passages from 18 documents (publicly available documents; licence notes are in `corpus/ATTRIBUTION.md`).
- Question set v2: 36 questions with source-verified gold spans, frozen at git tag `eval-frozen-v2`. Split: 22 development, 14 test.
- Modes: keyword (BM25), semantic (ELSER), hybrid (RRF, fused), weighted (RRF with weights, fused locally because Elasticsearch 9.0.0 rejects the weighted retriever format).
- Metrics: document hit@1, passage hit@1, passage hit@5, MRR. Counts are shown as k/N.
- Unanswerable questions (2 per split) are excluded from the hit counts.
- Passage matching uses the gold span; where no span matched, a word-overlap fallback was used (11 passage matches in the test run).

## Development split (run 20261108-085517, N=20 answerable)

| Metric | keyword | semantic | hybrid | weighted |
|---|---|---|---|---|
| Document hit@1 | 18/20 | 18/20 | 18/20 | 18/20 |
| Passage hit@1 | 10/20 | 6/20 | 9/20 | 8/20 |
| Passage hit@5 | 15/20 | 16/20 | 16/20 | 16/20 |
| MRR | 0.596 | 0.478 | 0.581 | 0.543 |

## Test split (run 20261108-091348, run once, N=12 answerable)

Semantic has N=11: question Q03 failed with Elasticsearch HTTP 408 ("timeout [10s] waiting for inference result").

| Metric | keyword | semantic | hybrid | weighted |
|---|---|---|---|---|
| Document hit@1 | 10/12 | 8/11 | 10/12 | 10/12 |
| Passage hit@1 | 2/12 | 0/11 | 1/12 | 1/12 |
| Passage hit@5 | 4/12 | 7/11 | 6/12 | 6/12 |
| MRR | 0.242 | 0.182 | 0.247 | 0.252 |

The test split was run **once** and must not be run again.

## What we can and cannot say

- Finding the right **document** worked in most cases for every mode. Finding the right **passage** at rank 1 was much harder.
- No mode wins consistently. On the development split keyword had the most passage hits at rank 1; on the test split semantic had the most passage hits in the top five. The order changed between splits.
- Typo questions favoured keyword on both splits.
- With N between 11 and 20 per split, differences of one or two questions are within noise.
- Q13 (a national-security refusal clause in the RTI Act) is a real keyword miss.
- ELSER can time out even when warm (Q03). Warm it up before presenting.

## Rejected experiments

1. **Score threshold for "no good match".** We checked whether a minimum score could separate unanswerable questions from answerable ones. It could not: keyword scores for answerable questions ranged 17.2 to 78.1, against 21.4 and 27.6 for the two unanswerable ones; semantic scores ranged 5.7 to 24.9, against 7.4 and 14.4. The ranges overlap. Instead the app shows a standing note ("may not contain an answer") and a query-word overlap line.
2. **Weighted fusion.** It showed no advantage over plain hybrid, so it stays only as a labelled option.

## Known limitations

- Small question set; one author checked the gold spans.
- Many standards and RFC passages end on headings or page footers (chunker limitation; the corpus was not re-chunked).
- Semantic highlighting inside rrf, linear and rerank retrievers is unverified.
- English-only (ELSER).
