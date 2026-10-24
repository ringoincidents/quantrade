"""QT-CASE-003-CORR-001 semantic portability correction.

This is not a new holdout. It tests whether semantic account identity can be
resolved across predeclared DART IS/CIS placement without account-name guessing.
"""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from quantrade.capabilities.cash_flow_valuation import (
    CashFlowDCFInput,
    CashFlowDCFScenario,
    evaluate_cash_flow_dcf,
)
from quantrade.capabilities.dart_fundamental_provider import (
    DartFundamentalObservationProvider,
    DartProviderConfig,
)
from quantrade.capabilities.fundamental_counter_research import (
    AnnualCashConversion,
    FundamentalCounterResearchInput,
    FundamentalCounterResearchPolicy,
    evaluate_fundamental_counter_research,
)
from quantrade.capabilities.fundamental_evidence import FundamentalQuery
from quantrade.capabilities.fundamental_semantics import (
    BASIC_EPS_ACCOUNT_ID,
    INTANGIBLE_PURCHASE_ACCOUNT_ID,
    OPERATING_CASH_FLOW_ACCOUNT_ID,
    OWNER_PROFIT_ACCOUNT_ID,
    PARENT_EQUITY_ACCOUNT_ID,
    PPE_PURCHASE_ACCOUNT_ID,
    SemanticMetricApplicabilityInput,
    SemanticMetricRequirement,
    collect_requested_metric_keys,
    evaluate_semantic_metric_applicability,
)
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
from quantrade.capabilities.valuation_crosscheck import (
    ValuationCrossCheckInput,
    ValuationMethodSnapshot,
    ValuationScenarioSnapshot,
    evaluate_valuation_crosscheck,
)
from quantrade.capabilities.valuation_method_applicability import (
    DomainCheck,
    ValuationMethodApplicabilityInput,
    evaluate_method_applicability,
)
from scripts.run_qt_case_001 import (
    last_close_on_or_before,
    percentile_linear,
)
from scripts.run_qt_case_003 import fetch_prices


EXPERIMENT_ID = "QT-CASE-003-CORR-001"
PREREGISTRATION_COMMIT = "1c52896c63cae1f8398dfd276e936e813007e4bb"
CASE_ID = "QT-CASE-003-CORR-001:KRX:006400"
ASSET_ID = "KRX:006400"
CASE_AS_OF = "2026-10-05T23:59:59+09:00"
REQUIRED_RETURN_PCT = 15.0

RESULT_PATH = Path(
    "research/experiments/QT-CASE-003-CORR-001_RESULT.json"
)
REPORT_PATH = Path(
    "research/experiments/QT-CASE-003-CORR-001_RESULT_REPORT.md"
)
FULL_PATH = Path("/tmp/QT-CASE-003-CORR-001_FULL_ARTIFACT.json")


def req(
    requirement_id: str,
    account_id: str,
    divisions: tuple[str, ...],
    suffix: str,
    periods: tuple[str, ...],
) -> SemanticMetricRequirement:
    return SemanticMetricRequirement(
        requirement_id=requirement_id,
        account_id=account_id,
        allowed_statement_divisions=divisions,
        amount_suffix=suffix,
        fiscal_period_ends=periods,
    )


PE_REQUIREMENTS = (
    req(
        "EPS_ANNUAL",
        BASIC_EPS_ACCOUNT_ID,
        ("IS", "CIS"),
        "CURRENT_PERIOD",
        tuple(f"{year}-12-31" for year in (2022, 2023, 2024, 2025)),
    ),
    req(
        "EPS_H1_YTD",
        BASIC_EPS_ACCOUNT_ID,
        ("IS", "CIS"),
        "CURRENT_YTD",
        ("2025-06-30", "2026-06-30"),
    ),
)

DCF_REQUIREMENTS = (
    req(
        "OWNER_PROFIT_ANNUAL",
        OWNER_PROFIT_ACCOUNT_ID,
        ("IS", "CIS"),
        "CURRENT_PERIOD",
        tuple(f"{year}-12-31" for year in (2022, 2023, 2024, 2025)),
    ),
    req(
        "OWNER_PROFIT_H1_YTD",
        OWNER_PROFIT_ACCOUNT_ID,
        ("IS", "CIS"),
        "CURRENT_YTD",
        ("2025-06-30", "2026-06-30"),
    ),
    req(
        "CFO",
        OPERATING_CASH_FLOW_ACCOUNT_ID,
        ("CF",),
        "CURRENT_PERIOD",
        tuple(f"{year}-12-31" for year in (2022, 2023, 2024, 2025))
        + ("2025-06-30", "2026-06-30"),
    ),
    req(
        "PPE_CAPEX",
        PPE_PURCHASE_ACCOUNT_ID,
        ("CF",),
        "CURRENT_PERIOD",
        tuple(f"{year}-12-31" for year in (2022, 2023, 2024, 2025))
        + ("2025-06-30", "2026-06-30"),
    ),
    req(
        "INTANGIBLE_CAPEX",
        INTANGIBLE_PURCHASE_ACCOUNT_ID,
        ("CF",),
        "CURRENT_PERIOD",
        tuple(f"{year}-12-31" for year in (2022, 2023, 2024, 2025))
        + ("2025-06-30", "2026-06-30"),
    ),
    req(
        "PARENT_EQUITY",
        PARENT_EQUITY_ACCOUNT_ID,
        ("BS",),
        "CURRENT_PERIOD",
        tuple(f"{year}-12-31" for year in (2022, 2023, 2024, 2025)),
    ),
    req(
        "EPS_FY2025_FOR_SHARES",
        BASIC_EPS_ACCOUNT_ID,
        ("IS", "CIS"),
        "CURRENT_PERIOD",
        ("2025-12-31",),
    ),
)


def resolved_value(artifact, requirement_id: str, period: str) -> float:
    matches = [
        row
        for row in artifact.resolved
        if row["requirement_id"] == requirement_id
        and row["fiscal_period_end"] == period
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"semantic requirement unresolved: {requirement_id} {period}"
        )
    return float(matches[0]["value"])


def owner_cash_flow(dcf_semantic, period: str) -> float:
    return (
        resolved_value(dcf_semantic, "CFO", period)
        - resolved_value(dcf_semantic, "PPE_CAPEX", period)
        - resolved_value(dcf_semantic, "INTANGIBLE_CAPEX", period)
    )


def write_result(result: dict) -> None:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    FULL_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# QT-CASE-003-CORR-001 Result — Semantic Portability Correction",
        "",
        f"- Semantic P/E status: **{result['pe_semantic']['status']}**",
        f"- Semantic DCF status: **{result['dcf_semantic']['status']}**",
        f"- P/E method applicability: **{result['pe_method']['status']}**",
        f"- DCF method applicability: **{result['dcf_method']['status']}**",
        f"- Cross-method status: **{result['cross_method_status']}**",
    ]
    if result.get("valuation_crosscheck"):
        lines.extend(
            [
                f"- Cross-method classification: "
                f"**{result['valuation_crosscheck']['classification']}**",
                f"- Robust expected return: "
                f"**{result['valuation_crosscheck']['robust_metrics']['expected_return_pct']:.2f}%**",
            ]
        )
    lines.extend(
        [
            "",
            "- Original QT-CASE-003 remains unchanged.",
            "- Account-name fallback: false.",
            "- Substitute method auto-selection: false.",
            "- PAPER/live execution: false.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def run() -> dict:
    requirements = PE_REQUIREMENTS + DCF_REQUIREMENTS
    query_keys = collect_requested_metric_keys(requirements)

    provider = DartFundamentalObservationProvider(
        config=DartProviderConfig(
            report_codes=("11011", "11012"),
        ),
        corp_code_overrides={"006400": "00126362"},
    )
    raw = provider.query(
        FundamentalQuery(
            asset_id=ASSET_ID,
            as_of=CASE_AS_OF,
            metric_keys=query_keys,
            fiscal_period_end_from="2022-01-01",
            fiscal_period_end_to="2026-06-30",
        )
    )
    observations = tuple(raw.observations)

    pe_semantic = evaluate_semantic_metric_applicability(
        SemanticMetricApplicabilityInput(
            case_id=CASE_ID,
            observations=observations,
            requirements=PE_REQUIREMENTS,
        )
    )
    dcf_semantic = evaluate_semantic_metric_applicability(
        SemanticMetricApplicabilityInput(
            case_id=CASE_ID,
            observations=observations,
            requirements=DCF_REQUIREMENTS,
        )
    )

    pe_values = [
        float(row["value"])
        for row in pe_semantic.resolved
    ]
    pe_method = evaluate_method_applicability(
        ValuationMethodApplicabilityInput(
            case_id=CASE_ID,
            method_id="PE",
            semantic_status=pe_semantic.status,
            semantic_artifact_ref="QT-CASE-003-CORR-001:PE_SEMANTIC",
            domain_checks=(
                DomainCheck(
                    "ALL_REQUIRED_EPS_POSITIVE",
                    (
                        pe_semantic.status == "READY"
                        and bool(pe_values)
                        and all(value > 0.0 for value in pe_values)
                    ),
                    "NON_POSITIVE_EPS",
                    tuple(
                        row["observation_id"]
                        for row in pe_semantic.resolved
                    ),
                ),
            ),
        )
    )

    fy2025_profit = (
        resolved_value(
            dcf_semantic,
            "OWNER_PROFIT_ANNUAL",
            "2025-12-31",
        )
        if dcf_semantic.status == "READY"
        else 0.0
    )
    fy2025_eps = (
        resolved_value(
            dcf_semantic,
            "EPS_FY2025_FOR_SHARES",
            "2025-12-31",
        )
        if dcf_semantic.status == "READY"
        else 0.0
    )
    ttm_cf = (
        owner_cash_flow(dcf_semantic, "2025-12-31")
        + owner_cash_flow(dcf_semantic, "2026-06-30")
        - owner_cash_flow(dcf_semantic, "2025-06-30")
        if dcf_semantic.status == "READY"
        else 0.0
    )
    implied_shares = (
        fy2025_profit / fy2025_eps
        if fy2025_profit > 0.0 and fy2025_eps > 0.0
        else 0.0
    )
    dcf_method = evaluate_method_applicability(
        ValuationMethodApplicabilityInput(
            case_id=CASE_ID,
            method_id="OWNER_CASH_FLOW_DCF",
            semantic_status=dcf_semantic.status,
            semantic_artifact_ref="QT-CASE-003-CORR-001:DCF_SEMANTIC",
            domain_checks=(
                DomainCheck(
                    "FY2025_OWNER_PROFIT_POSITIVE",
                    fy2025_profit > 0.0,
                    "NON_POSITIVE_FY2025_OWNER_PROFIT",
                ),
                DomainCheck(
                    "FY2025_BASIC_EPS_POSITIVE",
                    fy2025_eps > 0.0,
                    "NON_POSITIVE_FY2025_EPS",
                ),
                DomainCheck(
                    "IMPLIED_SHARES_POSITIVE",
                    implied_shares > 0.0,
                    "NON_POSITIVE_IMPLIED_SHARES",
                ),
                DomainCheck(
                    "TTM_OWNER_CASH_FLOW_POSITIVE",
                    ttm_cf > 0.0,
                    "NON_POSITIVE_TTM_OWNER_CASH_FLOW",
                ),
            ),
        )
    )

    prices, price_meta = fetch_prices()
    current_price_row = last_close_on_or_before(
        prices,
        "2026-10-05",
        same_calendar_year=True,
    )
    current_price = float(current_price_row["close"])

    base = {
        "schema": "quantrade_qt_case_003_corr_001_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "case": {
            "case_id": CASE_ID,
            "asset_id": ASSET_ID,
            "as_of": CASE_AS_OF,
            "price_date": current_price_row["date"],
            "current_price": current_price,
        },
        "pe_semantic": asdict(pe_semantic),
        "dcf_semantic": asdict(dcf_semantic),
        "pe_method": asdict(pe_method),
        "dcf_method": asdict(dcf_method),
        "cross_method_status": (
            "READY"
            if pe_method.status == "READY"
            and dcf_method.status == "READY"
            else "INCOMPLETE_REQUIRED_METHODS"
        ),
        "valuation_crosscheck": None,
        "portfolio_sandbox": None,
        "risk_sandbox": None,
        "source": {
            "open_dart_provider": raw.provider,
            "price_source": price_meta,
        },
        "authority": {
            "target_weight_set": False,
            "portfolio_proposal_created": False,
            "committee_decision_created": False,
            "founder_decision_created": False,
            "decision_plan_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    }

    if base["cross_method_status"] != "READY":
        write_result(base)
        return base

    annual_eps = {
        year: resolved_value(
            pe_semantic,
            "EPS_ANNUAL",
            f"{year}-12-31",
        )
        for year in (2022, 2023, 2024, 2025)
    }
    ttm_eps = (
        annual_eps[2025]
        + resolved_value(
            pe_semantic,
            "EPS_H1_YTD",
            "2026-06-30",
        )
        - resolved_value(
            pe_semantic,
            "EPS_H1_YTD",
            "2025-06-30",
        )
    )
    pe_rows = []
    for year in (2022, 2023, 2024, 2025):
        price = last_close_on_or_before(
            prices,
            f"{year}-12-31",
            same_calendar_year=True,
        )
        pe_rows.append(
            {
                "year": year,
                "pe": float(price["close"]) / annual_eps[year],
            }
        )
    pe_values_history = [row["pe"] for row in pe_rows]
    p25 = percentile_linear(pe_values_history, 0.25)
    p50 = percentile_linear(pe_values_history, 0.50)
    p75 = percentile_linear(pe_values_history, 0.75)

    pe_scenarios = (
        ScenarioAssumption(
            "BEAR", "Bear", 0.25, ttm_eps * 0.80 * p25
        ),
        ScenarioAssumption(
            "BASE", "Base", 0.50, ttm_eps * p50
        ),
        ScenarioAssumption(
            "BULL", "Bull", 0.25, ttm_eps * 1.20 * p75
        ),
    )
    pe_economics = evaluate_investment_case(
        InvestmentCaseInput(
            case_id=CASE_ID,
            asset_id=ASSET_ID,
            as_of=CASE_AS_OF,
            current_price=current_price,
            currency="KRW",
            valuation_horizon_days=365,
            required_return_pct=REQUIRED_RETURN_PCT,
            scenarios=pe_scenarios,
        )
    )

    cash_flow_per_share = ttm_cf / implied_shares
    dcf = evaluate_cash_flow_dcf(
        CashFlowDCFInput(
            case_id=CASE_ID,
            asset_id=ASSET_ID,
            as_of=CASE_AS_OF,
            current_price=current_price,
            currency="KRW",
            owner_cash_flow_per_share=cash_flow_per_share,
            required_return_pct=REQUIRED_RETURN_PCT,
            scenarios=(
                CashFlowDCFScenario(
                    "BEAR", "Bear", 0.25, 0.80, 0.0, 0.0, 10.0, 5
                ),
                CashFlowDCFScenario(
                    "BASE", "Base", 0.50, 1.00, 3.0, 2.0, 10.0, 5
                ),
                CashFlowDCFScenario(
                    "BULL", "Bull", 0.25, 1.20, 5.0, 3.0, 10.0, 5
                ),
            ),
        )
    )

    crosscheck = evaluate_valuation_crosscheck(
        ValuationCrossCheckInput(
            case_id=CASE_ID,
            methods=(
                ValuationMethodSnapshot(
                    "PE",
                    "HISTORICAL_PE",
                    pe_economics.schema,
                    current_price,
                    REQUIRED_RETURN_PCT,
                    tuple(
                        ValuationScenarioSnapshot(
                            row.scenario_id,
                            row.probability,
                            row.fair_value,
                        )
                        for row in pe_scenarios
                    ),
                ),
                ValuationMethodSnapshot(
                    "OWNER_CASH_FLOW_DCF",
                    "OWNER_CASH_FLOW_DCF",
                    dcf.schema,
                    current_price,
                    REQUIRED_RETURN_PCT,
                    tuple(
                        ValuationScenarioSnapshot(
                            row["scenario_id"],
                            row["probability"],
                            row["fair_value"],
                        )
                        for row in dcf.scenarios
                    ),
                ),
            ),
        )
    )
    robust_economics = evaluate_investment_case(
        InvestmentCaseInput(
            case_id=CASE_ID,
            asset_id=ASSET_ID,
            as_of=CASE_AS_OF,
            current_price=current_price,
            currency="KRW",
            valuation_horizon_days=365,
            required_return_pct=REQUIRED_RETURN_PCT,
            scenarios=tuple(
                ScenarioAssumption(
                    row["scenario_id"],
                    row["scenario_id"].title(),
                    float(row["probability"]),
                    float(row["robust_lower_of_methods_fair_value"]),
                )
                for row in crosscheck.robust_scenarios
            ),
        )
    )

    annual_cf = {
        year: owner_cash_flow(dcf_semantic, f"{year}-12-31")
        for year in (2022, 2023, 2024, 2025)
    }
    annual_profit = {
        year: resolved_value(
            dcf_semantic,
            "OWNER_PROFIT_ANNUAL",
            f"{year}-12-31",
        )
        for year in (2022, 2023, 2024, 2025)
    }
    ttm_profit = (
        annual_profit[2025]
        + resolved_value(
            dcf_semantic,
            "OWNER_PROFIT_H1_YTD",
            "2026-06-30",
        )
        - resolved_value(
            dcf_semantic,
            "OWNER_PROFIT_H1_YTD",
            "2025-06-30",
        )
    )
    historical_pb = []
    for year in (2022, 2023, 2024, 2025):
        equity = resolved_value(
            dcf_semantic,
            "PARENT_EQUITY",
            f"{year}-12-31",
        )
        price = last_close_on_or_before(
            prices,
            f"{year}-12-31",
            same_calendar_year=True,
        )
        historical_pb.append(
            float(price["close"]) / (equity / implied_shares)
        )
    current_pb = current_price / (
        resolved_value(
            dcf_semantic,
            "PARENT_EQUITY",
            "2025-12-31",
        )
        / implied_shares
    )

    counter = evaluate_fundamental_counter_research(
        FundamentalCounterResearchInput(
            case_id=CASE_ID,
            annual_cash_conversion=tuple(
                AnnualCashConversion(
                    year,
                    annual_cf[year],
                    annual_profit[year],
                )
                for year in (2022, 2023, 2024, 2025)
            ),
            ttm_owner_cash_flow_proxy=ttm_cf,
            ttm_profit_attributable_to_owners=ttm_profit,
            historical_pe_values=tuple(pe_values_history),
            historical_pb_values=tuple(historical_pb),
            current_pb=current_pb,
            policy=FundamentalCounterResearchPolicy(4.0, 0.75),
        )
    )

    portfolio = assess_portfolio_opportunity(
        PortfolioOpportunityInput(
            case_economics=robust_economics,
            alternatives=(
                CapitalAlternative(
                    "SANDBOX-CASH", "CASH", 3.0, 0.0,
                    ("QT-CASE-003-CORR-001:SANDBOX",),
                ),
                CapitalAlternative(
                    "SANDBOX-CORE", "CORE_BENCHMARK", 8.0, None,
                    ("QT-CASE-003-CORR-001:SANDBOX",),
                ),
            ),
            constraints=PortfolioConstraintSnapshot(
                "QT-CASE-003-CORR-001-SANDBOX",
                "2026-10-05T23:00:00+09:00",
                True,
                "QT-CASE-003-CORR-001:SANDBOX",
                0.0,
                10.0,
                20.0,
                10.0,
                2.0,
                ("QT-CASE-003-CORR-001:SANDBOX",),
            ),
            valuation_crosscheck=crosscheck,
        )
    )

    risk = None
    if portfolio.status == "ELIGIBLE_FOR_PORTFOLIO_REVIEW":
        risk = create_risk_opinion(
            RiskOpinionInput(
                portfolio_assessment=portfolio,
                candidate=CandidateRiskProfile(
                    ASSET_ID,
                    float(
                        robust_economics.metrics[
                            "lowest_scenario_return_pct"
                        ]
                    ),
                    None,
                    None,
                    False,
                    ("QT-CASE-003-CORR-001:ROBUST-BEAR",),
                ),
                policy=RiskPolicySnapshot(
                    "QT-CASE-003-CORR-001-RISK",
                    "2026-10-05T22:00:00+09:00",
                    10.0,
                    2.0,
                    -20.0,
                    None,
                    None,
                    False,
                    False,
                    False,
                    ("QT-CASE-003-CORR-001:SANDBOX",),
                ),
                state=RiskStateSnapshot(
                    "QT-CASE-003-CORR-001-RISK-STATE",
                    "2026-10-05T22:30:00+09:00",
                    0.0,
                    -5.0,
                    ("QT-CASE-003-CORR-001:SANDBOX",),
                ),
            )
        )

    base.update(
        {
            "pe_economics": asdict(pe_economics),
            "cash_flow_dcf": asdict(dcf),
            "valuation_crosscheck": asdict(crosscheck),
            "counter_research": asdict(counter),
            "portfolio_sandbox": asdict(portfolio),
            "risk_sandbox": None if risk is None else asdict(risk),
            "derived_inputs": {
                "ttm_eps": ttm_eps,
                "ttm_owner_cash_flow_proxy": ttm_cf,
                "implied_basic_shares": implied_shares,
            },
        }
    )
    write_result(base)
    return base


def main() -> None:
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "pe_semantic": result["pe_semantic"]["status"],
                "dcf_semantic": result["dcf_semantic"]["status"],
                "pe_method": result["pe_method"]["status"],
                "pe_reasons": result["pe_method"]["reasons"],
                "dcf_method": result["dcf_method"]["status"],
                "dcf_reasons": result["dcf_method"]["reasons"],
                "cross_method_status": result["cross_method_status"],
                "cross_method_classification": (
                    None
                    if result["valuation_crosscheck"] is None
                    else result["valuation_crosscheck"]["classification"]
                ),
                "portfolio_status": (
                    None
                    if result["portfolio_sandbox"] is None
                    else result["portfolio_sandbox"]["status"]
                ),
                "execution_authorized": result["authority"][
                    "execution_authorized"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
