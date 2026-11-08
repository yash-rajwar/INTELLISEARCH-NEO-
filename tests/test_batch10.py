import unittest
from unittest import mock

# Everything is imported inside the tests on purpose (config must load after other test modules).
# app.py is not imported either, because that changes the shared logger.


class CitationCheckTests(unittest.TestCase):
    def test_valid_and_invalid_numbers_are_separated(self):
        from askcheck import check_citations

        r = check_citations("It is so [1] and also [9], again [1] and [0].", 5)
        self.assertEqual(r["valid"], [1])
        self.assertEqual(r["invalid"], [0, 9])
        self.assertTrue(r["has_citations"])

    def test_answer_without_citations_is_flagged(self):
        from askcheck import check_citations

        r = check_citations("No brackets here.", 5)
        self.assertFalse(r["has_citations"])
        self.assertEqual(r["valid"], [])


class OverlapNoticeTests(unittest.TestCase):
    def test_unrelated_passages_trigger_the_notice(self):
        from askcheck import no_term_overlap

        hits = [{"passage": "Gardening tips for spring tomatoes."}]
        self.assertTrue(no_term_overlap("penalty for password misuse", hits))

    def test_a_shared_word_clears_the_notice(self):
        from askcheck import no_term_overlap

        hits = [{"passage": "Gardening tips."}, {"passage": "A password must be kept secret."}]
        self.assertFalse(no_term_overlap("penalty for password misuse", hits))

    def test_question_without_content_words_claims_nothing(self):
        from askcheck import no_term_overlap

        self.assertFalse(no_term_overlap("the of and", [{"passage": "anything"}]))


class OllamaStatusTests(unittest.TestCase):
    def test_not_configured(self):
        import llm

        with mock.patch.object(llm, "MODEL", ""):
            self.assertEqual(llm.status()["state"], "not_configured")

    def test_not_running(self):
        import llm
        import requests

        with mock.patch.object(llm, "MODEL", "m"), mock.patch.object(
            llm.requests, "get", side_effect=requests.ConnectionError("down")
        ):
            self.assertEqual(llm.status()["state"], "not_running")

    def test_model_missing_and_ready(self):
        import llm

        reply = mock.Mock()
        reply.json.return_value = {"models": [{"name": "other:latest"}]}
        with mock.patch.object(llm, "MODEL", "m"), mock.patch.object(llm.requests, "get", return_value=reply):
            self.assertEqual(llm.status()["state"], "model_missing")
        reply.json.return_value = {"models": [{"name": "m:latest"}]}
        with mock.patch.object(llm, "MODEL", "m"), mock.patch.object(llm.requests, "get", return_value=reply):
            self.assertEqual(llm.status()["state"], "ready")

    def test_generate_asks_for_a_low_temperature(self):
        import llm

        reply = mock.Mock()
        reply.json.return_value = {"message": {"content": "ok [1]"}}
        with mock.patch.object(llm, "MODEL", "m"), mock.patch.object(
            llm.requests, "post", return_value=reply
        ) as post:
            self.assertEqual(llm.generate("q", ["source text"]), "ok [1]")
        self.assertEqual(post.call_args.kwargs["json"]["options"]["temperature"], 0.1)


class EvidenceNumberingTests(unittest.TestCase):
    def test_citations_stay_in_step_when_a_hit_is_skipped(self):
        from intelligence import evidence_reply

        hits = [
            {"passage": "", "index": "i", "id": "0", "title": "empty"},
            {"passage": "A password must be kept secret.", "index": "i", "id": "1", "title": "t"},
        ]
        result = evidence_reply("password", hits)
        self.assertEqual([e["citation"] for e in result], [1])


if __name__ == "__main__":
    unittest.main()
