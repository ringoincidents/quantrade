"""Synthetic reference harness for independent Risk Opinion.

Fixtures demonstrate separation between Portfolio eligibility and Risk authority.
They are not real Client risk settings or investment recommendations.
"""
from __future__ import annotations

from dataclasses import asdict

from quantrade.capabilities.investment_case import (
    InvestmentCaseInput,
    ScenarioAssumption,
    evaluate_investment_case,
)
from quantrade.capabilities.portfolio_opportunity import (
    CapitalAlternative,
    PortfolioConstraintSnapshot,
    PortfolioOpportunityInput,
    assess_portfolio_opportunity,
)
from quantrade.capabilities.risk_opinion import (
    CandidateRiskProfile,
    RiskOpinionInput,
    RiskPolicySnapshot,
    RiskStateSnapshot,
    create_risk_opinion,
)


def _portfolio_assessment():
    case = evaluate_investment_case(
        InvestmentCaseInput(
            case_id="CASE-RISK-REFERENCE",
            asset_id="KRX:REFERENCE-A",
            as_of="2026-10-05T12:00:00+09:00",
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
    return assess_portfolio_opportunity(
        PortfolioOpportunityInput(
            case_economics=case,
            alternatives=(
                CapitalAlternative(
                    alternative_id="CASH",
                    alternative_type="CASH",
                    expected_return_pct=3.0,
                    downside_pct=0.0,
                    basis_refs=("fixture://cash",),
                ),
                CapitalAlternative(
                    alternative_id="CORE",
                    alternative_type="CORE_BENCHMARK",
                    expected_return_pct=8.0,
                    downside_pct=-20.0,
                    basis_refs=("fixture://core",),
                ),
            ),
            constraints=PortfolioConstraintSnapshot(
                snapshot_id="PORT-RISK-REFERENCE",
                as_of="2026-10-05T11:00:00+09:00",
                mandate_allows_new_exposure=True,
                mandate_ref="fixture://mandate",
                current_asset_weight_pct=2.0,
                max_asset_weight_pct=15.0,
                current_liquidity_pct=25.0,
                minimum_liquidity_reserve_pct=10.0,
                available_downside_budget_pct=4.0,
                constraint_refs=("fixture://portfolio-policy",),
            ),
        )
    )


def reference_risk_opinions() -> dict:
    portfolio = _portfolio_assessment()
    base_policy = RiskPolicySnapshot(
        policy_id="RISK-POLICY-REFERENCE",
        as_of="2026-10-05T10:00:00+09:00",
        max_single_asset_weight_pct=10.0,
        max_incremental_downside_budget_pct=2.0,
        max_portfolio_drawdown_pct=-20.0,
        max_abs_correlation_to_portfolio=0.80,
        max_exit_days=5.0,
        leverage_allowed=False,
        require_correlation_data=True,
        require_liquidity_data=True,
        policy_refs=("fixture://risk-policy",),
    )
    base_state = RiskStateSnapshot(
        snapshot_id="RISK-STATE-REFERENCE",
        as_of="2026-10-05T10:30:00+09:00",
        current_asset_weight_pct=2.0,
        current_portfolio_drawdown_pct=-6.0,
        state_refs=("fixture://risk-state",),
    )

    limited = create_risk_opinion(
        RiskOpinionInput(
            portfolio_assessment=portfolio,
            candidate=CandidateRiskProfile(
                asset_id="KRX:REFERENCE-A",
                worst_case_return_pct=-40.0,
                max_abs_correlation_to_portfolio=0.45,
                estimated_exit_days=2.0,
                uses_leverage=False,
                risk_refs=("fixture://candidate-risk",),
            ),
            policy=base_policy,
            state=base_state,
        )
    )

    veto = create_risk_opinion(
        RiskOpinionInput(
            portfolio_assessment=portfolio,
            candidate=CandidateRiskProfile(
                asset_id="KRX:REFERENCE-A",
                worst_case_return_pct=-40.0,
                max_abs_correlation_to_portfolio=0.95,
                estimated_exit_days=2.0,
                uses_leverage=False,
                risk_refs=("fixture://candidate-risk-high-corr",),
            ),
            policy=base_policy,
            state=base_state,
        )
    )

    missing = create_risk_opinion(
        RiskOpinionInput(
            portfolio_assessment=portfolio,
            candidate=CandidateRiskProfile(
                asset_id="KRX:REFERENCE-A",
                worst_case_return_pct=-40.0,
                max_abs_correlation_to_portfolio=None,
                estimated_exit_days=None,
                uses_leverage=False,
                risk_refs=("fixture://candidate-risk-incomplete",),
            ),
            policy=base_policy,
            state=base_state,
        )
    )

    return {
        "schema": "quantrade_risk_opinion_reference_v1",
        "cases": {
            "pass_with_limits": asdict(limited),
            "correlation_veto": asdict(veto),
            "missing_information": asdict(missing),
        },
        "lessons": (
            "PORTFOLIO_ELIGIBILITY_DOES_NOT_BIND_RISK",
            "RISK_MAY_REDUCE_CAPITAL_HEADROOM",
            "RISK_MAY_VETO",
            "MISSING_RISK_DATA_IS_NOT_IMPLICIT_PASS",
            "RISK_POSITION_CEILING_IS_NOT_TARGET_WEIGHT",
        ),
        "authority": {
            "risk_opinion_created": True,
            "committee_decision_created": False,
            "execution_authorized": False,
        },
    }
