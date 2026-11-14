"""Synthetic reference harness for Investment Case learning.

The fixtures measure forecast/calibration behavior only. They do not represent
real investment recommendations, actual portfolio P&L, or proof of alpha.
"""
from __future__ import annotations

from dataclasses import asdict

from quantrade.capabilities.case_learning import (
    CaseLearningInput,
    FalsificationResult,
    OutcomeSnapshot,
    aggregate_case_calibration,
    evaluate_case_learning,
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


def _economics(case_id: str):
    return evaluate_investment_case(
        InvestmentCaseInput(
            case_id=case_id,
            asset_id="KRX:REFERENCE",
            as_of="2026-01-01T12:00:00+09:00",
            current_price=100.0,
            currency="KRW",
            valuation_horizon_days=365,
            required_return_pct=10.0,
            scenarios=(
                ScenarioAssumption(
                    "bear",
                    "Bear",
                    0.25,
                    60.0,
                ),
                ScenarioAssumption(
                    "base",
                    "Base",
                    0.50,
                    125.0,
                ),
                ScenarioAssumption(
                    "bull",
                    "Bull",
                    0.25,
                    170.0,
                ),
            ),
        )
    )


def _thesis(case_id: str) -> dict:
    compiled = compile_thesis_contract(
        ThesisContractInput(
            case_id=case_id,
            as_of="2026-01-01T12:00:00+09:00",
            observations=(
                Observation(
                    observation_id="OBS-1",
                    statement="Synthetic verified observation.",
                    source_ref="fixture://observation",
                    source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
                    observed_at="2025-12-31T09:00:00+09:00",
                ),
            ),
            thesis_claims=(
                ThesisClaim(
                    thesis_id="THESIS-1",
                    statement="Synthetic thesis.",
                    support_refs=("OBS-1",),
                ),
            ),
            falsification_conditions=(
                FalsificationCondition(
                    condition_id="FAL-1",
                    thesis_id="THESIS-1",
                    statement="Synthetic falsification condition.",
                    observable="fixture_metric",
                    evaluation_horizon="one_year",
                ),
            ),
        )
    )
    return asdict(compiled)


def reference_case_learning() -> dict:
    case_a = "CASE-LEARNING-REFERENCE-A"
    case_b = "CASE-LEARNING-REFERENCE-B"

    learning_a = evaluate_case_learning(
        CaseLearningInput(
            case_economics=_economics(case_a),
            thesis_contract=_thesis(case_a),
            outcome=OutcomeSnapshot(
                case_id=case_a,
                evaluated_at="2027-01-01T12:00:00+09:00",
                realized_price=110.0,
                benchmark_return_pct=8.0,
                outcome_refs=("fixture://outcome/a",),
            ),
            falsification_results=(
                FalsificationResult(
                    condition_id="FAL-1",
                    status="TRIGGERED",
                    observed_at="2026-12-31T09:00:00+09:00",
                    source_refs=("fixture://falsification/a",),
                    note="Synthetic condition triggered.",
                ),
            ),
        )
    )

    learning_b = evaluate_case_learning(
        CaseLearningInput(
            case_economics=_economics(case_b),
            thesis_contract=_thesis(case_b),
            outcome=OutcomeSnapshot(
                case_id=case_b,
                evaluated_at="2027-01-01T12:00:00+09:00",
                realized_price=80.0,
                benchmark_return_pct=8.0,
                outcome_refs=("fixture://outcome/b",),
            ),
            falsification_results=(
                FalsificationResult(
                    condition_id="FAL-1",
                    status="NOT_TRIGGERED",
                    observed_at="2026-12-31T09:00:00+09:00",
                    source_refs=("fixture://falsification/b",),
                    note="Synthetic condition did not trigger.",
                ),
            ),
        )
    )

    aggregate = aggregate_case_calibration(
        (learning_a, learning_b)
    )

    return {
        "schema": "quantrade_case_learning_reference_v1",
        "cases": {
            "falsified_positive_outcome": asdict(learning_a),
            "non_falsified_negative_outcome": asdict(learning_b),
        },
        "aggregate": asdict(aggregate),
        "lessons": (
            "THESIS_FALSIFICATION_AND_PRICE_OUTCOME_ARE_DISTINCT",
            "SINGLE_CASE_DOES_NOT_PROVE_ALPHA",
            "COUNTERFACTUAL_EXCESS_IS_NOT_ACTUAL_PORTFOLIO_VALUE_ADDED",
            "LOSS_AND_HURDLE_PROBABILITIES_CAN_BE_CALIBRATED",
            "PERFORMANCE_ACCOUNTING_REMAINS_SEPARATE",
        ),
        "authority": {
            "model_called": False,
            "performance_record_created": False,
            "investment_decision_created": False,
            "execution_authorized": False,
        },
    }
