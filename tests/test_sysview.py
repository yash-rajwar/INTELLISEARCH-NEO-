import unittest
from datetime import datetime, timezone

# Imports happen inside the tests on purpose (config must load after other test modules).

NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


class LicenceViewTests(unittest.TestCase):
    def test_trial_with_plenty_of_time_is_ok(self):
        from sysview import license_view

        v = license_view({"type": "trial", "status": "active", "expires": "2026-12-07T08:02:57.998Z"}, NOW)
        self.assertEqual(v["level"], "ok")
        self.assertEqual(v["days"], 29)
        self.assertEqual(v["expires"], "2026-12-07")

    def test_trial_under_seven_days_is_a_red_banner(self):
        from sysview import license_view

        v = license_view({"type": "trial", "status": "active", "expires": "2026-11-13T00:00:00Z"}, NOW)
        self.assertEqual(v["level"], "bad")
        self.assertIn("5 day", v["message"])

    def test_expired_trial_says_semantic_search_is_unavailable(self):
        from sysview import license_view

        v = license_view({"type": "trial", "status": "active", "expires": "2026-11-01T00:00:00Z"}, NOW)
        self.assertEqual(v["level"], "bad")
        self.assertIn("expired", v["message"])
        self.assertIn("Keyword search still works", v["message"])

    def test_basic_licence_is_flagged(self):
        from sysview import license_view

        v = license_view({"type": "basic", "status": "active", "expires": None}, NOW)
        self.assertEqual(v["level"], "bad")
        self.assertIn("Basic", v["message"])

    def test_inactive_status_is_flagged(self):
        from sysview import license_view

        v = license_view({"type": "trial", "status": "expired", "expires": "2026-12-07T00:00:00Z"}, NOW)
        self.assertEqual(v["level"], "bad")

    def test_unreadable_licence_is_unknown_not_an_error(self):
        from sysview import license_view

        self.assertEqual(license_view({"error": "HTTP 500"}, NOW)["level"], "unknown")
        self.assertEqual(license_view(None, NOW)["level"], "unknown")


class DiagnosticsReportTests(unittest.TestCase):
    def test_report_has_facts_and_never_extra_fields(self):
        from sysview import diagnostics_report, license_view

        status = {
            "es_version": "9.0.0",
            "es_password": "hunter2",
            "secret": "hunter2",
            "counts": {"corpus": 7102, "uploads": None},
            "elser": {"state": "started", "allocations": 1},
            "corpus": {"exists": True, "docs": 7102, "semantic": True},
            "ocr": {"ready": False},
            "ollama": {"configured": False},
            "port": 5003,
        }
        lic = license_view({"type": "trial", "status": "active", "expires": "2026-12-07T08:02:57.998Z"}, NOW)
        text = diagnostics_report(status, lic, NOW)
        self.assertIn("9.0.0", text)
        self.assertIn("Count corpus: 7102", text)
        self.assertIn("Count uploads: unavailable", text)
        self.assertNotIn("hunter2", text)


if __name__ == "__main__":
    unittest.main()
