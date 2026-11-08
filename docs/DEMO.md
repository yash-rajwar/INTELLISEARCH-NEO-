# Demo script (about 7 minutes)

Rehearse every query below on the demo machine first. Do not improvise queries on the day.

## Before you start
- T-1 h: start Docker and `es01`, run `python app.py`, open `/system` (license active, ELSER ok).
- Run one semantic search to warm ELSER (cold start is about 30 s).
- Open these tabs: `/system`, `/compare`, `/search`, `/evaluation`.
- Have the fallback screen recording ready to open.

## Script
1. **System page (30 s).** Elasticsearch 9.0.0, trial license, 18 public documents, 7,102 passages. Everything runs locally on public data.
2. **Compare methods (90 s).** Use a query from the rehearsal where keyword and semantic differ. Show the four columns and the latency difference (keyword about 70 ms, semantic about 130 ms, hybrid about 170 ms, warm).
3. **Sources (60 s).** Open a result with "Original source". It opens the PDF at the right page.
4. **Evaluation page (120 s).** Read the counts as k/N, not percentages.
   - All four modes find the right document first for 18 of 20 dev questions.
   - At passage level, keyword is best at rank 1 (10/20 vs 6/20 for semantic). Hybrid and weighted are one question ahead at ranks 3 to 5, which is within noise.
   - Typo questions: keyword 2/3, semantic-based modes 1/3.
   - Weighted fusion showed no advantage over plain hybrid.
   - Score-based "no good match" was tested and rejected: unanswerable questions scored inside the range of answerable ones.
5. **Close (30 s).** What is shown: a repeatable method on public data. What is not shown: real documents, security, scale. Proposed next step: a pilot on approved test files.

## If something fails
- ELSER slow or failing: the app labels the keyword fallback. Say so, switch to keyword, then show `/evaluation`.
- Elasticsearch down: `/evaluation` still works from saved files. Then play the recording.
- Never guess a cause aloud. Say what you see.

## Statements that must stay true
- A prototype on public and synthetic data, not a deployed system.
- Quote k/N counts with the question count, never accuracy percentages.
- Built with AI assistance; you reviewed and tested it and can explain each part.
- The three Indian government documents have unverified reuse terms. Say so if asked.
