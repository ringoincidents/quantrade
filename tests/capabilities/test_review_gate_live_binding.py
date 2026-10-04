import unittest

from scripts.review_gate_shadow_binding import build_shadow_binding


class ReviewGateLiveBindingTests(unittest.TestCase):
    def test_sanitized_client_conflict_matches_existing_routing_intent(self):
        artifact = build_shadow_binding({
            "schema": "quantrade_institutional_case_precheck_v1",
            "experiment_id": "QT-LIVE-003",
            "run_id": "fixture",
            "mode": "PAPER_PRECHECK",
            "strategy_directive": {"reasons": ["CLIENT_PLAN_CONFLICT"]},
            "ai_call_gate": {
                "call_ai": True,
                "call_type": "CLIENT_STRATEGY_REVIEW",
                "reasons": ["CLIENT_MANDATE_CONFLICT"],
            },
        })
        self.assertEqual("MANDATORY_REVIEW", artifact["shadow_gate"]["level"])
        self.assertTrue(artifact["comparison"]["routing_intent_agreement"])
        self.assertFalse(artifact["source"]["private_client_values_consumed"])
        self.assertFalse(artifact["authority"]["existing_gate_replaced"])
        self.assertFalse(artifact["authority"]["actual_path_changed"])

    def test_unknown_actual_telemetry_is_not_invented(self):
        artifact = build_shadow_binding({
            "ai_call_gate": {"call_ai": True, "reasons": ["CLIENT_MANDATE_CONFLICT"]},
        })
        self.assertIsNone(artifact["comparison"]["actual_ai_call_observed"])
        self.assertIsNone(artifact["comparison"]["model_cost_usd_observed"])
        self.assertIsNone(artifact["comparison"]["latency_ms_observed"])
        self.assertEqual(0.0, artifact["comparison"]["savings_claimed_usd"])

    def test_unknown_reason_does_not_gain_authority(self):
        artifact = build_shadow_binding({
            "ai_call_gate": {"call_ai": True, "reasons": ["UNMAPPED_FUTURE_REASON"]},
        })
        self.assertEqual("NO_REVIEW", artifact["shadow_gate"]["level"])
        self.assertFalse(artifact["comparison"]["routing_intent_agreement"])
        self.assertFalse(artifact["authority"]["automatic_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
