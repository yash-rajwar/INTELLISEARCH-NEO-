"""Security headers on real responses. The app runs in a separate process (see test_evaluation_page)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MISSING_UPLOAD = "/uploaded/" + "0" * 32


def _smallest_corpus_file():
    folder = ROOT / "corpus" / "files"
    if not folder.is_dir():
        return None
    files = [p for p in folder.iterdir() if p.suffix.lower() in (".pdf", ".txt")]
    return min(files, key=lambda p: p.stat().st_size).name if files else None


def _fetch(paths):
    code = (
        "import json, app\n"
        "client = app.app.test_client()\n"
        "out = {}\n"
        "for path in json.loads(%r):\n"
        "    r = client.get(path)\n"
        "    out[path] = {'status': r.status_code, 'headers': dict(r.headers)}\n"
        "print(json.dumps(out))\n"
    ) % json.dumps(paths)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert result.returncode == 0, "app process failed: " + result.stderr[-600:]
    data = json.loads(result.stdout.strip().splitlines()[-1])
    return {p: {"status": v["status"], "h": {k.lower(): x for k, x in v["headers"].items()}}
            for p, v in data.items()}


@pytest.fixture(scope="module")
def responses():
    paths = ["/evaluation", "/no-such-page", MISSING_UPLOAD]
    name = _smallest_corpus_file()
    if name:
        paths.append("/corpus-file/" + name)
    return _fetch(paths), name


def _basic(h):
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "no-referrer"
    assert h["x-frame-options"] == "DENY"


@pytest.mark.parametrize("path", ["/evaluation", "/no-such-page"])
def test_html_pages_have_the_full_header_set(responses, path):
    data, _ = responses
    h = data[path]["h"]
    _basic(h)
    assert "default-src 'self'" in h["content-security-policy"]
    assert "frame-ancestors 'none'" in h["content-security-policy"]


def test_missing_page_and_missing_upload_are_404(responses):
    data, _ = responses
    assert data["/no-such-page"]["status"] == 404
    assert data[MISSING_UPLOAD]["status"] == 404
    _basic(data[MISSING_UPLOAD]["h"])


def test_corpus_file_is_inline_with_a_known_type(responses):
    data, name = responses
    if not name:
        pytest.skip("no files in corpus/files on this machine")
    entry = data["/corpus-file/" + name]
    assert entry["status"] == 200
    h = entry["h"]
    _basic(h)
    assert h["content-disposition"].startswith("inline")
    assert h["content-type"].startswith(("application/pdf", "text/plain"))
