import unittest

from quantrade.capabilities.review_gate import ReviewEvent
from quantrade.capabilities.review_gate_evaluation import (
    EvaluationScenario,
    build_evaluation_artifact,
    canonical_scenarios,
)


class ReviewGateEvaluationHarnessTests(unittest.TestCase):
    def test_canonical_matrix_covers_all_three_review_levels(self):
        artifact = build_evaluation_artifact()
        levels = {item["observed_level"] for item in artifact["results"]}
        self.assertEqual({"NO_REVIEW", "BOUNDED_REVIEW", "MANDATORY_REVIEW"}, levels)
        self.assertEqual(7, artifact["scenario_count"])
        self.assertEqual(0, artifact["expected_mismatch_count"])

    def test_risk_and_client_safety_scenarios_are_mandatory(self):
        artifact = build_evaluation_artifact()
        by_id = {item["scenario_id"]: item for item in artifact["results"]}
        for scenario_id in (
            "risk_policy_breach",
            "client_mandate_conflict",
            "liquidity_constraint_breach",
        ):
            self.assertEqual("MANDATORY_REVIEW", by_id[scenario_id]["observed_level"])

    def test_disagreement_is_preserved_not_auto_fixed(self):
        scenario = EvaluationScenario(
            "deliberate_disagreement",
            "Legacy asks for AI while deterministic event is routine.",
            (ReviewEvent("ROUTINE_OBSERVATION", 0.10, "Research"),),
            "NO_REVIEW",
            "Performance & Learning",
            True,
        )
        artifact = build_evaluation_artifact((scenario,))
        self.assertEqual(["deliberate_disagreement"], artifact["disagreements"]["legacy_routing"])
        self.assertFalse(artifact["promotion"]["automatic_promotion_allowed"])

    def test_high_materiality_novel_event_is_not_silently_ignored(self):
        by_id = {
            scenario.scenario_id: scenario for scenario in canonical_scenarios()
        }
        artifact = build_evaluation_artifact((by_id["high_materiality_novel_event"],))
        self.assertEqual("MANDATORY_REVIEW", artifact["results"][0]["observed_level"])

    def test_harness_has_no_authority(self):
        artifact = build_evaluation_artifact()
        self.assertFalse(artifact["authority"]["ai_called"])
        self.assertFalse(artifact["authority"]["risk_policy_changed"])
        self.assertFalse(artifact["authority"]["investment_decision_created"])
        self.assertFalse(artifact["authority"]["execution_authorized"])
        self.assertFalse(artifact["promotion"]["production_authority_granted"])


if __name__ == "__main__":
    unittest.main()
