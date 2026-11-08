"""Batch 23: pinned requirements are consistent; highlighting escapes HTML."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _pins(name):
    out = {}
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        line = line.split(";")[0].split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        assert "==" in line, name + " must pin exact versions: " + line
        key, _, version = line.partition("==")
        out[re.sub(r"[-_.]+", "-", key.strip().lower())] = version.strip()
    return out


def test_runtime_requirements_are_exact_and_covered_by_the_lock_file():
    direct, lock = _pins("requirements.txt"), _pins("requirements-lock.txt")
    assert direct
    for name, version in direct.items():
        assert lock.get(name) == version, name + " differs between requirements and the lock file"


def test_dev_requirements_are_exact():
    assert _pins("requirements-dev.txt")


def test_highlighting_escapes_html_in_passages():
    from search import highlight_html

    out = str(highlight_html("<script>alert(1)</script> personal data", "data"))
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "<mark" in out
