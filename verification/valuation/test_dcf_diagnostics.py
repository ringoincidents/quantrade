import unittest
from dataclasses import replace
from decimal import localcontext
from quantrade.capabilities.cash_flow_valuation import CashFlowDCFInput,CashFlowDCFScenario
from dcf_diagnostics import diagnostics,checked

KW={"cash_flow_basis":"FCFE_PER_SHARE","discount_basis":"COST_OF_EQUITY"}
def fixture():
    return CashFlowDCFInput("SYNTHETIC-DCF","SYNTHETIC","2026-11-28T00:00:00+00:00",100,"USD",10,12,
        (CashFlowDCFScenario("base","Base",1,1,0,0,10,5,("synthetic:assumption",)),))
def run(r=None,**kw):
    return diagnostics(r or fixture(),scenario_id="base",**(KW|kw))
class Tests(unittest.TestCase):
    def test_perpetuity_and_reverse(self):
        a=run()
        self.assertEqual(a["weighted_fair_value"],"100.000000")
        self.assertEqual(a["illustrative_entry_price"],"80.000000")
        self.assertEqual(a["valuation_gap_pct"],"0.000000")
        self.assertAlmostEqual(float(a["reverse_dcf"]["growth_pct"]),0,places=5)
        self.assertAlmostEqual(float(a["reverse_dcf"]["price_residual"]),0,places=5)
        self.assertFalse(a["valuation_gap_is_annualized_return"])
    def test_sensitivity_monotonic(self):
        cells=run()["sensitivity"]["cells"]
        values={(c["discount_rate_pct"],c["explicit_growth_pct"]):float(c["fair_value"]) for c in cells}
        self.assertEqual(values[(10,0)],100)
        self.assertGreater(values[(8,0)],values[(10,0)])
        self.assertGreater(values[(10,0)],values[(12,0)])
        self.assertGreater(values[(10,2)],values[(10,-2)])
    def test_terminal_share(self):
        a=run()
        self.assertAlmostEqual(float(a["scenarios"][0]["terminal_value_share_pct"]),100/1.1**5,places=5)
        self.assertFalse(a["scenarios"][0]["terminal_dominant"])
    def test_terminal_spread(self):
        r=fixture();r=replace(r,scenarios=(replace(r.scenarios[0],terminal_growth_pct=9.5),))
        with self.assertRaisesRegex(ValueError,"TERMINAL_SPREAD_MINIMUM"):run(r)
    def test_invalid_grid_cell(self):
        r=fixture();r=replace(r,scenarios=(replace(r.scenarios[0],terminal_growth_pct=8),))
        a=run(r)
        self.assertEqual(sum(c["state"]=="BLOCKED" for c in a["sensitivity"]["cells"]),3)
    def test_wrong_discount_basis(self):
        with self.assertRaisesRegex(ValueError,"CASH_FLOW_DISCOUNT_MISMATCH"):run(discount_basis="WACC")
    def test_wrong_cash_flow_basis(self):
        with self.assertRaisesRegex(ValueError,"CASH_FLOW_DISCOUNT_MISMATCH"):run(cash_flow_basis="FCFF")
    def test_unbounded_horizon(self):
        r=fixture();r=replace(r,scenarios=(replace(r.scenarios[0],explicit_years=1000000),))
        with self.assertRaisesRegex(ValueError,"HORIZON_BOUND"):run(r)
    def test_fractional_horizon(self):
        r=fixture();r=replace(r,scenarios=(replace(r.scenarios[0],explicit_years=5.5),))
        with self.assertRaisesRegex(ValueError,"HORIZON_BOUND"):run(r)
    def test_negative_anchor(self):
        with self.assertRaisesRegex(ValueError,"POSITIVE_PRICE_AND_CASH_FLOW"):run(replace(fixture(),owner_cash_flow_per_share=-1))
    def test_nan(self):
        with self.assertRaisesRegex(ValueError,"NUMERIC_BOUND"):run(replace(fixture(),current_price=float("nan")))
    def test_timezone(self):
        with self.assertRaisesRegex(ValueError,"AS_OF_TIMEZONE"):run(replace(fixture(),as_of="2026-11-28"))
    def test_assumptions_required(self):
        r=fixture();r=replace(r,scenarios=(replace(r.scenarios[0],assumption_refs=()),))
        with self.assertRaisesRegex(ValueError,"ASSUMPTION_REFERENCE_REQUIRED"):run(r)
    def test_probability(self):
        r=fixture();r=replace(r,scenarios=(replace(r.scenarios[0],probability=.99),))
        with self.assertRaisesRegex(ValueError,"PROBABILITY_SUM_EXACT"):run(r)
    def test_weighted_scenario(self):
        r=fixture();base=r.scenarios[0]
        r=replace(r,scenarios=(replace(base,probability=.5),replace(base,scenario_id="bear",probability=.5,starting_cash_flow_factor=.5)))
        self.assertEqual(run(r)["weighted_fair_value"],"75.000000")
    def test_reverse_no_solution(self):
        self.assertEqual(run(replace(fixture(),current_price=1e10))["reverse_dcf"]["state"],"OUTSIDE_SEARCH_RANGE")
    def test_reverse_reconstructs_price(self):
        a=run(replace(fixture(),current_price=150))
        self.assertEqual(a["reverse_dcf"]["state"],"SOLVED_CONDITIONAL")
        self.assertGreater(float(a["reverse_dcf"]["growth_pct"]),0)
        self.assertAlmostEqual(float(a["reverse_dcf"]["price_residual"]),0,places=5)
    def test_decimal_context_independent(self):
        with localcontext() as c:
            c.prec=5
            self.assertEqual(run()["weighted_fair_value"],"100.000000")
    def test_no_authority(self):
        a=run()
        self.assertFalse(a["basis"]["basis_verified"])
        self.assertFalse(a["assumptions_validated"])
        self.assertFalse(a["portfolio_authorized"])
        self.assertFalse(a["trade_authorized"])
if __name__=="__main__":unittest.main()
