"""Checks for the project documents: no percentage figures, and every file they name exists."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOCS = ["README.md", "CHANGELOG.md", "docs/DEMO.md", "docs/TRACEABILITY.md", "docs/PROGRESS.md"]
LINKED = ["README.md", "docs/DEMO.md", "docs/TRACEABILITY.md"]
FILE_REF = re.compile(r"`((?:docs|corpus|scripts|eval|tests)/[\w./-]+\.(?:md|py|csv))`")


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_no_percentage_figures_in_the_project_documents():
    for name in DOCS:
        assert not re.search(r"\d\s*%", _read(name)), name


def test_files_named_in_the_documents_exist():
    for name in LINKED:
        for ref in FILE_REF.findall(_read(name)):
            assert (ROOT / ref).is_file(), "%s names %s, which does not exist" % (name, ref)
