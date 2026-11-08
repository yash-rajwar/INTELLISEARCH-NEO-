import re
import pytest
from chunking import (ChunkLimitError, chunk_lines, chunk_pages, chunk_text,
                      strip_gutenberg)

WORDS = ("alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo "
         "lima mike november oscar papa quebec romeo sierra tango").split()


def make_text(n_chars: int, markers: dict[float, str] | None = None) -> str:
    out, i, size = [], 0, 0
    while size < n_chars:
        line = " ".join(WORDS[(i + k) % len(WORDS)] for k in range(12)) + f" line{i:06d}."
        if (i + 1) % 7 == 0:
            line += "\n"
        out.append(line)
        size += len(line) + 1
        i += 1
    text = "\n".join(out)[:n_chars]
    for frac, m in (markers or {}).items():
        pos = int(n_chars * frac)
        text = text[:pos] + f" {m} " + text[pos + len(m) + 2:]
    return text


def test_markers_all_findable_in_230k():
    marks = {0.05: "ZXQ05", 0.25: "ZXQ25", 0.50: "ZXQ50", 0.75: "ZXQ75", 0.95: "ZXQ95"}
    text = make_text(230_000, marks)
    chunks = chunk_text(text)
    joined = "\n".join(c.text for c in chunks)
    for m in marks.values():
        assert m in joined


def test_no_chunk_exceeds_target_by_10_percent_and_no_word_cut():
    text = make_text(60_000)
    for c in chunk_text(text, 1400, 180):
        assert len(c.text) <= 1400 * 1.1
        assert c.start_char == 0 or text[c.start_char - 1].isspace()
        assert c.end_char == len(text) or text[c.end_char].isspace() or text[c.end_char - 1] in ".!?"


def test_chunks_cover_all_text():
    text = make_text(50_000)
    chunks = chunk_text(text)
    covered = bytearray(len(text))
    for c in chunks:
        assert text[c.start_char:c.end_char] == c.text
        covered[c.start_char:c.end_char] = b"\x01" * (c.end_char - c.start_char)
    for m in re.finditer(r"\S", text):
        assert covered[m.start()], f"uncovered char at {m.start()}"


def test_short_chunks_only_last():
    chunks = chunk_text(make_text(40_000))
    for c in chunks[:-1]:
        assert len(c.text) >= 0.4 * 1400 - 5


def test_limit_raises_instead_of_truncating():
    with pytest.raises(ChunkLimitError):
        chunk_text(make_text(100_000), max_chunks=10)


def test_300_page_pdf_last_page_marker():
    pages = [(p, f"Page {p} body. " + make_text(2500) + (" ENDMARKER " if p == 300 else ""))
             for p in range(1, 301)]
    chunks = chunk_pages(pages)
    assert max(c.page_number for c in chunks) == 300
    assert any("ENDMARKER" in c.text and c.page_number == 300 for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_line_ranges_point_at_right_lines():
    lines = [f"LINE{i:05d} " + "word " * 12 for i in range(1, 2001)]
    text = "\n".join(lines)
    for c in chunk_lines(text):
        got = re.findall(r"LINE(\d{5})", c.text)
        assert c.start_line <= int(got[0]) <= c.end_line
        assert c.start_line <= int(got[-1]) <= c.end_line
        assert c.end_line - c.start_line <= len(got) + 1


def test_gutenberg_strip_keeps_original_line_numbers():
    head = "Title\nAuthor\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\n"
    foot = "\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nlicence text\n"
    body_lines = [f"BODY{i:04d} " + "word " * 10 for i in range(1, 400)]
    text = head + "\n".join(body_lines) + foot
    body, first_line = strip_gutenberg(text)
    assert "PROJECT GUTENBERG" not in body and "licence text" not in body
    assert first_line == 4
    for c in chunk_lines(body, first_line):
        n = int(re.findall(r"BODY(\d{4})", c.text)[0])
        assert c.start_line <= n + 3 <= c.end_line  # BODY0001 sits on original line 4


def test_no_markers_returns_unchanged():
    assert strip_gutenberg("plain text\nno markers") == ("plain text\nno markers", 1)


def test_deterministic():
    t = make_text(30_000)
    assert [c.text for c in chunk_text(t)] == [c.text for c in chunk_text(t)]
