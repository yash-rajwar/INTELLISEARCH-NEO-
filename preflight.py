"""Checks to run before starting the app.

Read-only: it never changes Elasticsearch and never prints the password.
Each check gives a row of (status, name, detail) with status PASS, WARN or FAIL.
"""

import importlib
import socket
import sys
import tempfile
import time

import requests

from config import BOOKS_DIR, DATA, ES_PASSWORD, ES_URL, ES_USER, PORT, ROOT, settings


def python_status(version):
    """Supported Python versions are 3.10 to 3.13."""
    text = ".".join(str(n) for n in version[:3])
    if version < (3, 10):
        return "FAIL", f"Python {text} is too old; 3.10 to 3.13 is needed"
    if version >= (3, 14):
        return "WARN", f"Python {text} is newer than tested; use 3.12 in a venv"
    return "PASS", f"Python {text}"


def license_status(lic, now=None):
    """Summarise the dict under 'license' from GET _license."""
    now = time.time() if now is None else now
    kind = lic.get("type", "unknown")
    state = lic.get("status", "unknown")
    if state != "active":
        return "WARN", f"{kind} license is {state}: semantic search unavailable, keyword search still works"
    if kind == "basic":
        return "WARN", "basic license: ELSER (semantic search) is not available"
    expiry = lic.get("expiry_date_in_millis")
    if not expiry:
        return "PASS", f"{kind} license, no expiry date"
    days = (expiry / 1000 - now) / 86400
    if days < 0:
        return "WARN", f"{kind} license has expired: semantic search unavailable"
    if days < 7:
        return "WARN", f"{kind} license ends in {days:.1f} days"
    return "PASS", f"{kind} license, {days:.0f} days left"


def check_packages():
    rows = []
    for name in ("flask", "requests", "pypdf", "docx", "pymupdf"):
        try:
            importlib.import_module(name)
            rows.append(("PASS", "Package " + name, "installed"))
        except ImportError:
            rows.append(("FAIL", "Package " + name, "missing: pip install -r requirements.txt"))
    return rows


def check_folders():
    rows = []
    for folder in (ROOT / "templates", ROOT / "static"):
        ok = folder.is_dir()
        rows.append(("PASS" if ok else "FAIL", "Folder " + folder.name, str(folder) if ok else "missing"))
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=DATA):
            pass
        rows.append(("PASS", "Data folder", f"{DATA} is writable"))
    except OSError as exc:
        rows.append(("FAIL", "Data folder", f"{DATA} is not writable ({exc})"))
    if BOOKS_DIR.is_dir():
        rows.append(("PASS", "Books folder", str(BOOKS_DIR)))
    else:
        rows.append(("WARN", "Books folder", f"{BOOKS_DIR} not found: legacy book viewer unavailable (optional)"))
    return rows


def check_elasticsearch():
    rows = []
    session = requests.Session()
    session.trust_env = False
    if ES_PASSWORD:
        session.auth = (ES_USER, ES_PASSWORD)
    else:
        rows.append(("WARN", "ES_PASSWORD", "not set; put it in the .env file"))
    try:
        r = session.get(ES_URL + "/", timeout=5)
    except requests.RequestException as exc:
        rows.append(("FAIL", "Elasticsearch", f"cannot reach {ES_URL} ({type(exc).__name__})"))
        return rows
    if r.status_code == 401:
        rows.append(("FAIL", "Elasticsearch", "login refused: check ES_USER and ES_PASSWORD"))
        return rows
    if r.status_code != 200:
        rows.append(("FAIL", "Elasticsearch", f"unexpected HTTP {r.status_code}"))
        return rows
    rows.append(("PASS", "Elasticsearch", f"{ES_URL} version {r.json().get('version', {}).get('number', '?')}"))

    try:
        lic = session.get(ES_URL + "/_license", timeout=5).json().get("license", {})
        status, detail = license_status(lic)
        rows.append((status, "License", detail))
    except (requests.RequestException, ValueError) as exc:
        rows.append(("WARN", "License", f"could not read license ({type(exc).__name__})"))

    endpoint = settings.es_inference_id
    try:
        r = session.get(f"{ES_URL}/_inference/sparse_embedding/{endpoint}", timeout=5)
        if r.status_code == 200:
            rows.append(("PASS", "ELSER endpoint", f"{endpoint} exists (the model itself loads on first use)"))
        else:
            rows.append(("WARN", "ELSER endpoint", f"{endpoint} not found (HTTP {r.status_code}): semantic search unavailable"))
    except requests.RequestException as exc:
        rows.append(("WARN", "ELSER endpoint", f"could not check ({type(exc).__name__})"))
    return rows


def check_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        taken = s.connect_ex(("127.0.0.1", PORT)) == 0
    if taken:
        return [("FAIL", f"Port {PORT}", "already in use; stop that program first")]
    return [("PASS", f"Port {PORT}", "free")]


def check_optional():
    rows = []
    try:
        from ocr import available

        ok, message = available()
        rows.append(("PASS" if ok else "WARN", "OCR (optional)", "ready" if ok else str(message)))
    except Exception as exc:
        rows.append(("WARN", "OCR (optional)", f"check failed: {exc}"))
    try:
        from llm import enabled

        on = enabled()
        rows.append(("PASS" if on else "WARN", "Local AI (optional)", "configured" if on else "not configured; evidence-only mode works"))
    except Exception as exc:
        rows.append(("WARN", "Local AI (optional)", f"check failed: {exc}"))
    return rows


def run_checks():
    status, detail = python_status(sys.version_info)
    rows = [(status, "Python", detail)]
    rows += check_packages()
    rows += check_folders()
    rows += check_elasticsearch()
    rows += check_port()
    rows += check_optional()
    return rows


def main():
    rows = run_checks()
    width = max(len(name) for _, name, _ in rows)
    print("IntelliSearch preflight (read-only)\n")
    for status, name, detail in rows:
        print(f"[{status:<4}] {name:<{width}}  {detail}")
    fails = sum(1 for r in rows if r[0] == "FAIL")
    warns = sum(1 for r in rows if r[0] == "WARN")
    print(f"\n{fails} FAIL, {warns} WARN.")
    print("Not ready: fix the FAIL lines first." if fails else "Ready to start: python app.py")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())