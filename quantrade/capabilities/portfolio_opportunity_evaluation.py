"""Synthetic reference harness for Portfolio opportunity-cost assessment.

The fixtures demonstrate deterministic review eligibility only. They do not
represent a real Client portfolio or investment recommendation.
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


def reference_portfolio_opportunities() -> dict:
    attractive_case = evaluate_investment_case(
        InvestmentCaseInput(
            case_id="CASE-PORTFOLIO-REFERENCE-001",
            asset_id="KRX:REFERENCE-A",
            as_of="2026-10-05T12:00:00+09:00",
            current_price=100.0,
            currency="KRW",
            valuation_horizon_days=365,
            required_return_pct=12.0,
            scenarios=(
                ScenarioAssumption("bear", "Bear", 0.25, 60.0),
                ScenarioAssumption("base", "Base", 0.50, 125.0),
                ScenarioAssumption("bull", "Bull", 0.25, 170.0),
            ),
        )
    )
    alternatives = (
        CapitalAlternative(
            alternative_id="ALT-CASH",
            alternative_type="CASH",
            expected_return_pct=3.0,
            downside_pct=0.0,
            basis_refs=("fixture://cash-return",),
        ),
        CapitalAlternative(
            alternative_id="ALT-CORE",
            alternative_type="CORE_BENCHMARK",
            expected_return_pct=8.0,
            downside_pct=-25.0,
            basis_refs=("fixture://core-expectation",),
        ),
    )
    constraints = PortfolioConstraintSnapshot(
        snapshot_id="PORT-SNAPSHOT-001",
        as_of="2026-10-05T11:00:00+09:00",
        mandate_allows_new_exposure=True,
        mandate_ref="fixture://mandate",
        current_asset_weight_pct=4.0,
        max_asset_weight_pct=12.0,
        current_liquidity_pct=20.0,
        minimum_liquidity_reserve_pct=12.0,
        available_downside_budget_pct=2.0,
        constraint_refs=(
            "fixture://concentration-limit",
            "fixture://liquidity-reserve",
            "fixture://downside-budget",
        ),
    )
    eligible = assess_portfolio_opportunity(
        PortfolioOpportunityInput(
            case_economics=attractive_case,
            alternatives=alternatives,
            constraints=constraints,
        )
    )

    crowded_constraints = PortfolioConstraintSnapshot(
        snapshot_id="PORT-SNAPSHOT-002",
        as_of="2026-10-05T11:00:00+09:00",
        mandate_allows_new_exposure=True,
        mandate_ref="fixture://mandate",
        current_asset_weight_pct=12.0,
        max_asset_weight_pct=12.0,
        current_liquidity_pct=20.0,
        minimum_liquidity_reserve_pct=12.0,
        available_downside_budget_pct=2.0,
        constraint_refs=("fixture://no-concentration-headroom",),
    )
    crowded = assess_portfolio_opportunity(
        PortfolioOpportunityInput(
            case_economics=attractive_case,
            alternatives=alternatives,
            constraints=crowded_constraints,
        )
    )

    return {
        "schema": "quantrade_portfolio_opportunity_reference_v1",
        "cases": {
            "eligible_for_review": asdict(eligible),
            "no_headroom": asdict(crowded),
        },
        "lessons": (
            "ATTRACTIVE_SECURITY_DOES_NOT_IMPLY_ALLOCATE",
            "CAPITAL_HAS_EXPLICIT_ALTERNATIVES",
            "LIQUIDITY_CONCENTRATION_AND_DOWNSIDE_LIMIT_DEPLOYMENT",
            "DETERMINISTIC_UPPER_BOUND_IS_NOT_TARGET_WEIGHT",
            "PORTFOLIO_REVIEW_ELIGIBILITY_IS_NOT_COMMITTEE_AUTHORITY",
        ),
        "authority": {
            "model_called": False,
            "portfolio_proposal_created": False,
            "target_weight_set": False,
            "risk_opinion_created": False,
            "committee_decision_created": False,
            "execution_authorized": False,
        },
    }
