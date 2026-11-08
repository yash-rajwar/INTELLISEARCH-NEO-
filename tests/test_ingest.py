import json

import pytest
from dataclasses import replace

from settings import load_settings

import ingest


class FakeES:
    """In-memory stand-in for ESHttp (only what ingest.py uses)."""

    def __init__(self, fail_first=None):
        self.docs, self.calls, self.fail_first = {}, [], fail_first or {}
        self.created = False
        self.semantic = True

    def exists(self, index):
        return self.created

    def invalidate(self, key=None):
        pass

    def mapping(self, index):
        props = {"content_semantic": {"type": "semantic_text"}} if self.semantic else {}
        return {index: {"mappings": {"properties": props}}}

    def request(self, method, path, *, json=None, ndjson=None, timeout=45, retries=None):
        import json as j

        self.calls.append((method, path))
        if path == "/":
            return {"version": {"number": "9.0.0"}}
        if method == "PUT":
            self.created = True
            return {"acknowledged": True}
        if path.startswith("_inference"):
            return {}
        if path.endswith("_refresh"):
            return {}
        if path.endswith("_count"):
            ((field, value),) = json["query"]["term"].items()
            return {"count": sum(1 for d in self.docs.values() if d.get(field) == value)}
        if "_delete_by_query" in path:
            ((field, value),) = json["query"]["term"].items()
            for k in [k for k, d in self.docs.items() if d.get(field) == value]:
                del self.docs[k]
            return {}
        if path == "_bulk":
            lines = ndjson.decode().strip().split("\n")
            items = []
            for a, s in zip(lines[::2], lines[1::2]):
                cid = j.loads(a)["index"]["_id"]
                if self.fail_first.get(cid, 0) > 0:
                    self.fail_first[cid] -= 1
                    items.append({"index": {"_id": cid, "status": 429, "error": {"type": "busy"}}})
                else:
                    self.docs[cid] = j.loads(s)
                    items.append({"index": {"_id": cid, "status": 201}})
            return {"errors": any("error" in i["index"] for i in items), "items": items}
        raise AssertionError(f"unexpected call {method} {path}")


def make_pdf(path, pages):
    import pymupdf

    d = pymupdf.open()
    for t in pages:
        p = d.new_page()
        p.insert_textbox(pymupdf.Rect(50, 50, 550, 780), t, fontsize=9)
    d.save(path)


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "files"
    root.mkdir()
    make_pdf(root / "a.pdf", [("Alpha paragraph. " * 60)] * 3)
    (root / "b.txt").write_text("line one\n" + "text " * 800 + "\nlast line", encoding="utf-8")
    return root


def cfg(tmp_path):
    base = load_settings(env={}, env_file=None)  # pure defaults, never reads .env
    return replace(base, data_dir=tmp_path / "data")


def run(corpus, tmp_path, es, *extra):
    out = []
    code = ingest.main(
        ["--path", str(corpus), *extra],
        es=es,
        settings=cfg(tmp_path),
        out=out.append,
        sleep=lambda s: None,
    )
    return code, out


def test_dry_run_never_touches_elasticsearch(corpus, tmp_path):
    es = FakeES()
    code, out = run(corpus, tmp_path, es, "--dry-run")
    assert code == 0 and es.calls == []
    assert any("a.pdf" in l and "chunks" in l for l in out)


def test_ingest_then_second_run_creates_no_duplicates(corpus, tmp_path):
    es = FakeES()
    code, _ = run(corpus, tmp_path, es)
    assert code == 0
    n = len(es.docs)
    assert n > 3 and all("content_semantic" in d for d in es.docs.values())
    assert {d["page_number"] for d in es.docs.values() if d["filename"] == "a.pdf"} == {1, 2, 3}
    assert all("start_line" in d for d in es.docs.values() if d["filename"] == "b.txt")
    code, out = run(corpus, tmp_path, es)
    assert code == 0 and len(es.docs) == n and sum("already indexed" in l for l in out) == 2


def test_interrupted_document_is_cleaned_and_completed(corpus, tmp_path):
    es = FakeES()
    run(corpus, tmp_path, es)
    full = dict(es.docs)
    victim = next(k for k, d in es.docs.items() if d["filename"] == "b.txt")
    del es.docs[victim]  # simulate a half-finished run
    _code, out = run(corpus, tmp_path, es)
    assert len(es.docs) == len(full) and any("interrupted" in l for l in out)


def test_corrupt_pdf_reported_and_skipped_run_continues(corpus, tmp_path):
    (corpus / "bad.pdf").write_bytes(b"%PDF-1.4 this is not a pdf")
    (corpus / "empty.txt").write_text("", encoding="utf-8")
    es = FakeES()
    code, out = run(corpus, tmp_path, es)
    assert code == 1
    assert any("bad.pdf: FAILED" in l for l in out) and any("empty.txt: FAILED" in l for l in out)
    assert {d["filename"] for d in es.docs.values()} == {"a.pdf", "b.txt"}
    log = (tmp_path / "data" / "ingest" / "ingest_errors.jsonl").read_text().splitlines()
    assert len(log) == 2


def test_no_error_file_when_everything_succeeds(corpus, tmp_path):
    run(corpus, tmp_path, FakeES())
    assert not (tmp_path / "data" / "ingest" / "ingest_errors.jsonl").exists()
    assert list((tmp_path / "data" / "ingest").glob("summary-*.json"))


def test_failed_items_are_retried(corpus, tmp_path):
    es = FakeES()
    es_first = FakeES(fail_first={})
    # pick a real chunk id after a dry look: first chunk of b.txt
    run(corpus, tmp_path, es_first)
    cid = next(k for k, d in es_first.docs.items() if d["filename"] == "b.txt")
    es = FakeES(fail_first={cid: 2})
    code, _ = run(corpus, tmp_path, es)
    assert code == 0 and cid in es.docs


def test_permanent_item_failure_is_logged(corpus, tmp_path):
    es_first = FakeES()
    run(corpus, tmp_path, es_first)
    cid = next(k for k, d in es_first.docs.items() if d["filename"] == "b.txt")
    es = FakeES(fail_first={cid: 99})
    code, _ = run(corpus, tmp_path, es)
    assert code == 1 and cid not in es.docs
    rows = [
        json.loads(l)
        for l in (tmp_path / "data" / "ingest" / "ingest_errors.jsonl").read_text().splitlines()
    ]
    assert rows[0]["_id"] == cid and rows[0]["stage"] == "bulk"


def test_replace_removes_older_version_of_same_filename(corpus, tmp_path):
    es = FakeES()
    run(corpus, tmp_path, es)
    {k for k, d in es.docs.items() if d["filename"] == "b.txt"}
    (corpus / "b.txt").write_text("completely different content " * 200, encoding="utf-8")
    _code, out = run(corpus, tmp_path, es)
    assert any("another version" in l for l in out)
    run(corpus, tmp_path, es, "--replace")
    hashes = {d["content_hash"] for d in es.docs.values() if d["filename"] == "b.txt"}
    assert len(hashes) == 1


def test_refuses_to_write_to_a_legacy_index(corpus, tmp_path):
    bad = replace(cfg(tmp_path), corpus_index="books_passages_phase2e_v1")
    out = []
    assert ingest.main(["--path", str(corpus)], es=FakeES(), settings=bad, out=out.append) == 2


def test_tier_and_only_selection(tmp_path):
    for n in ("nist-csf-2.pdf", "rfc-9293.pdf", "gutenberg-alice.txt", "other.pdf", "x.csv"):
        (tmp_path / n).write_bytes(b"x")
    files, skipped = ingest.select_files(tmp_path, {1}, [])
    assert [f.name for f in files] == ["nist-csf-2.pdf"]
    files, _ = ingest.select_files(tmp_path, set(), ["alice"])
    assert [f.name for f in files] == ["gutenberg-alice.txt"]
    assert ("x.csv", "unsupported file type") in skipped


def test_no_semantic_run_omits_semantic_field(corpus, tmp_path):
    es = FakeES()
    es.semantic = False
    code, _ = run(corpus, tmp_path, es, "--no-semantic")
    assert code == 0 and all("content_semantic" not in d for d in es.docs.values())
