"""Batch 25: the architecture note names only files that exist; rerank is never described as a feature."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_architecture_names_only_existing_python_files():
    text = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    names = set(re.findall(r"`([A-Za-z0-9_./-]+\.py)`", text))
    assert len(names) > 15
    for name in names:
        assert (ROOT / name).is_file(), name + " is named in ARCHITECTURE.md but does not exist"


def test_rerank_is_reported_as_not_working():
    for doc in ("README.md", "docs/EVALUATION.md", "docs/PROGRESS.md", "docs/ARCHITECTURE.md"):
        text = (ROOT / doc).read_text(encoding="utf-8").lower()
        assert "rerank" in text, doc
        assert "could not" in text or "rejected" in text, doc
