import unittest

from quantrade.capabilities.valuation_crosscheck import (
    ValuationCrossCheckError,
    ValuationCrossCheckInput,
    ValuationMethodSnapshot,
    ValuationScenarioSnapshot,
    evaluate_valuation_crosscheck,
)


def method(method_id, values, *, price=100.0, hurdle=15.0):
    return ValuationMethodSnapshot(
        method_id=method_id,
        method_type=method_id,
        source_schema=f"schema:{method_id}",
        current_price=price,
        required_return_pct=hurdle,
        scenarios=(
            ValuationScenarioSnapshot(
                "BEAR",
                0.25,
                values[0],
            ),
            ValuationScenarioSnapshot(
                "BASE",
                0.50,
                values[1],
            ),
            ValuationScenarioSnapshot(
                "BULL",
                0.25,
                values[2],
            ),
        ),
        source_refs=(f"fixture://{method_id}",),
    )


class ValuationCrossCheckTests(unittest.TestCase):
    def test_mixed_methods_bind_to_lower_method_by_scenario(self):
        result = evaluate_valuation_crosscheck(
            ValuationCrossCheckInput(
                case_id="CASE-X",
                methods=(
                    method("PE", (80.0, 130.0, 200.0)),
                    method("DCF", (70.0, 100.0, 150.0)),
                ),
            )
        )
        self.assertEqual(
            "CROSS_METHOD_MIXED",
            result.classification,
        )
        self.assertEqual(
            "DCF",
            result.robust_scenarios[0]["binding_method_id"],
        )
        self.assertEqual(
            105.0,
            result.robust_metrics["weighted_fair_value"],
        )
        self.assertEqual(
            5.0,
            result.robust_metrics["expected_return_pct"],
        )
        self.assertFalse(
            result.robust_metrics["valuation_gate_passed"]
        )

    def test_all_methods_clear_can_pass_gate(self):
        result = evaluate_valuation_crosscheck(
            ValuationCrossCheckInput(
                case_id="CASE-C",
                methods=(
                    method("PE", (90.0, 140.0, 210.0)),
                    method("DCF", (85.0, 135.0, 180.0)),
                ),
            )
        )
        self.assertEqual(
            "CROSS_METHOD_CONFIRMED",
            result.classification,
        )
        self.assertTrue(
            result.robust_metrics["all_methods_clear_hurdle"]
        )
        self.assertTrue(
            result.robust_metrics["valuation_gate_passed"]
        )

    def test_no_method_clears_is_rejected(self):
        result = evaluate_valuation_crosscheck(
            ValuationCrossCheckInput(
                case_id="CASE-R",
                methods=(
                    method("PE", (60.0, 90.0, 120.0)),
                    method("DCF", (50.0, 80.0, 110.0)),
                ),
            )
        )
        self.assertEqual(
            "CROSS_METHOD_REJECTED",
            result.classification,
        )
        self.assertFalse(
            result.robust_metrics["valuation_gate_passed"]
        )

    def test_scenario_id_mismatch_fails_closed(self):
        first = method("PE", (80.0, 130.0, 200.0))
        second = ValuationMethodSnapshot(
            method_id="DCF",
            method_type="DCF",
            source_schema="schema:DCF",
            current_price=100.0,
            required_return_pct=15.0,
            scenarios=(
                ValuationScenarioSnapshot("BEAR", 0.25, 70.0),
                ValuationScenarioSnapshot("BASE", 0.50, 100.0),
                ValuationScenarioSnapshot("UPSIDE", 0.25, 150.0),
            ),
        )
        with self.assertRaisesRegex(
            ValuationCrossCheckError,
            "share scenario IDs",
        ):
            evaluate_valuation_crosscheck(
                ValuationCrossCheckInput(
                    case_id="CASE-BAD",
                    methods=(first, second),
                )
            )

    def test_probability_mismatch_fails_closed(self):
        first = method("PE", (80.0, 130.0, 200.0))
        second = ValuationMethodSnapshot(
            method_id="DCF",
            method_type="DCF",
            source_schema="schema:DCF",
            current_price=100.0,
            required_return_pct=15.0,
            scenarios=(
                ValuationScenarioSnapshot("BEAR", 0.20, 70.0),
                ValuationScenarioSnapshot("BASE", 0.55, 100.0),
                ValuationScenarioSnapshot("BULL", 0.25, 150.0),
            ),
        )
        with self.assertRaisesRegex(
            ValuationCrossCheckError,
            "share scenario probabilities",
        ):
            evaluate_valuation_crosscheck(
                ValuationCrossCheckInput(
                    case_id="CASE-BAD",
                    methods=(first, second),
                )
            )

    def test_price_mismatch_fails_closed(self):
        with self.assertRaisesRegex(
            ValuationCrossCheckError,
            "share current_price",
        ):
            evaluate_valuation_crosscheck(
                ValuationCrossCheckInput(
                    case_id="CASE-BAD",
                    methods=(
                        method("PE", (80.0, 130.0, 200.0)),
                        method(
                            "DCF",
                            (70.0, 100.0, 150.0),
                            price=101.0,
                        ),
                    ),
                )
            )

    def test_no_capital_authority(self):
        result = evaluate_valuation_crosscheck(
            ValuationCrossCheckInput(
                case_id="CASE-X",
                methods=(
                    method("PE", (80.0, 130.0, 200.0)),
                    method("DCF", (70.0, 100.0, 150.0)),
                ),
            )
        )
        self.assertFalse(result.authority["model_called"])
        self.assertFalse(
            result.authority["portfolio_proposal_created"]
        )
        self.assertFalse(
            result.authority["target_weight_set"]
        )
        self.assertFalse(
            result.authority["committee_decision_created"]
        )
        self.assertFalse(result.authority["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
