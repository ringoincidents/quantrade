import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from quantrade.workbench.entry_monitor import Quote, Target, check_entry

class EntryMonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 28, tzinfo=timezone.utc)
        self.q = Quote("DEMO", D("80"), "USD", self.now, "synthetic")
        self.t = Target("DEMO", D("100"), D(".20"), "USD", "v1",
                        "synthetic", self.now, self.now + timedelta(days=7))
    def check(self, q, t):
        return check_entry(q, t, as_of=self.now, max_age=timedelta(days=1))
    def test_boundary(self):
        r = self.check(self.q, self.t)
        self.assertEqual(r["status"], "REVIEW")
        self.assertEqual(r["entry_price"], D("80"))
        self.assertEqual(r["safety_margin"], D(".20"))
    def test_above(self):
        self.assertEqual(self.check(replace(self.q, price=D("80.01")), self.t)["status"], "WAIT")
    def test_stale(self):
        self.assertEqual(self.check(replace(self.q, observed_at=self.now-timedelta(days=2)), self.t)["reason"], "QUOTE_NOT_CURRENT")
    def test_future(self):
        self.assertEqual(self.check(replace(self.q, observed_at=self.now+timedelta(seconds=1)), self.t)["reason"], "QUOTE_NOT_CURRENT")
    def test_expired(self):
        self.assertEqual(self.check(self.q, replace(self.t, expires_at=self.now))["reason"], "TARGET_NOT_CURRENT")
    def test_missing(self):
        self.assertEqual(self.check(None, self.t)["reason"], "MISSING_INPUT")
    def test_currency(self):
        self.assertEqual(self.check(replace(self.q, currency="KRW"), self.t)["reason"], "IDENTITY_OR_CURRENCY_MISMATCH")
    def test_invalid(self):
        self.assertEqual(self.check(replace(self.q, price=D("NaN")), self.t)["reason"], "INVALID_NUMBER")
    def test_provenance(self):
        self.assertEqual(self.check(replace(self.q, source=""), self.t)["reason"], "MISSING_PROVENANCE")
    def test_naive_time(self):
        self.assertEqual(self.check(replace(self.q, observed_at=self.now.replace(tzinfo=None)), self.t)["reason"], "INVALID_TIME")

if __name__ == "__main__":
    unittest.main()
