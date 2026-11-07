import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from settings import load_env_file, load_settings


class SettingsTests(unittest.TestCase):
    def test_defaults_need_no_environment(self):
        s = load_settings(env={}, env_file=None)
        self.assertEqual(s.es_url, "http://127.0.0.1:9200")
        self.assertEqual(s.es_inference_id, ".elser-2-elasticsearch")
        self.assertEqual(s.corpus_index, "intellisearch_corpus_v1")
        self.assertEqual(s.host, "127.0.0.1")
        self.assertEqual(s.port, 5003)
        self.assertEqual(s.es_password, "")
        self.assertFalse(s.legacy_enabled)
        self.assertIsNone(s.books_dir)
        self.assertEqual(s.chunk_target_chars, 1400)
        self.assertEqual(s.chunk_overlap_chars, 180)

    def test_environment_overrides_defaults(self):
        env = {"ES_URL": "http://example:9200/", "PORT": "6000", "LEGACY_ENABLED": "true"}
        s = load_settings(env=env, env_file=None)
        self.assertEqual(s.es_url, "http://example:9200")  # trailing slash removed
        self.assertEqual(s.port, 6000)
        self.assertTrue(s.legacy_enabled)

    def test_old_intelli_names_still_work_and_new_names_win(self):
        old = load_settings(env={"INTELLI_ES_PASSWORD": "old"}, env_file=None)
        self.assertEqual(old.es_password, "old")
        both = load_settings(env={"INTELLI_ES_PASSWORD": "old", "ES_PASSWORD": "new"}, env_file=None)
        self.assertEqual(both.es_password, "new")

    def test_env_file_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder) / ".env"
            f.write_text(
                "# a comment\n"
                "ES_PASSWORD=secret # trailing comment\n"
                'ES_USER="elastic"\n'
                "PORT=7000\n"
                "\n"
                "not a setting line\n",
                encoding="utf-8",
            )
            values = load_env_file(f)
            self.assertEqual(values["ES_PASSWORD"], "secret")
            self.assertEqual(values["ES_USER"], "elastic")
            self.assertEqual(values["PORT"], "7000")
            self.assertEqual(len(values), 3)

    def test_real_environment_beats_env_file(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder) / ".env"
            f.write_text("PORT=7000\nES_USER=fromfile\n", encoding="utf-8")
            s = load_settings(env={"PORT": "8000"}, env_file=f)
            self.assertEqual(s.port, 8000)
            self.assertEqual(s.es_user, "fromfile")

    def test_missing_env_file_is_fine(self):
        self.assertEqual(load_env_file(Path("does-not-exist.env")), {})

    def test_bad_number_and_bad_bool_give_clear_errors(self):
        with self.assertRaises(ValueError) as a:
            load_settings(env={"PORT": "abc"}, env_file=None)
        self.assertIn("PORT", str(a.exception))
        with self.assertRaises(ValueError) as b:
            load_settings(env={"LEGACY_ENABLED": "maybe"}, env_file=None)
        self.assertIn("LEGACY_ENABLED", str(b.exception))

    def test_books_dir_is_optional_and_made_absolute(self):
        s = load_settings(env={"BOOKS_DIR": "./data/books"}, env_file=None)
        self.assertTrue(s.books_dir.is_absolute())

    def test_v2_data_dir_is_optional(self):
        self.assertIsNone(load_settings(env={}, env_file=None).v2_data_dir)
        s = load_settings(env={"V2_DATA_DIR": "./old_v2"}, env_file=None)
        self.assertTrue(s.v2_data_dir.is_absolute())


if __name__ == "__main__":
    unittest.main()