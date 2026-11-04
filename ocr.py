"""Optional OCR for image-only PDF pages. Uses installed Tesseract via PyMuPDF."""
import os
from pathlib import Path

def available():
    try:
        import fitz
    except ImportError:
        return False, 'PyMuPDF is missing.'
    tessdata=os.environ.get('TESSDATA_PREFIX','').strip()
    candidates=[Path(tessdata)] if tessdata else []
    candidates += [Path(r'C:\Program Files\Tesseract-OCR\tessdata'),Path(r'C:\Program Files (x86)\Tesseract-OCR\tessdata')]
    for folder in candidates:
        if folder.is_dir() and (folder/'eng.traineddata').is_file():return True, str(folder)
    return False, 'Tesseract English language data not found. Install Tesseract and set TESSDATA_PREFIX to its tessdata folder.'

def ocr_pdf_pages(data,missing_page_numbers):
    ok,tessdata=available()
    if not ok:raise ValueError('OCR unavailable: '+tessdata)
    if len(missing_page_numbers)>40:
        raise ValueError('At most 40 scanned pages per PDF can be OCR processed in this showcase.')
    import fitz
    output={}
    with fitz.open(stream=data,filetype='pdf') as doc:
        for number in missing_page_numbers:
            try:
                page=doc[number-1]
                tp=page.get_textpage_ocr(language='eng',dpi=150,full=True,tessdata=tessdata)
                output[number]=(page.get_text(textpage=tp) or '').replace('\x00','')
            except Exception as exc:
                raise ValueError(f'OCR failed on page {number}. Confirm installed Tesseract and English language pack: {exc}') from exc
    return output
