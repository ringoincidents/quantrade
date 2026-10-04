import unittest

from scripts.review_gate_shadow_binding import build_shadow_binding


class ReasonTranslationSafetyTests(unittest.TestCase):
    def test_mapped_reasons_report_complete_coverage(self):
        artifact = build_shadow_binding({
            "strategy_directive": {"reasons": ["CLIENT_PLAN_CONFLICT"]},
            "ai_call_gate": {"call_ai": True, "reasons": ["CLIENT_MANDATE_CONFLICT"]},
        })
        translation = artifact["reason_translation"]
        self.assertTrue(translation["coverage_complete"])
        self.assertEqual(0, translation["unmapped_count"])
        self.assertFalse(artifact["comparison"]["requires_translation_review"])

    def test_unknown_reason_is_preserved_not_dropped(self):
        artifact = build_shadow_binding({
            "ai_call_gate": {"call_ai": True, "reasons": ["UNMAPPED_FUTURE_REASON"]},
        })
        translation = artifact["reason_translation"]
        self.assertFalse(translation["coverage_complete"])
        self.assertEqual(1, translation["unmapped_count"])
        self.assertEqual(["UNMAPPED_FUTURE_REASON"], translation["unmapped_reasons"])
        self.assertEqual("UNMAPPED", translation["records"][0]["translation_status"])
        self.assertTrue(artifact["comparison"]["requires_translation_review"])

    def test_unknown_reason_does_not_receive_invented_authority(self):
        artifact = build_shadow_binding({
            "ai_call_gate": {"call_ai": True, "reasons": ["UNMAPPED_FUTURE_REASON"]},
        })
        self.assertEqual("NO_REVIEW", artifact["shadow_gate"]["level"])
        self.assertFalse(artifact["authority"]["unmapped_reason_auto_escalated"])
        self.assertFalse(artifact["authority"]["automatic_promotion_allowed"])
        self.assertFalse(artifact["comparison"]["routing_intent_agreement"])

    def test_duplicate_mapped_semantics_create_one_event_but_keep_provenance(self):
        artifact = build_shadow_binding({
            "strategy_directive": {"reasons": ["CLIENT_PLAN_CONFLICT"]},
            "ai_call_gate": {"call_ai": True, "reasons": ["CLIENT_MANDATE_CONFLICT"]},
        })
        self.assertEqual(2, artifact["reason_translation"]["reason_count"])
        self.assertEqual(1, len(artifact["translated_events"]))
        self.assertEqual("CLIENT_MANDATE_CONFLICT", artifact["translated_events"][0]["event_type"])


if __name__ == "__main__":
    unittest.main()
