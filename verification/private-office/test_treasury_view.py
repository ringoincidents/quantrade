import unittest
from datetime import datetime,timezone
from treasury_view import Cache,parse,summarize,bp
from treasury_pilot import official_url
NOW=datetime(2026,11,28,12,tzinfo=timezone.utc)
def fixture(a="4.69",b="4.94",day="2026-11-27"):
    return ('<feed><entry><properties><NEW_DATE>'+day+'</NEW_DATE><BC_2YEAR>'+a+'</BC_2YEAR><BC_10YEAR>'+b+'</BC_10YEAR></properties></entry></feed>').encode()
class TreasuryViewTests(unittest.TestCase):
    def test_parse(self):
        v=parse(fixture(),2026,NOW);self.assertEqual(v["spread_10y_2y_bp"],25)
        self.assertEqual(v["observation_date"],"2026-11-27")
        self.assertFalse(v["original_publication_time_verified"])
        self.assertIsNone(v["five_observation_change_10y_bp"])
    def test_missing_and_future(self):
        for b in (fixture(b=""),fixture(day="2026-11-29"),fixture(a="nan")):
            with self.assertRaises(ValueError):parse(b,2026,NOW)
    def test_no_forward_fill(self):
        a=fixture().replace(b"</feed>",b"<entry><properties><NEW_DATE>2026-11-28</NEW_DATE><BC_2YEAR>4.7</BC_2YEAR></properties></entry></feed>")
        with self.assertRaisesRegex(ValueError,"LATEST_PAIR_MISSING"):parse(a,2026,NOW)
    def test_cache(self):
        calls=[];clock=[0]
        def load(y):
            calls.append(y)
            if len(calls)>1:raise TimeoutError()
            return fixture(),official_url(y)
        c=Cache(load,lambda:clock[0],lambda:NOW)
        self.assertEqual(c.get()["mode"],"MANUAL_DATED_REFERENCE");self.assertFalse(calls)
        self.assertEqual(c.get(True)["state"],"FETCHED");c.get(True);self.assertEqual(len(calls),1)
        clock[0]=3600;v=c.get(True);self.assertEqual(v["state"],"REFRESH_FAILED");self.assertTrue(v["historical_only"])
        self.assertEqual(v["data"]["ust_par_10y_pct"],4.94)
    def test_no_source_substitution(self):
        c=Cache(lambda y:(fixture(),"https://example.org"),now=lambda:NOW)
        self.assertEqual(c.get(True)["mode"],"MANUAL_DATED_REFERENCE")
        self.assertEqual(c.get()["state"],"REFRESH_FAILED")
    def test_decimal_bp(self):
        self.assertEqual(bp(4.94,4.69),25);self.assertEqual(bp(4.94,5.04),-10)
