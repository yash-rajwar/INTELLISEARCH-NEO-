"""Helpers for the /system page: a licence summary and a safe diagnostics report.

Pure functions, so they can be tested without Elasticsearch or the web app.
"""

from datetime import datetime, timezone

from badge import days_left


def license_view(info, now=None):
    """Summarise the licence for the page. Levels: ok, bad, unknown (bad = show a red banner)."""
    out = {
        "type": "",
        "status": "",
        "expires": "",
        "days": None,
        "level": "unknown",
        "message": "The licence could not be read.",
    }
    if not isinstance(info, dict) or info.get("error"):
        return out
    kind = str(info.get("type") or "")
    status = str(info.get("status") or "")
    expires = str(info.get("expires") or "")
    days = days_left(expires, now)
    out.update(type=kind, status=status, expires=expires[:10], days=days)
    if status and status != "active":
        out.update(
            level="bad",
            message=f"Licence {status}: semantic search (ELSER) is unavailable. Keyword search still works.",
        )
    elif kind == "trial":
        if days is None:
            out["message"] = "Trial licence, but the end date could not be read."
        elif days < 0:
            out.update(
                level="bad",
                message="The trial licence has expired and the cluster has reverted to Basic: "
                "semantic search (ELSER) is unavailable. Keyword search still works.",
            )
        elif days < 7:
            out.update(
                level="bad",
                message=f"The trial licence ends in {days} day(s), on {expires[:10]}. "
                "After that semantic search stops working.",
            )
        else:
            out.update(level="ok", message=f"Trial licence, {days} days left (ends {expires[:10]}).")
    elif kind == "basic":
        out.update(
            level="bad",
            message="Basic licence: semantic search (ELSER) is not available on this licence. "
            "Keyword search still works.",
        )
    elif kind:
        out.update(level="ok", message=f"Licence: {kind}.")
    return out


def diagnostics_report(status, lic, when=None):
    """Plain-text report for support. Only a fixed list of safe fields is included."""
    when = when or datetime.now(timezone.utc)
    status = status if isinstance(status, dict) else {}
    elser = status.get("elser") or {}
    corpus = status.get("corpus") or {}
    ocr = status.get("ocr") or {}
    ollama = status.get("ollama") or {}
    lines = [
        "IntelliSearch diagnostics (no passwords)",
        "Generated: " + when.strftime("%Y-%m-%d %H:%M UTC"),
        "Elasticsearch: " + str(status.get("es_version") or "offline"),
    ]
    if status.get("es_error"):
        lines.append("Elasticsearch error: " + str(status["es_error"])[:200])
    lines += [
        "Licence: " + str(lic.get("message", "")),
        "ELSER deployment: " + str(elser.get("state", "unknown")) + ", allocations " + str(elser.get("allocations")),
        "Corpus index found: " + str(bool(corpus.get("exists"))) + ", passages " + str(corpus.get("docs")),
        "Corpus has semantic field: " + str(bool(corpus.get("semantic"))),
    ]
    for key, count in (status.get("counts") or {}).items():
        lines.append("Count " + str(key) + ": " + ("unavailable" if count is None else str(count)))
    lines += [
        "OCR ready: " + str(bool(ocr.get("ready"))),
        "Local AI model configured: " + str(bool(ollama.get("configured"))),
        "App port: " + str(status.get("port")),
    ]
    return "\n".join(lines)
