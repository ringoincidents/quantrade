import unittest
from datetime import datetime,timezone
from macro_view import ids,parse,Cache
from bls_monthly import parse as monthly
from calendar_refresh import Cache as CalendarCache
NOW=datetime(2026,11,28,12,tzinfo=timezone.utc)
def fixture(group):
    keys=ids(group)
    rows=["observation_date,"+",".join(keys)]
    for day,val in (("2025-10-01","100"),("2026-09-01","110"),("2026-10-01","121")):
        rows.append(day+","+",".join([val if k!="UNRATE" else "4.1" for k in keys]))
    return ("\n".join(rows)+"\n").encode()
HTML=b"<table><tr><th>Date</th><th>Time</th><th>Release</th></tr><tr><td>Tuesday, December 01, 2026</td><td>10:00 AM</td><td>Job Openings</td></tr><tr><td>Friday, December 25, 2026</td><td>&nbsp;</td><td>Christmas Day</td></tr></table>"
class MacroTests(unittest.TestCase):
    def test_mom_yoy(self):
        v={x["id"]:x for x in parse(fixture("M"),"M",NOW)}
        self.assertEqual(v["CPIAUCSL"]["mom_pct"],"10.0000")
        self.assertEqual(v["CPIAUCSL"]["yoy_pct"],"21.0000")
        self.assertEqual(v["PAYEMS"]["monthly_change_people"],"11000")
        self.assertFalse(v["CPIAUCSL"]["original_publication_time_verified"])
    def test_bad_header_date_and_number(self):
        for x in (b"html",fixture("M").replace(b"2026-10-01",b"2026-12-01"),fixture("M").replace(b",121",b",NaN")):
            with self.assertRaises(ValueError):parse(x,"M",NOW)
    def test_missing_not_zero(self):
        v=parse(fixture("M").replace(b",121",b",."),"M",NOW)
        self.assertEqual(v[0]["observation_date"],"2026-09-01")
    def test_cache(self):
        clock=[0];calls=[]
        def load(g,n):
            calls.append(1)
            if len(calls)>1:raise TimeoutError()
            return fixture(g)
        c=Cache(load,lambda:clock[0],lambda:NOW)
        self.assertEqual(c.get("M")["mode"],"MANUAL_DATED_REFERENCE")
        self.assertEqual(c.get("M",True)["state"],"FETCHED")
        c.get("M",True);self.assertEqual(len(calls),1)
        clock[0]=3600;v=c.get("M",True)
        self.assertTrue(v["historical_only"]);self.assertEqual(v["state"],"REFRESH_FAILED")
    def test_monthly_fallback(self):
        rows=monthly(HTML,2026,12);self.assertEqual(len(rows),1);self.assertEqual(rows[0]["at_kst"],"2026-12-02T00:00:00+09:00")
        c=CalendarCache(lambda: (_ for _ in ()).throw(TimeoutError()),now=lambda:NOW,fallback=lambda now:(rows,rows[0]["source"]))
        self.assertEqual(c.get()["state"],"FETCHED_MONTHLY_FALLBACK")
    def test_bad_calendar(self):
        with self.assertRaises(ValueError):monthly(HTML,2026,11)
