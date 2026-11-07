import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preflight import license_status, python_status


class PreflightTests(unittest.TestCase):
    NOW = 1_800_000_000

    def lic(self, **kw):
        base = {"type": "trial", "status": "active", "expiry_date_in_millis": (self.NOW + 30 * 86400) * 1000}
        base.update(kw)
        return base

    def test_healthy_trial_passes(self):
        status, detail = license_status(self.lic(), self.NOW)
        self.assertEqual(status, "PASS")
        self.assertIn("30 days left", detail)

    def test_trial_ending_soon_warns(self):
        status, _ = license_status(self.lic(expiry_date_in_millis=(self.NOW + 3 * 86400) * 1000), self.NOW)
        self.assertEqual(status, "WARN")

    def test_basic_license_warns_about_elser(self):
        status, detail = license_status({"type": "basic", "status": "active"}, self.NOW)
        self.assertEqual(status, "WARN")
        self.assertIn("ELSER", detail)

    def test_expired_license_warns(self):
        status, _ = license_status(self.lic(status="expired"), self.NOW)
        self.assertEqual(status, "WARN")

    def test_python_versions(self):
        self.assertEqual(python_status((3, 12, 10))[0], "PASS")
        self.assertEqual(python_status((3, 9, 0))[0], "FAIL")
        self.assertEqual(python_status((3, 14, 1))[0], "WARN")


if __name__ == "__main__":
    unittest.main()