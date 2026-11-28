import unittest
from datetime import datetime,timezone
from calendar_refresh import parse,Cache
NOW=datetime(2026,11,28,tzinfo=timezone.utc)
FIX=b"BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:test\r\nDTSTART;TZID=America/New_York:20261201T100000\r\nSUMMARY:JOLTS\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
class RefreshTests(unittest.TestCase):
    def test_timezone(self):
        self.assertEqual(parse(FIX,NOW)[0]["at_kst"],"2026-12-02T00:00:00+09:00")
    def test_bad_or_ambiguous(self):
        for x in (b"html",FIX.replace(b"America/New_York",b"Unknown")):
            with self.assertRaises(ValueError):parse(x,NOW)
    def test_throttle_and_failure(self):
        calls=[];clock=[0]
        def load():
            calls.append(1)
            if len(calls)>1:raise TimeoutError()
            return FIX
        c=Cache(load,lambda:clock[0],lambda:NOW)
        self.assertEqual(c.get()["state"],"FETCHED");c.get();self.assertEqual(len(calls),1)
        clock[0]=3600;v=c.get()
        self.assertEqual(v["state"],"REFRESH_FAILED");self.assertTrue(v["historical_only"])
        self.assertEqual(len(v["events"]),1)
