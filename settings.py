"""Settings for IntelliSearch NEO.

Values come from environment variables, and from an optional .env file in the
project folder. A real environment variable always wins over the .env file.
Every setting has a safe default, except the Elasticsearch password.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


def load_env_file(path: Optional[Path]) -> dict:
    """Read KEY=VALUE lines from a .env file. A missing file gives an empty dict."""
    values = {}
    if path is None or not Path(path).is_file():
        return values
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]  # quoted value: keep everything inside the quotes
        elif " #" in value:
            value = value.split(" #", 1)[0].strip()  # drop a trailing comment
        values[key.strip()] = value
    return values


def _text(env: dict, name: str, default: str = "") -> str:
    return env.get(name, default).strip()


def _int(env: dict, name: str, default: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} must be a whole number, got {raw!r}") from None


def _bool(env: dict, name: str, default: bool) -> bool:
    if name not in env:
        return default
    raw = env[name].strip().lower()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ValueError(f"{name} must be true or false, got {raw!r}")


def _path(value: str, base: Path = ROOT) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (base / p).resolve()


@dataclass(frozen=True)
class Settings:
    es_url: str
    es_user: str
    es_password: str
    es_inference_id: str
    corpus_index: str
    legacy_enabled: bool
    books_dir: Optional[Path]
    v2_data_dir: Optional[Path]
    data_dir: Path
    host: str
    port: int
    chunk_target_chars: int
    chunk_overlap_chars: int
    max_upload_mb: int
    max_chunks_per_doc: int
    enable_rerank: bool
    rerank_inference_id: str
    ollama_model: str
    ollama_url: str
    log_queries: bool
    presenter_mode: bool
    allow_non_loopback: bool = False
    context_neighbours: int = 1


def load_settings(env: Optional[dict] = None, env_file: Optional[Path] = ROOT / ".env") -> Settings:
    """Build Settings. Pass env={} and env_file=None in tests to get pure defaults."""
    merged = load_env_file(env_file)
    merged.update(os.environ if env is None else env)  # real environment wins

    books = _text(merged, "BOOKS_DIR")
    v2 = _text(merged, "V2_DATA_DIR")
    return Settings(
        # INTELLI_ES_* are the older names; the new names win when both are set.
        es_url=(_text(merged, "ES_URL") or _text(merged, "INTELLI_ES_URL") or "http://127.0.0.1:9200").rstrip("/"),
        es_user=_text(merged, "ES_USER") or _text(merged, "INTELLI_ES_USER") or "elastic",
        es_password=_text(merged, "ES_PASSWORD") or _text(merged, "INTELLI_ES_PASSWORD"),
        es_inference_id=_text(merged, "ES_INFERENCE_ID", ".elser-2-elasticsearch"),
        corpus_index=_text(merged, "CORPUS_INDEX", "intellisearch_corpus_v1"),
        legacy_enabled=_bool(merged, "LEGACY_ENABLED", False),
        books_dir=_path(books) if books else None,
        v2_data_dir=_path(v2) if v2 else None,
        data_dir=_path(_text(merged, "DATA_DIR", "./data")),
        host=_text(merged, "HOST", "127.0.0.1"),
        port=_int(merged, "PORT", 5003),
        chunk_target_chars=_int(merged, "CHUNK_TARGET_CHARS", 1400),
        chunk_overlap_chars=_int(merged, "CHUNK_OVERLAP_CHARS", 180),
        max_upload_mb=_int(merged, "MAX_UPLOAD_MB", 25),
        max_chunks_per_doc=_int(merged, "MAX_CHUNKS_PER_DOC", 3000),
        enable_rerank=_bool(merged, "ENABLE_RERANK", False),
        rerank_inference_id=_text(merged, "RERANK_INFERENCE_ID", ".rerank-v1-elasticsearch"),
        ollama_model=_text(merged, "OLLAMA_MODEL"),
        ollama_url=_text(merged, "OLLAMA_URL", "http://127.0.0.1:11434"),
        log_queries=_bool(merged, "LOG_QUERIES", True),
        presenter_mode=_bool(merged, "PRESENTER_MODE", False),
        allow_non_loopback=_bool(merged, "ALLOW_NON_LOOPBACK", False),
        context_neighbours=_int(merged, "CONTEXT_NEIGHBOURS", 1),
    )