"""Helpers for the Compare methods page.

annotate() reads the results of the four methods and adds to the outputs dict:
  - a status for every method (ok, slow, fallback, failed, skipped), and
  - a marker on every hit saying whether the same document was also found by the other method.

The comparison uses the top results of keyword and semantic search, matched by document title.
It says nothing about relevance; it only shows where the two methods agree and disagree.
"""

import logging

log = logging.getLogger(__name__)

SLOW_MS = 3000

MARKERS = {
    "both": ("Found by both", "both"),
    "meaning": ("Only found by meaning", "meaning"),
    "keyword": ("Only found by keywords", "keyword"),
}


def _result(entry):
    return (entry or {}).get("result") or None


def _title(hit):
    return hit.get("title", "") if isinstance(hit, dict) else getattr(hit, "title", "")


def _is_fallback(result):
    return "fallback" in str(result.get("mode_used", "")).lower()


def _elapsed(result):
    try:
        return float(result.get("elapsed_ms"))
    except (TypeError, ValueError):
        return None


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def _unique(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _set_status(entry):
    """Give one method's entry a status and a short label for the page."""
    result = _result(entry)
    error = entry.get("error")
    if error:
        skipped = str(error).startswith("Skipped")
        entry["status"] = "skipped" if skipped else "failed"
        entry["status_label"] = entry["status"]
    elif result is None:
        entry["status"] = "failed"
        entry["status_label"] = "failed"
    elif _is_fallback(result):
        entry["status"] = "fallback"
        entry["status_label"] = "keyword fallback"
    else:
        ms = _elapsed(result)
        if ms is not None and ms > SLOW_MS:
            entry["status"] = "slow"
            entry["status_label"] = "slow, %.1f s" % (ms / 1000)
        else:
            entry["status"] = "ok"
            entry["status_label"] = "ok" if ms is None else "ok, %d ms" % round(ms)


def _sentence(meaning_count, keyword_count):
    if meaning_count == 0 and keyword_count == 0:
        return "Keyword and semantic search returned the same documents in their top results."
    return (
        "In their top results, semantic search found %s that keyword search did not, "
        "and keyword search found %s that semantic search did not."
        % (_plural(meaning_count, "document"), _plural(keyword_count, "document"))
    )


def _compare(outputs, summary):
    keyword = _result(outputs.get("keyword"))
    semantic = _result(outputs.get("semantic"))
    if keyword is None or semantic is None:
        summary["note"] = "Markers need results from both keyword and semantic search, and one of them is missing."
        return
    if _is_fallback(keyword) or _is_fallback(semantic):
        summary["note"] = "A method fell back to keyword search for this query, so a comparison by meaning is not possible."
        return
    keyword_titles = _unique(_title(h) for h in keyword["hits"])
    semantic_titles = _unique(_title(h) for h in semantic["hits"])
    if not keyword_titles or not semantic_titles:
        summary["note"] = "One of the two methods returned no results, so there is nothing to compare."
        return
    k, s = set(keyword_titles), set(semantic_titles)
    summary["meaning_only"] = [t for t in semantic_titles if t not in k]
    summary["keyword_only"] = [t for t in keyword_titles if t not in s]
    summary["comparable"] = True
    summary["sentence"] = _sentence(len(summary["meaning_only"]), len(summary["keyword_only"]))
    for entry in outputs.values():
        result = _result(entry)
        if result is None:
            continue
        for hit in result["hits"]:
            if not isinstance(hit, dict):
                continue
            title = hit.get("title", "")
            if title in k and title in s:
                key = "both"
            elif title in s:
                key = "meaning"
            elif title in k:
                key = "keyword"
            else:
                continue
            hit["marker"] = key
            hit["marker_label"], hit["marker_class"] = MARKERS[key]


def annotate(outputs):
    """Add statuses and markers to outputs (in place) and return a summary dict for the template."""
    summary = {"comparable": False, "sentence": "", "note": "", "meaning_only": [], "keyword_only": []}
    try:
        for entry in outputs.values():
            _set_status(entry)
        _compare(outputs, summary)
    except Exception:  # noqa: BLE001 - the Compare page must still render
        log.exception("compare page: could not annotate results")
        summary = {"comparable": False, "sentence": "", "note": "", "meaning_only": [], "keyword_only": []}
    return summary
