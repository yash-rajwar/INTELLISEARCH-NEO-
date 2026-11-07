"""Small start-up helpers: a secret key that survives restarts, and file logging."""

import logging
import os
import secrets
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_NAME = "intellisearch"


def load_secret_key(data_dir):
    """Return the Flask secret key.

    1. SECRET_KEY (or the older INTELLI_SECRET_KEY) from the environment, if set.
    2. Otherwise a key saved in <data_dir>/secret.key, created on first use.
    A stable key stops "Form expired" errors after the server restarts.
    If the folder cannot be written, a temporary key is returned instead.
    """
    from_env = (os.environ.get("SECRET_KEY") or os.environ.get("INTELLI_SECRET_KEY") or "").strip()
    if from_env:
        return from_env
    path = Path(data_dir) / "secret.key"
    try:
        saved = path.read_text(encoding="utf-8").strip()
    except OSError:
        saved = ""
    if saved:
        return saved
    key = secrets.token_hex(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(key, encoding="utf-8")
    except OSError:
        pass  # keep running with a key that lasts until the server stops
    return key


def setup_logging(data_dir, level=logging.INFO):
    """Log to the console and to <data_dir>/logs/intellisearch.log (rotating).

    Safe to call more than once: handlers are only added the first time.
    """
    logger = logging.getLogger(LOG_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    try:
        log_dir = Path(data_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "intellisearch.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("Could not open the log file; logging to the console only.")
    return logger
