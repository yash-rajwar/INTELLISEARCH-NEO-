#!/usr/bin/env python3
"""Download the IntelliSearch demo corpus (public / openly licensed documents only).

Run from the repository root:

    python scripts/download_corpus.py              # download everything (tiers 1, 2 and 3)
    python scripts/download_corpus.py --tiers 1    # only the small, high-value core set
    python scripts/download_corpus.py --list       # show what would be downloaded
    python scripts/download_corpus.py --only rfc-9110,nist-800-61r3
    python scripts/download_corpus.py --force      # re-download even if a file exists

What it does
  * Tries each document's URLs in order and checks that the file really is a PDF or
    a text file (not an HTML error page).
  * If a landing page is returned instead of a PDF, looks for a PDF link on that page.
  * Saves files to  corpus/files/<id>.<pdf|txt>  and never modifies them afterwards.
  * Records source URL, licence note, size, page count and SHA-256 in corpus/manifest.csv.
  * On later runs it verifies files against the recorded SHA-256 and reports changes.
  * Writes corpus/ATTRIBUTION.md with the source and licence note for every document.
  * If a download fails, it tells you exactly where to save the file by hand. Re-run the
    script afterwards and it will register the manually saved file.

Only public-domain or openly licensed documents are in the catalogue. Licence notes are
a starting point: check each document's own notice before you rely on it.

Windows note: a missing certificate file named in REQUESTS_CA_BUNDLE / CURL_CA_BUNDLE /
SSL_CERT_FILE is ignored automatically (certificate checking stays on).

Exit codes: 0 = all fine, 1 = at least one download failed, 2 = a file changed upstream.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

try:  # pypdf is already a project dependency; only used to count pages
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

logging.getLogger("pypdf").setLevel(logging.ERROR)

USER_AGENT = "IntelliSearch-corpus-downloader/1.0 (student research project; public documents only)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
MIN_BYTES = {"pdf": 10_000, "txt": 2_000}
MAX_BYTES = 200 * 1024 * 1024
PAUSE_SECONDS = 1.0

# Licence notes (starting points, not legal advice).
NIST_LICENCE = (
    "US government work; NIST says its publications are generally not copyrighted in the US "
    "and grants a worldwide right to reprint for any foreign rights. Check the notice in the PDF."
)
IETF_LICENCE = (
    "IETF Trust Legal Provisions allow copying and distributing UNMODIFIED text with "
    "attribution. Do not edit the text."
)
INDIA_LICENCE = "Official Government of India publication. Check the site's reuse terms."
NASA_LICENCE = (
    "NASA-authored works are generally not copyrighted; confirm in NASA's reuse guidance "
    "and check for third-party figures."
)
GUTENBERG_LICENCE = (
    "Public domain in the US; Project Gutenberg terms apply. Check your local law, as "
    "Project Gutenberg advises. Files are kept unmodified."
)

NIST_PDF = "https://nvlpubs.nist.gov/nistpubs/{path}.pdf"
RFC_BASE = "https://www.rfc-editor.org/rfc/rfc{n}"
GUTENBERG_TEXT = (
    "https://www.gutenberg.org/cache/epub/{n}/pg{n}.txt",
    "https://www.gutenberg.org/ebooks/{n}.txt.utf-8",
)


@dataclass(frozen=True)
class Doc:
    """One document in the catalogue."""

    id: str
    tier: int
    collection: str
    title: str
    publisher: str
    kind: str  # default file type: "pdf" or "txt"
    urls: tuple[str, ...]
    licence: str
    manual_hint: str = ""
    link_hint: str = ""  # text a PDF link on a landing page should contain


def _gutenberg(doc_id: str, number: int, title: str) -> Doc:
    return Doc(
        id=doc_id,
        tier=3,
        collection="books",
        title=title,
        publisher="Project Gutenberg",
        kind="txt",
        urls=tuple(u.format(n=number) for u in GUTENBERG_TEXT),
        licence=GUTENBERG_LICENCE,
        manual_hint=f"Open https://www.gutenberg.org/ebooks/{number} and save the 'Plain Text UTF-8' file.",
    )


def build_catalogue() -> list[Doc]:
    """Return every document the project may download."""
    return [
        # ---- Tier 1: small, high-value core set ----
        Doc(
            "nist-800-61r3", 1, "standards",
            "NIST SP 800-61 Rev. 3: Incident Response Recommendations and Considerations "
            "for Cybersecurity Risk Management",
            "NIST", "pdf",
            (NIST_PDF.format(path="SpecialPublications/NIST.SP.800-61r3"),
             "https://csrc.nist.gov/pubs/sp/800/61/r3/final"),
            NIST_LICENCE,
            "Open https://csrc.nist.gov/pubs/sp/800/61/r3/final and use the PDF download link.",
            "800-61r3",
        ),
        Doc(
            "nist-csf-2", 1, "standards",
            "NIST Cybersecurity Framework (CSF) 2.0 (NIST CSWP 29)",
            "NIST", "pdf",
            (NIST_PDF.format(path="CSWP/NIST.CSWP.29"), "https://doi.org/10.6028/NIST.CSWP.29"),
            NIST_LICENCE,
            "Open https://doi.org/10.6028/NIST.CSWP.29 and use the PDF download link.",
            "cswp.29",
        ),
        Doc(
            "nist-ai-rmf-1", 1, "standards",
            "NIST AI Risk Management Framework 1.0 (NIST AI 100-1)",
            "NIST", "pdf",
            (NIST_PDF.format(path="ai/NIST.AI.100-1"), "https://doi.org/10.6028/NIST.AI.100-1"),
            NIST_LICENCE,
            "Open https://doi.org/10.6028/NIST.AI.100-1 and use the PDF download link.",
            "ai.100-1",
        ),
        Doc(
            "india-dpdp-2023", 1, "legal",
            "The Digital Personal Data Protection Act, 2023 (Act 22 of 2023)",
            "Government of India (India Code)", "pdf",
            ("https://www.indiacode.nic.in/bitstream/123456789/22037/2/a2023-22.pdf",
             "https://www.meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf",
             "https://www.trai.gov.in/sites/default/files/2024-09/DPDT_11082024.pdf"),
            INDIA_LICENCE,
            "Open https://www.indiacode.nic.in/bitstream/123456789/22037/2/a2023-22.pdf in your browser "
            "(the server is slow; wait for it) or search the Act on https://www.indiacode.nic.in.",
        ),
        Doc(
            "india-it-act-2000", 1, "legal",
            "The Information Technology Act, 2000 (as amended)",
            "Government of India (India Code)", "pdf",
            ("https://www.indiacode.nic.in/bitstream/123456789/13116/1/it_act_2000_updated.pdf",),
            INDIA_LICENCE,
            "Search 'Information Technology Act, 2000' on https://www.indiacode.nic.in "
            "and save the PDF.",
        ),
        Doc(
            "india-rti-2005", 1, "legal",
            "The Right to Information Act, 2005",
            "Government of India", "pdf",
            ("https://www.bis.gov.in/PDF/pdf/rti/RTI2005.pdf",
             "https://www.iitg.ac.in/rti/links/rti-act.pdf"),
            INDIA_LICENCE,
            "Open https://www.indiacode.nic.in/handle/123456789/2065 and download the Act's PDF.",
        ),
        Doc(
            "rfc-9110", 1, "rfc", "RFC 9110: HTTP Semantics", "IETF", "pdf",
            (RFC_BASE.format(n=9110) + ".pdf", RFC_BASE.format(n=9110) + ".txt"),
            IETF_LICENCE,
            "Open https://www.rfc-editor.org/rfc/rfc9110 and save the PDF or text version.",
        ),
        Doc(
            "rfc-8446", 1, "rfc",
            "RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3", "IETF", "pdf",
            (RFC_BASE.format(n=8446) + ".pdf", RFC_BASE.format(n=8446) + ".txt"),
            IETF_LICENCE,
            "Open https://www.rfc-editor.org/rfc/rfc8446 and save the PDF or text version.",
        ),
        # ---- Tier 2: the two large documents ----
        Doc(
            "nist-800-53r5", 2, "standards",
            "NIST SP 800-53 Rev. 5: Security and Privacy Controls for Information Systems "
            "and Organizations",
            "NIST", "pdf",
            (NIST_PDF.format(path="SpecialPublications/NIST.SP.800-53r5"),
             "https://doi.org/10.6028/NIST.SP.800-53r5"),
            NIST_LICENCE,
            "Open https://doi.org/10.6028/NIST.SP.800-53r5 and use the PDF download link.",
            "800-53r5",
        ),
        Doc(
            "nasa-se-handbook", 2, "engineering",
            "NASA Systems Engineering Handbook (NASA/SP-2016-6105 Rev 2)",
            "NASA", "pdf",
            ("https://www.nasa.gov/sites/default/files/atoms/files/nasa_systems_engineering_handbook_0.pdf",),
            NASA_LICENCE,
            "Search 'NASA Systems Engineering Handbook SP-2016-6105' on nasa.gov and save the PDF.",
        ),
        # ---- Tier 3: optional extras ----
        Doc(
            "nist-800-171r3", 3, "standards",
            "NIST SP 800-171 Rev. 3: Protecting Controlled Unclassified Information in "
            "Nonfederal Systems and Organizations",
            "NIST", "pdf",
            (NIST_PDF.format(path="SpecialPublications/NIST.SP.800-171r3"),
             "https://doi.org/10.6028/NIST.SP.800-171r3"),
            NIST_LICENCE,
            "Open https://doi.org/10.6028/NIST.SP.800-171r3 and use the PDF download link.",
            "800-171r3",
        ),
        Doc(
            "rfc-9293", 3, "rfc", "RFC 9293: Transmission Control Protocol (TCP)", "IETF", "pdf",
            (RFC_BASE.format(n=9293) + ".pdf", RFC_BASE.format(n=9293) + ".txt"),
            IETF_LICENCE,
            "Open https://www.rfc-editor.org/rfc/rfc9293 and save the PDF or text version.",
        ),
        _gutenberg("gutenberg-art-of-war", 132, "The Art of War (Sun Tzu, Lionel Giles translation)"),
        _gutenberg("gutenberg-pride-and-prejudice", 1342, "Pride and Prejudice (Jane Austen)"),
        _gutenberg("gutenberg-frankenstein", 84, "Frankenstein; or, The Modern Prometheus (Mary Shelley)"),
        _gutenberg("gutenberg-sherlock-holmes", 1661, "The Adventures of Sherlock Holmes (Arthur Conan Doyle)"),
        _gutenberg("gutenberg-dracula", 345, "Dracula (Bram Stoker)"),
        _gutenberg("gutenberg-alice", 11, "Alice's Adventures in Wonderland (Lewis Carroll)"),
    ]


# --------------------------------------------------------------------------------------
# File checks
# --------------------------------------------------------------------------------------

def extension_for(url: str, default: str) -> str:
    """Pick 'pdf' or 'txt' from a URL's suffix, falling back to the document's default."""
    suffix = Path(urlparse(url).path).suffix.lower().lstrip(".")
    return suffix if suffix in ("pdf", "txt") else default


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_head(path: Path, size: int = 2048) -> bytes:
    with path.open("rb") as handle:
        return handle.read(size)


def looks_like_html(path: Path) -> bool:
    head = read_head(path).lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html")) or b"<html" in head[:512]


def validate_file(path: Path, ext: str) -> tuple[bool, str]:
    """Check that a downloaded file is really what we expect. Returns (ok, reason)."""
    if not path.exists():
        return False, "file missing"
    if ext == "pdf" and read_head(path, 5) != b"%PDF-":
        return False, "does not start with %PDF- (probably an HTML page)"
    if ext == "txt" and looks_like_html(path):
        return False, "got an HTML page instead of text"
    size = path.stat().st_size
    if size < MIN_BYTES[ext]:
        return False, f"too small ({size} bytes)"
    return True, "ok"


def count_pdf_pages(path: Path) -> str:
    if PdfReader is None:
        return ""
    try:
        return str(len(PdfReader(str(path)).pages))
    except Exception:  # damaged or encrypted PDFs: page count is optional information
        return ""


def first_text_line(path: Path) -> str:
    """First non-empty line of a file's text (first page for PDFs), as plain ASCII, so the
    user can confirm the right document was saved. Returns '' if it cannot be read."""
    text = ""
    try:
        if path.suffix.lower() == ".pdf":
            if PdfReader is None:
                return ""
            text = PdfReader(str(path)).pages[0].extract_text() or ""
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # purely informational; never stop the download for this
        return ""
    for line in text.splitlines():
        line = " ".join(line.split())
        if len(line) >= 8:
            return line[:80].encode("ascii", "replace").decode("ascii")
    return ""


def find_pdf_links(html_path: Path, base_url: str, hint: str) -> list[str]:
    """Return PDF links found on a landing page, best matches first."""
    text = html_path.read_text(encoding="utf-8", errors="replace")
    links = []
    for match in re.finditer(r"""href\s*=\s*["']([^"']+\.pdf[^"']*)["']""", text, re.IGNORECASE):
        absolute = urljoin(base_url, match.group(1))
        if absolute not in links:
            links.append(absolute)
    wanted = hint.lower()
    links.sort(key=lambda link: 0 if wanted and wanted in link.lower() else 1)
    return links[:5]


# --------------------------------------------------------------------------------------
# Network
# --------------------------------------------------------------------------------------

CA_ENV_VARS = ("REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "SSL_CERT_FILE")


def clear_broken_ca_settings() -> list[str]:
    """Ignore certificate-file settings that point at a file that does not exist.

    Some installers set an environment variable such as REQUESTS_CA_BUNDLE to a certificate
    file that is later missing, which makes every HTTPS download fail. We drop such a setting
    for THIS run only. Certificate checking stays ON and uses Python's built-in certificates.
    """
    cleared = []
    for name in CA_ENV_VARS:
        value = os.environ.get(name)
        if value and not Path(value).exists():
            del os.environ[name]
            cleared.append(f"{name}={value}")
    return cleared


class FetchError(Exception):
    """A download attempt failed. `blocked` = server refused our User-Agent; `retry` = worth retrying."""

    def __init__(self, message: str, *, blocked: bool = False, retry: bool = False) -> None:
        super().__init__(message)
        self.blocked = blocked
        self.retry = retry


def _get_once(session: requests.Session, url: str, dest: Path, timeout: int, user_agent: str) -> str:
    """One download attempt. Returns the final URL after redirects."""
    try:
        with session.get(
            url, headers={"User-Agent": user_agent}, stream=True,
            timeout=timeout, allow_redirects=True,
        ) as response:
            code = response.status_code
            if code in (403, 406):
                raise FetchError(f"HTTP {code}", blocked=True)
            if code == 429 or code >= 500:
                raise FetchError(f"HTTP {code}", retry=True)
            if code >= 400:
                raise FetchError(f"HTTP {code}")
            written = 0
            with dest.open("wb") as handle:
                for block in response.iter_content(chunk_size=256 * 1024):
                    written += len(block)
                    if written > MAX_BYTES:
                        raise FetchError("file is larger than the safety limit")
                    handle.write(block)
            return response.url
    except requests.RequestException as exc:
        raise FetchError(f"{type(exc).__name__}: {exc}", retry=True) from exc
    except OSError as exc:  # for example a missing certificate file or a full disk
        raise FetchError(f"{type(exc).__name__}: {exc}") from exc


def fetch(session: requests.Session, url: str, dest: Path, timeout: int) -> str:
    """Download `url` to `dest`. Uses a polite User-Agent first and a browser-style one
    only if the server refuses the first (HTTP 403/406). Retries temporary errors."""
    error = FetchError("no attempt made")
    for user_agent in (USER_AGENT, BROWSER_USER_AGENT):
        blocked = False
        for attempt in range(1, 4):
            try:
                return _get_once(session, url, dest, timeout, user_agent)
            except FetchError as exc:
                error = exc
                if exc.blocked:
                    blocked = True
                    break
                if not exc.retry:
                    raise
                time.sleep(2 * attempt)
        if not blocked:
            break
    raise error


# --------------------------------------------------------------------------------------
# Manifest and attribution
# --------------------------------------------------------------------------------------

MANIFEST_COLUMNS = [
    "id", "collection", "tier", "title", "publisher", "filename", "source_url",
    "licence_note", "retrieved_on", "bytes", "pages", "sha256", "status",
]


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["id"]: row for row in csv.DictReader(handle) if row.get("id")}


def save_manifest(path: Path, rows: dict[str, dict[str, str]], order: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    known = [i for i in order if i in rows]
    extra = [i for i in rows if i not in order]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for doc_id in known + extra:
            writer.writerow(rows[doc_id])


def write_attribution(path: Path, rows: dict[str, dict[str, str]], order: list[str]) -> None:
    lines = [
        "# Corpus attribution",
        "",
        "Documents downloaded from the public sources below. Files are stored unmodified.",
        "Licence notes are starting points, not legal advice; check each document's own notice.",
        "",
    ]
    for doc_id in [i for i in order if i in rows] + [i for i in rows if i not in order]:
        row = rows[doc_id]
        if row.get("status") not in ("downloaded", "ok", "registered", "changed"):
            continue
        lines += [
            f"## {row['title']}",
            f"- Publisher: {row['publisher']}",
            f"- Source: {row['source_url']}",
            f"- Retrieved: {row['retrieved_on']}",
            f"- File: `{row['filename']}`",
            f"- Licence note: {row['licence_note']}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------------------
# Main work
# --------------------------------------------------------------------------------------

def find_existing(files_dir: Path, doc: Doc) -> Path | None:
    for ext in ("pdf", "txt"):
        candidate = files_dir / f"{doc.id}.{ext}"
        if candidate.exists():
            return candidate
    return None


def make_row(doc: Doc, path: Path, source_url: str, status: str, retrieved_on: str) -> dict[str, str]:
    ext = path.suffix.lstrip(".")
    return {
        "id": doc.id, "collection": doc.collection, "tier": str(doc.tier), "title": doc.title,
        "publisher": doc.publisher, "filename": path.name, "source_url": source_url,
        "licence_note": doc.licence, "retrieved_on": retrieved_on,
        "bytes": str(path.stat().st_size),
        "pages": count_pdf_pages(path) if ext == "pdf" else "",
        "sha256": sha256_of(path), "status": status,
    }


def download_doc(session: requests.Session, doc: Doc, files_dir: Path, timeout: int) -> tuple[Path, str] | None:
    """Try every URL for a document. Returns (saved path, url used) or None."""
    pending = list(doc.urls)
    tried: set[str] = set()
    while pending:
        url = pending.pop(0)
        if url in tried:
            continue
        tried.add(url)
        ext = extension_for(url, doc.kind)
        part = files_dir / f"{doc.id}.{ext}.part"
        try:
            final_url = fetch(session, url, part, timeout)
        except FetchError as exc:
            print(f"      - {url}\n        failed: {exc}")
            part.unlink(missing_ok=True)
            continue
        ok, reason = validate_file(part, ext)
        if ok:
            target = files_dir / f"{doc.id}.{ext}"
            part.replace(target)
            other = files_dir / f"{doc.id}.{'txt' if ext == 'pdf' else 'pdf'}"
            other.unlink(missing_ok=True)  # never keep two versions of the same document
            return target, final_url
        print(f"      - {url}\n        rejected: {reason}")
        if ext == "pdf" and looks_like_html(part):  # landing page: look for the real PDF link
            links = [link for link in find_pdf_links(part, final_url, doc.link_hint) if link not in tried]
            pending[0:0] = links  # best match first, ahead of the remaining fallback URLs
        part.unlink(missing_ok=True)
        time.sleep(PAUSE_SECONDS)
    return None


def run(args: argparse.Namespace, catalogue: list[Doc] | None = None) -> int:
    catalogue = catalogue if catalogue is not None else build_catalogue()
    tiers = {int(t) for t in args.tiers.split(",") if t.strip()}
    only = {name.strip() for name in args.only.split(",") if name.strip()}
    selected = [d for d in catalogue if (d.id in only if only else d.tier in tiers)]
    unknown = only - {d.id for d in catalogue}
    if unknown:
        print(f"Unknown document id(s): {', '.join(sorted(unknown))}")
        return 1

    if args.list:
        print(f"{'id':32} {'tier':4} {'type':4}  title")
        for doc in selected:
            print(f"{doc.id:32} {doc.tier:<4} {doc.kind:4}  {doc.title[:70]}")
        return 0

    for setting in clear_broken_ca_settings():
        print(f"Note: ignoring {setting} because that file does not exist. "
              "(Certificate checking is still ON.)")

    dest = Path(args.dest)
    files_dir = dest / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = dest / "manifest.csv"
    rows = load_manifest(manifest_path)
    order = [d.id for d in catalogue]
    today = date.today().isoformat()

    session = requests.Session()
    failed: list[Doc] = []
    changed: list[str] = []
    counts = {"downloaded": 0, "ok": 0, "registered": 0, "changed": 0}

    for number, doc in enumerate(selected, start=1):
        print(f"[{number}/{len(selected)}] {doc.id}  ({doc.title[:60]})")
        existing = find_existing(files_dir, doc)
        pinned = rows.get(doc.id, {}).get("sha256", "")

        if existing and not args.force:
            ext = existing.suffix.lstrip(".")
            ok, reason = validate_file(existing, ext)
            if not ok:
                print(f"    existing file is not valid ({reason}); moving it aside and downloading again")
                existing.replace(existing.with_suffix(existing.suffix + ".bad"))
                existing = None
            else:
                digest = sha256_of(existing)
                if pinned and digest != pinned:
                    status = "changed"
                    changed.append(doc.id)
                    print("    CHANGED: file differs from the checksum in manifest.csv "
                          "(use --force to download a fresh copy and re-pin)")
                elif pinned:
                    status = "ok"
                    print("    already downloaded, checksum matches")
                else:
                    status = "registered"
                    print("    found an existing file, registering it in the manifest")
                old_source = rows.get(doc.id, {}).get("source_url", "manually saved")
                rows[doc.id] = make_row(doc, existing, old_source, status, rows.get(doc.id, {}).get("retrieved_on", today))
                counts[status] += 1
                continue

        result = download_doc(session, doc, files_dir, args.timeout)
        if result is None:
            failed.append(doc)
            rows.setdefault(doc.id, {})
            print("    FAILED: could not download from any URL")
            continue
        path, used_url = result
        row = make_row(doc, path, used_url, "downloaded", today)
        rows[doc.id] = row
        counts["downloaded"] += 1
        size_mb = int(row["bytes"]) / (1024 * 1024)
        pages = f", {row['pages']} pages" if row["pages"] else ""
        print(f"    downloaded {size_mb:.1f} MB{pages}, sha256 {row['sha256'][:12]}...")
        first_line = first_text_line(path)
        if first_line:
            print(f"    starts with: {first_line}")
        time.sleep(PAUSE_SECONDS)

    rows = {k: v for k, v in rows.items() if v}
    save_manifest(manifest_path, rows, order)
    write_attribution(dest / "ATTRIBUTION.md", rows, order)

    print("\nSUMMARY")
    print(f"  downloaded: {counts['downloaded']}   already ok: {counts['ok']}   "
          f"registered: {counts['registered']}   changed: {counts['changed']}   failed: {len(failed)}")
    print(f"  files:      {files_dir}")
    print(f"  manifest:   {manifest_path}")
    if failed:
        print("\nMANUAL STEPS (these could not be downloaded automatically):")
        for doc in failed:
            print(f"  - {doc.id}: {doc.manual_hint}")
            print(f"    Save it as {files_dir / (doc.id + '.' + doc.kind)} and run this script again "
                  f"(it will register the file).")
        return 1
    if changed:
        return 2
    print("\nNext: check each licence note in corpus/ATTRIBUTION.md, then ingest the files.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download the IntelliSearch demo corpus.")
    parser.add_argument("--dest", default="corpus", help="output folder (default: ./corpus)")
    parser.add_argument("--tiers", default="1,2,3", help="comma-separated tiers to download (default: 1,2,3)")
    parser.add_argument("--only", default="", help="comma-separated document ids (overrides --tiers)")
    parser.add_argument("--list", action="store_true", help="list the selected documents and exit")
    parser.add_argument("--force", action="store_true", help="download again even if a file exists")
    parser.add_argument("--timeout", type=int, default=120, help="per-request timeout in seconds (default 120)")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(run(parse_args()))
