"""Hardened Elasticsearch HTTP client (WP-03): one Session, retries, TTL cache.

New module: the older es_client.py is untouched. Uses `requests`, as before.
"""

from __future__ import annotations

import time
from urllib.parse import quote

import requests

RETRY_STATUS = {429, 502, 503, 504}


class ESFailure(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class TTLCache:
    """Tiny time-based cache. get() calls loader() only when the entry is missing or old."""

    def __init__(self, ttl: float = 60.0, clock=time.monotonic):
        self.ttl, self.clock, self._d = ttl, clock, {}

    def get(self, key, loader):
        now = self.clock()
        hit = self._d.get(key)
        if hit is not None and now - hit[0] < self.ttl:
            return hit[1]
        value = loader()
        self._d[key] = (now, value)
        return value

    def invalidate(self, key=None):
        if key is None:
            self._d.clear()
        else:
            self._d.pop(key, None)


class ESHttp:
    def __init__(
        self,
        settings,
        session=None,
        *,
        sleep=time.sleep,
        retries: int = 3,
        clock=time.monotonic,
        cache_ttl: float = 60.0,
    ):
        self.url = settings.es_url.rstrip("/")
        self.s = session or requests.Session()
        self.s.trust_env = False  # ignore broken proxy / CA environment variables
        self.s.auth = (settings.es_user, settings.es_password)
        self.sleep, self.retries = sleep, retries
        self.cache = TTLCache(cache_ttl, clock)

    # -- core call ---------------------------------------------------------
    def request(self, method, path, *, json=None, ndjson=None, timeout=45, retries=None):
        attempts = (self.retries if retries is None else retries) + 1
        last: ESFailure | None = None
        for n in range(attempts):
            try:
                kw = {"timeout": (5, timeout)}
                if ndjson is not None:
                    kw["data"] = ndjson
                    kw["headers"] = {"Content-Type": "application/x-ndjson"}
                elif json is not None:
                    kw["json"] = json
                r = self.s.request(method, f"{self.url}/{path.lstrip('/')}", **kw)
            except requests.Timeout:
                last = ESFailure(
                    f"Elasticsearch timed out after {timeout}s (ELSER may be busy or cold)"
                )
            except requests.RequestException as e:
                last = ESFailure(f"Cannot connect to Elasticsearch at {self.url}: {e}")
            else:
                if r.status_code < 400:
                    return r.json() if r.content else {}
                last = self._failure(r)
                if r.status_code not in RETRY_STATUS:
                    raise last  # 4xx and other errors are not retried
            if n < attempts - 1:
                self.sleep(min(2**n, 8))
        raise last  # type: ignore[misc]

    @staticmethod
    def _failure(r) -> ESFailure:
        if r.status_code == 401:
            return ESFailure(
                "Elasticsearch HTTP 401: wrong user or password (check ES_PASSWORD in .env)", 401
            )
        try:
            detail = r.json().get("error")
        except Exception:
            detail = r.text[:300]
        if isinstance(detail, dict):
            detail = detail.get("reason") or str(detail)[:300]
        return ESFailure(f"Elasticsearch HTTP {r.status_code}: {str(detail)[:500]}", r.status_code)

    # -- cached helpers ----------------------------------------------------
    def exists(self, index: str) -> bool:
        def load():
            try:
                r = self.s.request("HEAD", f"{self.url}/{quote(index)}", timeout=(5, 10))
            except requests.RequestException as e:
                raise ESFailure(f"Cannot connect to Elasticsearch at {self.url}: {e}") from e
            if r.status_code == 200:
                return True
            if r.status_code == 404:
                return False
            raise self._failure(r)

        return self.cache.get(("exists", index), load)

    def mapping(self, index: str) -> dict:
        return self.cache.get(
            ("mapping", index), lambda: self.request("GET", f"{quote(index)}/_mapping", timeout=15)
        )

    def invalidate(self, key=None):
        self.cache.invalidate(key)
