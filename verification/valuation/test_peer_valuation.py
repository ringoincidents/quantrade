import unittest
from dataclasses import replace
from peer_valuation import Firm,Adjustment,Scenario,Request,evaluate
from method_gate import compare
from quantrade.capabilities.valuation_crosscheck import ValuationMethodSnapshot,ValuationScenarioSnapshot
ASOF="2026-11-28T00:00:00Z"
QUOTE="2026-11-27T21:00:00Z"
def firm(id,price=100):
    return Firm(id,"industrial","US","US_GAAP","USD","2025-01-01","2025-12-31","2026-03-01T00:00:00Z",QUOTE,price,10,100,200,100,0,0,0,20,0,1000,5,15,(),("synthetic:filing-"+id,"synthetic:quote","synthetic:shares"))
def fixture(method="PE"):
    return Request("case",ASOF,"synthetic:quote","synthetic:shares","synthetic:scenarios","synthetic:universe",firm("target"),(firm("a",80),firm("b",100),firm("c",120)),(Scenario("base",1,1,1,50,("synthetic:base",)),),method)
def run(r=None):return evaluate(r or fixture(),scope="SYNTHETIC_ONLY")
class Tests(unittest.TestCase):
    def test_pe(self):
        a,_=run()
        self.assertEqual(a["multiple_distribution"],{"min":"8.000000","p25":"9.000000","median":"10.000000","p75":"11.000000","max":"12.000000"})
        self.assertEqual(a["weighted_fair_value_per_share"],"100.000000")
    def test_ev_ebitda(self):
        a,_=run(fixture("EV_EBITDA"))
        self.assertEqual(a["multiple_distribution"]["median"],"5.400000")
        self.assertEqual(a["target_ev_equity_bridge"],"80.000000")
        self.assertEqual(a["weighted_fair_value_per_share"],"100.000000")
    def test_normalization(self):
        r=fixture()
        t=replace(r.target,common_income=120,ebitda=180,adjustments=(Adjustment("gain","DISPOSAL_GAIN_LOSS",20,0,"synthetic:gain"),Adjustment("loss","DISASTER_LOSS",0,-20,"synthetic:loss")))
        a,_=run(replace(r,target=t))
        self.assertEqual(a["target_normalized_eps"],"10.000000")
        self.assertEqual(a["target_normalized_ebitda"],"200.000000")
    def test_peer_normalization(self):
        r=fixture();p=replace(r.peers[0],common_income=120,adjustments=(Adjustment("gain","DISPOSAL_GAIN_LOSS",20,0,"synthetic:gain"),))
        a,_=run(replace(r,peers=(p,*r.peers[1:])))
        self.assertEqual(a["included"][0]["multiple"],"8.000000")
    def test_recurring_expense_not_removed(self):
        r=fixture();t=replace(r.target,adjustments=(Adjustment("sbc","STOCK_COMPENSATION",-10,-10,"synthetic:sbc"),))
        with self.assertRaisesRegex(ValueError,"ADJUSTMENT_CATEGORY"):run(replace(r,target=t))
    def test_duplicate_adjustment(self):
        r=fixture();a=Adjustment("a","DISASTER_LOSS",-5,-5,"synthetic:a")
        with self.assertRaisesRegex(ValueError,"ADJUSTMENT_ID"):run(replace(r,target=replace(r.target,adjustments=(a,a))))
    def test_peer_exclusions(self):
        r=fixture();extra=(replace(firm("d"),business_group="other"),replace(firm("e"),revenue_growth_pct=40),replace(firm("f"),operating_margin_pct=50),replace(firm("g"),revenue=100000),replace(firm("h"),common_income=-5),r.target)
        a,_=run(replace(r,peers=r.peers+extra))
        self.assertEqual(len(a["included"]),3)
        reasons={x["asset_id"]:x["reasons"] for x in a["excluded"]}
        for k,reason in [("d","MISMATCH_BUSINESS_GROUP"),("e","GROWTH_GAP"),("f","MARGIN_GAP"),("g","SIZE_GAP"),("h","NONPOSITIVE_MULTIPLE_COMPONENT"),("target","SELF")]:self.assertIn(reason,reasons[k])
    def test_same_context(self):
        r=fixture();extras=(replace(firm("d"),currency="KRW"),replace(firm("e"),accounting_basis="IFRS"),replace(firm("f"),quote_as_of="2026-11-26T21:00:00Z"),replace(firm("g"),geography="KR"),replace(firm("h"),period_start="2025-02-01",period_end="2026-01-31"))
        a,_=run(replace(r,peers=r.peers+extras))
        self.assertEqual(len(a["excluded"]),5)
    def test_future(self):
        r=fixture();p=replace(firm("d"),published_at="2027-01-01T00:00:00Z")
        a,_=run(replace(r,peers=r.peers+(p,)))
        self.assertIn("INVALID_INPUT:PIT_OR_QUOTE",a["excluded"][0]["reasons"])
    def test_insufficient(self):
        r=fixture();a,s=run(replace(r,peers=r.peers[:2]))
        self.assertEqual(a["state"],"BLOCKED_INSUFFICIENT_PEERS");self.assertIsNone(s)
    def test_negative_target(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"TARGET_DENOMINATOR_NONPOSITIVE"):run(replace(r,target=replace(r.target,common_income=-1)))
    def test_duplicate_peer(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_PEER"):run(replace(r,peers=r.peers+(r.peers[0],)))
    def test_no_outlier_removal(self):
        r=fixture();a,_=run(replace(r,peers=r.peers+(firm("outlier",10000),)))
        self.assertEqual(len(a["included"]),4)
        self.assertEqual(a["multiple_distribution"]["max"],"1000.000000")
        self.assertEqual(a["multiple_distribution"]["median"],"11.000000")
    def test_scenario_weights(self):
        r=fixture();s=r.scenarios[0]
        a,_=run(replace(r,scenarios=(replace(s,id="bear",probability=.5,peer_quantile_pct=25),replace(s,id="bull",probability=.5,peer_quantile_pct=75,normalized_income_factor=2))))
        self.assertEqual(a["weighted_fair_value_per_share"],"155.000000")
    def test_bad_probability(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"PROBABILITY_SUM"):run(replace(r,scenarios=(replace(r.scenarios[0],probability=.9),)))
    def test_bridge(self):
        a,m=run()
        other=replace(m,snapshot=ValuationMethodSnapshot("fcff","FCFF_DCF","synthetic:fcff",100,0,(ValuationScenarioSnapshot("base",1,110),),("synthetic:fcff",)))
        cross=compare((m,other),scope="SYNTHETIC_ONLY")
        self.assertEqual(cross["conservative_fair_value"],a["weighted_fair_value_per_share"])
    def test_context_refs(self):
        with self.assertRaisesRegex(ValueError,"TARGET_CONTEXT_REFS"):run(replace(fixture(),quote_ref="synthetic:wrong"))
    def test_live_blocked(self):
        with self.assertRaisesRegex(ValueError,"LIVE_SCOPE_BLOCKED"):evaluate(fixture(),scope="PUBLIC_CANDIDATE")
    def test_no_authority(self):
        a,_=run()
        for k in ("universe_complete_verified","source_verified","adjustments_verified","thresholds_adopted","portfolio_authorized","trade_authorized","valuation_gap_is_annualized_return"):self.assertFalse(a[k])
if __name__=="__main__":unittest.main()
