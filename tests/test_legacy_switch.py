import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import build_sources


class LegacySwitchTests(unittest.TestCase):
    def test_off_leaves_only_uploads(self):
        self.assertEqual(list(build_sources(False)), ["uploads"])

    def test_on_restores_all_five_in_the_old_order(self):
        self.assertEqual(
            list(build_sources(True)),
            ["passages", "books", "documents", "uploads", "uploads_v2"],
        )

    def test_legacy_index_names_never_appear_when_off(self):
        names = {index for index, _ in build_sources(False).values()}
        self.assertFalse(names & {"books_passages_phase2e_v1", "books_20", "demo_documents"})


if __name__ == "__main__":
    unittest.main()