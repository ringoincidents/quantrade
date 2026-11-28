import unittest,copy
from decimal import Decimal
from performance_view import evaluate,fixture,matched_trade,trade_fixture,snapshot
class PerformanceTests(unittest.TestCase):
    def calc(self,rows=None,**kw):
        return evaluate(fixture() if rows is None else rows,**{"currency":"KRW","scope":"FULL_NAV","flow_coverage_confirmed":True,**kw})
    def test_exact_returns(self):
        v=self.calc()
        self.assertEqual(Decimal(v["twr_fraction"]),Decimal(".1495"))
        self.assertEqual(Decimal(v["investment_pnl"]),Decimal("152000"))
        self.assertEqual(Decimal(v["sampled_max_drawdown_fraction"]),Decimal("-.05"))
        self.assertFalse(v["independent_flow_coverage_verified"])
    def test_pure_deposit_no_return(self):
        rows=fixture()[:2];rows[1].update(nav_before_flow="1000000",nav_after_flow="1500000")
        v=self.calc(rows)
        self.assertEqual(Decimal(v["twr_fraction"]),0);self.assertEqual(Decimal(v["investment_pnl"]),0)
    def test_incomplete_nav_or_flows(self):
        for kwargs in ({"scope":"SECURITIES_ONLY"},{"flow_coverage_confirmed":False}):
            with self.assertRaises(ValueError):self.calc(**kwargs)
    def test_bad_reconciliation(self):
        rows=fixture();rows[1]["external_flow"]="0"
        with self.assertRaisesRegex(ValueError,"FLOW_RECONCILIATION_FAILED"):self.calc(rows)
    def test_unsorted_currency_and_missing_marks(self):
        rows=fixture()
        with self.assertRaises(ValueError):self.calc(rows[::-1])
        rows[2]["currency"]="USD"
        with self.assertRaises(ValueError):self.calc(rows)
        with self.assertRaises(ValueError):self.calc([])
    def test_trade_matched(self):
        v=matched_trade(trade_fixture())
        self.assertEqual(Decimal(v["net_price_pnl_after_fees"]),98)
        self.assertEqual(Decimal(v["net_return_on_entry_notional"]),Decimal(".098"))
    def test_no_hindsight_or_unmatched_trade(self):
        for k,val in (("lot_state","UNMATCHED"),("side","SHORT"),("thesis_recorded_at","2026-11-03T00:00:00Z")):
            r=trade_fixture();r[k]=val
            with self.assertRaises(ValueError):matched_trade(r)
    def test_synthetic_authority(self):
        v=snapshot();self.assertFalse(v["actual_account_connected"]);self.assertFalse(v["order_authorized"])
