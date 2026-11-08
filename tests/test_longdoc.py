import unittest

# Imports happen inside the tests on purpose (config must load after other test modules).


def long_text(paragraphs):
    return "\n\n".join(
        f"Section {i} discusses topic{i} in considerable detail for the careful reader." for i in range(paragraphs)
    )


class SectionAndSummaryTests(unittest.TestCase):
    def test_sections_cover_the_whole_text(self):
        from longdoc import SECTION_CHARS, split_sections

        text = long_text(3000) + "\n\nENDMARK final paragraph."
        sections = split_sections(text)
        self.assertGreater(len(sections), 2)
        self.assertIn("ENDMARK", sections[-1])
        self.assertTrue(all(len(s) <= SECTION_CHARS for s in sections))

    def test_short_text_is_one_section_and_whole_document(self):
        from longdoc import summarize_long

        r = summarize_long(long_text(20), 3)
        self.assertEqual(r["sections"], 1)
        self.assertEqual(r["coverage"], "the whole document")
        self.assertTrue(r["sentences"])

    def test_long_text_is_summarised_in_sections(self):
        from longdoc import summarize_long

        r = summarize_long(long_text(3000), 6)
        self.assertGreaterEqual(r["sections"], 3)
        self.assertTrue(0 < len(r["sentences"]) <= 6)
        self.assertEqual(r["coverage"], "the whole document")

    def test_cut_short_text_says_so(self):
        from longdoc import summarize_long

        r = summarize_long(long_text(20), 3, total_chars=999999)
        self.assertIn("first", r["coverage"])
        self.assertIn("999,999", r["coverage"])


class ChunkAndAlignTests(unittest.TestCase):
    def test_a_long_unbroken_paragraph_still_makes_progress(self):
        from longdoc import chunk_text

        chunks = chunk_text("word " * 2000, 100)
        self.assertGreater(len(chunks), 10)
        self.assertTrue(all(len(c) <= 200 for c in chunks))

    def test_near_duplicate_passages_are_paired_and_flagged(self):
        from longdoc import aligned_passages

        left = (
            "The organization shall retain audit logs for incident response and review them regularly.\n\n"
            "Gardening notes about tomatoes, soil, sunlight and watering schedules in spring."
        )
        right = (
            "The organization shall retain audit logs for incident response and review them every month.\n\n"
            "Completely different text on bridges, rivers and steel construction methods."
        )
        r = aligned_passages(left, right, chunk=100)
        top = r["pairs"][0]
        self.assertTrue(top["near_duplicate"])
        self.assertIn("audit logs", top["left"])
        self.assertIn("audit logs", top["right"])
        self.assertIn("does not measure meaning", r["measure"])
        self.assertFalse(r["sampled"])

    def test_very_long_documents_are_sampled_and_say_so(self):
        from longdoc import aligned_passages

        text = long_text(1000)
        r = aligned_passages(text, text, chunk=60, limit_chunks=100)
        self.assertTrue(r["sampled"])
        self.assertLessEqual(r["left_passages"], 100)


class ExplainFuzzyTests(unittest.TestCase):
    def test_fuzzy_mode_has_an_explanation(self):
        from intelligence import explain

        text = explain("recieve", "you receive it", "fuzzy")["description"]
        self.assertIn("Fuzzy", text)
        self.assertNotIn("not specified", text)


if __name__ == "__main__":
    unittest.main()
