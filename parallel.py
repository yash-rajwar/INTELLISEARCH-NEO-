"""Run the four Compare methods in two parallel phases.

Phase 1: keyword and semantic at the same time.
Phase 2: hybrid and weighted at the same time, unless semantic timed out.
A timeout means ELSER is cold or busy, so the two ELSER-based methods are marked
skipped instead of calling it again. Logging happens in the calling thread.
"""

from concurrent.futures import ThreadPoolExecutor

SKIPPED = "Skipped to avoid repeated ELSER timeouts. BM25 comparison is still available."


def _one(search_fn, mode, expected):
    try:
        return mode, {"result": search_fn(mode), "error": ""}
    except expected as exc:
        return mode, {"result": None, "error": str(exc)}


def _phase(modes, search_fn, log_fn, expected, outputs):
    with ThreadPoolExecutor(max_workers=len(modes)) as pool:
        futures = [pool.submit(_one, search_fn, mode, expected) for mode in modes]
        done = [future.result() for future in futures]
    for mode, entry in done:
        outputs[mode] = entry
        result = entry["result"]
        if result is None:
            log_fn(mode, 0, 0, "error")
        else:
            log_fn(mode, len(result["hits"]), result["elapsed_ms"], "ok")


def run_compare(search_fn, log_fn, expected=(Exception,)):
    """Return {mode: {"result": ..., "error": ...}} in the order keyword, semantic, hybrid, weighted."""
    outputs = {}
    _phase(("keyword", "semantic"), search_fn, log_fn, expected, outputs)
    reason = outputs["semantic"]["error"].lower()
    if "timed out" in reason or "408" in reason:
        for mode in ("hybrid", "weighted"):
            outputs[mode] = {"result": None, "error": SKIPPED}
    else:
        _phase(("hybrid", "weighted"), search_fn, log_fn, expected, outputs)
    return outputs
