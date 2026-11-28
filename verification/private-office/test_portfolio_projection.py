import unittest
import json
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from portfolio_projection import collect,SnapshotCache,Blocked,number

NOW=datetime(2026,11,28,7,tzinfo=timezone.utc)
def fixture(path,account=None,params=None):
    if path=="/api/v1/accounts":
        return [{"accountSeq":"987654321"},{"accountSeq":"123456789"}]
    if path=="/api/v1/holdings":
        return {"items":[{"symbol":"FIX_KR" if account=="123456789" else "FIX_US",
                 "name":"Synthetic","currency":"KRW" if account=="123456789" else "USD",
                 "quantity":"2","lastPrice":"10","marketValue":{"amount":"20"},
                 "profitLoss":{"amount":"-1","rate":"-0.05"}}],"hasNext":False}
    if path=="/api/v1/buying-power":
        return {"cashBuyingPower":"100"}
    if path=="/api/v1/exchange-rate":
        return {"rate":"1000"}
    raise AssertionError("unexpected route")

class ProjectionTests(unittest.TestCase):
    def test_two_accounts_and_no_fake_nav(self):
        r=collect(fixture,lambda:NOW)
        self.assertEqual(r["securities_value_krw"],"20020")
        self.assertEqual(r["securities_native"],{"KRW":"20","USD":"20"})
        self.assertIsNone(r["cash_balance"])
        self.assertIsNone(r["total_nav"])
        self.assertIsNone(r["total_return"])
        self.assertEqual(r["accounts"][0]["buying_power"]["KRW"],"100")
        self.assertNotIn("123456789",json.dumps(r))
        self.assertNotIn("987654321",json.dumps(r))
        self.assertFalse(r["order_authorized"])
        self.assertFalse(r["decision_authorized"])
    def test_missing_fx_no_partial_total(self):
        def read(path,**kw):
            if path=="/api/v1/exchange-rate": raise OSError("fixture")
            return fixture(path,**kw)
        r=collect(read,lambda:NOW)
        self.assertIsNone(r["securities_value_krw"])
        self.assertEqual(r["fx_state"],"UNAVAILABLE")
        self.assertTrue(all(h["securities_weight_fraction"] is None for a in r["accounts"] for h in a["holdings"]))
    def test_pagination_or_duplicate_fails(self):
        for kind in ("page","duplicate"):
            def read(path,**kw):
                r=fixture(path,**kw)
                if path=="/api/v1/holdings":
                    if kind=="page": r["nextCursor"]="next"
                    else: r["items"]*=2
                return r
            with self.assertRaises(Blocked):
                collect(read,lambda:NOW)
    def test_numeric_validation(self):
        for x in [True,1.0,"NaN","1.0000000000001",Decimal("Infinity")]:
            with self.assertRaises(Blocked): number(x)
    def test_snapshot_window_bound(self):
        times=iter([NOW,NOW+timedelta(seconds=121)])
        with self.assertRaisesRegex(Blocked,"SNAPSHOT_WINDOW_INVALID"):
            collect(fixture,lambda:next(times))
    def test_event_during_refresh_rejects_result(self):
        cache=SnapshotCache()
        old=cache.begin()
        cache.invalidate()
        self.assertFalse(cache.finish(old,collect(fixture,lambda:NOW)))
        self.assertEqual(cache.view(NOW)["state"],"RECONCILIATION_REQUIRED")
        new=cache.begin()
        self.assertTrue(cache.finish(new,collect(fixture,lambda:NOW)))
        self.assertTrue(cache.view(NOW)["current_observation"])
        cache.invalidate()
        self.assertFalse(cache.view(NOW)["current_observation"])
        self.assertIsNotNone(cache.view(NOW)["last_observation"])
    def test_out_of_order_failure_and_stale(self):
        cache=SnapshotCache()
        a=cache.begin(); b=cache.begin()
        self.assertFalse(cache.finish(a,collect(fixture,lambda:NOW)))
        self.assertTrue(cache.finish(b,collect(fixture,lambda:NOW)))
        self.assertEqual(cache.view(NOW+timedelta(minutes=6))["state"],"STALE")
        c=cache.begin()
        cache.fail(c)
        self.assertEqual(cache.view(NOW)["state"],"REFRESH_FAILED")
        self.assertFalse(cache.view(NOW)["current_observation"])
