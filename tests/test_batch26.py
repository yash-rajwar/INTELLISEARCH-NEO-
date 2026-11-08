"""Batch 26: the product name is IntelliSearch NEO (static checks, no app import)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BARE = re.compile(r"(?<![\w\-/\\.])IntelliSearch(?![\w\-/\\])(?! NEO)(?! V3)")


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_base_template_uses_the_new_name_everywhere():
    html = _read("templates/base.html")
    assert html.count("IntelliSearch NEO") >= 4
    assert not BARE.search(html)


def test_titles_and_banners():
    assert "IntelliSearch NEO" in _read("templates/evaluation.html")
    assert "INTELLISEARCH NEO" in _read("templates/demo.html")
    assert "IntelliSearch NEO prototype" in _read("app.py")


def test_readme_title():
    assert _read("README.md").lstrip().startswith("# IntelliSearch NEO")
