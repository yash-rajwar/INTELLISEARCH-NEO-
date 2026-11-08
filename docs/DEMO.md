# Demo guide (about 7 minutes)

Prototype on public and synthetic data. Not a deployed system.

## T-24 h
- [ ] Full dry run on the machine you will present from.
- [ ] `python -m pytest -q` passes; `git tag demo-2026-11-09`.
- [ ] `python warm_corpus_text.py` run once on this machine (about 2 minutes). Summarize and Compare need the
      cached text; without it the first click on SP 800-53 takes about 80 s.
- [ ] Time Summarize on SP 800-53 once. If it takes over 20 s, do not demo it live: pick two shorter documents.
- [ ] Open `/evaluation` and read the typo rows for both splits. Say only what they show.
- [ ] Backup screen recording saved on the desktop.
- [ ] Do NOT re-run the frozen test split (`eval-frozen-v2`). It was run once.

## T-1 h
- [ ] Start Docker, then `es01`. Never run `docker volume rm` or `docker compose down -v`.
- [ ] Network: trusted network or phone hotspot only (`es01` is on 0.0.0.0:9200).
- [ ] Open `/system`: licence badge not red (trial ends 2026-12-07), ELSER ok.
- [ ] Run one semantic query so ELSER is warm (first call after idle is about 30 s).
- [ ] Presenter mode on. Close notifications. Open the tabs below, including `/evaluation`.

## T-10 min
- [ ] Run one more semantic query (a warm call can still time out, HTTP 408 was seen once).
- [ ] Backup recording opens.

## Script
1. **System page (30 s).** Version, licence badge, ELSER status, counts: 18 documents, 7,102 passages.
   Say: "Everything runs locally on public and synthetic data."
2. **Why semantic search (90 s).** Compare page, query:
   `What is the person whose personal data is collected called?`
   Expected document: the DPDP Act (the answer uses the term "Data Principal", which the question never says).
   In one live check on the demo laptop the Data Principal definition (DPDP Act, page 2) was rank 3 in keyword,
   rank 2 in semantic, and rank 1 in hybrid and weighted. Semantic also returned NIST SP 800-53 pages 384 and 385,
   marked "only found by meaning". Warm latencies in that check: keyword 69 ms, semantic 241 ms,
   hybrid 497 ms, weighted 414 ms. Re-run it on the day: the numbers will differ, so say what you see.
   If the result is not clear on the day, do not force it.
3. **Sources (60 s).** Open one result, click a page chip, show the page. "Corpus results point back to their source."
4. **Typos (30 s).** Search `Concent Manger single point of contact` in keyword and semantic mode.
   Say what the typo table on `/evaluation` shows for each split. Do not say more than it shows.
5. **Upload (60 s).** Upload a small public PDF, show the stages, then search a phrase from it in keyword and semantic mode.
6. **Summarize / Compare documents (45 s).** Pick two corpus documents. Point at the coverage line and the aligned passages.
7. **Honest results (90 s).** `/evaluation` or `docs/EVALUATION.md`. Say the counts, the limits, the rejected experiments (see below).
8. **Close (30 s).** Proven: a repeatable method on public data. Not proven: real documents, security, scale.
   Proposed next step: a pilot on approved test files.

## Say this about the results
- Document hit@1 was 18/20 for every mode on the development split and 8/11 to 10/12 on the test split.
- Passage hit@1 was hard: development 6/20 to 10/20, test 0/11 to 2/12.
- No mode won consistently. Keyword led passage hit@1 on development; semantic led passage hit@5 on test (7/11). The order changed between splits.
- With 11 to 20 questions per split, a difference of one or two questions is within noise.
- Rejected: a score threshold for "no good match" (score ranges of answerable and unanswerable questions overlap) and weighted fusion (no advantage over plain hybrid).
- Real miss: Q13 (national-security refusal in the RTI Act) is a genuine keyword miss.
- Never quote a single accuracy percentage.

## If something fails
- **ELSER timeout:** the app labels the keyword fallback. Say so, switch to keyword mode, continue.
- **Elasticsearch down:** `/evaluation` still opens (it reads saved files). Also play the recording and show `docs/EVALUATION.md`.
- Never guess a cause aloud. Say what you see.

## Statements that must stay true
- "A prototype on public and synthetic data, not a deployed system."
- "Built with AI assistance. I have reviewed and tested it and can explain each part."
- ELSER is English-only. After the trial ends (2026-12-07) semantic search needs a licence; keyword search keeps working.
- If asked about the corpus licences: three Indian government documents have unverified reuse terms.

## After the demo
- [ ] Rebind `es01` to `127.0.0.1:9200` and change the default elastic password.
- [ ] Delete the scratch index `zz_elser_probe` (only after an explicit yes).
