import unittest

from quantrade.capabilities.review_gate import (
    ReviewEvent,
    ReviewGatePolicy,
    evaluate_review_need,
)


class ReviewGateTests(unittest.TestCase):
    def test_quiet_state_avoids_review_without_calling_ai(self):
        result = evaluate_review_need([
            ReviewEvent("ROUTINE_MARKET_UPDATE", 0.2, "Research"),
        ])
        self.assertEqual("NO_REVIEW", result.level)
        self.assertFalse(result.authority["ai_called"])
        self.assertFalse(result.authority["investment_decision_created"])

    def test_material_change_requests_bounded_review(self):
        result = evaluate_review_need([
            ReviewEvent("REGIME_CHANGE", 0.6, "Research"),
        ])
        self.assertEqual("BOUNDED_REVIEW", result.level)

    def test_unresolved_departmental_disagreement_requests_review(self):
        result = evaluate_review_need([
            ReviewEvent("DEPARTMENT_DISAGREEMENT", 0.1, "Portfolio", unresolved=True),
        ])
        self.assertEqual("BOUNDED_REVIEW", result.level)

    def test_risk_breach_cannot_be_suppressed_by_low_materiality(self):
        result = evaluate_review_need([
            ReviewEvent("RISK_POLICY_BREACH", 0.01, "Risk & Compliance"),
        ])
        self.assertEqual("MANDATORY_REVIEW", result.level)
        self.assertFalse(result.authority["risk_veto_overridden"])

    def test_client_mandate_conflict_is_mandatory(self):
        result = evaluate_review_need([
            ReviewEvent("CLIENT_MANDATE_CONFLICT", 0.1, "Strategy"),
        ])
        self.assertEqual("MANDATORY_REVIEW", result.level)

    def test_invalid_materiality_fails_closed(self):
        with self.assertRaises(ValueError):
            evaluate_review_need([
                ReviewEvent("REGIME_CHANGE", 1.1, "Research"),
            ])

    def test_policy_is_explicit_and_replaceable(self):
        policy = ReviewGatePolicy(bounded_materiality=0.8, mandatory_materiality=0.95)
        result = evaluate_review_need(
            [ReviewEvent("REGIME_CHANGE", 0.6, "Research")],
            policy=policy,
        )
        self.assertEqual("NO_REVIEW", result.level)


if __name__ == "__main__":
    unittest.main()
