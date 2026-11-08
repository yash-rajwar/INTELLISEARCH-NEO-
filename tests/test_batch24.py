"""Batch 24: /demo and /system content. Pages are fetched in a separate process (see test_evaluation_page)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _page(path):
    code = "import app; print(app.app.test_client().get(%r).get_data(as_text=True))" % path
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert result.returncode == 0, "page process failed: " + result.stderr[-600:]
    return result.stdout


@pytest.fixture(scope="module")
def demo_html():
    return _page("/demo")


def test_demo_page_always_has_prepared_examples_and_a_step_bar(demo_html):
    assert 'class="demo-case"' in demo_html
    assert 'aria-label="Demo steps"' in demo_html
    assert "Honest results" in demo_html


def test_system_page_is_v4_and_reports_rerank_off():
    html = _page("/system")
    assert "V4 APP" in html and "V3 APP" not in html
    assert "Reranking" in html and "rejected on this machine" in html
