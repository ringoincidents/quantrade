import unittest

from quantrade.capabilities.investment_case import (
    ConsensusObservation,
    InvestmentCaseError,
    InvestmentCaseInput,
    ScenarioAssumption,
    evaluate_investment_case,
)
from quantrade.capabilities.investment_case_evaluation import reference_cases


class InvestmentCaseEconomicsTests(unittest.TestCase):
    def _case(self, *, consensus=None, scenarios=None, required_return_pct=10.0):
        return InvestmentCaseInput(
            case_id="CASE-1",
            asset_id="KRX:000000",
            as_of="2026-10-05T12:00:00+09:00",
            current_price=100.0,
            currency="KRW",
            valuation_horizon_days=365,
            required_return_pct=required_return_pct,
            scenarios=scenarios or (
                ScenarioAssumption("bear", "Bear", 0.25, 80.0),
                ScenarioAssumption("base", "Base", 0.50, 120.0),
                ScenarioAssumption("bull", "Bull", 0.25, 180.0),
            ),
            consensus=consensus,
        )

    def test_weighted_value_and_expected_return_are_deterministic(self):
        result = evaluate_investment_case(self._case())
        self.assertEqual(125.0, result.metrics["weighted_fair_value"])
        self.assertEqual(25.0, result.metrics["expected_return_pct"])
        self.assertEqual(
            15.0,
            result.metrics["expected_excess_over_hurdle_pct"],
        )
        self.assertTrue(result.metrics["expected_return_hurdle_met"])
        self.assertEqual(-20.0, result.metrics["lowest_scenario_return_pct"])
        self.assertEqual(80.0, result.metrics["highest_scenario_return_pct"])
        self.assertEqual(0.25, result.metrics["probability_of_price_loss"])

    def test_probability_sum_fails_closed(self):
        scenarios = (
            ScenarioAssumption("bear", "Bear", 0.20, 80.0),
            ScenarioAssumption("base", "Base", 0.50, 120.0),
            ScenarioAssumption("bull", "Bull", 0.20, 180.0),
        )
        with self.assertRaisesRegex(
            InvestmentCaseError,
            "probabilities must sum to 1",
        ):
            evaluate_investment_case(self._case(scenarios=scenarios))

    def test_duplicate_scenario_id_is_rejected(self):
        scenarios = (
            ScenarioAssumption("same", "Bear", 0.5, 80.0),
            ScenarioAssumption("same", "Bull", 0.5, 180.0),
        )
        with self.assertRaisesRegex(
            InvestmentCaseError,
            "duplicate scenario_id",
        ):
            evaluate_investment_case(self._case(scenarios=scenarios))

    def test_negative_or_zero_value_is_rejected(self):
        scenarios = (
            ScenarioAssumption("bear", "Bear", 0.5, 0.0),
            ScenarioAssumption("bull", "Bull", 0.5, 180.0),
        )
        with self.assertRaisesRegex(
            InvestmentCaseError,
            "fair_value must be positive",
        ):
            evaluate_investment_case(self._case(scenarios=scenarios))

    def test_consensus_is_comparison_only(self):
        without = evaluate_investment_case(self._case())
        consensus = ConsensusObservation(
            source_id="fixture://consensus",
            observed_at="2026-10-04T12:00:00+09:00",
            target_value=250.0,
            currency="KRW",
            horizon_days=365,
        )
        with_consensus = evaluate_investment_case(
            self._case(consensus=consensus)
        )
        self.assertEqual(
            without.metrics["weighted_fair_value"],
            with_consensus.metrics["weighted_fair_value"],
        )
        self.assertFalse(
            with_consensus.consensus_comparison[
                "consensus_used_to_compute_internal_weighted_value"
            ]
        )
        self.assertEqual(
            150.0,
            with_consensus.consensus_comparison[
                "current_to_consensus_return_pct"
            ],
        )

    def test_future_consensus_observation_is_rejected(self):
        consensus = ConsensusObservation(
            source_id="fixture://future",
            observed_at="2026-10-06T00:00:00+09:00",
            target_value=120.0,
            currency="KRW",
        )
        with self.assertRaisesRegex(
            InvestmentCaseError,
            "after case as_of",
        ):
            evaluate_investment_case(
                self._case(consensus=consensus)
            )

    def test_currency_mismatch_is_rejected(self):
        consensus = ConsensusObservation(
            source_id="fixture://consensus",
            observed_at="2026-10-04T00:00:00+09:00",
            target_value=120.0,
            currency="USD",
        )
        with self.assertRaisesRegex(
            InvestmentCaseError,
            "currency must match",
        ):
            evaluate_investment_case(
                self._case(consensus=consensus)
            )

    def test_arithmetic_does_not_create_authority(self):
        result = evaluate_investment_case(self._case())
        self.assertFalse(result.validation["assumptions_validated_as_true"])
        self.assertFalse(result.authority["canonical_evidence_created"])
        self.assertFalse(result.authority["thesis_validated"])
        self.assertFalse(result.authority["portfolio_proposal_created"])
        self.assertFalse(result.authority["position_size_set"])
        self.assertFalse(result.authority["risk_opinion_created"])
        self.assertFalse(result.authority["committee_decision_created"])
        self.assertFalse(result.authority["paper_authorized"])
        self.assertFalse(result.authority["execution_authorized"])
        self.assertFalse(result.authority["live_order_possible"])

    def test_hurdle_can_fail_even_with_positive_expected_return(self):
        result = evaluate_investment_case(
            self._case(required_return_pct=30.0)
        )
        self.assertGreater(result.metrics["expected_return_pct"], 0)
        self.assertFalse(result.metrics["expected_return_hurdle_met"])
        self.assertLess(
            result.metrics["expected_excess_over_hurdle_pct"],
            0,
        )

    def test_reference_harness_preserves_non_authority(self):
        artifact = reference_cases()
        first = artifact["cases"]["attractive_but_risky"]
        second = artifact["cases"]["no_edge"]
        self.assertTrue(
            first["metrics"]["expected_return_hurdle_met"]
        )
        self.assertFalse(
            second["metrics"]["expected_return_hurdle_met"]
        )
        self.assertGreater(
            first["metrics"]["probability_of_price_loss"],
            0,
        )
        self.assertFalse(
            artifact["authority"]["portfolio_proposal_created"]
        )
        self.assertFalse(
            artifact["authority"]["committee_decision_created"]
        )
        self.assertFalse(
            artifact["authority"]["execution_authorized"]
        )


if __name__ == "__main__":
    unittest.main()
