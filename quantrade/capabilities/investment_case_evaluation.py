"""Synthetic reference harness for Investment Case economics.

These cases validate the arithmetic/authority boundary only. They do not
represent investment recommendations or evidence that any valuation assumption
is correct.
"""
from __future__ import annotations

from dataclasses import asdict

from quantrade.capabilities.investment_case import (
    ConsensusObservation,
    InvestmentCaseInput,
    ScenarioAssumption,
    evaluate_investment_case,
)


def reference_cases() -> dict:
    attractive_but_risky = InvestmentCaseInput(
        case_id="CASE-REFERENCE-001",
        asset_id="KRX:REFERENCE-A",
        as_of="2026-10-05T12:00:00+09:00",
        current_price=100_000.0,
        currency="KRW",
        valuation_horizon_days=365,
        required_return_pct=15.0,
        scenarios=(
            ScenarioAssumption(
                scenario_id="bear",
                label="Bear",
                probability=0.25,
                fair_value=55_000.0,
                thesis_note="Synthetic downside case.",
                assumption_refs=("fixture://bear-assumption",),
            ),
            ScenarioAssumption(
                scenario_id="base",
                label="Base",
                probability=0.50,
                fair_value=120_000.0,
                thesis_note="Synthetic base case.",
                assumption_refs=("fixture://base-assumption",),
            ),
            ScenarioAssumption(
                scenario_id="bull",
                label="Bull",
                probability=0.25,
                fair_value=170_000.0,
                thesis_note="Synthetic upside case.",
                assumption_refs=("fixture://bull-assumption",),
            ),
        ),
        consensus=ConsensusObservation(
            source_id="fixture://sell-side-consensus",
            observed_at="2026-10-04T09:00:00+09:00",
            target_value=130_000.0,
            currency="KRW",
            horizon_days=365,
            methodology_note="Synthetic external observation only.",
        ),
    )

    no_edge = InvestmentCaseInput(
        case_id="CASE-REFERENCE-002",
        asset_id="KRX:REFERENCE-B",
        as_of="2026-10-05T12:00:00+09:00",
        current_price=100_000.0,
        currency="KRW",
        valuation_horizon_days=365,
        required_return_pct=12.0,
        scenarios=(
            ScenarioAssumption(
                scenario_id="bear",
                label="Bear",
                probability=0.30,
                fair_value=80_000.0,
            ),
            ScenarioAssumption(
                scenario_id="base",
                label="Base",
                probability=0.50,
                fair_value=102_000.0,
            ),
            ScenarioAssumption(
                scenario_id="bull",
                label="Bull",
                probability=0.20,
                fair_value=125_000.0,
            ),
        ),
    )

    first = evaluate_investment_case(attractive_but_risky)
    second = evaluate_investment_case(no_edge)

    return {
        "schema": "quantrade_investment_case_reference_evaluation_v1",
        "cases": {
            "attractive_but_risky": asdict(first),
            "no_edge": asdict(second),
        },
        "lessons": [
            "POSITIVE_EXPECTED_VALUE_DOES_NOT_AUTHORIZE_A_TRADE",
            "DOWNSIDE_AND_SCENARIO_DISPERSION_REMAIN_VISIBLE",
            "CONSENSUS_IS_AN_OBSERVATION_NOT_INTERNAL_VALUE",
            "HURDLE_COMPARISON_IS_ARITHMETIC_NOT_PORTFOLIO_SUITABILITY",
            "MODEL_OUTPUT_IS_NOT_EVIDENCE",
        ],
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "committee_decision_created": False,
            "execution_authorized": False,
        },
    }
