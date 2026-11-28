import unittest
from dataclasses import replace
from fcff_wacc import Amount,Year,Scenario,Request,evaluate
from method_gate import compare
from quantrade.capabilities.valuation_crosscheck import ValuationMethodSnapshot,ValuationScenarioSnapshot

ASOF="2026-11-28T00:00:00+00:00"
QUOTE="2026-11-27T21:00:00+00:00"
def a(v,unit="USD",ref="synthetic:filing",date=QUOTE):return Amount(v,unit,ref,date)
def fixture():
    # EBIT 100, tax 20%, D&A 10, capex 10, NWC 0 -> FCFF 80.
    # rf 4 + beta 1 * ERP 6 -> Ke 10%; Kd 5%*(1-.2)=4%;
    # 50% target debt -> WACC 7%; perpetual growth zero.
    s=Scenario("base",1,(Year(100,20,10,10,0),)*5,0,15,20,4,1,6,5,20,50,("synthetic:forecast",))
    return Request("case","asset","USD",ASOF,QUOTE,"synthetic:quote","synthetic:shares","synthetic:scenarios",
        a(100,"USD_PER_SHARE","synthetic:quote"),a(1000),a(200),a(100),a(20),a(10),a(5),a(5),a(10,"SHARES","synthetic:shares"),(s,))
def run(r=None):return evaluate(r or fixture(),scope="SYNTHETIC_ONLY")
def change(r=None,**kw):
    r=r or fixture()
    return replace(r,scenarios=(replace(r.scenarios[0],**kw),))
class Tests(unittest.TestCase):
    def test_wacc(self):
        report,_=run();s=report["scenarios"][0]
        self.assertEqual(s["cost_of_equity_pct"],"10.000000")
        self.assertEqual(s["after_tax_debt_cost_pct"],"4.000000")
        self.assertEqual(s["wacc_pct"],"7.000000")
        self.assertEqual(report["current_market_debt_weight_pct"],"16.666667")
    def test_fcff_and_ev_perpetuity(self):
        r,_=run();s=r["scenarios"][0]
        self.assertEqual(s["years"][0]["nopat"],"80.000000")
        self.assertEqual(s["years"][0]["fcff"],"80.000000")
        self.assertAlmostEqual(float(s["enterprise_value"]),80/.07,places=5)
    def test_equity_bridge(self):
        r,_=run();s=r["scenarios"][0]
        self.assertEqual(r["equity_bridge"]["net_adjustment"],"-100.000000")
        self.assertAlmostEqual(float(s["fair_value_per_share"]),(80/.07-100)/10,places=5)
    def test_reinvestment(self):
        r,_=run(change(terminal_growth_pct=3,terminal_roic_pct=15))
        s=r["scenarios"][0];self.assertEqual(s["terminal_nopat"],"82.400000")
        self.assertEqual(s["terminal_reinvestment"],"16.480000")
        self.assertEqual(s["terminal_fcff"],"65.920000")
    def test_negative_early_fcff(self):
        y=Year(-100,20,10,20,5)
        r,_=run(change(years=(y,Year(100,20,10,10,0))))
        self.assertEqual(r["scenarios"][0]["years"][0]["nopat"],"-100.000000")
        self.assertEqual(r["scenarios"][0]["years"][0]["fcff"],"-115.000000")
    def test_no_terminal_profit(self):
        with self.assertRaisesRegex(ValueError,"TERMINAL_OPERATING_PROFIT_REQUIRED"):run(change(years=(Year(-1,20,1,1,0),)))
    def test_growth_wacc(self):
        with self.assertRaisesRegex(ValueError,"TERMINAL_SPREAD"):run(change(terminal_growth_pct=7))
    def test_reinvestment_bound(self):
        with self.assertRaisesRegex(ValueError,"TERMINAL_REINVESTMENT_DOMAIN"):run(change(terminal_growth_pct=3,terminal_roic_pct=2))
    def test_no_negative_equity(self):
        with self.assertRaisesRegex(ValueError,"NONPOSITIVE_RESIDUAL_EQUITY"):run(replace(fixture(),market_debt=a(2000)))
    def test_mixed_currency(self):
        with self.assertRaisesRegex(ValueError,"UNIT_MISMATCH"):run(replace(fixture(),market_debt=a(200,"KRW")))
    def test_future_input(self):
        with self.assertRaisesRegex(ValueError,"FUTURE_SOURCE"):run(replace(fixture(),market_debt=a(200,date="2027-01-01T00:00:00Z")))
    def test_quote_binding(self):
        with self.assertRaisesRegex(ValueError,"QUOTE_BINDING"):run(replace(fixture(),current_price=a(100,"USD_PER_SHARE")))
    def test_shares_binding(self):
        with self.assertRaisesRegex(ValueError,"SHARE_BINDING"):run(replace(fixture(),diluted_shares=a(10,"SHARES")))
    def test_zero_shares(self):
        with self.assertRaisesRegex(ValueError,"CAPITAL_BASE"):run(replace(fixture(),diluted_shares=a(0,"SHARES","synthetic:shares")))
    def test_wrong_profile(self):
        with self.assertRaisesRegex(ValueError,"PROFILE_OR_BASIS"):run(replace(fixture(),profile="FINANCIAL"))
    def test_wrong_scale(self):
        with self.assertRaisesRegex(ValueError,"ACCOUNTING_BASIS"):run(replace(fixture(),unit_scale="MILLIONS"))
    def test_wrong_lease_policy(self):
        with self.assertRaisesRegex(ValueError,"ACCOUNTING_BASIS"):run(replace(fixture(),lease_policy="UNDEFINED"))
    def test_probabilities(self):
        with self.assertRaisesRegex(ValueError,"PROBABILITY_SUM"):run(change(probability=.9))
    def test_scenario_weighting(self):
        q=fixture();s=q.scenarios[0]
        r,_=run(replace(q,scenarios=(replace(s,probability=.5),replace(s,id="bear",probability=.5,years=(Year(50,20,10,10,0),)*5))))
        self.assertAlmostEqual(float(r["weighted_fair_value_per_share"]),(60/.07-100)/10,places=5)
    def test_context_bridge(self):
        report,m=run()
        other=replace(m,snapshot=ValuationMethodSnapshot("pe","PE","synthetic:pe",100,0,(ValuationScenarioSnapshot("base",1,120),),("synthetic:pe",)))
        cross=compare((m,other),scope="SYNTHETIC_ONLY")
        self.assertEqual(cross["conservative_fair_value"],report["weighted_fair_value_per_share"])
        self.assertFalse(cross["trade_authorized"])
    def test_closed_live(self):
        with self.assertRaisesRegex(ValueError,"LIVE_SCOPE_BLOCKED"):evaluate(fixture(),scope="PUBLIC_CANDIDATE")
    def test_no_authority(self):
        r,_=run()
        for key in ("source_verified","assumptions_validated","economic_overlap_verified","portfolio_authorized","trade_authorized"):self.assertFalse(r[key])
if __name__=="__main__":unittest.main()
