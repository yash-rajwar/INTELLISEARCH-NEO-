"""Chunker v2 (WP-05): sentence-aware, never silent about limits.

Pure functions, no Elasticsearch, no file access. Offsets are character
offsets into the text that was passed in.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import Iterable

DEFAULT_TARGET = 1400
DEFAULT_OVERLAP = 180
DEFAULT_MAX_CHUNKS = 3000
MIN_FRACTION = 0.4  # a chunk is not cut shorter than this share of the target

_SENTENCE_END = re.compile(r"""[.!?]["')\]]*\s""")
_WS = re.compile(r"\s")


class ChunkLimitError(ValueError):
    """Raised instead of silently truncating a document."""


@dataclass
class Chunk:
    chunk_index: int
    text: str
    start_char: int
    end_char: int
    page_number: int | None = None
    start_line: int | None = None
    end_line: int | None = None


def _find_break(text: str, start: int, end: int, min_end: int) -> int:
    """Best cut position in (min_end, end]: paragraph, sentence, whitespace."""
    window = text[min_end:end]
    p = window.rfind("\n\n")
    if p != -1:
        return min_end + p + 2
    last = None
    for m in _SENTENCE_END.finditer(window):
        last = m
    if last is not None:
        return min_end + last.end()
    for i in range(len(window) - 1, -1, -1):
        if window[i].isspace():
            return min_end + i + 1
    return end  # one huge unbroken token: hard cut (rare)


def chunk_text(
    text: str,
    target: int = DEFAULT_TARGET,
    overlap: int = DEFAULT_OVERLAP,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> list[Chunk]:
    """Split text into chunks of at most `target` characters."""
    if target < 200:
        raise ValueError("target must be at least 200 characters")
    if not 0 <= overlap < target // 2:
        raise ValueError("overlap must be between 0 and target/2")
    n = len(text)
    chunks: list[Chunk] = []
    start = 0
    while start < n:
        while start < n and text[start].isspace():
            start += 1
        if start >= n:
            break
        end = min(start + target, n)
        if end < n:
            end = _find_break(text, start, end, start + int(target * MIN_FRACTION))
        piece = text[start:end]
        stripped = piece.rstrip()
        if stripped:
            chunks.append(Chunk(len(chunks), stripped, start, start + len(stripped)))
            if len(chunks) > max_chunks:
                raise ChunkLimitError(
                    f"document needs more than {max_chunks} chunks; refusing to truncate "
                    "(raise MAX_CHUNKS_PER_DOC or split the file)"
                )
        if end >= n:
            break
        nxt = end - overlap
        if nxt <= start:
            nxt = end
        else:
            # move forward to a word start so we never begin inside a word
            while nxt < end and not text[nxt - 1].isspace():
                nxt += 1
        start = nxt
    return chunks


def chunk_pages(
    pages: Iterable[tuple[int, str]],
    target: int = DEFAULT_TARGET,
    overlap: int = DEFAULT_OVERLAP,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> list[Chunk]:
    """Chunk page by page (PDF). pages = [(page_number, text), ...]."""
    out: list[Chunk] = []
    for page_number, text in pages:
        for c in chunk_text(text, target, overlap, max_chunks):
            c.page_number = page_number
            c.chunk_index = len(out)
            out.append(c)
            if len(out) > max_chunks:
                raise ChunkLimitError(
                    f"document needs more than {max_chunks} chunks; refusing to truncate"
                )
    return out


_PG_START = re.compile(r"^\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG", re.I)
_PG_END = re.compile(r"^\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG", re.I)


def strip_gutenberg(text: str) -> tuple[str, int]:
    """Remove the Project Gutenberg header and footer.

    Returns (body, first_line) where first_line is the 1-based line number
    in the ORIGINAL file of the first body line, so line citations stay true.
    Text without the markers is returned unchanged with first_line = 1.
    """
    lines = text.splitlines(keepends=True)
    first, last = 0, len(lines)
    for i, ln in enumerate(lines):
        if _PG_START.match(ln.strip()):
            first = i + 1
            break
    for i in range(len(lines) - 1, first - 1, -1):
        if _PG_END.match(lines[i].strip()):
            last = i
            break
    return "".join(lines[first:last]), first + 1


def chunk_lines(
    text: str,
    first_line: int = 1,
    target: int = DEFAULT_TARGET,
    overlap: int = DEFAULT_OVERLAP,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> list[Chunk]:
    """Chunk plain text and attach start_line / end_line (original numbering)."""
    chunks = chunk_text(text, target, overlap, max_chunks)
    starts = [0]
    for m in re.finditer("\n", text):
        starts.append(m.end())
    for c in chunks:
        c.start_line = first_line + bisect_right(starts, c.start_char) - 1
        c.end_line = first_line + bisect_right(starts, max(c.end_char - 1, 0)) - 1
    return chunks
