import unittest
from dataclasses import replace
from method_gate import Metric,screen,compare,ComparableMethod
from quantrade.capabilities.valuation_crosscheck import ValuationMethodSnapshot,ValuationScenarioSnapshot
ASOF="2026-11-28T00:00:00+00:00"
QUOTE="2026-11-27T21:00:00+00:00"
def metric(v,u="CCY_PER_SHARE"):return Metric(v,"synthetic:metric",QUOTE,u)
def rows(profile,metrics):
    return {r["method_id"]:r for r in screen(case_id="case",profile=profile,as_of=ASOF,metrics=metrics,scope="SYNTHETIC_ONLY")["methods"]}
def methods():
    def one(mid,kind,values,refs):
        snap=ValuationMethodSnapshot(mid,kind,"synthetic:snapshot",100,0,tuple(ValuationScenarioSnapshot(s,.5,v) for s,v in zip(("bear","bull"),values)),("synthetic:output-"+mid,))
        return ComparableMethod(snap,"case","asset","USD",ASOF,QUOTE,"synthetic:quote","synthetic:share","synthetic:scenario","PRESENT_EQUITY_PER_DILUTED_SHARE",0,refs,("synthetic:growth",))
    return (one("a","FCFE_DCF",(80,160),("synthetic:earnings",)),one("b","PE",(140,100),("synthetic:earnings",)))
def run(ms=None):return compare(ms or methods(),scope="SYNTHETIC_ONLY")
class Tests(unittest.TestCase):
    def test_positive_pe(self):
        r=rows("OPERATING",{"NORMALIZED_EPS":metric(5),"COMPARABLE_PE":metric(20,"MULTIPLE")})
        self.assertEqual(r["PE"]["status"],"CANDIDATE_INPUTS_PRESENT")
        self.assertEqual(r["FCFF_DCF"]["status"],"BLOCKED")
    def test_negative_pe(self):
        r=rows("OPERATING",{"NORMALIZED_EPS":metric(-5),"COMPARABLE_PE":metric(20,"MULTIPLE")})
        self.assertIn("NONPOSITIVE_NORMALIZED_EPS",r["PE"]["reasons"])
    def test_bank_ev_ebitda(self):
        r=rows("FINANCIAL",{"NORMALIZED_EBITDA":metric(100,"CCY"),"COMPARABLE_EV_EBITDA":metric(10,"MULTIPLE"),"NET_DEBT":metric(-10,"CCY"),"DILUTED_SHARES":metric(10,"SHARES")})
        self.assertIn("PROFILE_NOT_IN_CANDIDATE_RULES",r["EV_EBITDA"]["reasons"])
    def test_reit_affo(self):
        r=rows("REIT",{"AFFO_PER_SHARE":metric(5),"COMPARABLE_P_AFFO":metric(12,"MULTIPLE")})
        self.assertEqual(r["P_AFFO"]["status"],"CANDIDATE_INPUTS_PRESENT")
    def test_pre_profit_pe(self):
        self.assertEqual(rows("PRE_PROFIT",{"NORMALIZED_EPS":metric(1),"COMPARABLE_PE":metric(20,"MULTIPLE")})["PE"]["status"],"BLOCKED")
    def test_unknown_profile(self):
        self.assertEqual(screen(case_id="case",profile="OTHER",as_of=ASOF,metrics={},scope="SYNTHETIC_ONLY")["state"],"PROFILE_REVIEW_REQUIRED")
    def test_ddm_invalid_spread(self):
        r=rows("FINANCIAL",{"SUSTAINABLE_DPS":metric(2),"COST_OF_EQUITY":metric(6,"PERCENT"),"DIVIDEND_GROWTH":metric(6,"PERCENT")})
        self.assertIn("DIVIDEND_GROWTH_NOT_BELOW_DISCOUNT",r["DDM"]["reasons"])
    def test_bad_metric_unit(self):
        with self.assertRaisesRegex(ValueError,"UNIT_MISMATCH"):rows("OPERATING",{"NORMALIZED_EPS":metric(5,"CCY")})
    def test_future_metric(self):
        with self.assertRaisesRegex(ValueError,"FUTURE_METRIC"):rows("OPERATING",{"NORMALIZED_EPS":replace(metric(5),observed_at="2027-01-01T00:00:00Z")})
    def test_real_scope(self):
        with self.assertRaisesRegex(ValueError,"LIVE_SCOPE_BLOCKED"):compare(methods(),scope="PUBLIC_CANDIDATE")
    def test_conservative(self):
        r=run()
        self.assertEqual(r["conservative_fair_value"],"90.000000")
        self.assertEqual(r["conservative_valuation_gap_pct"],"-10.000000")
        self.assertEqual([x["weighted_fair_value"] for x in r["method_weighted_values"]],[120,120])
        self.assertEqual(r["state"],"REVIEW_REQUIRED")
    def test_dependencies(self):
        r=run()
        self.assertEqual(r["distinct_families"],2)
        self.assertEqual(r["method_dependency_diagnostics"][0]["shared_refs"],["synthetic:earnings","synthetic:growth"])
        self.assertFalse(r["method_independence_established"])
    def test_same_family(self):
        a,b=methods();b=replace(b,snapshot=replace(b.snapshot,method_type="FCFF_DCF"))
        r=run((a,b));self.assertEqual(r["distinct_families"],1);self.assertTrue(r["method_dependency_diagnostics"][0]["same_family"])
    def test_duplicate_type(self):
        a,b=methods();b=replace(b,snapshot=replace(b.snapshot,method_type="FCFE_DCF"))
        with self.assertRaisesRegex(ValueError,"DUPLICATE_METHOD_TYPE"):run((a,b))
    def test_mismatched_contexts(self):
        a,b=methods()
        for k,v in [("case_id","other"),("asset_id","other"),("currency","KRW"),("quote_ref","synthetic:other"),("share_basis_ref","synthetic:other"),("scenario_definition_ref","synthetic:other"),("valuation_horizon_days",365),("value_basis","ENTERPRISE_VALUE")]:
            with self.subTest(k=k),self.assertRaisesRegex(ValueError,"CONTEXT_MISMATCH"):run((a,replace(b,**{k:v})))
    def test_mismatched_asof(self):
        a,b=methods()
        with self.assertRaisesRegex(ValueError,"AS_OF_MISMATCH"):run((a,replace(b,as_of="2026-11-29T00:00:00Z")))
    def test_future_quote(self):
        ms=tuple(replace(m,quote_as_of="2026-11-29T00:00:00Z") for m in methods())
        with self.assertRaisesRegex(ValueError,"FUTURE_QUOTE"):run(ms)
    def test_hurdle(self):
        ms=tuple(replace(m,snapshot=replace(m.snapshot,required_return_pct=10)) for m in methods())
        with self.assertRaisesRegex(ValueError,"HURDLE_NOT_APPLICABLE"):run(ms)
    def test_scenario_mismatch(self):
        a,b=methods();s=b.snapshot.scenarios;b=replace(b,snapshot=replace(b.snapshot,scenarios=(replace(s[0],probability=.6),replace(s[1],probability=.4))))
        with self.assertRaisesRegex(ValueError,"SCENARIO_MISMATCH"):run((a,b))
    def test_price_mismatch(self):
        a,b=methods()
        with self.assertRaisesRegex(ValueError,"PRICE_MISMATCH"):run((a,replace(b,snapshot=replace(b.snapshot,current_price=101))))
    def test_no_authority(self):
        r=run()
        for key in ("source_verified","economic_scenario_alignment_verified","portfolio_authorized","trade_authorized","valuation_gap_is_annualized_return"):self.assertFalse(r[key])
if __name__=="__main__":unittest.main()
