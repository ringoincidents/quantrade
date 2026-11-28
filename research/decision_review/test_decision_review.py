import unittest
from decision_review import Case,route,call_plan
class DecisionReviewTests(unittest.TestCase):
    def test_routine(self):
        for k in ("DOC_UI_ROUTINE","LOCAL_BUG_FIX","REGRESSION_TEST","EXISTING_MODULE_EXTENSION"):
            p=route(Case(k));self.assertIn(p["grade"],("D0","D1"));self.assertEqual(p["required_independent_reviews"],0)
            self.assertEqual(p["institutional_gate"],"NO_REVIEW");self.assertFalse(p["founder_approval_required"])
    def test_hypothesis(self):
        p=route(Case("NEW_HYPOTHESIS"));self.assertEqual(p["grade"],"D2");self.assertEqual(p["required_independent_reviews"],1)
        self.assertEqual(p["institutional_gate"],"BOUNDED_REVIEW")
    def test_override_routine(self):
        for f in ("security_impact","capital_impact","privacy_impact","production_impact","irreversible","extra_cost","uncertain_scope"):
            p=route(Case("DOC_UI_ROUTINE",**{f:True}));self.assertEqual(p["grade"],"D3");self.assertEqual(p["required_independent_reviews"],2)
            self.assertTrue(p["founder_approval_required"])
    def test_dissent_escalates(self):
        self.assertEqual(route(Case("NEW_HYPOTHESIS",unresolved_material_finding=True))["grade"],"D3")
    def test_unknown_fail_closed(self):
        p=route(Case("NOT_CLASSIFIED"));self.assertEqual(p["grade"],"D3");self.assertIn("UNCLASSIFIED_SCOPE",p["reasons"])
    def test_canonical_risk_events(self):
        for k in ("RISK_POLICY_BREACH","CLIENT_MANDATE_CONFLICT","LIQUIDITY_CONSTRAINT_BREACH"):
            self.assertEqual(route(Case(k))["institutional_gate"],"MANDATORY_REVIEW")
    def test_no_cost_by_default(self):
        p=call_plan(Case("NEW_HYPOTHESIS"));self.assertEqual(p["planned_calls"],0);self.assertFalse(p["external_call_authorized"])
    def test_sensitive_never_planned(self):
        p=call_plan(Case("SECURITY_BOUNDARY"),scope="PRIVATE",provider_approved=True,budget_reserved=True,max_calls_remaining=10)
        self.assertEqual(p["call_plan_state"],"BLOCKED_DISCLOSURE_SCOPE")
    def test_budget_not_downgraded(self):
        p=call_plan(Case("SECURITY_BOUNDARY"),scope="SYNTHETIC_APPROVED",provider_approved=True,budget_reserved=True,max_calls_remaining=1)
        self.assertEqual(p["call_plan_state"],"BLOCKED_BUDGET");self.assertEqual(p["required_independent_reviews"],2)
    def test_candidate_not_authorized(self):
        p=call_plan(Case("SECURITY_BOUNDARY"),scope="PUBLIC_APPROVED",provider_approved=True,budget_reserved=True,max_calls_remaining=2)
        self.assertEqual(p["planned_calls"],2);self.assertFalse(p["external_call_authorized"]);self.assertFalse(p["review_completed"]);self.assertFalse(p["decision_authorized"])
    def test_invalid_flags(self):
        with self.assertRaises(ValueError):route(Case("DOC_UI_ROUTINE",security_impact=1))
        with self.assertRaises(ValueError):call_plan(Case("NEW_HYPOTHESIS"),max_calls_remaining=True)
