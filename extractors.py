"""Extract trusted plain text from uploaded public/local samples. Never execute file contents."""

import io
from config import MAX_PAGES

# Safety limit: one upload may not create more passages than this.
MAX_PASSAGES = 3000


def text_pages(data: bytes, extension: str, ocr=False):
    if extension == ".txt":
        text = data.decode("utf-8-sig", errors="replace").replace("\x00", "")
        return [{"page": None, "text": text}], 0
    if extension == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported. Please use an unencrypted copy.")
        if len(reader.pages) > MAX_PAGES:
            raise ValueError(f"PDF exceeds {MAX_PAGES} pages.")
        output = []
        missing = []
        for i, pg in enumerate(reader.pages, 1):
            txt = (pg.extract_text() or "").replace("\x00", "")
            if txt.strip():
                output.append({"page": i, "text": txt})
            else:
                missing.append(i)
        if ocr and missing:
            from ocr import ocr_pdf_pages

            ocr_text = ocr_pdf_pages(data, missing)
            for page_num, txt in ocr_text.items():
                if txt.strip():
                    output.append({"page": page_num, "text": txt, "ocr": True})
        output.sort(key=lambda p: p["page"])
        if not output:
            raise ValueError(
                "No searchable text found. Enable OCR for scanned PDFs (requires Tesseract)."
            )
        return output, len(reader.pages)
    if extension == ".docx":
        from docx import Document
        from docx.oxml.ns import qn

        doc = Document(io.BytesIO(data))
        output = []
        for elem in doc.element.body.iterchildren():
            if elem.tag == qn("w:p"):
                s = "".join(elem.itertext()).strip()
                if s:
                    output.append(s)
            elif elem.tag == qn("w:tbl"):
                for row in elem.findall(qn("w:tr")):
                    cells = []
                    for cell in row.findall(qn("w:tc")):
                        cells.append(" ".join(x for x in cell.itertext() if x.strip()))
                    if cells:
                        output.append(" | ".join(cells))
        if not output:
            raise ValueError("DOCX does not contain readable text.")
        return [{"page": None, "text": "\n".join(output)}], 0
    raise ValueError("Unsupported file extension.")


def make_chunks(pages, target=1400, overlap=180):
    # Split page text into overlapping passages. Nothing is cut off silently:
    # a file that needs more than MAX_PASSAGES passages is refused instead.
    chunks = []
    for p in pages:
        original = p["text"]
        if not original.strip():
            continue
        start = 0
        while start < len(original):
            end = min(len(original), start + target)
            if end < len(original):
                cutoff = max(
                    original.rfind("\n", start + int(target * 0.6), end),
                    original.rfind(" ", start + int(target * 0.6), end),
                )
                if cutoff > start:
                    end = cutoff
            value = original[start:end].strip()
            if value:
                chunks.append({"page_number": p["page"], "content": value})
                if len(chunks) > MAX_PASSAGES:
                    raise ValueError(
                        f"This file would create more than {MAX_PASSAGES} passages. "
                        "Please upload a smaller file or split it."
                    )
            if end >= len(original):
                break
            start = max(start + 1, end - overlap)
    if not chunks:
        raise ValueError("No readable text could be chunked.")
    return chunks
