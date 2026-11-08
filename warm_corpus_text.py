"""Extract and cache the text of every corpus document so Summarize and Compare are fast.

Run from the repository root:  python warm_corpus_text.py
It reads files only; it never touches Elasticsearch.
"""

import time

from documents import corpus_catalog, read_source

for cid in corpus_catalog():
    started = time.monotonic()
    try:
        result = read_source("corpus:" + cid)
        print(f"{cid}: {len(result['text']):,} characters, {time.monotonic() - started:.1f} s")
    except Exception as exc:  # noqa: BLE001 - report every problem and carry on
        print(f"{cid}: FAILED - {str(exc)[:150]}")
