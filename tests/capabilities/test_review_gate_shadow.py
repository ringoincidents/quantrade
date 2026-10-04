import unittest

from quantrade.capabilities.review_gate import ReviewEvent
from quantrade.capabilities.review_gate_shadow import (
    ActualReviewOutcome,
    observe_shadow,
    summarize_shadow,
)


class ReviewGateShadowTests(unittest.TestCase):
    def test_shadow_never_changes_actual_path(self):
        record = observe_shadow(
            [ReviewEvent("ROUTINE_MARKET_UPDATE", 0.1, "Research")],
            ActualReviewOutcome(True, "BOUNDED_REVIEW", 0.02, 1500),
        )
        self.assertTrue(record.measurement["avoidable_review_candidate"])
        self.assertFalse(record.authority["actual_path_changed"])
        self.assertFalse(record.authority["ai_call_suppressed"])
        self.assertEqual(0.0, record.measurement["savings_claimed_usd"])

    def test_missing_mandatory_review_is_flagged_not_fixed_by_shadow(self):
        record = observe_shadow(
            [ReviewEvent("RISK_POLICY_BREACH", 0.01, "Risk & Compliance")],
            ActualReviewOutcome(False),
        )
        self.assertEqual("MANDATORY_REVIEW", record.gate_result["level"])
        self.assertTrue(record.measurement["potential_false_negative"])
        self.assertFalse(record.authority["investment_decision_changed"])

    def test_summary_requires_human_organizational_review_for_promotion(self):
        records = [
            observe_shadow(
                [ReviewEvent("ROUTINE_MARKET_UPDATE", 0.1, "Research")],
                ActualReviewOutcome(True, "BOUNDED_REVIEW", 0.01, 1000),
            ),
            observe_shadow(
                [ReviewEvent("CLIENT_MANDATE_CONFLICT", 0.1, "Strategy")],
                ActualReviewOutcome(True, "MANDATORY_REVIEW", 0.03, 2000),
            ),
        ]
        summary = summarize_shadow(records)
        self.assertEqual(2, summary["sample_count"])
        self.assertEqual(1, summary["avoidable_review_candidates"])
        self.assertEqual(1, summary["escalation_matches"])
        self.assertEqual("REVIEW_REQUIRED", summary["promotion_recommendation"])
        self.assertFalse(summary["authority"]["automatic_promotion_allowed"])
        self.assertEqual(0.0, summary["claimed_savings_usd"])

    def test_negative_measurement_fails_closed(self):
        with self.assertRaises(ValueError):
            observe_shadow(
                [ReviewEvent("ROUTINE_MARKET_UPDATE", 0.1, "Research")],
                ActualReviewOutcome(True, estimated_model_cost_usd=-1),
            )


if __name__ == "__main__":
    unittest.main()
