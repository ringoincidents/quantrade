import unittest
from datetime import datetime, date, timezone
from quantrade.workbench import session_calendar as c

def at(value):
    return datetime.fromisoformat(value)

class CalendarTests(unittest.TestCase):
    def test_thanksgiving_holiday(self):
        for market in ("XNYS","XNAS"):
            self.assertIsNone(c.us_scheduled_session(market,date(2026,11,26)))
            self.assertEqual(c.latest_scheduled_close(market,at("2026-11-26T21:00:00+00:00")).session_date,date(2026,11,25))

    def test_early_close_boundary(self):
        for market in ("XNYS","XNAS"):
            before=c.latest_scheduled_close(market,at("2026-11-27T17:59:59+00:00"))
            after=c.latest_scheduled_close(market,at("2026-11-27T18:00:00+00:00"))
            self.assertEqual(before.session_date,date(2026,11,25))
            self.assertEqual(after.session_date,date(2026,11,27))
            self.assertEqual(after.close_at.isoformat(),"2026-11-27T13:00:00-05:00")

    def test_provider_date_boundary_no_prior_fallback(self):
        before=c.assess("XNAS",at("2026-11-28T13:59:59+09:00"))
        after=c.assess("XNAS",at("2026-11-28T14:00:00+09:00"))
        self.assertEqual(before["state"],"PUBLICATION_WINDOW_PENDING")
        self.assertEqual(after["state"],"PLAN_ELIGIBLE_UNVERIFIED")
        self.assertEqual(before["session_date"],"2026-11-27")
        self.assertEqual(after["session_date"],"2026-11-27")
        self.assertFalse(after["decision_authorized"])
        self.assertFalse(after["actual_finality_verified"])

    def test_weekend_and_monday_before_close(self):
        for instant in ["2026-11-29T12:00:00+09:00","2026-11-30T20:59:59+00:00"]:
            self.assertEqual(c.latest_scheduled_close("XNYS",at(instant)).session_date,date(2026,11,27))
        self.assertEqual(c.latest_scheduled_close("XNYS",at("2026-11-30T21:00:00+00:00")).session_date,date(2026,11,30))

    def test_declared_stale_session(self):
        result=c.assess("XNYS",at("2026-11-28T16:00:00+09:00"),declared_session="2026-11-25")
        self.assertEqual(result["state"],"SESSION_MISMATCH")
        self.assertFalse(result["decision_authorized"])

    def test_fail_closed_missing_coverage_and_krx(self):
        for market,instant,reason in [
            ("KRX","2026-11-28T16:00:00+09:00","CALENDAR_MARKET_UNVERIFIED"),
            ("XNYS","2026-12-05T16:00:00+09:00","CALENDAR_OUTSIDE_COVERAGE"),
            ("XNYS","2026-11-23T10:00:00-05:00","NO_COMPLETED_SESSION_IN_COVERAGE"),
            ("XNYS","2026-11-28T16:00:00","INVALID_AS_OF")]:
            result=c.assess(market,at(instant))
            self.assertEqual(result["reason"],reason)
            self.assertFalse(result["decision_authorized"])

    def test_zoneinfo_dst_reference(self):
        # Timezone conversion only; outside dates are not enabled calendar sessions.
        summer=datetime(2026,7,6,16,tzinfo=c.US_ZONE)
        winter=datetime(2026,11,27,13,tzinfo=c.US_ZONE)
        self.assertEqual(summer.astimezone(timezone.utc).hour,20)
        self.assertEqual(winter.astimezone(timezone.utc).hour,18)
        with self.assertRaisesRegex(ValueError,"CALENDAR_OUTSIDE_COVERAGE"):
            c.us_scheduled_session("XNYS",summer.date())
