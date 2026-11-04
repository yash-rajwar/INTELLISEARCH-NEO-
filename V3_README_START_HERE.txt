INTELLISEARCH V3 — DEMONSTRATION-READY R&D SHOWCASE
====================================================
Release: 2026-10-15 (local proof-of-concept)

IMPORTANT
---------
* Use local non-sensitive demo files only. There is NO user authentication.
* Port 5003, bound to 127.0.0.1; V2 remains on 5002 and the original Flask app on 5000.
* This ZIP contains ONLY the folder intellisearch_showcase_v3; it does NOT replace
  book_search_app.py or the existing V1/V2 directories.
* The existing research indexes are READ-ONLY. V2 uploads/index/database are also
  READ-ONLY when accessed by V3. V3 writes ONLY to its own new upload index:
  intellisearch_showcase_chunks_v3 and its local data folder.
* DO NOT delete or recreate old Elasticsearch indexes for this application.
* An ELSER inference endpoint in the mapping does not guarantee model availability.
  Use /system and the explicit one-query /semantic-check test.

WHAT WAS IMPROVED
-----------------
1. Robust multi-collection search: native Elasticsearch RRF for uniform mappings;
   separated lexical + semantic retrieval and rank fusion for mixed collections.
   Semantic requests are scoped to indexes with semantic_text mappings.
2. Explicit BM25 fallback when hybrid inference fails; never mislabel a fallback.
3. Previous V2 upload index can be queried read-only and V2 files browsed from V3
   without reindexing, copying or modifying the originals.
4. Presentation-ready demo walkthrough with prepared book questions, Kibana
   commands, PDF navigation example and suggested presentation sequence.
5. Diagnostics page: cluster and index counts, inference mapping, optional OCR
   and local AI configuration, and one opt-in ELSER live query.
6. Improved visibility of effective retrieval method and latency.
7. All existing V2 modules retained: document library, PDF/DOCX/TXT extraction,
   source context, optional OCR, extractive Q&A/summaries, optional Ollama,
   classification, document comparison, related docs, bookmarks, analytics.

INSTALLATION — WINDOWS POWERSHELL
---------------------------------
Prerequisites: Docker Desktop started; Elasticsearch on port 9200; the V2 Python
virtual environment is already installed at:
 C:\Users\master\Downloads\gutenberg_books\.intellisearch_v2_env

1. Download IntelliSearch_V3_Demo_Ready.zip from ChatGPT into Downloads.
2. Confirm actual ZIP location before extracting:
   Test-Path "$HOME\Downloads\IntelliSearch_V3_Demo_Ready.zip"
   Output must be True. If False, locate the ZIP in your browser downloads.

3. Extract into your EXISTING gutenberg_books project (new folder only):
   Expand-Archive -LiteralPath "$HOME\Downloads\IntelliSearch_V3_Demo_Ready.zip" -DestinationPath "$HOME\Downloads\gutenberg_books" -Force

4. Change directory:
   cd C:\Users\master\Downloads\gutenberg_books

5. Reuse V2's already installed Python dependencies (NO DOWNLOAD REQUIRED):
   .\.intellisearch_v2_env\Scripts\python.exe .\intellisearch_showcase_v3\preflight.py

6. Run all offline tests:
   .\.intellisearch_v2_env\Scripts\python.exe -m unittest discover -s .\intellisearch_showcase_v3\tests -v

7. Start IntelliSearch V3:
   .\.intellisearch_v2_env\Scripts\python.exe .\intellisearch_showcase_v3\app.py
   Enter your local Elasticsearch password when prompted. Keep PowerShell open.

8. Open browser:
   http://127.0.0.1:5003/
   http://127.0.0.1:5003/demo
   http://127.0.0.1:5003/system

KIBANA / ELASTICSEARCH (EXISTING SERVICES)
-----------------------------------------
Kibana: http://localhost:5601
From Kibana > Dev Tools > Console (read-only requests):
 GET /
 GET _cat/indices?v
 GET books_passages_phase2e_v1/_count
 GET books_passages_phase2e_v1/_mapping

V3 index is created only on the first successful upload; BEFORE that the
command GET intellisearch_showcase_chunks_v3/_count returns index_not_found.

DEMO ORDER
----------
A. Open /system and show the 5 whole books, 2,354 passages, 12 demo docs.
B. /demo, select the Frankenstein example; compare BM25 / ELSER / RRF.
C. Open result context, source line, and explain that chapter labels can be
   imperfect. Do not claim result rank equals answer accuracy.
D. /library upload samples/sample_two_page_brief.pdf using BM25 first.
E. /search: choose "V3 uploaded documents", keyword mode,
   query "blue lantern North Archive". Open original PDF page 2.
F. /library upload both policy comparison TXT samples and /doc-compare.
G. /summarize and /ask: without Ollama these are extractive evidence, NOT
   AI-generated answers. For local LLM configure INTELLI_V3_OLLAMA_MODEL.
H. /analytics and /bookmarks; then open Kibana Dev Tools.

V2 UPLOADS
----------
If you uploaded files previously in V2, they appear under the second library
section IF the original V2 SQLite and uploaded files still exist. In /search,
choose "Existing V2 uploads (read-only)". V3 does NOT duplicate or change them.
If the V2 index exists but not the V2 SQLite storage, text can be searched but
source-file links may return 404; preserve the original V2 data directory.

OPTIONAL LOCAL AI
-----------------
With Ollama already installed/running AND a compatible model downloaded:
  $env:INTELLI_V3_OLLAMA_MODEL = 'YOUR_LOCAL_MODEL_NAME'
Then start V3 from this same terminal. This is optional: no cloud LLM is needed
for search, evidence excerpts, extractive summaries or comparisons.

OPTIONAL OCR
------------
Install Tesseract and its English language data separately. PyMuPDF is installed
in the V2 virtual environment. Enable the OCR checkbox for scanned PDFs only.
/system will indicate whether English OCR language data was located.

DATA + COMPATIBILITY
--------------------
V3 SQLite: intellisearch_showcase_v3\data\showcase.sqlite3
V3 original uploads: intellisearch_showcase_v3\data\uploads
V3 Elasticsearch index: intellisearch_showcase_chunks_v3
V2 SQLite / original uploads / index: opened read-only by V3 (when available)
Do not extract a newer ZIP over a modified V3 tree without keeping a backup.

VALIDATION LIMITATIONS
----------------------
Offline checks cover syntax, templates, Python modules, simulated Elasticsearch
responses and bundled sample extraction. The ZIP was NOT tested against your
live Windows Elasticsearch/ELSER service and no full Flask browser test was
possible in the isolated build environment. Run preflight, unit tests and a
live demonstration on your machine before presenting. Optional Ollama OCR and
performance/relevance results have not been validated in V3.

TROUBLESHOOTING
---------------
- Preflight 5003 in use: stop an earlier V3 instance (Ctrl+C in its terminal).
- Connection error 9200: open Docker Desktop and start the original Elasticsearch.
- ELSER timeout: use BM25, inspect /system, don't reinstall/reindex.
- Files not found: ensure the ZIP extracted under gutenberg_books, containing
  a folder named intellisearch_showcase_v3 (not another nested folder).
- Missing Python libraries: run the same V2 environment interpreter that worked
  for V2; do not create another environment unless necessary.
- Existing V2 upload not visible: check that V2's data and index still exist;
  V3 never modifies them.
