import unittest

from search import group_hits, highlight_html


def hit(doc, page):
    return {
        "index": "i", "document_id": doc, "filename": doc + ".pdf", "title": doc,
        "type": "corpus", "file_type": "pdf", "page": page, "start_line": None,
    }  # fmt: skip


class GroupingTests(unittest.TestCase):
    def test_eleven_chunks_in_two_documents_give_two_groups(self):
        hits = [hit("a", p) for p in (23, 17, 18)] + [hit("b", 3)]
        groups = group_hits(hits)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["pages"], [17, 18, 23])
        self.assertEqual(len(groups[0]["hits"]), 3)
        self.assertEqual(groups[1]["rank"], 2)

    def test_empty_and_single(self):
        self.assertEqual(group_hits([]), [])
        self.assertEqual(len(group_hits([hit("a", 1)])), 1)

    def test_highlight_escapes_html(self):
        out = str(highlight_html("<script>alert(1)</script> incident response", "incident"))
        self.assertNotIn("<script>", out)
        self.assertIn("<mark>incident</mark>", out)

    def test_highlight_without_query_still_escapes(self):
        self.assertEqual(str(highlight_html("<b>x</b>", "")), "&lt;b&gt;x&lt;/b&gt;")


if __name__ == "__main__":
    unittest.main()
