import unittest
from dataclasses import replace,asdict
from valuation_dossier import DossierInput,ScenarioDefinition,evaluate,METHODS
from method_gate import digest
from test_fcff_wacc import fixture as fcff_fixture
from test_peer_valuation import fixture as peer_fixture
from quantrade.capabilities.cash_flow_valuation import CashFlowDCFInput,CashFlowDCFScenario

def fixture():
    f=fcff_fixture();p=peer_fixture()
    defs=(ScenarioDefinition("base",1,"Flat operating profit and stable capital requirements.","synthetic:base"),)
    ref="synthetic:scenario:"+digest([asdict(x) for x in defs])
    f=replace(f,scenario_definition_ref=ref,scenarios=(replace(f.scenarios[0],assumption_refs=("synthetic:base","synthetic:forecast")),))
    t=replace(p.target,asset_id=f.asset_id,debt=200,excess_cash=100,nonoperating_assets=20,nci=10,preferred=5,other_claims=5)
    p=replace(p,as_of=f.as_of,scenario_definition_ref=ref,target=t)
    c=CashFlowDCFInput(f.case_id,f.asset_id,f.as_of,100,"USD",10,0,(CashFlowDCFScenario("base","Base",1,1,0,0,10,5,("synthetic:base",)),))
    return DossierInput(f,c,p,defs,("synthetic:quote","synthetic:shares","synthetic:fcfe"),"base")
def run(r=None):return evaluate(r or fixture(),scope="SYNTHETIC_ONLY")
class Tests(unittest.TestCase):
    def test_full_dossier(self):
        result=run();b=result["dossier"]
        self.assertEqual(b["state"],"REVIEW_REQUIRED")
        self.assertEqual(tuple(x["method"] for x in b["methods"]),METHODS)
        self.assertEqual(b["summary"]["calculated_count"],4)
        self.assertEqual(b["crosscheck"]["distinct_families"],2)
        self.assertEqual(b["crosscheck"]["conservative_fair_value"],"98.000000")
        self.assertEqual(result["dossier_sha256"],digest(b))
    def test_repeatability(self):
        self.assertEqual(run(),run())
    def test_no_authority(self):
        b=run()["dossier"]
        for k in ("source_verified","assumptions_validated","fcfe_fcff_reconciled","scenario_economics_reconciled","valuation_target_approved","portfolio_authorized","trade_authorized"):self.assertFalse(b[k])
    def test_mandatory_missing_peers(self):
        r=fixture();b=run(replace(r,relative=replace(r.relative,peers=r.relative.peers[:2])))["dossier"]
        self.assertEqual(b["summary"]["calculated_count"],2)
        self.assertEqual(b["state"],"BLOCKED_INCOMPLETE_VALUATION")
        self.assertIsNone(b["crosscheck"])
        self.assertEqual(b["crosscheck_block_reason"],"MANDATORY_METHOD_BLOCKED")
        self.assertEqual([x["state"] for x in b["methods"]][2:],["BLOCKED_INSUFFICIENT_PEERS"]*2)
    def test_one_method_blocked(self):
        r=fixture();b=run(replace(r,fcfe=replace(r.fcfe,owner_cash_flow_per_share=-1)))["dossier"]
        self.assertEqual(b["summary"]["calculated_count"],3)
        self.assertIsNone(b["crosscheck"])
        self.assertEqual(b["methods"][0]["state"],"BLOCKED_INPUT_OR_DOMAIN")
    def test_negative_income_blocks_only_pe(self):
        r=fixture();p=replace(r.relative,target=replace(r.relative.target,common_income=-1))
        b=run(replace(r,relative=p))["dossier"]
        self.assertEqual(b["summary"]["calculated_count"],3)
        self.assertEqual(b["methods"][2]["state"],"BLOCKED_INPUT_OR_DOMAIN")
        self.assertIsNone(b["crosscheck"])
    def test_currency_mismatch(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"CURRENCY_MISMATCH"):run(replace(r,fcfe=replace(r.fcfe,currency="KRW")))
    def test_price_mismatch(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"PRICE_MISMATCH"):run(replace(r,fcfe=replace(r.fcfe,current_price=101)))
    def test_share_count_mismatch(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"SHARE_COUNT_MISMATCH"):run(replace(r,relative=replace(r.relative,target=replace(r.relative.target,diluted_shares=11))))
    def test_capital_component_mismatch(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"CAPITAL_BRIDGE_MISMATCH"):run(replace(r,relative=replace(r.relative,target=replace(r.relative.target,debt=201,excess_cash=101))))
    def test_scenario_definition_tamper(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"DEFINITION_DIGEST_MISMATCH"):run(replace(r,definitions=(replace(r.definitions[0],narrative="Changed"),)))
    def test_scenario_ref_missing(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"SCENARIO_ASSUMPTION_BINDING"):run(replace(r,fcfe=replace(r.fcfe,scenarios=(replace(r.fcfe.scenarios[0],assumption_refs=("synthetic:other",)),))))
    def test_probability_mismatch(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"SCENARIO_PROBABILITY"):run(replace(r,fcfe=replace(r.fcfe,scenarios=(replace(r.fcfe.scenarios[0],probability=.9),))))
    def test_source_context(self):
        r=fixture()
        with self.assertRaisesRegex(ValueError,"FCFE_CONTEXT_REFS"):run(replace(r,fcfe_input_refs=("synthetic:fcfe",)))
    def test_future_target_not_ignored(self):
        r=fixture();p=replace(r.relative,target=replace(r.relative.target,published_at="2027-01-01T00:00:00Z"))
        b=run(replace(r,relative=p))["dossier"]
        self.assertIsNone(b["crosscheck"])
    def test_no_live(self):
        with self.assertRaisesRegex(ValueError,"LIVE_SCOPE_BLOCKED"):evaluate(fixture(),scope="PUBLIC_CANDIDATE")
if __name__=="__main__":unittest.main()
