import unittest
from dataclasses import asdict, replace

from quantrade.capabilities.case_learning import (
    CaseCalibrationAggregate,
    CaseLearningError,
    CaseLearningInput,
    FalsificationResult,
    OutcomeSnapshot,
    aggregate_case_calibration,
    evaluate_case_learning,
)
from quantrade.capabilities.case_learning_evaluation import (
    reference_case_learning,
)
from quantrade.capabilities.investment_case import (
    InvestmentCaseInput,
    ScenarioAssumption,
    evaluate_investment_case,
)
from quantrade.capabilities.thesis_contract import (
    FalsificationCondition,
    Observation,
    SourceKind,
    ThesisClaim,
    ThesisContractInput,
    compile_thesis_contract,
)


class CaseLearningTests(unittest.TestCase):
    def _economics(self, case_id="CASE-LEARN"):
        return evaluate_investment_case(
            InvestmentCaseInput(
                case_id=case_id,
                asset_id="KRX:000000",
                as_of="2026-01-01T12:00:00+09:00",
                current_price=100.0,
                currency="KRW",
                valuation_horizon_days=365,
                required_return_pct=10.0,
                scenarios=(
                    ScenarioAssumption("bear", "Bear", 0.25, 60.0),
                    ScenarioAssumption("base", "Base", 0.50, 125.0),
                    ScenarioAssumption("bull", "Bull", 0.25, 170.0),
                ),
            )
        )

    def _thesis(self, case_id="CASE-LEARN"):
        return asdict(
            compile_thesis_contract(
                ThesisContractInput(
                    case_id=case_id,
                    as_of="2026-01-01T12:00:00+09:00",
                    observations=(
                        Observation(
                            observation_id="OBS",
                            statement="Verified observation.",
                            source_ref="fixture://obs",
                            source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
                            observed_at="2025-12-31T09:00:00+09:00",
                        ),
                    ),
                    thesis_claims=(
                        ThesisClaim(
                            thesis_id="TH",
                            statement="Investment thesis.",
                            support_refs=("OBS",),
                        ),
                    ),
                    falsification_conditions=(
                        FalsificationCondition(
                            condition_id="FAL",
                            thesis_id="TH",
                            statement="Condition.",
                            observable="metric",
                            evaluation_horizon="one_year",
                        ),
                    ),
                )
            )
        )

    def _request(
        self,
        *,
        case_id="CASE-LEARN",
        realized_price=110.0,
        benchmark_return_pct=8.0,
        falsification_status="NOT_TRIGGERED",
        falsification_observed_at="2026-12-31T09:00:00+09:00",
        falsification_refs=("fixture://fal",),
    ):
        return CaseLearningInput(
            case_economics=self._economics(case_id),
            thesis_contract=self._thesis(case_id),
            outcome=OutcomeSnapshot(
                case_id=case_id,
                evaluated_at="2027-01-01T12:00:00+09:00",
                realized_price=realized_price,
                benchmark_return_pct=benchmark_return_pct,
                outcome_refs=("fixture://outcome",),
            ),
            falsification_results=(
                FalsificationResult(
                    condition_id="FAL",
                    status=falsification_status,
                    observed_at=falsification_observed_at,
                    source_refs=falsification_refs,
                ),
            ),
        )

    def test_learning_computes_return_error_and_counterfactual_excess(self):
        result = evaluate_case_learning(self._request())

        self.assertEqual(20.0, result.forecast["expected_return_pct"])
        self.assertEqual(10.0, result.outcome["realized_return_pct"])
        self.assertEqual(
            -10.0,
            result.calibration["return_forecast_error_pct_points"],
        )
        self.assertEqual(
            10.0,
            result.calibration[
                "return_forecast_absolute_error_pct_points"
            ],
        )
        self.assertEqual(
            2.0,
            result.outcome[
                "counterfactual_excess_vs_benchmark_pct"
            ],
        )
        self.assertFalse(
            result.calibration["single_case_proves_alpha"]
        )

    def test_loss_and_hurdle_brier_components_are_deterministic(self):
        result = evaluate_case_learning(self._request())

        self.assertEqual(
            0.25,
            result.forecast["predicted_loss_probability"],
        )
        self.assertEqual(
            0.75,
            result.forecast["predicted_hurdle_probability"],
        )
        self.assertEqual(
            0,
            result.calibration["actual_loss_indicator"],
        )
        self.assertEqual(
            1,
            result.calibration["actual_hurdle_indicator"],
        )
        self.assertEqual(
            0.0625,
            result.calibration["loss_event_brier_component"],
        )
        self.assertEqual(
            0.0625,
            result.calibration["hurdle_event_brier_component"],
        )

    def test_thesis_can_be_falsified_even_when_price_outcome_is_positive(self):
        result = evaluate_case_learning(
            self._request(falsification_status="TRIGGERED")
        )
        self.assertEqual("FALSIFIED", result.thesis_learning["status"])
        self.assertEqual(
            ("FAL",),
            result.thesis_learning["triggered_condition_ids"],
        )
        self.assertGreater(result.outcome["realized_return_pct"], 0)

    def test_unresolved_falsification_remains_unresolved_without_source_ref(self):
        result = evaluate_case_learning(
            self._request(
                falsification_status="UNRESOLVED",
                falsification_refs=(),
            )
        )
        self.assertEqual(
            "UNRESOLVED",
            result.thesis_learning["status"],
        )
        self.assertEqual(
            ("FAL",),
            result.thesis_learning["unresolved_condition_ids"],
        )

    def test_resolved_falsification_requires_source_ref(self):
        with self.assertRaisesRegex(
            CaseLearningError,
            "resolved falsification result requires source_refs",
        ):
            evaluate_case_learning(
                self._request(
                    falsification_status="NOT_TRIGGERED",
                    falsification_refs=(),
                )
            )

    def test_future_falsification_observation_is_rejected(self):
        with self.assertRaisesRegex(
            CaseLearningError,
            "cannot be after outcome evaluation",
        ):
            evaluate_case_learning(
                self._request(
                    falsification_observed_at=(
                        "2027-01-02T09:00:00+09:00"
                    )
                )
            )

    def test_outcome_must_be_after_case_as_of(self):
        request = self._request()
        bad = replace(
            request,
            outcome=replace(
                request.outcome,
                evaluated_at="2026-01-01T11:00:00+09:00",
            ),
        )
        with self.assertRaisesRegex(
            CaseLearningError,
            "must be after case as_of",
        ):
            evaluate_case_learning(bad)

    def test_case_ids_must_match(self):
        request = self._request()
        bad = replace(
            request,
            outcome=replace(
                request.outcome,
                case_id="OTHER",
            ),
        )
        with self.assertRaisesRegex(
            CaseLearningError,
            "outcome case_id must match",
        ):
            evaluate_case_learning(bad)

    def test_every_falsification_condition_requires_result(self):
        request = self._request()
        bad = replace(request, falsification_results=())
        with self.assertRaisesRegex(
            CaseLearningError,
            "missing falsification results",
        ):
            evaluate_case_learning(bad)

    def test_aggregate_calibration_is_descriptive_not_alpha_claim(self):
        first = evaluate_case_learning(self._request())
        second = evaluate_case_learning(
            self._request(
                case_id="CASE-LEARN-2",
                realized_price=80.0,
            )
        )
        aggregate = aggregate_case_calibration((first, second))

        self.assertIsInstance(aggregate, CaseCalibrationAggregate)
        self.assertEqual(2, aggregate.sample_count)
        self.assertEqual(
            -25.0,
            aggregate.metrics[
                "mean_return_forecast_error_pct_points"
            ],
        )
        self.assertEqual(
            25.0,
            aggregate.metrics[
                "mean_absolute_return_forecast_error_pct_points"
            ],
        )
        self.assertEqual(
            0.3125,
            aggregate.metrics["mean_loss_event_brier_score"],
        )
        self.assertEqual(
            0.3125,
            aggregate.metrics["mean_hurdle_event_brier_score"],
        )
        self.assertFalse(
            aggregate.metrics["statistical_significance_established"]
        )
        self.assertFalse(
            aggregate.metrics["actual_portfolio_value_added_measured"]
        )

    def test_learning_artifact_has_no_capital_authority(self):
        result = evaluate_case_learning(self._request())
        self.assertFalse(result.authority["model_called"])
        self.assertFalse(
            result.authority["canonical_evidence_created"]
        )
        self.assertFalse(
            result.authority["portfolio_proposal_created"]
        )
        self.assertFalse(
            result.authority["committee_decision_created"]
        )
        self.assertFalse(
            result.authority["performance_record_created"]
        )
        self.assertFalse(result.authority["execution_authorized"])

    def test_reference_harness_keeps_price_outcome_and_thesis_truth_separate(self):
        artifact = reference_case_learning()
        positive = artifact["cases"]["falsified_positive_outcome"]
        negative = artifact["cases"]["non_falsified_negative_outcome"]

        self.assertGreater(
            positive["outcome"]["realized_return_pct"],
            0,
        )
        self.assertEqual(
            "FALSIFIED",
            positive["thesis_learning"]["status"],
        )
        self.assertLess(
            negative["outcome"]["realized_return_pct"],
            0,
        )
        self.assertEqual(
            "NOT_FALSIFIED",
            negative["thesis_learning"]["status"],
        )
        self.assertFalse(
            artifact["aggregate"]["metrics"][
                "actual_portfolio_value_added_measured"
            ]
        )
        self.assertFalse(artifact["authority"]["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
