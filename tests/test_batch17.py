"""Small checks for batch 17: no stale startup label, ledger names the cited runs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_startup_banner_has_no_stale_v3_label():
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "original, V1 and V2 unchanged" not in text


def test_progress_ledger_names_the_cited_runs_and_the_frozen_tag():
    text = (ROOT / "docs" / "PROGRESS.md").read_text(encoding="utf-8")
    assert "20261108-085517" in text
    assert "20261108-091348" in text
    assert "eval-frozen-v2" in text
