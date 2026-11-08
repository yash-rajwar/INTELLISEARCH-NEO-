# Changelog

Entries below cover the batches checked while writing this file. Earlier batches are in `git log`.

## V4 (November 2026)

- Fuzzy keyword mode (BM25 with typo tolerance, no ELSER call), shown as a fifth method on the Search page.
  `/compare` still shows four modes.
- Upload runs in the background. The library shows `indexing...`, then `indexed` or `error`, and refreshes
  itself. A restart marks unfinished uploads as interrupted. Delete is refused while a file is still being
  indexed. The duplicate check happens when the file is submitted.
- Source context can show neighbouring passages from the corpus.
- "Found by meaning" label and "Show more results" on search results.
- Corpus paperwork: `corpus/ATTRIBUTION.md` and `corpus/manifest.csv`.

## V3

Original showcase front end over the legacy indexes. See `git log`.
