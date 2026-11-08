"""License, version, ELSER health and warm-up (WP-03)."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

from es_http import ESFailure


def version(es) -> str:
    return es.request("GET", "/", timeout=8).get("version", {}).get("number", "unknown")


def license_info(es, now: datetime | None = None) -> dict:
    lic = es.request("GET", "_license", timeout=10).get("license", {})
    expiry_ms = lic.get("expiry_date_in_millis")
    now = now or datetime.now(UTC)
    days_left = expires = None
    if expiry_ms:
        exp = datetime.fromtimestamp(expiry_ms / 1000, tz=UTC)
        expires, days_left = exp.date().isoformat(), (exp - now).days
    return {
        "type": lic.get("type"),
        "status": lic.get("status"),
        "expires": expires,
        "days_left": days_left,
    }


def warm_up(es, inference_id: str, timeout: int = 120) -> float:
    """Run one tiny inference so ELSER is loaded. Returns seconds taken."""
    t0 = time.monotonic()
    es.request(
        "POST",
        f"_inference/{inference_id}",
        json={"input": ["warm up"]},
        timeout=timeout,
        retries=1,
    )
    return time.monotonic() - t0


def warm_up_in_background(es, inference_id: str, log=print) -> threading.Thread:
    def run():
        try:
            log(f"ELSER warm-up finished in {warm_up(es, inference_id):.1f}s")
        except ESFailure as exc:
            log(f"ELSER warm-up failed (BM25 still works): {exc}")

    t = threading.Thread(target=run, name="elser-warmup", daemon=True)
    t.start()
    return t


def elser_health(es, index: str, timeout: int = 60) -> dict:
    """One tiny semantic query. status: ok (<5 s), slow (<30 s), failed, no_index."""
    if not es.exists(index):
        return {"status": "no_index", "ms": None}
    t0 = time.monotonic()
    try:
        es.request(
            "POST",
            f"{index}/_search",
            timeout=timeout,
            retries=0,
            json={
                "size": 1,
                "_source": False,
                "query": {"semantic": {"field": "content_semantic", "query": "health check"}},
            },
        )
    except ESFailure as exc:
        return {"status": "failed", "ms": int((time.monotonic() - t0) * 1000), "error": str(exc)}
    ms = int((time.monotonic() - t0) * 1000)
    return {"status": "ok" if ms < 5000 else "slow", "ms": ms}
