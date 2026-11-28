import unittest

from quantrade.capabilities.valuation_method_applicability import (
    DomainCheck,
    ValuationMethodApplicabilityInput,
    evaluate_method_applicability,
)


class ValuationMethodApplicabilityTests(unittest.TestCase):
    def test_ready_semantics_and_domain_checks_are_ready(self):
        result = evaluate_method_applicability(
            ValuationMethodApplicabilityInput(
                case_id="CASE-A",
                method_id="PE",
                semantic_status="READY",
                semantic_artifact_ref="fixture://semantic",
                domain_checks=(
                    DomainCheck(
                        "POSITIVE_EPS",
                        True,
                        "NON_POSITIVE_EPS",
                    ),
                ),
            )
        )
        self.assertEqual("READY", result.status)
        self.assertEqual((), result.reasons)

    def test_missing_semantics_block_method(self):
        result = evaluate_method_applicability(
            ValuationMethodApplicabilityInput(
                case_id="CASE-M",
                method_id="PE",
                semantic_status="MISSING",
                semantic_artifact_ref="fixture://semantic",
                domain_checks=(),
            )
        )
        self.assertEqual("NOT_APPLICABLE", result.status)
        self.assertIn("SEMANTIC_METRIC_MISSING", result.reasons)

    def test_ambiguous_semantics_block_method(self):
        result = evaluate_method_applicability(
            ValuationMethodApplicabilityInput(
                case_id="CASE-A",
                method_id="DCF",
                semantic_status="AMBIGUOUS",
                semantic_artifact_ref="fixture://semantic",
                domain_checks=(),
            )
        )
        self.assertEqual("NOT_APPLICABLE", result.status)
        self.assertIn(
            "SEMANTIC_METRIC_AMBIGUOUS",
            result.reasons,
        )

    def test_failed_domain_check_blocks_method(self):
        result = evaluate_method_applicability(
            ValuationMethodApplicabilityInput(
                case_id="CASE-D",
                method_id="PE",
                semantic_status="READY",
                semantic_artifact_ref="fixture://semantic",
                domain_checks=(
                    DomainCheck(
                        "POSITIVE_EPS",
                        False,
                        "NON_POSITIVE_EPS",
                        ("OBS-EPS",),
                    ),
                ),
            )
        )
        self.assertEqual("NOT_APPLICABLE", result.status)
        self.assertIn("NON_POSITIVE_EPS", result.reasons)

    def test_gate_never_selects_substitute_method(self):
        result = evaluate_method_applicability(
            ValuationMethodApplicabilityInput(
                case_id="CASE-D",
                method_id="PE",
                semantic_status="READY",
                semantic_artifact_ref="fixture://semantic",
                domain_checks=(
                    DomainCheck(
                        "POSITIVE_EPS",
                        False,
                        "NON_POSITIVE_EPS",
                    ),
                ),
            )
        )
        self.assertFalse(
            result.authority["substitute_method_selected"]
        )
        self.assertFalse(
            result.authority["portfolio_proposal_created"]
        )
        self.assertFalse(result.authority["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
