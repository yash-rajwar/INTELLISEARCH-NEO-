# Traceability: Indexer findings and V4 behaviour

The earlier Indexer evaluation listed the problems below (their IDs). This note maps each one to the V4
behaviour that addresses it. It is a map, not a test report. Everything was built and tried on public
documents only.

How to read it: "Commits" are the commits whose messages describe the change. "Tests" are test files whose
names match the topic; open the file to confirm what it covers. "Check by hand" is the quick manual check
to run before the demo.

| Indexer finding | V4 behaviour | Commits | Tests | Check by hand |
|---|---|---|---|---|
| F-01 Long files silently truncated | Uploads are indexed without the old silent cap; chunker v2 | 0b746a0, 6ab692a, db7d2f8 | tests/test_chunker_caps.py, tests/test_chunking.py | Upload a long file with marker words spread through it and search for each marker |
| F-02 Results repeat the same document | One card per document, query words highlighted | d013290 | tests/test_grouping.py | Search a common term and check for one card per document |
| F-03 No page navigation | Corpus results link to the original with a page anchor; source context links to the originals | d0322ba, bde3702 | no dedicated test confirmed | Click a page chip and check the PDF opens at that page |
| F-04 Modified files stay stale | Duplicate detection by content hash; uploaded documents can be deleted | 0b746a0, 4a8f829 | tests/test_upload_delete.py | Upload a modified copy of a file and check that the old text is gone |
| F-05, F-06 Unsupported, empty or corrupt files | Failed uploads are cleaned up; background upload shows indexed or error and recovers after a restart | 4a8f829, 4a5c60a | tests/test_upload_delete.py, tests/test_background.py | Upload an empty file, a corrupt PDF and an unsupported type; check the message and that nothing stays in the library |
| F-07 Undefined fuzzy behaviour | Fuzzy keyword mode with a documented typo rule and explanation text | 30b0201, f80db95, 6acaba4 | tests/test_fuzzy.py | Search a query with a typo in keyword and fuzzy mode and read the explanation |
| No relevance measurement | Evaluation harness, 36-question set with gold spans, saved runs, `/evaluation` page with hits/questions | c673c6d, 9856e7f, c71427f, f7fe1aa, fd9a31e, 1144d95 | tests/test_eval_metrics.py, tests/test_evaluation_page.py | Open `/evaluation` with Elasticsearch stopped |

## Not claimed
- Performance on real organisational documents, security, or scale.
- That any search mode is better than another: the results in `docs/EVALUATION.md` do not show that.
- That uploaded files get the same page links as corpus documents. Check this before saying it.
- Anything about the earlier benchmark results, which are kept separate from the V4 evaluation.
