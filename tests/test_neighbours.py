import unittest

# Imports happen inside the tests on purpose (config must load after other test modules).


class NeighbourIdTests(unittest.TestCase):
    def test_corpus_ids_use_five_digits(self):
        from config import CORPUS_INDEX
        from search import neighbour_hit_ids

        self.assertEqual(
            neighbour_hit_ids(CORPUS_INDEX, "abc", 90),
            [(89, "abc_00089"), (91, "abc_00091")],
        )

    def test_upload_ids_use_four_digits(self):
        from config import UP_INDEX
        from search import neighbour_hit_ids

        self.assertEqual(
            neighbour_hit_ids(UP_INDEX, "abc", 7),
            [(6, "abc_0006"), (8, "abc_0008")],
        )

    def test_first_passage_has_no_previous_one(self):
        from config import CORPUS_INDEX
        from search import neighbour_hit_ids

        self.assertEqual(neighbour_hit_ids(CORPUS_INDEX, "abc", 0), [(1, "abc_00001")])
        self.assertEqual(neighbour_hit_ids(CORPUS_INDEX, "abc", None), [(1, "abc_00001")])


if __name__ == "__main__":
    unittest.main()
