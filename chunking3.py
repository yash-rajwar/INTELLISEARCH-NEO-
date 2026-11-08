"""Chunker v3 (batch 27): cleaner passages for PDFs.

Three changes compared with chunking.chunk_pages (chunker v2):
1. Running headers, footers and bare page numbers are removed before chunking
   (lines that repeat at the page edges of many pages).
2. Pages are joined into one stream, so a passage can continue across a page
   break. page_number is the page where the passage STARTS.
3. A passage never ends on a heading line, and the next passage starts at a
   sentence start when one is close enough to the overlap point.

Pure functions: no Elasticsearch, no file access. Chunker v2 stays untouched.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from collections import Counter
from difflib import SequenceMatcher

from chunking import Chunk, ChunkLimitError, _find_break, DEFAULT_TARGET, DEFAULT_OVERLAP, DEFAULT_MAX_CHUNKS, MIN_FRACTION

ZONE_LINES = 8          # look at this many lines at the top and bottom of each page
MIN_PAGES_SHARE = 0.2   # a line seen in the page edges of this share of pages is boilerplate
MIN_PAGES = 3
SENTENCE_SLACK = 120  # the overlap may grow by this much to start on a sentence

_MARKER = re.compile(r"^\(?[a-z0-9#]{1,3}\)?\.?$")
_SENT_START = re.compile(r"""[.!?]["')\]\u201d\u2019]*\s+(?=[A-Z0-9(])""")
_PAGE_LABEL = re.compile(r"^(?:page\s+)?(?:\d{1,4}|[ivxl]{1,6})$", re.I)
_END_PUNCT = re.compile(r"[.!?:;,\"')\]\u201d\u2019]$")
_NUMBERED = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[A-Z]\.\d+(?:\.\d+)*\.?|Appendix\s+[A-Z]\b[.:]?)\s+\S")
_ALLCAPS = re.compile(r"^[A-Z][A-Z0-9 ,&/()\-]{3,80}$")
_SECTION = re.compile(r"^(?:\d+(?:\.\d+)+\.?\s+[A-Z]|\d+\.\s+[A-Z][^.]{2,}$|Appendix\s+[A-Z]\b|[A-Z]\.\d+(?:\.\d+)*\.?\s+[A-Z])")


def _norm(line: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", line.strip())).lower()


def _similar(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 0.25 * max(len(a), len(b)):
        return False
    m = SequenceMatcher(None, a, b)
    return m.real_quick_ratio() >= 0.85 and m.quick_ratio() >= 0.85 and m.ratio() >= 0.85


def find_running_lines(pages) -> set[str]:
    """Normalised lines that repeat at the page edges of many pages.

    Rule A: a line (or a near-identical variant, e.g. a typo) in the top or bottom
    8 lines of at least 20% of the pages.
    Rule B: a line with 8+ letters that is the first or last line of at least 3 pages
    (chapter or section running titles).
    """
    pages = list(pages)
    if not pages:
        return set()
    wide: Counter[str] = Counter()
    tight: Counter[str] = Counter()
    for _, text in pages:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        wide.update({_norm(ln) for ln in lines[:ZONE_LINES] + lines[-ZONE_LINES:]})
        tight.update({_norm(ln) for ln in lines[:2] + lines[-2:]})
    need = max(MIN_PAGES, int(len(pages) * MIN_PAGES_SHARE))
    pool = [k for k, v in wide.items() if v >= 2 and len(k) <= 120 and not _MARKER.match(k)]
    pool.sort(key=lambda k: -wide[k])
    running: set[str] = set()
    used: set[str] = set()
    for k in pool:  # greedy clusters of near-identical lines
        if k in used:
            continue
        members = [k] + [j for j in pool if j not in used and j != k and _similar(k, j)]
        used.update(members)
        if sum(wide[m] for m in members) >= need:
            running.update(members)
    for k, v in tight.items():
        if v >= MIN_PAGES and sum(ch.isalpha() for ch in k) >= 8:
            running.add(k)
    running.discard("")
    running.add("#")
    return running


def clean_pages(pages):
    """Remove running headers, footers and bare page numbers from page edges."""
    pages = list(pages)
    running = find_running_lines(pages)
    out, removed = [], 0
    for number, text in pages:
        lines = text.splitlines()
        idx = [i for i, ln in enumerate(lines) if ln.strip()]
        zone = set(idx[:ZONE_LINES]) | set(idx[-ZONE_LINES:])
        keep = []
        for i, ln in enumerate(lines):
            if i in zone and ln.strip() and (_norm(ln) in running or _PAGE_LABEL.match(ln.strip())):
                removed += 1
                continue
            keep.append(ln.rstrip())
        out.append((number, "\n".join(keep).strip("\n")))
    return out, removed


def is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 110 or _END_PUNCT.search(s):
        return False
    return bool(_NUMBERED.match(s) or _ALLCAPS.match(s))


def _line_start(text: str, pos: int) -> int:
    return text.rfind("\n", 0, pos) + 1


def _avoid_heading_end(text: str, start: int, end: int, min_end: int) -> int:
    """If the chunk would end on a heading line, cut before that heading instead."""
    piece = text[start:end].rstrip()
    ls = _line_start(text, start + len(piece))
    if ls > min_end and ls > start and is_heading(text[ls:start + len(piece)]):
        return ls
    return end


def _next_start(text: str, start: int, end: int, overlap: int) -> int:
    """Where the next chunk begins: about `overlap` characters back, preferably at a sentence start."""
    nxt = end - overlap
    if nxt <= start:
        return end
    lo, hi = max(start + 1, nxt - SENTENCE_SLACK), end - 40
    best = None
    for m in _SENT_START.finditer(text, lo, hi):
        if best is None or abs(m.end() - nxt) < abs(best - nxt):
            best = m.end()
    if best is not None and start < best < end:
        return best
    while nxt < end and not text[nxt - 1].isspace():
        nxt += 1
    return nxt


def chunk_stream(text, target=DEFAULT_TARGET, overlap=DEFAULT_OVERLAP, max_chunks=DEFAULT_MAX_CHUNKS):
    n = len(text)
    chunks: list[Chunk] = []
    start = 0
    while start < n:
        while start < n and text[start].isspace():
            start += 1
        if start >= n:
            break
        min_end = start + int(target * MIN_FRACTION)
        end = min(start + target, n)
        if end < n:
            end = _find_break(text, start, end, min_end)
            end = _avoid_heading_end(text, start, end, min_end)
        stripped = text[start:end].rstrip()
        if stripped:
            chunks.append(Chunk(len(chunks), stripped, start, start + len(stripped)))
            if len(chunks) > max_chunks:
                raise ChunkLimitError(f"document needs more than {max_chunks} chunks")
        if end >= n:
            break
        start = _next_start(text, start, end, overlap)
    return chunks


def chunk_pages_v3(pages, target=DEFAULT_TARGET, overlap=DEFAULT_OVERLAP, max_chunks=DEFAULT_MAX_CHUNKS):
    """pages = [(page_number, text)]. Returns chunks with page_number = page where the chunk starts."""
    cleaned, _ = clean_pages(pages)
    parts, bounds, pos, prev = [], [], 0, ""
    for number, text in cleaned:
        if not text.strip():
            continue
        if parts:
            sep = "\n\n" if _END_PUNCT.search(prev.rstrip()) else "\n"
            parts.append(sep)
            pos += len(sep)
        bounds.append((pos, number))
        parts.append(text)
        pos += len(text)
        prev = text
    stream = "".join(parts)
    chunks = chunk_stream(stream, target, overlap, max_chunks)
    starts = [b[0] for b in bounds]
    heads = []
    off = 0
    for ln in stream.split("\n"):
        s = ln.strip()
        if s and len(s) <= 110 and _SECTION.match(s) and not _END_PUNCT.search(s):
            heads.append((off, s[:200]))
        off += len(ln) + 1
    hstarts = [h[0] for h in heads]
    for c in chunks:
        c.page_number = bounds[max(bisect_right(starts, c.start_char) - 1, 0)][1]
        j = bisect_right(hstarts, c.start_char) - 1
        c.section = heads[j][1] if j >= 0 else None
    return chunks
