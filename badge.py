"""Text for the licence chip in the top bar. Cached so pages stay fast."""

import time
from datetime import datetime, timezone

OK_SECONDS = 300
FAIL_SECONDS = 60
_cache = {"until": 0.0, "text": ""}


def days_left(expiry, now=None):
    """Whole days until an ISO date such as 2026-12-07T08:02:57.998Z. None if unreadable."""
    if not expiry:
        return None
    try:
        when = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (when - now).days


def chip_text(info, now=None):
    if not isinstance(info, dict):
        return ""
    kind = info.get("type")
    status = info.get("status")
    if status and status != "active":
        return f"Licence {status}"
    days = days_left(info.get("expires"), now)
    if kind == "trial" and days is not None:
        if days < 0:
            return "Trial licence expired"
        return f"Trial licence: {days} days left"
    if kind:
        return f"Licence: {kind}"
    return ""


def license_chip(get_client, clock=time.monotonic):
    """Return the chip text, or "" when it cannot be found. Never raises."""
    now = clock()
    if now < _cache["until"]:
        return _cache["text"]
    try:
        text = chip_text(get_client().license_info())
        _cache.update(until=now + OK_SECONDS, text=text)
    except Exception:  # noqa: BLE001 - a cosmetic chip must never break a page
        _cache.update(until=now + FAIL_SECONDS, text="")
    return _cache["text"]
