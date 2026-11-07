"""Allowlisted Elasticsearch operations; all legacy indexes remain strictly read-only."""

import json
import time
import requests
from urllib.parse import quote
from config import CORPUS_INDEX, ES_INFERENCE_ID, ES_URL, ES_USER, ES_PASSWORD, UP_INDEX, SOURCES

CONNECT_ATTEMPTS = 3  # only for "could not connect" errors
RETRY_DELAY = 0.4  # seconds, multiplied by the attempt number
COUNTS_MAX_AGE = 30  # seconds to keep the collection counts


class ESFailure(RuntimeError):
    pass


class ES:
    def __init__(self, password=None, session=None):
        self.s = session or requests.Session()
        self.s.trust_env = False
        self.s.auth = (ES_USER, ES_PASSWORD if password is None else password)
        self.inference_id = None
        self.upload_semantic = False
        self._counts_cache = None  # (time, counts)

    def api(self, method, path, *, payload=None, timeout=45, raw=None):
        kw = {"timeout": (5, timeout)}
        if raw is not None:
            kw["data"] = raw
            kw["headers"] = {"Content-Type": "application/x-ndjson"}
        elif payload is not None:
            kw["json"] = payload
        url = ES_URL + "/" + path.lstrip("/")
        for attempt in range(1, CONNECT_ATTEMPTS + 1):
            try:
                r = self.s.request(method, url, **kw)
                break
            except requests.Timeout as e:
                # Never retried: a slow ELSER call would only get slower.
                raise ESFailure(
                    f"Elasticsearch timed out after {timeout}s; ELSER may be busy. {e}"
                ) from e
            except requests.ConnectionError as e:
                if attempt == CONNECT_ATTEMPTS:
                    raise ESFailure(f"Cannot connect to Elasticsearch: {e}") from e
                time.sleep(RETRY_DELAY * attempt)
            except requests.RequestException as e:
                raise ESFailure(f"Cannot connect to Elasticsearch: {e}") from e
        if r.status_code >= 400:
            try:
                detail = r.json().get("error")
            except Exception:
                detail = r.text[:300]
            if isinstance(detail, dict):
                detail = detail.get("reason") or str(detail)[:300]
            raise ESFailure(f"Elasticsearch HTTP {r.status_code}: {str(detail)[:500]}")
        try:
            return r.json() if r.content else {}
        except ValueError as e:
            raise ESFailure(f"Elasticsearch sent a reply that is not JSON: {e}") from e

    def exists(self, index):
        if index not in [x[0] for x in SOURCES.values()]:
            raise ESFailure("Unknown index")
        try:
            res = self.s.head(ES_URL + "/" + quote(index), timeout=(5, 8))
            return res.status_code == 200
        except requests.RequestException:
            return False

    def probe(self):
        root = self.api("GET", "/", timeout=8)
        return root.get("version", {}).get("number", "unknown")

    def counts(self, max_age=COUNTS_MAX_AGE):
        cached = self._counts_cache
        if cached and time.monotonic() - cached[0] < max_age:
            return dict(cached[1])
        out = {}
        for k, (idx, _) in SOURCES.items():
            try:
                out[k] = (
                    self.api("GET", f"{idx}/_count", timeout=10)["count"] if self.exists(idx) else 0
                )
            except (KeyError, ESFailure):
                out[k] = None
        if None not in out.values():  # do not remember a failed attempt
            self._counts_cache = (time.monotonic(), out)
        return dict(out)

    def get_inference(self):
        # Reuse the endpoint that an existing semantic index really uses; never guess it.
        candidates = [CORPUS_INDEX]
        if "passages" in SOURCES:
            candidates.append(SOURCES["passages"][0])
        for index in candidates:
            try:
                data = self.api("GET", f"{index}/_mapping", timeout=12)
                props = data[index]["mappings"]["properties"]
            except (ESFailure, KeyError, TypeError):
                continue
            sem = props.get("content_semantic", {})
            if sem.get("type") == "semantic_text":
                return sem.get("inference_id") or ".elser-2-elasticsearch"
        return None

    def warm_up(self):
        """Run one tiny ELSER inference so the first real query is not slow. Returns milliseconds."""
        started = time.monotonic()
        self.api(
            "POST",
            f"_ml/trained_models/{quote(ES_INFERENCE_ID, safe='')}/_infer?timeout=120s",
            payload={"docs": [{"text_field": "warm up"}]},
            timeout=130,
        )
        return round((time.monotonic() - started) * 1000)

    def license_info(self):
        data = self.api("GET", "_license", timeout=10).get("license", {})
        return {
            "type": data.get("type"),
            "status": data.get("status"),
            "expires": data.get("expiry_date"),
        }

    def elser_status(self):
        """State of the ELSER deployment, in plain words. Never raises."""
        try:
            data = self.api("GET", "_ml/trained_models/_stats", timeout=10)
        except ESFailure as exc:
            return {"state": "unknown", "allocations": None, "note": str(exc)[:200]}
        for entry in data.get("trained_model_stats", []):
            dep = entry.get("deployment_stats") or {}
            if dep.get("deployment_id") != ES_INFERENCE_ID:
                continue
            state = dep.get("state", "unknown")
            allocations = (dep.get("allocation_status") or {}).get("allocation_count")
            note = ""
            if state == "failed":
                note = "The deployment failed; it needs to be stopped and restarted."
            elif state == "started" and allocations == 0:
                note = "Scaled to zero while idle: the first semantic query can take about 30 s. Open /warmup before presenting."
            return {"state": state, "allocations": allocations, "note": note}
        return {
            "state": "not deployed",
            "allocations": None,
            "note": "No deployment found for "
            + ES_INFERENCE_ID
            + "; the first call may start one.",
        }

    def corpus_status(self):
        """Read-only report on the corpus index. It never creates, changes or deletes it."""
        out = {"exists": False, "docs": None, "semantic": False, "inference_id": None}
        if not self.exists(CORPUS_INDEX):
            return out
        out["exists"] = True
        try:
            out["docs"] = self.api("GET", f"{CORPUS_INDEX}/_count", timeout=10)["count"]
            mapping = self.api("GET", f"{CORPUS_INDEX}/_mapping", timeout=12)
            props = mapping[CORPUS_INDEX]["mappings"]["properties"]
        except (KeyError, TypeError, ESFailure):
            return out
        sem = props.get("content_semantic", {})
        out["semantic"] = sem.get("type") == "semantic_text"
        out["inference_id"] = sem.get("inference_id") if out["semantic"] else None
        return out

    def make_upload_index(self):
        if self.exists(UP_INDEX):
            data = self.api("GET", UP_INDEX + "/_mapping", timeout=12)
            props = data[UP_INDEX]["mappings"]["properties"]
            self.upload_semantic = props.get("content_semantic", {}).get("type") == "semantic_text"
            return self.upload_semantic
        properties = {
            "document_id": {"type": "keyword"},
            "filename": {"type": "keyword"},
            "title": {"type": "text"},
            "file_type": {"type": "keyword"},
            "content": {"type": "text"},
            "chunk_index": {"type": "integer"},
            "page_number": {"type": "integer"},
            "created_at": {"type": "date"},
        }
        inference = None
        try:
            inference = self.get_inference()
        except (ESFailure, KeyError, TypeError):
            pass
        if inference:
            properties["content_semantic"] = {"type": "semantic_text", "inference_id": inference}
        try:
            self.api(
                "PUT",
                UP_INDEX,
                payload={"mappings": {"dynamic": "strict", "properties": properties}},
                timeout=18,
            )
        except ESFailure:
            if not inference:
                raise
            # The local model can be unavailable despite a prior semantic index.
            # Never block BM25 uploads because ELSER mapping setup failed.
            properties.pop("content_semantic", None)
            if not self.exists(UP_INDEX):
                self.api(
                    "PUT",
                    UP_INDEX,
                    payload={"mappings": {"dynamic": "strict", "properties": properties}},
                    timeout=18,
                )
            inference = None
        self.upload_semantic = bool(inference)
        self.inference_id = inference
        return self.upload_semantic

    def bulk_upload(self, doc_id, documents, *, semantic=False):
        if not self.exists(UP_INDEX):
            raise ESFailure("Showcase index missing.")
        rows = []
        for i, doc in enumerate(documents):
            if doc.get("document_id") != doc_id:
                raise ESFailure("Document ID mismatch")
            val = dict(doc)
            if semantic and self.upload_semantic:
                val["content_semantic"] = val["content"]
            rows.append(
                json.dumps({"index": {"_index": UP_INDEX, "_id": doc_id + "_" + str(i).zfill(4)}})
            )
            rows.append(json.dumps(val, ensure_ascii=False))
        # Bound batch sizes to protect ELSER, avoid partial timeouts with unbounded requests.
        for start in range(0, len(rows), 20):
            batch = "\n".join(rows[start : start + 20]) + "\n"
            is_final = start + 20 >= len(rows)
            endpoint = "_bulk?refresh=wait_for" if is_final else "_bulk"
            res = self.api(
                "POST", endpoint, raw=batch.encode("utf-8"), timeout=160 if semantic else 30
            )
            if res.get("errors"):
                faults = [
                    x.get("index", {}).get("error")
                    for x in res.get("items", [])
                    if x.get("index", {}).get("error")
                ]
                raise ESFailure(
                    "Bulk indexing error: " + str(faults[0])[:350]
                    if faults
                    else "Bulk indexing error"
                )
        self._counts_cache = None  # the collection counts have changed

    def get_hit(self, index, doc_id):
        if index not in [x[0] for x in SOURCES.values()]:
            raise ESFailure("Invalid index.")
        try:
            data = self.api("GET", quote(index) + "/_doc/" + quote(doc_id, safe=""), timeout=12)
        except ESFailure as exc:
            if "HTTP 404" in str(exc):
                return {}
            raise
        return data.get("_source", {})
