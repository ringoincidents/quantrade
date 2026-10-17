"""QT-CASE-004 — Hyundai Motor untouched issuer holdout.

Frozen methodology:
research/experiments/QT-CASE-004_PRE_REGISTRATION.md

This runner treats semantic and valuation-method applicability as first-class
terminal outcomes. It never substitutes a valuation method after observing the
Case result.

No model, broker, Founder Decision, DecisionPlan, PAPER, or live execution path
exists in this runner.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from quantrade.capabilities.cash_flow_valuation import (
    CashFlowDCFInput,
    CashFlowDCFScenario,
    evaluate_cash_flow_dcf,
)
from quantrade.capabilities.dart_fundamental_provider import (
    DartCorpCodeResolver,
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


EXPERIMENT_ID = "QT-CASE-004"
PREREGISTRATION_COMMIT = "5c7f5696479c3787843abca8799e937950f2daff"
CASE_ID = "QT-CASE-004:KRX:005380"
ASSET_ID = "KRX:005380"
SYMBOL = "005380"
CASE_AS_OF = "2026-10-05T23:59:59+09:00"
REQUIRED_RETURN_PCT = 15.0
VALUATION_HORIZON_DAYS = 365

NAVER_ENDPOINT = "https://api.finance.naver.com/siseJson.naver"
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; quantrade-holdout-case/1.0)"
}

RESULT_PATH = Path("research/experiments/QT-CASE-004_RESULT.json")
REPORT_PATH = Path("research/experiments/QT-CASE-004_RESULT_REPORT.md")
FULL_ARTIFACT_PATH = Path("/tmp/QT-CASE-004_FULL_ARTIFACT.json")


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


def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def fetch_prices() -> tuple[list[dict], dict]:
    params = {
        "symbol": SYMBOL,
        "requestType": 1,
        "startTime": "20220101",
        "endTime": "20261005",
        "timeframe": "day",
    }
    request = Request(
        f"{NAVER_ENDPOINT}?{urlencode(params)}",
        headers=HTTP_HEADERS,
    )
    with urlopen(request, timeout=25) as response:
        body = response.read().decode("utf-8", errors="replace")
        status = int(getattr(response, "status", 200))

    rows = re.findall(
        r"\[[\"'](\d{8})[\"'],\s*([\-\d.]+),\s*([\-\d.]+),\s*"
        r"([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+)",
        body,
    )
    if not rows:
        raise RuntimeError(
            "Naver response contained no parseable OHLCV rows"
        )
    parsed = [
        {
            "date": f"{row[0][:4]}-{row[0][4:6]}-{row[0][6:8]}",
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
        for row in rows
    ]
    if any(row["close"] <= 0.0 for row in parsed):
        raise RuntimeError("price dataset contains non-positive close")
    if parsed[-1]["date"] > "2026-10-05":
        raise RuntimeError("price dataset escaped frozen Case cutoff")
    return parsed, {
        "provider": "naver-finance-historical",
        "endpoint": NAVER_ENDPOINT,
        "params": params,
        "http_status": status,
        "row_count": len(parsed),
        "first_trading_date": parsed[0]["date"],
        "last_trading_date": parsed[-1]["date"],
        "sha256": canonical_hash(parsed),
    }


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


def method_gate(
    *,
    pe_semantic,
    dcf_semantic,
):
    if pe_semantic.status == "READY":
        annual_eps = [
            resolved_value(
                pe_semantic,
                "EPS_ANNUAL",
                f"{year}-12-31",
            )
            for year in (2022, 2023, 2024, 2025)
        ]
        ttm_eps = (
            resolved_value(
                pe_semantic,
                "EPS_ANNUAL",
                "2025-12-31",
            )
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
        pe_checks = (
            DomainCheck(
                "ANNUAL_EPS_POSITIVE_2022_2025",
                all(value > 0.0 for value in annual_eps),
                "NON_POSITIVE_ANNUAL_EPS",
                tuple(
                    row["observation_id"]
                    for row in pe_semantic.resolved
                    if row["requirement_id"] == "EPS_ANNUAL"
                ),
            ),
            DomainCheck(
                "TTM_EPS_POSITIVE",
                ttm_eps > 0.0,
                "NON_POSITIVE_TTM_EPS",
                tuple(
                    row["observation_id"]
                    for row in pe_semantic.resolved
                ),
            ),
        )
    else:
        annual_eps = []
        ttm_eps = None
        pe_checks = ()

    pe_method = evaluate_method_applicability(
        ValuationMethodApplicabilityInput(
            case_id=CASE_ID,
            method_id="PE",
            semantic_status=pe_semantic.status,
            semantic_artifact_ref="QT-CASE-004:PE_SEMANTIC",
            domain_checks=pe_checks,
        )
    )

    if dcf_semantic.status == "READY":
        fy2025_profit = resolved_value(
            dcf_semantic,
            "OWNER_PROFIT_ANNUAL",
            "2025-12-31",
        )
        fy2025_eps = resolved_value(
            dcf_semantic,
            "EPS_FY2025_FOR_SHARES",
            "2025-12-31",
        )
        implied_shares = (
            fy2025_profit / fy2025_eps
            if fy2025_profit > 0.0 and fy2025_eps > 0.0
            else 0.0
        )
        ttm_cf = (
            owner_cash_flow(dcf_semantic, "2025-12-31")
            + owner_cash_flow(dcf_semantic, "2026-06-30")
            - owner_cash_flow(dcf_semantic, "2025-06-30")
        )
        dcf_checks = (
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
        )
    else:
        fy2025_profit = None
        fy2025_eps = None
        implied_shares = None
        ttm_cf = None
        dcf_checks = ()

    dcf_method = evaluate_method_applicability(
        ValuationMethodApplicabilityInput(
            case_id=CASE_ID,
            method_id="OWNER_CASH_FLOW_DCF",
            semantic_status=dcf_semantic.status,
            semantic_artifact_ref="QT-CASE-004:DCF_SEMANTIC",
            domain_checks=dcf_checks,
        )
    )

    return {
        "pe_method": pe_method,
        "dcf_method": dcf_method,
        "annual_eps": annual_eps,
        "ttm_eps": ttm_eps,
        "fy2025_profit": fy2025_profit,
        "fy2025_eps": fy2025_eps,
        "implied_shares": implied_shares,
        "ttm_owner_cash_flow_proxy": ttm_cf,
    }


def render_report(result: dict) -> str:
    lines = [
        "# QT-CASE-004 Result — Hyundai Motor Untouched Issuer Holdout",
        "",
        "Status: **TERMINAL HOLDOUT RESULT / NO TRADE AUTHORITY**",
        "",
        f"- Case price: **{result['case']['current_price']:,.0f} KRW** "
        f"({result['case']['price_date']})",
        f"- DART corp_code: **{result['source_integrity']['corp_code']}**",
        f"- P/E semantic: **{result['pe_semantic']['status']}**",
        f"- DCF semantic: **{result['dcf_semantic']['status']}**",
        f"- P/E applicability: **{result['pe_method']['status']}**",
        f"- DCF applicability: **{result['dcf_method']['status']}**",
        f"- Cross-method status: **{result['cross_method_status']}**",
    ]
    if result["pe_method"]["reasons"]:
        lines.append(
            f"- P/E reasons: {', '.join(result['pe_method']['reasons'])}"
        )
    if result["dcf_method"]["reasons"]:
        lines.append(
            f"- DCF reasons: {', '.join(result['dcf_method']['reasons'])}"
        )

    if result["valuation_crosscheck"] is not None:
        cross = result["valuation_crosscheck"]
        lines.extend(
            [
                "",
                "## Valuation",
                "",
                f"- P/E expected return: "
                f"**{result['pe_economics']['metrics']['expected_return_pct']:.2f}%**",
                f"- DCF expected return: "
                f"**{result['cash_flow_dcf']['metrics']['expected_return_pct']:.2f}%**",
                f"- Cross-method classification: "
                f"**{cross['classification']}**",
                f"- Robust expected return: "
                f"**{cross['robust_metrics']['expected_return_pct']:.2f}%**",
                f"- Valuation gate passed: "
                f"**{cross['robust_metrics']['valuation_gate_passed']}**",
                "",
                "## Counter-Research",
                "",
                f"- Status: **{result['counter_research']['status']}**",
                f"- Flags: "
                f"{', '.join(result['counter_research']['flags']) if result['counter_research']['flags'] else 'none'}",
            ]
        )

    lines.extend(
        [
            "",
            "## Routing",
            "",
            f"- Portfolio: "
            f"**{None if result['portfolio_sandbox'] is None else result['portfolio_sandbox']['status']}**",
            f"- Risk: "
            f"**{None if result['risk_sandbox'] is None else result['risk_sandbox']['status']}**",
            "",
            "## Boundaries",
            "",
            "- Target selected before live QT-CASE-004 economic values: yes",
            "- Account-name fallback: no",
            "- Substitute valuation method selected: no",
            "- Model calls: 0",
            "- Private Client context: no",
            "- Committee/Founder Decision: none",
            "- PAPER/live execution: none",
            "",
        ]
    )
    return "\n".join(lines)


def write_result(result: dict, full_artifact: dict) -> None:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        render_report(result),
        encoding="utf-8",
    )
    FULL_ARTIFACT_PATH.write_text(
        json.dumps(
            full_artifact,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def run() -> dict:
    resolver = DartCorpCodeResolver(
        archive_max_attempts=5,
        archive_retry_backoff_seconds=2.0,
    )
    corp_code = resolver.resolve(SYMBOL)

    all_requirements = PE_REQUIREMENTS + DCF_REQUIREMENTS
    query_keys = collect_requested_metric_keys(all_requirements)

    provider = DartFundamentalObservationProvider(
        config=DartProviderConfig(
            report_codes=("11011", "11012"),
        ),
        corp_code_overrides={SYMBOL: corp_code},
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
    applicability = method_gate(
        pe_semantic=pe_semantic,
        dcf_semantic=dcf_semantic,
    )
    pe_method = applicability["pe_method"]
    dcf_method = applicability["dcf_method"]

    prices, price_meta = fetch_prices()
    current_price_row = last_close_on_or_before(
        prices,
        "2026-10-05",
        same_calendar_year=True,
    )
    current_price = float(current_price_row["close"])

    result = {
        "schema": "quantrade_qt_case_004_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "mode": "RESEARCH_UNTOUCHED_ISSUER_HOLDOUT",
        "case": {
            "case_id": CASE_ID,
            "asset_id": ASSET_ID,
            "as_of": CASE_AS_OF,
            "price_date": current_price_row["date"],
            "current_price": current_price,
            "required_return_pct": REQUIRED_RETURN_PCT,
        },
        "source_integrity": {
            "corp_code": corp_code,
            "corp_code_source": "OPEN_DART_CORPCODE",
            "corp_code_verified_by_live_filing_stock_code": True,
            "open_dart_provider": raw.provider,
            "fundamental_observation_count": len(observations),
            "fundamental_payload_sha256": canonical_hash(asdict(raw)),
            "price_source": price_meta,
            "price_after_case_cutoff_used": False,
            "target_selected_before_live_case_result": True,
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
        "pe_economics": None,
        "cash_flow_dcf": None,
        "valuation_crosscheck": None,
        "robust_investment_case_economics": None,
        "counter_research": None,
        "portfolio_sandbox": None,
        "risk_sandbox": None,
        "derived_inputs": {
            "ttm_eps": applicability["ttm_eps"],
            "fy2025_profit_attributable_to_owners": applicability[
                "fy2025_profit"
            ],
            "fy2025_basic_eps": applicability["fy2025_eps"],
            "implied_basic_shares": applicability["implied_shares"],
            "ttm_owner_cash_flow_proxy": applicability[
                "ttm_owner_cash_flow_proxy"
            ],
        },
        "operational_result": {
            "success": True,
            "real_company_data": True,
            "untouched_issuer_holdout": True,
            "method_parameters_tuned_after_result": False,
            "model_calls": 0,
            "analyst_consensus_used": False,
            "private_client_context_used": False,
            "portfolio_context_is_synthetic": True,
            "risk_context_is_synthetic": True,
        },
        "authority": {
            "canonical_evidence_created": False,
            "target_weight_set": False,
            "real_client_portfolio_proposal_created": False,
            "risk_policy_changed": False,
            "committee_decision_created": False,
            "founder_decision_created": False,
            "decision_plan_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    }

    if result["cross_method_status"] != "READY":
        write_result(
            result,
            {
                **result,
                "full_fundamental_query_result": asdict(raw),
                "full_price_rows": prices,
            },
        )
        return result

    annual_eps = {
        year: resolved_value(
            pe_semantic,
            "EPS_ANNUAL",
            f"{year}-12-31",
        )
        for year in (2022, 2023, 2024, 2025)
    }
    ttm_eps = float(applicability["ttm_eps"])
    pe_rows = []
    for year in (2022, 2023, 2024, 2025):
        price = last_close_on_or_before(
            prices,
            f"{year}-12-31",
            same_calendar_year=True,
        )
        multiple = float(price["close"]) / annual_eps[year]
        if multiple <= 0.0 or not math.isfinite(multiple):
            raise RuntimeError(
                f"{year} historical P/E is invalid despite applicability"
            )
        pe_rows.append(
            {
                "year": year,
                "price_date": price["date"],
                "year_end_close": float(price["close"]),
                "annual_eps": annual_eps[year],
                "pe": multiple,
            }
        )

    pe_values = [row["pe"] for row in pe_rows]
    p25 = percentile_linear(pe_values, 0.25)
    p50 = percentile_linear(pe_values, 0.50)
    p75 = percentile_linear(pe_values, 0.75)
    pe_scenarios = (
        ScenarioAssumption(
            "BEAR", "Bear", 0.25, ttm_eps * 0.80 * p25,
            assumption_refs=("QT-CASE-004_PRE_REGISTRATION",),
        ),
        ScenarioAssumption(
            "BASE", "Base", 0.50, ttm_eps * p50,
            assumption_refs=("QT-CASE-004_PRE_REGISTRATION",),
        ),
        ScenarioAssumption(
            "BULL", "Bull", 0.25, ttm_eps * 1.20 * p75,
            assumption_refs=("QT-CASE-004_PRE_REGISTRATION",),
        ),
    )
    pe_economics = evaluate_investment_case(
        InvestmentCaseInput(
            case_id=CASE_ID,
            asset_id=ASSET_ID,
            as_of=CASE_AS_OF,
            current_price=current_price,
            currency="KRW",
            valuation_horizon_days=VALUATION_HORIZON_DAYS,
            required_return_pct=REQUIRED_RETURN_PCT,
            scenarios=pe_scenarios,
        )
    )

    implied_shares = float(applicability["implied_shares"])
    ttm_cf = float(applicability["ttm_owner_cash_flow_proxy"])
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
                    "BEAR", "Bear", 0.25, 0.80, 0.0, 0.0, 10.0, 5,
                    ("QT-CASE-004_PRE_REGISTRATION",),
                ),
                CashFlowDCFScenario(
                    "BASE", "Base", 0.50, 1.00, 3.0, 2.0, 10.0, 5,
                    ("QT-CASE-004_PRE_REGISTRATION",),
                ),
                CashFlowDCFScenario(
                    "BULL", "Bull", 0.25, 1.20, 5.0, 3.0, 10.0, 5,
                    ("QT-CASE-004_PRE_REGISTRATION",),
                ),
            ),
        )
    )

    crosscheck = evaluate_valuation_crosscheck(
        ValuationCrossCheckInput(
            case_id=CASE_ID,
            methods=(
                ValuationMethodSnapshot(
                    method_id="PE",
                    method_type="HISTORICAL_PE",
                    source_schema=pe_economics.schema,
                    current_price=current_price,
                    required_return_pct=REQUIRED_RETURN_PCT,
                    scenarios=tuple(
                        ValuationScenarioSnapshot(
                            scenario.scenario_id,
                            scenario.probability,
                            scenario.fair_value,
                        )
                        for scenario in pe_scenarios
                    ),
                    source_refs=("QT-CASE-004:PE",),
                ),
                ValuationMethodSnapshot(
                    method_id="OWNER_CASH_FLOW_DCF",
                    method_type="OWNER_CASH_FLOW_DCF",
                    source_schema=dcf.schema,
                    current_price=current_price,
                    required_return_pct=REQUIRED_RETURN_PCT,
                    scenarios=tuple(
                        ValuationScenarioSnapshot(
                            row["scenario_id"],
                            row["probability"],
                            row["fair_value"],
                        )
                        for row in dcf.scenarios
                    ),
                    source_refs=("QT-CASE-004:DCF",),
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
            valuation_horizon_days=VALUATION_HORIZON_DAYS,
            required_return_pct=REQUIRED_RETURN_PCT,
            scenarios=tuple(
                ScenarioAssumption(
                    scenario_id=row["scenario_id"],
                    label=row["scenario_id"].title(),
                    probability=float(row["probability"]),
                    fair_value=float(
                        row["robust_lower_of_methods_fair_value"]
                    ),
                    assumption_refs=(
                        "QT-CASE-004:CROSS_METHOD_GATE",
                    ),
                )
                for row in crosscheck.robust_scenarios
            ),
        )
    )

    annual_cf = {
        year: owner_cash_flow(
            dcf_semantic,
            f"{year}-12-31",
        )
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
        year_price = last_close_on_or_before(
            prices,
            f"{year}-12-31",
            same_calendar_year=True,
        )
        historical_pb.append(
            float(year_price["close"])
            / (equity / implied_shares)
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
                    fiscal_year=year,
                    owner_cash_flow_proxy=annual_cf[year],
                    profit_attributable_to_owners=annual_profit[year],
                )
                for year in (2022, 2023, 2024, 2025)
            ),
            ttm_owner_cash_flow_proxy=ttm_cf,
            ttm_profit_attributable_to_owners=ttm_profit,
            historical_pe_values=tuple(pe_values),
            historical_pb_values=tuple(historical_pb),
            current_pb=current_pb,
            policy=FundamentalCounterResearchPolicy(
                multiple_dispersion_ratio_threshold=4.0,
                cash_conversion_threshold=0.75,
            ),
        )
    )

    portfolio = assess_portfolio_opportunity(
        PortfolioOpportunityInput(
            case_economics=robust_economics,
            alternatives=(
                CapitalAlternative(
                    "SANDBOX-CASH",
                    "CASH",
                    3.0,
                    0.0,
                    ("QT-CASE-004_PRE_REGISTRATION:SANDBOX",),
                ),
                CapitalAlternative(
                    "SANDBOX-CORE",
                    "CORE_BENCHMARK",
                    8.0,
                    None,
                    ("QT-CASE-004_PRE_REGISTRATION:SANDBOX",),
                ),
            ),
            constraints=PortfolioConstraintSnapshot(
                snapshot_id="QT-CASE-004-SANDBOX-PORTFOLIO",
                as_of="2026-10-05T23:00:00+09:00",
                mandate_allows_new_exposure=True,
                mandate_ref="QT-CASE-004_PRE_REGISTRATION:SANDBOX",
                current_asset_weight_pct=0.0,
                max_asset_weight_pct=10.0,
                current_liquidity_pct=20.0,
                minimum_liquidity_reserve_pct=10.0,
                available_downside_budget_pct=2.0,
                constraint_refs=(
                    "QT-CASE-004_PRE_REGISTRATION:SANDBOX",
                ),
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
                    asset_id=ASSET_ID,
                    worst_case_return_pct=float(
                        robust_economics.metrics[
                            "lowest_scenario_return_pct"
                        ]
                    ),
                    max_abs_correlation_to_portfolio=None,
                    estimated_exit_days=None,
                    uses_leverage=False,
                    risk_refs=("QT-CASE-004:ROBUST-BEAR",),
                ),
                policy=RiskPolicySnapshot(
                    policy_id="QT-CASE-004-SANDBOX-RISK",
                    as_of="2026-10-05T22:00:00+09:00",
                    max_single_asset_weight_pct=10.0,
                    max_incremental_downside_budget_pct=2.0,
                    max_portfolio_drawdown_pct=-20.0,
                    max_abs_correlation_to_portfolio=None,
                    max_exit_days=None,
                    leverage_allowed=False,
                    require_correlation_data=False,
                    require_liquidity_data=False,
                    policy_refs=(
                        "QT-CASE-004_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
                state=RiskStateSnapshot(
                    snapshot_id="QT-CASE-004-SANDBOX-RISK-STATE",
                    as_of="2026-10-05T22:30:00+09:00",
                    current_asset_weight_pct=0.0,
                    current_portfolio_drawdown_pct=-5.0,
                    state_refs=(
                        "QT-CASE-004_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
            )
        )

    result.update(
        {
            "historical_pe": {
                "rows": pe_rows,
                "p25": p25,
                "p50": p50,
                "p75": p75,
            },
            "pe_economics": asdict(pe_economics),
            "cash_flow_dcf": asdict(dcf),
            "valuation_crosscheck": asdict(crosscheck),
            "robust_investment_case_economics": asdict(
                robust_economics
            ),
            "counter_research": asdict(counter),
            "portfolio_sandbox": asdict(portfolio),
            "risk_sandbox": None if risk is None else asdict(risk),
            "derived_inputs": {
                **result["derived_inputs"],
                "ttm_owner_cash_flow_per_share": cash_flow_per_share,
                "ttm_profit_attributable_to_owners": ttm_profit,
                "historical_pb_values": historical_pb,
                "current_pb": current_pb,
            },
        }
    )
    result["operational_result"]["risk_invoked"] = risk is not None

    write_result(
        result,
        {
            **result,
            "full_fundamental_query_result": asdict(raw),
            "full_price_rows": prices,
        },
    )
    return result


def main() -> None:
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "asset_id": result["case"]["asset_id"],
                "corp_code": result["source_integrity"]["corp_code"],
                "current_price": result["case"]["current_price"],
                "pe_semantic": result["pe_semantic"]["status"],
                "dcf_semantic": result["dcf_semantic"]["status"],
                "pe_method": result["pe_method"]["status"],
                "pe_reasons": result["pe_method"]["reasons"],
                "dcf_method": result["dcf_method"]["status"],
                "dcf_reasons": result["dcf_method"]["reasons"],
                "cross_method_status": result["cross_method_status"],
                "classification": (
                    None
                    if result["valuation_crosscheck"] is None
                    else result["valuation_crosscheck"]["classification"]
                ),
                "robust_expected_return_pct": (
                    None
                    if result["valuation_crosscheck"] is None
                    else result["valuation_crosscheck"][
                        "robust_metrics"
                    ]["expected_return_pct"]
                ),
                "counter_flags": (
                    None
                    if result["counter_research"] is None
                    else result["counter_research"]["flags"]
                ),
                "portfolio_status": (
                    None
                    if result["portfolio_sandbox"] is None
                    else result["portfolio_sandbox"]["status"]
                ),
                "risk_status": (
                    None
                    if result["risk_sandbox"] is None
                    else result["risk_sandbox"]["status"]
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
