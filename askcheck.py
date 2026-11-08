"""Small, testable checks for the Ask page: citation validation and a word-overlap notice."""

import re

from intelligence import keywords

_CITATION = re.compile(r"\[(\d{1,3})\]")


def check_citations(answer, source_count):
    """Find [n] citations in an answer and separate real source numbers from invalid ones."""
    found = [int(n) for n in _CITATION.findall(answer or "")]
    valid = sorted({n for n in found if 1 <= n <= source_count})
    invalid = sorted({n for n in found if not 1 <= n <= source_count})
    return {"valid": valid, "invalid": invalid, "has_citations": bool(found)}


def no_term_overlap(question, hits):
    """True when no retrieved passage shares any content word with the question.

    This is a conservative notice, not a relevance score: an evaluation on this project showed
    that score thresholds cannot separate answerable from unanswerable questions.
    A question with no content words returns False (nothing can be claimed).
    """
    wanted = set(keywords(question))
    if not wanted:
        return False
    for hit in hits:
        if wanted & set(keywords(hit.get("passage") or hit.get("text") or "")):
            return False
    return True
