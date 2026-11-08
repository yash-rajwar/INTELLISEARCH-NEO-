"""Pure, inspectable document-intelligence helpers; no model downloads or network calls."""

import math
import re
from collections import Counter

STOP = set(
    "a an and are as at be been by can could did do does for from had has have how i if in into is it its may more most not of on or our should so some such than that the their them there these they this those to was were what when where which who why will with would you your about between document documents information".split()
)
TERMS = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{1,}")
SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'(])|\n\s*\n')
CATEGORIES = {
    "Research": (
        "study",
        "research",
        "experiment",
        "results",
        "analysis",
        "evidence",
        "hypothesis",
        "methodology",
        "investigation",
        "data",
    ),
    "Policy & Governance": (
        "policy",
        "guidelines",
        "directive",
        "compliance",
        "governance",
        "procedure",
        "standard",
        "regulation",
    ),
    "Technical": (
        "software",
        "system",
        "code",
        "network",
        "database",
        "api",
        "server",
        "deployment",
        "model",
        "algorithm",
        "security",
    ),
    "Finance": (
        "budget",
        "payment",
        "revenue",
        "cost",
        "expense",
        "fund",
        "invoice",
        "finance",
        "procurement",
    ),
    "Operations": (
        "operations",
        "workflow",
        "task",
        "schedule",
        "reporting",
        "timeline",
        "resources",
        "planning",
        "implementation",
    ),
    "Legal": (
        "legal",
        "agreement",
        "contract",
        "court",
        "law",
        "clause",
        "liability",
        "notice",
        "statute",
    ),
}


def keywords(text, max_terms=10000):
    return [
        x.lower()
        for x in TERMS.findall(text[:200000])[:max_terms]
        if x.lower() not in STOP and len(x) > 2
    ]


def sentences(text, limit=100000):
    s = [re.sub(r"\s+", " ", x).strip() for x in SPLIT.split(text[:limit])]
    return [x for x in s if len(x) > 35][:1200]


def classify(text):
    words = Counter(keywords(text))
    scores = {k: sum(words[t] for t in v) for k, v in CATEGORIES.items()}
    best = max(scores, key=scores.get) if scores else "General"
    if not scores.get(best):
        best = "General"
    tags = [term for term, _ in words.most_common(8)]
    return {"category": best, "tags": tags[:5], "signals": {k: v for k, v in scores.items() if v}}


def summarize(text, lines=5):
    ss = sentences(text)
    if not ss:
        return {"sentences": [], "method": "extractive"}
    freq = Counter(keywords(text))
    scored = []
    for idx, s in enumerate(ss):
        w = keywords(s)
        if not w:
            continue
        score = sum(min(freq.get(x, 0), 20) for x in w) / math.sqrt(len(w))
        # Small lead preference prevents burying the document's main topic.
        score += 1.3 / (idx + 1)
        scored.append((score, idx, s))
    chosen = sorted(sorted(scored, reverse=True)[: min(lines, len(scored))], key=lambda x: x[1])
    return {"sentences": [s for _, _, s in chosen], "method": "extractive"}


def compare_texts(left, right):
    lc = Counter(keywords(left))
    rc = Counter(keywords(right))
    both = lc.keys() & rc.keys()
    un = lc.keys() | rc.keys()
    overlap = len(both) / len(un) if un else 0
    common = sorted(both, key=lambda t: min(lc[t], rc[t]), reverse=True)[:15]
    only_left = [x for x, _ in lc.most_common(12) if x not in rc][:8]
    only_right = [x for x, _ in rc.most_common(12) if x not in lc][:8]
    return {
        "overlap_pct": round(overlap * 100, 1),
        "common": common,
        "left_only": only_left,
        "right_only": only_right,
        "left_excerpt": summarize(left, 3)["sentences"],
        "right_excerpt": summarize(right, 3)["sentences"],
    }


def explain(query, passage, method):
    qset = set(keywords(query))
    pset = set(keywords(passage))
    matched = sorted(qset & pset)
    descriptions = {
        "keyword": "BM25 retrieves lexical matches; Elasticsearch combines matching terms and document statistics.",
        "semantic": "ELSER sparse semantic retrieval ranks documents by inferred associations; visible word overlap is not an explanation of its internal model.",
        "hybrid": "RRF combines separate keyword and semantic ranking positions, rather than comparing their raw scores.",
        "weighted": "Weighted RRF combines keyword and semantic ranking positions, with the semantic branch weighted 1.5 in this showcase.",
        "fuzzy": "Fuzzy keyword search is BM25 that also accepts words with a few letters wrong: up to 1 letter for words of 3 to 5 letters, up to 2 for longer words. The first letter must match.",
    }
    return {
        "matched": matched[:18],
        "missing": sorted(qset - pset)[:18],
        "description": descriptions.get(method, "Method not specified."),
        "disclaimer": "This is a transparent query-term breakdown, not an attribution or proof of why ELSER ranked the passage.",
    }


def evidence_reply(question, hits, limit=5):
    """No LLM: visibly labeled evidence extracts, not purported generated answers."""
    qset = set(keywords(question))
    ranked = []
    for n, h in enumerate(hits[:limit], 1):
        passage = h.get("passage", "")
        spans = sentences(passage)
        if not spans:
            spans = [re.sub(r"\s+", " ", passage).strip()]
        spans = [s for s in spans if s][:8]
        if not spans:
            continue
        best = max(
            spans, key=lambda s: len(qset & set(keywords(s))) / max(1, math.sqrt(len(keywords(s))))
        )
        ranked.append(
            {
                "citation": len(ranked) + 1,
                "text": best[:420],
                "title": h.get("title", "Untitled"),
                "source_url": h.get("source_url") or "",
                "context_url": f"/context/{h['index']}/{h['id']}"
                if h.get("index") and h.get("id")
                else "",
            }
        )
    return ranked
