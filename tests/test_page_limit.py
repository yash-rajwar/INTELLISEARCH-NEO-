import io
import unittest

from pypdf import PdfWriter

import extractors


def blank_pdf(pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class PageLimitTests(unittest.TestCase):
    def test_default_limit_still_refuses_long_pdfs(self):
        data = blank_pdf(extractors.MAX_PAGES + 1)
        with self.assertRaises(ValueError) as caught:
            extractors.text_pages(data, ".pdf")
        self.assertIn("exceeds", str(caught.exception))

    def test_a_higher_limit_is_honoured(self):
        data = blank_pdf(extractors.MAX_PAGES + 1)
        try:
            extractors.text_pages(data, ".pdf", max_pages=extractors.MAX_PAGES + 50)
        except ValueError as exc:
            # blank pages may fail for another reason (no text), but never for length
            self.assertNotIn("exceeds", str(exc))


if __name__ == "__main__":
    unittest.main()
