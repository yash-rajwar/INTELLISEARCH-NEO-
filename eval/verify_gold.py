"""Locate every gold_span in the source files (no Elasticsearch involved) and freeze the question file.

    python eval\\verify_gold.py            reads eval\\questions_draft.csv, writes eval\\questions.csv
It matches on word tokens (ignores case, punctuation, line breaks and hyphen splits). PDF pages use the
same page numbers as the index. TXT lines use the original file's line numbers (same as the index).
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ROOT / "corpus" / "files"
TOK = re.compile(r"\w+")


def tokens(text):
    return [(m.group().lower(), m.start(), m.end()) for m in TOK.finditer(text)]


def find_all(hay, needle):
    n = len(needle)
    words = [t[0] for t in hay]
    return [i for i in range(len(words) - n + 1) if words[i : i + n] == needle]


def load_units(path):
    """-> list of (label, text). label = page number (PDF) or None (text)."""
    if path.suffix.lower() == ".pdf":
        import pymupdf

        doc = pymupdf.open(path)
        units = [(i + 1, doc[i].get_text().replace("\x00", "")) for i in range(len(doc))]
        doc.close()
        return units
    return [(None, path.read_bytes().decode("utf-8-sig", errors="replace").replace("\x00", ""))]


def nearest(units, gold):
    g = set(zip(gold, gold[1:]))
    best = (0, None, None)
    for label, text in units:
        toks = tokens(text)
        w = [t[0] for t in toks]
        size = len(gold)
        for i in range(0, max(1, len(w) - size + 1), max(1, size // 3)):
            hit = len(g & set(zip(w[i : i + size], w[i + 1 : i + size])))
            if hit > best[0]:
                best = (hit, label, text[toks[i][1] : toks[min(i + size, len(toks)) - 1][2]])
    return best


def main():
    src = ROOT / "eval" / "questions_draft.csv"
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig", newline="")))
    cache, missing = {}, 0
    for r in rows:
        if not r["gold_span"]:
            continue
        path = FILES / r["expected_doc"]
        if r["expected_doc"] not in cache:
            if not path.exists():
                missing += 1
                print(f"FILE MISSING {r['id']}: {path}")
                continue
            cache[r["expected_doc"]] = load_units(path)
        units = cache[r["expected_doc"]]
        gold = [t[0] for t in tokens(r["gold_span"])]
        hits = []
        for label, text in units:
            toks = tokens(text)
            for i in find_all(toks, gold):
                if label is not None:
                    hits.append(label)
                else:
                    a, b = toks[i][1], toks[i + len(gold) - 1][2]
                    hits.append((text.count("\n", 0, a) + 1, text.count("\n", 0, b) + 1))
        if not hits:
            missing += 1
            hit, label, window = nearest(units, gold)
            print(f"NOT FOUND {r['id']} ({r['expected_doc']}): {r['gold_span'][:70]}")
            if window:
                print(f"    closest text (page/unit {label}): {' '.join(window.split())[:260]}")
            continue
        first = hits[0]
        if isinstance(first, tuple):
            r["expected_lines"] = f"{first[0]}-{first[1]}"
            where = f"lines {r['expected_lines']}"
        else:
            r["expected_page"] = str(first)
            where = f"page {first}"
        if len(hits) > 1:
            extra = ", ".join(
                str(h) if not isinstance(h, tuple) else f"{h[0]}-{h[1]}" for h in hits[1:6]
            )
            r["notes"] = (r["notes"] + "; " if r["notes"] else "") + f"also at: {extra}"
            where += f" (+{len(hits) - 1} more)"
        print(f"ok        {r['id']} {r['expected_doc']}: {where}")
    if missing:
        print(
            f"\n{missing} gold span(s) not found: questions.csv NOT written. Paste this output back."
        )
        return 1
    out = ROOT / "eval" / "questions.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nAll gold spans found. Wrote {out} ({len(rows)} questions).")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
