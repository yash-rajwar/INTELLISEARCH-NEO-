import unittest
from unittest import mock
from urllib.parse import quote

import requests

import es_client
from config import CORPUS_INDEX, ES_INFERENCE_ID
from es_client import ES, ESFailure


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = {} if body is None else body
        self.content = b"x"
        self.text = str(self._body)

    def json(self):
        return self._body


class FakeSession:
    """Stands in for requests.Session. handler(method, url) returns a FakeResponse or raises."""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        return self.handler(method, url)

    def head(self, url, **kwargs):
        self.calls.append(("HEAD", url))
        return self.handler("HEAD", url)


def make(handler):
    session = FakeSession(handler)
    return ES(password="x", session=session), session


class RetryTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(es_client, "RETRY_DELAY", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_connection_error_is_retried(self):
        answers = [
            requests.ConnectionError("down"),
            FakeResponse(200, {"version": {"number": "9.0.0"}}),
        ]

        def handler(method, url):
            item = answers.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        es, session = make(handler)
        self.assertEqual(es.probe(), "9.0.0")
        self.assertEqual(len(session.calls), 2)

    def test_gives_up_after_the_last_attempt(self):
        def handler(method, url):
            raise requests.ConnectionError("down")

        es, session = make(handler)
        with self.assertRaises(ESFailure) as ctx:
            es.probe()
        self.assertIn("Cannot connect", str(ctx.exception))
        self.assertEqual(len(session.calls), es_client.CONNECT_ATTEMPTS)

    def test_client_errors_are_not_retried(self):
        es, session = make(lambda m, u: FakeResponse(404, {"error": {"reason": "no such index"}}))
        with self.assertRaises(ESFailure) as ctx:
            es.api("GET", "missing/_count")
        self.assertIn("HTTP 404", str(ctx.exception))
        self.assertEqual(len(session.calls), 1)

    def test_timeouts_are_not_retried(self):
        def handler(method, url):
            raise requests.Timeout("slow")

        es, session = make(handler)
        with self.assertRaises(ESFailure) as ctx:
            es.api("POST", "x/_search")
        self.assertIn("timed out", str(ctx.exception))
        self.assertEqual(len(session.calls), 1)


class CountsTests(unittest.TestCase):
    def test_counts_are_cached_until_they_expire(self):
        es, session = make(lambda m, u: FakeResponse(200, {"count": 7}))
        first = es.counts()
        used = len(session.calls)
        self.assertEqual(es.counts(), first)
        self.assertEqual(len(session.calls), used)  # served from the cache
        es.counts(max_age=0)
        self.assertGreater(len(session.calls), used)  # an expired cache asks again


class StatusTests(unittest.TestCase):
    def test_warm_up_posts_one_inference_call(self):
        es, session = make(lambda m, u: FakeResponse(200, {"inference_results": [{}]}))
        ms = es.warm_up()
        self.assertIsInstance(ms, int)
        method, url = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn(f"/_ml/trained_models/{quote(ES_INFERENCE_ID, safe='')}/_infer", url)

    def test_corpus_status_when_the_index_exists(self):
        mapping = {
            CORPUS_INDEX: {
                "mappings": {
                    "properties": {
                        "content_semantic": {
                            "type": "semantic_text",
                            "inference_id": ".elser-2-elasticsearch",
                        }
                    }
                }
            }
        }

        def handler(method, url):
            if method == "HEAD":
                return FakeResponse(200)
            if url.endswith("/_count"):
                return FakeResponse(200, {"count": 15732})
            if url.endswith("/_mapping"):
                return FakeResponse(200, mapping)
            raise AssertionError(url)

        es, _ = make(handler)
        self.assertEqual(
            es.corpus_status(),
            {
                "exists": True,
                "docs": 15732,
                "semantic": True,
                "inference_id": ".elser-2-elasticsearch",
            },
        )

    def test_corpus_status_when_the_index_is_missing(self):
        es, session = make(lambda m, u: FakeResponse(404))
        status = es.corpus_status()
        self.assertFalse(status["exists"])
        self.assertIsNone(status["docs"])
        self.assertFalse(status["semantic"])
        self.assertEqual([c[0] for c in session.calls], ["HEAD"])  # nothing else was called

    def test_elser_status_reports_scale_to_zero(self):
        body = {
            "trained_model_stats": [
                {
                    "deployment_stats": {
                        "deployment_id": ES_INFERENCE_ID,
                        "state": "started",
                        "allocation_status": {"allocation_count": 0},
                    }
                }
            ]
        }
        es, _ = make(lambda m, u: FakeResponse(200, body))
        status = es.elser_status()
        self.assertEqual(status["state"], "started")
        self.assertEqual(status["allocations"], 0)
        self.assertIn("zero", status["note"].lower())

    def test_elser_status_never_raises(self):
        es, _ = make(lambda m, u: FakeResponse(500, {"error": "boom"}))
        self.assertEqual(es.elser_status()["state"], "unknown")

    def test_license_info(self):
        body = {
            "license": {
                "type": "trial",
                "status": "active",
                "expiry_date": "2026-12-07T08:02:47.000Z",
            }
        }
        es, _ = make(lambda m, u: FakeResponse(200, body))
        self.assertEqual(
            es.license_info(),
            {"type": "trial", "status": "active", "expires": "2026-12-07T08:02:47.000Z"},
        )


if __name__ == "__main__":
    unittest.main()
