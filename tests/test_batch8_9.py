import unittest
from pathlib import Path
from unittest import mock

from jinja2 import Environment, FileSystemLoader

from querylog import make_query_logger  # no config import, safe at the top

# Everything that touches config/search is imported INSIDE the tests on purpose: the other test
# modules set up the environment first, and importing config earlier would change their results.
# These tests do not import app.py either, because that changes the shared logger.


class QueryLoggingSwitchTests(unittest.TestCase):
    def test_nothing_is_stored_when_logging_is_off(self):
        store = mock.Mock()
        make_query_logger(store, False)("q", "corpus", "keyword", 1, 2, "ok")
        store.assert_not_called()

    def test_query_is_stored_when_logging_is_on(self):
        store = mock.Mock()
        make_query_logger(store, True)("q", "corpus", "keyword", 1, 2, "ok")
        store.assert_called_once_with("q", "corpus", "keyword", 1, 2, "ok")


class FuzzyRuleTests(unittest.TestCase):
    def test_fuzzy_options_are_only_on_the_fuzzy_mode(self):
        from search import payload

        fuzzy = payload("recieve", "fuzzy")["query"]["multi_match"]
        self.assertEqual(fuzzy["fuzziness"], "AUTO")
        self.assertEqual(fuzzy["prefix_length"], 1)
        self.assertEqual(fuzzy["max_expansions"], 50)
        self.assertTrue(fuzzy["fuzzy_transpositions"])
        plain = payload("recieve", "keyword")["query"]["multi_match"]
        self.assertNotIn("prefix_length", plain)
        self.assertNotIn("fuzziness", plain)


class ResultHighlightTests(unittest.TestCase):
    def test_hits_template_marks_words_and_escapes_html(self):
        from search import highlight_html

        folder = Path(__file__).resolve().parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(str(folder)), autoescape=True)
        env.filters["hl"] = highlight_html
        hit = {
            "rank": 1,
            "type": "corpus",
            "title": "T",
            "passage": "<script>alert(1)</script> incident response",
            "score": None,
            "has_context": False,
            "source_url": "",
        }
        html = env.get_template("_hits.html").render(hits=[hit], q="incident", csrf_token="x")
        self.assertIn("<mark>incident</mark>", html)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
