# IntelliSearch

A local research prototype that compares keyword search (BM25), semantic search (ELSER) and rank-fused
hybrid search over a small set of publicly available documents. It is a Flask web app on top of
Elasticsearch.

## What it is

- A way to see, side by side, how different retrieval methods rank the same question.
- Every result links back to its source document and page.
- You can upload your own PDF, DOCX or TXT file, search it, and delete it again.

## What it is not

- Not a validated or production search system.
- No user accounts or access control. It binds to the local machine only.
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

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then set ES_PASSWORD in .env
python app.py
```

Open http://127.0.0.1:5000 (or the port printed in the console). Elasticsearch must be running first.
See `docs/CLUSTER_FACTS.md` for the cluster used in development.

## Corpus

18 documents (7,102 passages): NIST publications, Indian Acts, IETF RFCs, the NASA Systems Engineering
Handbook and six Project Gutenberg books. Sources and licence notes are in `corpus/ATTRIBUTION.md`;
checksums are in `corpus/manifest.csv`. Licence notes are starting points, not legal advice. The
documents themselves are not committed; `scripts/download_corpus.py` downloads them.

## Evaluation summary

Method and caveats are in `docs/EVALUATION.md`. In short: a hand-checked set of 36 questions,
22 for development and 14 for a test split that was run once.

- Finding the right document at rank 1 worked for most questions in every mode (test split:
  keyword 10/12, semantic 8/11, hybrid 10/12, weighted 10/12).
- Finding the right passage was harder. Passage hit@5 on the test split: keyword 4/12, semantic 7/11,
  hybrid 6/12, weighted 6/12.
- No mode wins consistently, and the order changed between the two splits. With 11 to 20 questions per
  split, differences of one or two questions are within noise.

## Known limitations

- Small question set; one author checked the answers.
- Many standards and RFC passages end on headings or page footers (chunker limitation).
- ELSER can time out even when warm. Warm it up before presenting.
- The Elasticsearch trial licence ends on 2026-12-07; keyword search still works afterwards.

## Built with AI assistance

This project was built with AI assistance. The developer has reviewed and tested it.
