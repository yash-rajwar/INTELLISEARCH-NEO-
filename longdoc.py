"""Long-document summaries and aligned passages. Pure Python, no network, no Elasticsearch."""

import math
import re
from collections import Counter

from intelligence import keywords, summarize

SECTION_CHARS = 60000
MEASURE = (
    "Similarity here is the share of distinct content words two passages have in common "
    "(Jaccard overlap). It does not measure meaning."
)


def split_sections(text, size=SECTION_CHARS):
    """Cut text into pieces of about `size` characters, preferring paragraph breaks."""
    text = text or ""
    sections = []
    start = 0
    total = len(text)
    while start < total:
        end = min(start + size, total)
        if end < total:
            cut = text.rfind("\n\n", start + size // 2, end)
            if cut == -1:
                cut = text.rfind(" ", start + size // 2, end)
            if cut != -1:
                end = cut
        piece = text[start:end].strip()
        if piece:
            sections.append(piece)
        start = end
    return sections


def summarize_long(text, lines=6, total_chars=None):
    """Extractive summary that covers all of `text`, section by section, then combined.

    total_chars is the length of the original document when `text` was cut short by the caller;
    the result then says so instead of claiming to cover the whole document.
    """
    text = text or ""
    if total_chars and total_chars > len(text):
        coverage = f"the first {len(text):,} of {total_chars:,} characters only"
    else:
        coverage = "the whole document"
    if len(text) <= SECTION_CHARS:
        result = summarize(text, lines)
        result.update(coverage=coverage, sections=1, chars=len(text))
        return result
    parts = split_sections(text)
    pooled = []
    for part in parts:
        pooled.extend(summarize(part, 2)["sentences"])
    chosen = summarize("\n\n".join(pooled), lines)["sentences"] if pooled else []
    return {
        "sentences": chosen,
        "method": "extractive, section by section and then combined",
        "coverage": coverage,
        "sections": len(parts),
        "chars": len(text),
    }


def chunk_text(text, size=1200):
    """Split text into passages of about `size` characters at paragraph boundaries."""
    chunks = []
    current = ""
    for para in re.split(r"\n\s*\n", text or ""):
        para = re.sub(r"\s+", " ", para).strip()
        if not para:
            continue
        if current and len(current) + len(para) + 1 > size:
            chunks.append(current)
            current = para
        else:
            current = (current + " " + para).strip()
        while len(current) > size * 2:
            cut = current.rfind(" ", 0, size)
            if cut <= 0:
                cut = size
            chunks.append(current[:cut])
            current = current[cut:].strip()
    if current:
        chunks.append(current)
    return chunks


def _sample(chunks, limit):
    if len(chunks) <= limit:
        return chunks, False
    step = math.ceil(len(chunks) / limit)
    return chunks[::step], True


def aligned_passages(left_text, right_text, near=0.6, max_pairs=12, chunk=1200, limit_chunks=400):
    """For each passage of the left document, find the most similar passage of the right one.

    Returns the strongest pairs. Pairs at or above `near` are marked as near-duplicates.
    Very long documents are sampled evenly (and the result says so).
    """
    left, left_sampled = _sample(chunk_text(left_text, chunk), limit_chunks)
    right, right_sampled = _sample(chunk_text(right_text, chunk), limit_chunks)
    right_terms = [set(keywords(c)) for c in right]
    index = {}
    for j, terms in enumerate(right_terms):
        for term in terms:
            index.setdefault(term, []).append(j)
    too_common = max(10, int(len(right) * 0.3))
    pairs = []
    for i, passage in enumerate(left):
        terms = set(keywords(passage))
        if not terms:
            continue
        votes = Counter()
        for term in terms:
            posting = index.get(term, [])
            if 0 < len(posting) <= too_common:
                votes.update(posting)
        best_j, best = None, 0.0
        for j, _count in votes.most_common(5):
            union = terms | right_terms[j]
            score = len(terms & right_terms[j]) / len(union) if union else 0.0
            if score > best:
                best_j, best = j, score
        if best_j is not None and best > 0:
            pairs.append(
                {
                    "left": left[i][:500],
                    "right": right[best_j][:500],
                    "score": round(best, 2),
                    "near_duplicate": best >= near,
                }
            )
    pairs.sort(key=lambda p: p["score"], reverse=True)
    return {
        "pairs": pairs[:max_pairs],
        "left_passages": len(left),
        "right_passages": len(right),
        "sampled": left_sampled or right_sampled,
        "measure": MEASURE,
    }
