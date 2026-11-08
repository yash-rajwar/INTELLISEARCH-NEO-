# Architecture

A local Flask web app over a single-node Elasticsearch. Public and synthetic documents only. The app listens on
127.0.0.1 and has no user accounts.

## Picture

```
 Browser (127.0.0.1:5003)
        |
        v
 +-------------------------------------------------------------+
 | app.py  (Flask routes, security headers, CSRF token)        |
 |   search.py -> modes, fusion, grouping, highlighting         |
 |   comparison.py, parallel.py -> Compare methods page         |
 |   related.py -> related corpus documents                     |
 |   documents.py, longdoc.py, intelligence.py -> summarize,    |
 |        classify, compare two documents (rule based)          |
 |   askcheck.py, llm.py -> Ask page (llm.py is optional)       |
 |   evalview.py -> /evaluation (reads saved files only)        |
 |   sysview.py, badge.py -> /system page, licence chip         |
 |   store.py -> SQLite: uploads, queries, bookmarks            |
 +----------------------+--------------------------------------+
                        | es_client.py (HTTP, retries, ELSER warm-up)
                        v
 +-------------------------------------------------------------+
 | Elasticsearch 9.0.0 (Docker, container es01)                |
 |   corpus index        18 documents, 7,102 passages          |
 |   uploads index       passages of uploaded files            |
 |   inference endpoint  ELSER (English only)                  |
 +-------------------------------------------------------------+

 Offline tools: ingest.py (build the corpus index), warm_corpus_text.py (cache text for
 Summarize and Compare), the evaluation harness (saved runs are read by /evaluation).
```

## Components

| File | Role |
|---|---|
| `app.py` | Routes, security headers, form protection, start-up |
| `settings.py`, `config.py` | Settings from the environment and `.env`; paths and collection names |
| `search.py` | Builds queries for each mode, fuses ranks, groups results by document, highlights words |
| `es_client.py` | The client the web app uses: retries, ELSER warm-up, cached counts, status |
| `es_http.py` | A retrying HTTP helper with a small cache |
| `chunking.py`, `extractors.py` | Split text into passages; read PDF, DOCX and TXT |
| `ingest.py`, `mappings.py` | Command-line ingestion into the corpus index and its mapping |
| `store.py` | SQLite records for uploads, queries and bookmarks |
| `documents.py`, `longdoc.py`, `intelligence.py` | Read a source, summarize long text, classify and compare (rule based, visible signals) |
| `comparison.py`, `parallel.py` | Compare methods page: status chips, agreement markers, two parallel phases |
| `related.py` | Related corpus documents with more-like-this |
| `askcheck.py`, `llm.py` | Citation checks for the Ask page; optional local Ollama (not used in the demo) |
| `evalview.py` | The `/evaluation` page |
| `sysview.py`, `badge.py`, `health.py`, `preflight.py` | Licence and ELSER status, diagnostics, start-up checks |
| `bootstrap.py`, `netguard.py` | Secret key and logging; refuse a non-loopback host |

## Data flow

1. **Ingestion.** `ingest.py` reads the documents listed in the corpus manifest, splits them into passages
   (about 1,400 characters, with overlap), and bulk-indexes them. ELSER embeddings are produced by Elasticsearch
   when a passage is indexed into the semantic field.
2. **Search.** The browser sends a query and a mode. `search.py` builds the request, calls Elasticsearch, groups the
   passages by document, adds highlighting and source links, and returns the page. A fallback to keyword search is
   always labelled.
3. **Upload.** A file is read, split into passages and indexed in the background. The page shows
   indexing, then indexed or error. A file with the same content hash is detected as a duplicate.
4. **Compare methods.** `parallel.py` runs keyword and semantic together, then hybrid and weighted together.
   After an ELSER timeout the two ELSER-based methods are skipped, and the page says so.

## Index design

Each passage is one Elasticsearch document with: a document id (a hash), the passage number, the page number,
the file name and type, the document title, the text (`content`, searched by BM25) and a semantic field
(`content_semantic`, filled by ELSER). A passage id is the document id plus the passage number, which is how
neighbouring passages are found. Uploads use a separate index. Older book indexes are hidden unless
`LEGACY_ENABLED` is on and are never modified.

## Search methods

| Method | How |
|---|---|
| Keyword | BM25 on the text field |
| Fuzzy keyword | BM25 that accepts a few wrong letters; the first letter must match; no ELSER call |
| Semantic | ELSER on the semantic field |
| Hybrid | Keyword and semantic fused with reciprocal rank fusion (RRF) |
| Weighted | RRF with ELSER weighted 1.5 and keyword 1.0, fused in the app because Elasticsearch 9.0.0 rejects the weighted retriever format |

The RRF constant is not recorded in this document; read `search.py` before quoting it.

## What this design does not do

- No user accounts, access control or encryption of stored files.
- No reranking: Elastic Rerank could not be loaded on the development laptop.
- No languages other than English for semantic search.
- No claim of accuracy on real organisational documents.
