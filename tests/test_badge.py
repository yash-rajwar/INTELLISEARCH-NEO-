import unittest

# Imports happen inside the tests on purpose (config must load after other test modules).


class FakeLicenceClient:
    def __init__(self, info=None, fail=False):
        self.info = info
        self.fail = fail
        self.calls = 0

    def license_info(self):
        self.calls += 1
        if self.fail:
            from es_client import ESFailure

            raise ESFailure("down")
        return self.info


class BadgeTests(unittest.TestCase):
    def setUp(self):
        import badge

        badge._cache.update(until=0.0, text="")

    def test_days_left(self):
        from datetime import datetime, timezone

        import badge

        now = datetime(2026, 11, 8, tzinfo=timezone.utc)
        self.assertEqual(badge.days_left("2026-12-07T08:02:57.998Z", now), 29)
        self.assertIsNone(badge.days_left("not a date", now))
        self.assertIsNone(badge.days_left(None, now))

    def test_chip_text_cases(self):
        from datetime import datetime, timezone

        import badge

        now = datetime(2026, 11, 8, tzinfo=timezone.utc)
        trial = {"type": "trial", "status": "active", "expires": "2026-12-07T08:02:57.998Z"}
        self.assertEqual(badge.chip_text(trial, now), "Trial licence: 29 days left")
        old = {"type": "trial", "status": "active", "expires": "2026-11-01T00:00:00Z"}
        self.assertEqual(badge.chip_text(old, now), "Trial licence expired")
        self.assertEqual(badge.chip_text({"type": "basic", "status": "active"}, now), "Licence: basic")
        self.assertEqual(badge.chip_text({"type": "trial", "status": "expired"}, now), "Licence expired")
        self.assertEqual(badge.chip_text("nonsense", now), "")

    def test_result_is_cached(self):
        import badge

        client = FakeLicenceClient({"type": "trial", "status": "active", "expires": "2099-01-01T00:00:00Z"})
        t = [0.0]
        first = badge.license_chip(lambda: client, clock=lambda: t[0])
        badge.license_chip(lambda: client, clock=lambda: t[0])
        self.assertTrue(first.startswith("Trial licence:"))
        self.assertEqual(client.calls, 1)
        t[0] = 1000.0
        badge.license_chip(lambda: client, clock=lambda: t[0])
        self.assertEqual(client.calls, 2)

    def test_failure_gives_empty_text_and_is_remembered(self):
        import badge

        client = FakeLicenceClient(fail=True)
        t = [0.0]
        self.assertEqual(badge.license_chip(lambda: client, clock=lambda: t[0]), "")
        badge.license_chip(lambda: client, clock=lambda: t[0])
        self.assertEqual(client.calls, 1)

    def test_client_that_cannot_be_created(self):
        import badge

        def broken():
            raise RuntimeError("no client")

        self.assertEqual(badge.license_chip(broken, clock=lambda: 0.0), "")


if __name__ == "__main__":
    unittest.main()
