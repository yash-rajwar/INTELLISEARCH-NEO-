# IntelliSearch NEO

A local research prototype that compares keyword search (BM25), semantic search (ELSER) and rank-fused
hybrid search over a small set of publicly available documents. It is a Flask web app on top of
Elasticsearch.

## What it is

- A way to see, side by side, how different retrieval methods rank the same question.
- Corpus results link back to the original document and page.
- You can upload your own PDF, DOCX or TXT file, search it, and delete it again.
- Summaries and side-by-side comparison of two documents, including long corpus PDFs.
- An evidence page that checks citations, and an optional local LLM answer (Ollama, loopback only; not used in the demo).
- Related documents for the corpus, found by shared vocabulary (not by meaning).
- A system page (licence, ELSER, corpus counts) and an evaluation page that shows saved results.

## What it is not

- Not a validated or production search system.
- No user accounts or access control. The app binds to the local machine only.
- Not tested on real organisational documents. The corpus is public documents only.
- English only (ELSER is English-only).

## Search methods

| Method | What it does |
|---|---|
| Keyword | BM25 |
| Fuzzy keyword | BM25 that tolerates typos; no ELSER call |
| Semantic | ELSER on a `semantic_text` field |
| Hybrid | Keyword and semantic fused with RRF |
| Weighted | RRF with weights, fused locally (Elasticsearch 9.0.0 rejects the weighted retriever format) |

If ELSER is unavailable, the app says so and falls back to keyword. It never hides the fallback.
The Compare methods page shows a status chip per method and marks results found by both methods,
only by meaning, or only by keywords.

## Quick start (Windows PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then set ES_PASSWORD in .env
python warm_corpus_text.py  # once, about 2 minutes
python app.py
```

Open http://127.0.0.1:5003 (the console prints the address). Elasticsearch must be running first.
`warm_corpus_text.py` caches the text of the corpus documents for Summarize and Compare; without it the
first click on the largest document takes about 80 seconds. See `docs/CLUSTER_FACTS.md` for the cluster
used in development and `docs/OFFICE_SETUP.md` for setting Elasticsearch up on another machine.

Run the tests (offline, no Elasticsearch needed): `python -m pytest -q`
Live smoke tests need a running cluster and are skipped unless you set `RUN_LIVE=1`; they are in `tests/test_live.py`.
`requirements-lock.txt` has the exact versions used in development.

## Corpus

18 documents (7,102 passages): NIST publications, Indian Acts, IETF RFCs, the NASA Systems Engineering
Handbook and six Project Gutenberg books. Sources and licence notes are in `corpus/ATTRIBUTION.md`;
checksums are in `corpus/manifest.csv`. Licence notes are starting points, not legal advice. The
reuse terms of three Indian government documents are unverified. The documents themselves are not
committed; `scripts/download_corpus.py` downloads them.

## Evaluation summary

Method and caveats are in `docs/EVALUATION.md`; the saved results can be opened in the app at `/evaluation`
(it works without Elasticsearch). In short: a hand-checked set of 36 questions, 22 for development and 14
for a test split that was run once. Counts are hits/questions.

- Finding the right document at rank 1 worked for most questions in every mode (development, N=20: 18/20
  in all four modes; test, N=12: keyword 10/12, semantic 8/11, hybrid 10/12, weighted 10/12).
- Finding the right passage was harder. Passage hit@1 on development: keyword 10/20, semantic 6/20,
  hybrid 9/20, weighted 8/20. Passage hit@5 on the test split: keyword 4/12, semantic 7/11, hybrid 6/12,
  weighted 6/12.
- No mode wins consistently, and the order changed between the two splits. With 11 to 20 questions per
  split, differences of one or two questions are within noise.

Two experiments were tried and not kept: a score threshold for "no good match" (the score ranges overlap) and
Elastic Rerank (its model could not be loaded on the development laptop, so it was never measured).

## More documents

- `docs/ARCHITECTURE.md`: components, data flow, index design and the search methods.
- `docs/DEMO.md`: demo script, checklists and fallbacks.
- `docs/TRACEABILITY.md`: earlier Indexer findings and the behaviour that addresses each one.
- `docs/PROGRESS.md`: progress ledger, decisions and open problems.
- `CHANGELOG.md`: what changed from V3 to V4.

## Known limitations

- Small question set; one author checked the answers.
- Many standards and RFC passages end on headings or page footers (chunker limitation).
- ELSER can time out even when warm. Warm it up before presenting.
- Elastic Rerank could not run on the development laptop; it is off.
- The code base still has style findings from ruff (192 at the last check).
- The Elasticsearch trial licence ends on 2026-12-07; keyword search still works afterwards.
- The development Elasticsearch container is published on all network interfaces with the default
  password until it is rebound to 127.0.0.1. Use it on a trusted network only.

## Built with AI assistance

This project was built with AI assistance. The developer has reviewed and tested it.
