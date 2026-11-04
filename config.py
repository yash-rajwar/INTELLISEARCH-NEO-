"""Config for a local-only, isolated IntelliSearch demo."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
DATA = ROOT / 'data'  # V3 has separate local metadata and uploads.
UPLOADS = DATA / 'uploads'
DB = DATA / 'showcase.sqlite3'
ES_URL = os.environ.get('INTELLI_ES_URL', 'http://127.0.0.1:9200').rstrip('/')
ES_USER = os.environ.get('INTELLI_ES_USER', 'elastic')
ES_PASSWORD = os.environ.get('INTELLI_ES_PASSWORD', '')
HOST = '127.0.0.1'  # Intentionally never listen on external interfaces.
PORT = 5003
UP_INDEX = 'intellisearch_showcase_chunks_v3'
V2_INDEX = 'intellisearch_showcase_chunks_v2'
V2_ROOT = PROJECT / 'intellisearch_showcase_v2'
V2_DATA = V2_ROOT / 'data'
SOURCES = {
    'passages': ('books_passages_phase2e_v1', 'Indexed book passages'),
    'books': ('books_20', 'Whole books'),
    'documents': ('demo_documents', 'Demo documents'),
    'uploads': (UP_INDEX, 'V3 uploaded documents'),
    'uploads_v2': (V2_INDEX, 'Existing V2 uploads (read-only)'),
}
BOOK_FILES = {
    '01': '01_Pride and Prejudice.txt',
    '02': '02_Frankenstein; or, the Modern Prometheus.txt',
    '03': '03_The Adventures of Sherlock Holmes.txt',
    '05': '05_Dracula.txt',
    '14': "14_Alice's Adventures in Wonderland.txt",
}
BOOK_NAMES = {'01': 'Pride and Prejudice', '02': 'Frankenstein', '03': 'The Adventures of Sherlock Holmes',
              '05': 'Dracula', '14': "Alice's Adventures in Wonderland"}
MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_PAGES = 200
MAX_CHUNKS = 120
MAX_CHARS = 270_000
ALLOWED = {'.pdf', '.txt', '.docx'}
