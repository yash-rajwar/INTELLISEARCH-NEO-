from datetime import UTC, datetime

import pytest
import requests

from es_http import ESFailure, ESHttp, TTLCache
from health import elser_health, license_info
from mappings import corpus_mapping, ensure_corpus_index


class Cfg:
    es_url = "http://es:9200"
    es_user = "elastic"
    es_password = "pw"
    es_inference_id = ".elser-2-elasticsearch"
    corpus_index = "intellisearch_corpus_v1"


class Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._b = status, body if body is not None else {}
        self.content = b"x"
        self.text = str(self._b)

    def json(self):
        return self._b


class Session:
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def request(self, method, url, **kw):
        self.calls.append((method, url))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make(script, **kw):
    sleeps = []
    return ESHttp(Cfg(), Session(script), sleep=sleeps.append, **kw), sleeps


def test_retries_503_then_succeeds_with_backoff():
    es, sleeps = make([Resp(503), Resp(503), Resp(200, {"ok": 1})])
    assert es.request("GET", "/") == {"ok": 1}
    assert sleeps == [1, 2]


def test_no_retry_on_4xx():
    es, sleeps = make([Resp(400, {"error": {"reason": "bad"}}), Resp(200)])
    with pytest.raises(ESFailure) as e:
        es.request("GET", "/")
    assert e.value.status == 400 and sleeps == [] and len(es.s.calls) == 1


def test_401_message_mentions_password():
    es, _ = make([Resp(401, {})])
    with pytest.raises(ESFailure, match="ES_PASSWORD"):
        es.request("GET", "/")


def test_connection_error_retried_then_fails_clearly():
    es, sleeps = make([requests.ConnectionError("x")] * 4)
    with pytest.raises(ESFailure, match="Cannot connect"):
        es.request("GET", "/")
    assert len(es.s.calls) == 4 and sleeps == [1, 2, 4]


def test_timeout_message():
    es, _ = make([requests.Timeout()] * 4)
    with pytest.raises(ESFailure, match="timed out"):
        es.request("GET", "/", timeout=7)


def test_ttl_cache_expiry_and_invalidate():
    t = [0.0]
    c = TTLCache(60, clock=lambda: t[0])
    n = []
    load = lambda: n.append(1) or len(n)
    assert c.get("k", load) == 1 and c.get("k", load) == 1
    t[0] = 61
    assert c.get("k", load) == 2
    c.invalidate("k")
    assert c.get("k", load) == 3


def test_exists_is_cached_one_head_call():
    es, _ = make([Resp(200)])
    assert es.exists("a") and es.exists("a")
    assert len(es.s.calls) == 1


def test_ensure_corpus_index_creates_once_never_deletes():
    es, _ = make([Resp(404), Resp(200, {"acknowledged": True})])
    assert ensure_corpus_index(es, Cfg()) is True
    methods = [m for m, _ in es.s.calls]
    assert methods == ["HEAD", "PUT"]


def test_mapping_is_strict_with_semantic_field():
    m = corpus_mapping(".elser-2-elasticsearch")
    assert m["mappings"]["dynamic"] == "strict"
    assert m["mappings"]["properties"]["content_semantic"]["type"] == "semantic_text"
    assert "content_semantic" not in corpus_mapping("x", semantic=False)["mappings"]["properties"]


def test_license_days_left():
    es, _ = make(
        [
            Resp(
                200,
                {
                    "license": {
                        "type": "trial",
                        "status": "active",
                        "expiry_date_in_millis": 1796630520000,
                    }
                },
            )
        ]
    )
    info = license_info(es, now=datetime(2026, 11, 7, tzinfo=UTC))
    assert info["type"] == "trial" and info["days_left"] == 30


def test_elser_health_failed_and_no_index():
    es, _ = make([Resp(404)])
    assert elser_health(es, "i")["status"] == "no_index"
    es2, _ = make([Resp(200), Resp(500, {"error": "boom"})])
    assert elser_health(es2, "i")["status"] == "failed"
