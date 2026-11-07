import logging
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bootstrap
import store


class SecretKeyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        env = mock.patch.dict(os.environ, {"SECRET_KEY": "", "INTELLI_SECRET_KEY": ""})
        env.start()
        self.addCleanup(env.stop)

    def test_key_is_created_once_and_reused(self):
        first = bootstrap.load_secret_key(self.folder)
        second = bootstrap.load_secret_key(self.folder)
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first), 32)
        self.assertTrue((self.folder / "secret.key").is_file())

    def test_environment_value_wins_and_no_file_is_written(self):
        with mock.patch.dict(os.environ, {"SECRET_KEY": "from-env"}):
            self.assertEqual(bootstrap.load_secret_key(self.folder), "from-env")
        self.assertFalse((self.folder / "secret.key").exists())

    def test_older_environment_name_still_works(self):
        with mock.patch.dict(os.environ, {"INTELLI_SECRET_KEY": "old-name"}):
            self.assertEqual(bootstrap.load_secret_key(self.folder), "old-name")

    def test_unwritable_folder_still_gives_a_key(self):
        blocker = self.folder / "blocker"
        blocker.write_text("this is a file, not a folder", encoding="utf-8")
        key = bootstrap.load_secret_key(blocker / "sub")
        self.assertGreaterEqual(len(key), 32)


class LoggingTests(unittest.TestCase):
    def _close_handlers(self):
        logger = logging.getLogger(bootstrap.LOG_NAME)
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)

    def test_creates_log_file_and_adds_handlers_only_once(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.addCleanup(self._close_handlers)  # runs before tmp.cleanup (last in, first out)
        logger = bootstrap.setup_logging(tmp.name)
        bootstrap.setup_logging(tmp.name)
        self.assertEqual(len(logger.handlers), 2)
        self.assertTrue((Path(tmp.name) / "logs" / "intellisearch.log").is_file())


class InitDbTests(unittest.TestCase):
    def test_init_db_closes_its_connection(self):
        opened = []
        real_connect = sqlite3.connect

        def spy(*args, **kwargs):
            conn = real_connect(*args, **kwargs)
            opened.append(conn)
            return conn

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            with (
                mock.patch.object(store, "DB", Path(tmp) / "t.sqlite3"),
                mock.patch.object(store, "DATA", Path(tmp)),
                mock.patch.object(store.sqlite3, "connect", spy),
            ):
                store.init_db()
        self.assertTrue(opened)
        for conn in opened:
            with self.assertRaises(sqlite3.ProgrammingError):  # a closed connection refuses queries
                conn.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
