"""Batch 27: chunker v3 (header/footer cleaning, heading rule, page flow) and the ingest guard.

Imports happen inside the tests (import-order lesson: no global state at module level).
"""
from types import SimpleNamespace

VOCAB = [
    "alpha", "bravo", "cedar", "delta", "ember", "fjord", "garnet", "harbor", "indigo", "juniper",
    "kernel", "lantern", "marble", "nectar", "onyx", "pillar", "quartz", "ripple", "sierra", "tundra",
    "umber", "velvet", "willow", "xenon", "yonder", "zephyr", "amber", "basalt", "cobalt", "dune",
    "echo", "flint", "glacier", "hollow", "iris", "jasper", "knoll", "lagoon", "meadow", "nimbus",
]


def _body(page, sentences=30):
    parts = []
    for k in range(sentences):
        a = VOCAB[(page * 7 + k * 3) % 40]
        b = VOCAB[(page + k * 5) % 40]
        c = VOCAB[(page * 11 + k) % 40]
        parts.append(f"The {a} {b} handles {c} during stage {page}.")
    return " ".join(parts)


def _pages(n=12):
    return [
        (i, f"ACME Standard 2025\nIncident Guide\n{_body(i)}\nPage {i}\nACME Standard 2025")
        for i in range(1, n + 1)
    ]


def test_clean_pages_removes_running_lines_and_page_numbers():
    from chunking3 import clean_pages

    cleaned, removed = clean_pages(_pages())
    assert removed >= 12 * 4
    for _, text in cleaned:
        assert "ACME Standard" not in text
        assert "Incident Guide" not in text
        assert "Page " not in text
        assert "handles" in text


def test_chunker_v3_output_is_clean_and_in_page_order():
    from chunking import chunk_pages
    from chunking3 import chunk_pages_v3

    pages = _pages()
    new = chunk_pages_v3(pages)
    old = chunk_pages(pages)
    assert new and len(new) <= len(old)
    assert new[0].page_number == 1
    numbers = [c.page_number for c in new]
    assert numbers == sorted(numbers) and max(numbers) <= 12
    for c in new:
        assert len(c.text) <= 1400
        assert "ACME Standard" not in c.text and "Incident Guide" not in c.text
    assert [c.chunk_index for c in new] == list(range(len(new)))


def test_a_passage_can_continue_across_a_page_break():
    from chunking3 import chunk_pages_v3

    chunks = chunk_pages_v3(_pages())
    assert any("stage 1." in c.text and "stage 2." in c.text for c in chunks)


def _heading_text():
    para = " ".join("This sentence belongs to a plain paragraph of the standard." for _ in range(5))
    first = "\n\n".join([para] * 4)
    return first + "\n\n2.1. Test Heading\n\n" + para + "\n\n" + para + "\n\n" + para


def test_v2_can_end_on_a_heading_and_v3_does_not():
    from chunking import chunk_text
    from chunking3 import chunk_stream

    text = _heading_text()
    old_last = chunk_text(text)[0].text.splitlines()[-1].strip()
    assert old_last == "2.1. Test Heading"  # the problem this batch fixes
    new = chunk_stream(text)
    for c in new:
        assert c.text.splitlines()[-1].strip() != "2.1. Test Heading"
    assert any("2.1. Test Heading" in c.text for c in new)


def test_section_label_is_filled_from_numbered_headings():
    from chunking3 import chunk_pages_v3

    page = "2.1. First Topic\n" + _body(1, 40)
    chunks = chunk_pages_v3([(1, page)])
    assert chunks[0].section == "2.1. First Topic"


def test_ingest_refuses_chunker_3_into_the_v1_index():
    import ingest

    lines = []
    cfg = SimpleNamespace(corpus_index="intellisearch_corpus_v1")
    try:
        rc = ingest.main(["--path", ".", "--chunker", "3", "--dry-run"], settings=cfg, out=lines.append)
    finally:
        ingest.CHUNKER_VERSION = 2
    assert rc == 2
    assert any("intellisearch_corpus_v1" in x and "Refusing" in x for x in lines)


def test_extract_pdf_uses_chunker_v3_when_selected():
    import ingest
    import pymupdf

    doc = pymupdf.open()
    for i in range(1, 9):
        page = doc.new_page()
        page.insert_text((72, 40), "ACME Standard 2025", fontsize=9)
        page.insert_text((72, 52), "Incident Guide", fontsize=9)
        y = 100
        for k in range(0, 24):
            page.insert_text((72, y), _body(i, 1) + f" Item {k} of page {i}.", fontsize=9)
            y += 14
        page.insert_text((72, 800), f"Page {i}", fontsize=9)
        page.insert_text((72, 812), "ACME Standard 2025", fontsize=9)
    data = doc.tobytes()
    doc.close()
    cfg = SimpleNamespace(chunk_target_chars=1400, chunk_overlap_chars=180, max_chunks_per_doc=3000)
    try:
        ingest.CHUNKER_VERSION = 2
        old, _ = ingest.extract_pdf(data, cfg)
        ingest.CHUNKER_VERSION = 3
        new, _ = ingest.extract_pdf(data, cfg)
    finally:
        ingest.CHUNKER_VERSION = 2
    assert any("ACME Standard" in c.text for c in old)
    assert not any("ACME Standard" in c.text or "Incident Guide" in c.text for c in new)
