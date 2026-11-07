"""Paths and constants for IntelliSearch.

Values that a user may change come from settings.py (environment variables and
an optional .env file). Names here are kept so the other modules do not change.
"""

from pathlib import Path

from settings import load_settings

settings = load_settings()

ROOT = Path(__file__).resolve().parent
DATA = settings.data_dir
UPLOADS = DATA / "uploads"
DB = DATA / "showcase.sqlite3"

ES_URL = settings.es_url
ES_USER = settings.es_user
ES_PASSWORD = settings.es_password
ES_INFERENCE_ID = settings.es_inference_id
CORPUS_INDEX = settings.corpus_index

HOST = "127.0.0.1"  # Intentionally never listen on external interfaces.
PORT = settings.port

# The old book collections are shown only when LEGACY_ENABLED=true.
LEGACY_ENABLED = settings.legacy_enabled

# Optional folders. If they do not exist the features that need them are simply unavailable.
BOOKS_DIR = settings.books_dir or (DATA / "books")
V2_DATA = settings.v2_data_dir or (DATA / "v2")

UP_INDEX = "intellisearch_showcase_chunks_v3"
V2_INDEX = "intellisearch_showcase_chunks_v2"

_ALL_SOURCES = {
    "corpus": (CORPUS_INDEX, "Document corpus"),
    "passages": ("books_passages_phase2e_v1", "Indexed book passages"),
    "books": ("books_20", "Whole books"),
    "documents": ("demo_documents", "Demo documents"),
    "uploads": (UP_INDEX, "V3 uploaded documents"),
    "uploads_v2": (V2_INDEX, "Existing V2 uploads (read-only)"),
}
_LEGACY_KEYS = ("passages", "books", "documents", "uploads_v2")


def build_sources(legacy_enabled):
    """The collections the app may use. Legacy ones appear only when enabled."""
    return {
        key: value
        for key, value in _ALL_SOURCES.items()
        if legacy_enabled or key not in _LEGACY_KEYS
    }


SOURCES = build_sources(LEGACY_ENABLED)

_ALL_BOOK_FILES = {
    "01": "01_Pride and Prejudice.txt",
    "02": "02_Frankenstein; or, the Modern Prometheus.txt",
    "03": "03_The Adventures of Sherlock Holmes.txt",
    "05": "05_Dracula.txt",
    "14": "14_Alice's Adventures in Wonderland.txt",
}
_ALL_BOOK_NAMES = {
    "01": "Pride and Prejudice",
    "02": "Frankenstein",
    "03": "The Adventures of Sherlock Holmes",
    "05": "Dracula",
    "14": "Alice's Adventures in Wonderland",
}
BOOK_FILES = _ALL_BOOK_FILES if LEGACY_ENABLED else {}
BOOK_NAMES = _ALL_BOOK_NAMES if LEGACY_ENABLED else {}

MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_PAGES = 200
MAX_CHUNKS = 120
MAX_CHARS = 270_000
ALLOWED = {".pdf", ".txt", ".docx"}
