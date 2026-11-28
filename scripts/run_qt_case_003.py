"""QT-CASE-003 — Samsung SDI holdout transfer Golden Run.

Frozen methodology:
research/experiments/QT-CASE-003_PRE_REGISTRATION.md

This is the first company holdout after QT-CASE-001/002. It uses the reusable
cross-method valuation gate before Portfolio review.

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
from quantrade.capabilities.thesis_contract import (
    Assumption,
    CounterClaim,
    FalsificationCondition,
    Inference,
    Observation,
    SourceKind,
    ThesisClaim,
    ThesisContractInput,
    compile_thesis_contract,
)
from quantrade.capabilities.valuation_crosscheck import (
    ValuationCrossCheckInput,
    ValuationMethodSnapshot,
    ValuationScenarioSnapshot,
    evaluate_valuation_crosscheck,
)
from scripts.run_qt_case_001 import (
    compute_ttm_eps,
    last_close_on_or_before,
    percentile_linear,
)
from scripts.run_qt_case_002 import (
    annual_cash_flow_history,
    historical_pb,
    implied_basic_shares,
    owner_profit,
    parent_equity,
    select_unique,
    ttm_cash_flow,
    ttm_parent_profit,
)


EXPERIMENT_ID = "QT-CASE-003"
PREREGISTRATION_COMMIT = "bf59d2b3b147d2a2864c151ba7751a3b136563ed"
CASE_ID = "QT-CASE-003:KRX:006400"
ASSET_ID = "KRX:006400"
SYMBOL = "006400"
CASE_AS_OF = "2026-10-05T23:59:59+09:00"
REQUIRED_RETURN_PCT = 15.0
VALUATION_HORIZON_DAYS = 365

EPS_PERIOD_KEY = (
    "DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:"
    "IS:CURRENT_PERIOD"
)
EPS_YTD_KEY = (
    "DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:"
    "IS:CURRENT_YTD"
)
CFO_KEY = (
    "DART_ACCOUNT:ifrs-full_CashFlowsFromUsedInOperatingActivities:"
    "CF:CURRENT_PERIOD"
)
PPE_CAPEX_KEY = (
    "DART_ACCOUNT:"
    "ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities:"
    "CF:CURRENT_PERIOD"
)
INTANGIBLE_CAPEX_KEY = (
    "DART_ACCOUNT:"
    "ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities:"
    "CF:CURRENT_PERIOD"
)
OWNER_PROFIT_PERIOD_KEY = (
    "DART_ACCOUNT:ifrs-full_ProfitLossAttributableToOwnersOfParent:"
    "IS:CURRENT_PERIOD"
)
OWNER_PROFIT_YTD_KEY = (
    "DART_ACCOUNT:ifrs-full_ProfitLossAttributableToOwnersOfParent:"
    "IS:CURRENT_YTD"
)
PARENT_EQUITY_KEY = (
    "DART_ACCOUNT:ifrs-full_EquityAttributableToOwnersOfParent:"
    "BS:CURRENT_PERIOD"
)

QUERY_KEYS = (
    EPS_PERIOD_KEY,
    EPS_YTD_KEY,
    CFO_KEY,
    PPE_CAPEX_KEY,
    INTANGIBLE_CAPEX_KEY,
    OWNER_PROFIT_PERIOD_KEY,
    OWNER_PROFIT_YTD_KEY,
    PARENT_EQUITY_KEY,
)

NAVER_ENDPOINT = "https://api.finance.naver.com/siseJson.naver"
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; quantrade-holdout-case/1.0)"
}
RESULT_PATH = Path("research/experiments/QT-CASE-003_RESULT.json")
REPORT_PATH = Path("research/experiments/QT-CASE-003_RESULT_REPORT.md")
FULL_ARTIFACT_PATH = Path("/tmp/QT-CASE-003_FULL_ARTIFACT.json")


class GoldenRunError(RuntimeError):
    """Raised when a preregistered QT-CASE-003 requirement cannot be met."""


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
        raise GoldenRunError(
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
        raise GoldenRunError("price dataset contains non-positive close")
    if parsed[-1]["date"] > "2026-10-05":
        raise GoldenRunError("price dataset escaped frozen Case cutoff")
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


def annual_eps_history(observations: list[dict]) -> dict[int, dict]:
    rows = {}
    for year in (2022, 2023, 2024, 2025):
        row = select_unique(
            observations,
            fiscal_period_end=f"{year}-12-31",
            metric_key=EPS_PERIOD_KEY,
        )
        if float(row["value"]) <= 0.0:
            raise GoldenRunError(
                f"{year} annual EPS is non-positive"
            )
        rows[year] = row
    return rows


def historical_pe(
    observations: list[dict],
    prices: list[dict],
) -> dict:
    eps = annual_eps_history(observations)
    rows = []
    for year in (2022, 2023, 2024, 2025):
        price = last_close_on_or_before(
            prices,
            f"{year}-12-31",
            same_calendar_year=True,
        )
        multiple = float(price["close"]) / float(eps[year]["value"])
        if multiple <= 0.0 or not math.isfinite(multiple):
            raise GoldenRunError(
                f"{year} historical P/E is invalid"
            )
        rows.append(
            {
                "year": year,
                "price_date": price["date"],
                "year_end_close": float(price["close"]),
                "annual_eps": float(eps[year]["value"]),
                "pe": multiple,
                "eps_observation_id": eps[year]["observation_id"],
                "eps_evidence_ref": eps[year]["evidence_ref"],
            }
        )
    values = [row["pe"] for row in rows]
    return {
        "rows": rows,
        "p25": percentile_linear(values, 0.25),
        "p50": percentile_linear(values, 0.50),
        "p75": percentile_linear(values, 0.75),
    }


def make_dart_observation(
    row: dict,
    observation_id: str,
    label: str,
) -> Observation:
    return Observation(
        observation_id=observation_id,
        statement=f"{label}: {row['value']} {row.get('unit') or ''}".strip(),
        source_ref=str(row["evidence_ref"]),
        source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
        observed_at=str(row["published_at"]),
    )


def make_price_observation(
    row: dict,
    *,
    observation_id: str,
    label: str,
    price_hash: str,
) -> Observation:
    return Observation(
        observation_id=observation_id,
        statement=f"{label}: {row['close']} KRW",
        source_ref=(
            f"{NAVER_ENDPOINT}#sha256={price_hash}&date={row['date']}"
        ),
        source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
        observed_at=f"{row['date']}T15:30:00+09:00",
    )


def build_thesis(
    *,
    observations: list[dict],
    prices: list[dict],
    price_meta: dict,
    current_price_row: dict,
    ttm_eps: dict,
    pe_history: dict,
    pe_economics: object,
    ttm_cf: dict,
    ttm_profit: dict,
    shares: dict,
    dcf: object,
    crosscheck: object,
    counter: object,
) -> object:
    nodes = [
        make_dart_observation(
            ttm_eps["source_rows"]["fy2025"],
            "OBS-EPS-FY2025",
            "FY2025 basic EPS",
        ),
        make_dart_observation(
            ttm_eps["source_rows"]["h1_2025"],
            "OBS-EPS-H1-2025",
            "2025-H1 YTD basic EPS",
        ),
        make_dart_observation(
            ttm_eps["source_rows"]["h1_2026"],
            "OBS-EPS-H1-2026",
            "2026-H1 YTD basic EPS",
        ),
        make_price_observation(
            current_price_row,
            observation_id="OBS-PRICE-CASE",
            label="Case-date close",
            price_hash=price_meta["sha256"],
        ),
    ]

    for year in (2022, 2023, 2024, 2025):
        eps_row = select_unique(
            observations,
            fiscal_period_end=f"{year}-12-31",
            metric_key=EPS_PERIOD_KEY,
        )
        nodes.append(
            make_dart_observation(
                eps_row,
                f"OBS-EPS-FY{year}",
                f"FY{year} basic EPS",
            )
        )
        pe_row = next(
            item for item in pe_history["rows"]
            if item["year"] == year
        )
        nodes.append(
            make_price_observation(
                {
                    "date": pe_row["price_date"],
                    "close": pe_row["year_end_close"],
                },
                observation_id=f"OBS-PRICE-YE-{year}",
                label=f"{year} year-end close",
                price_hash=price_meta["sha256"],
            )
        )
        cash = annual_cash_flow_history(observations)[year]
        for key, oid, label in (
            ("cfo", f"OBS-CFO-{year}", "operating cash flow"),
            ("ppe_capex", f"OBS-PPE-CAPEX-{year}", "PP&E purchases"),
            (
                "intangible_capex",
                f"OBS-INT-CAPEX-{year}",
                "intangible purchases",
            ),
        ):
            nodes.append(
                make_dart_observation(
                    cash["source_rows"][key],
                    oid,
                    f"FY{year} {label}",
                )
            )

    for prefix, period, source in (
        ("2025-H1", "2025-06-30", ttm_cf["h1_2025"]),
        ("2026-H1", "2026-06-30", ttm_cf["h1_2026"]),
    ):
        for key, oid, label in (
            ("cfo", f"OBS-CFO-{prefix}", "operating cash flow"),
            ("ppe_capex", f"OBS-PPE-CAPEX-{prefix}", "PP&E purchases"),
            (
                "intangible_capex",
                f"OBS-INT-CAPEX-{prefix}",
                "intangible purchases",
            ),
        ):
            nodes.append(
                make_dart_observation(
                    source["source_rows"][key],
                    oid,
                    f"{prefix} {label}",
                )
            )
        nodes.append(
            make_dart_observation(
                owner_profit(
                    observations,
                    period,
                    ytd=True,
                ),
                f"OBS-OWNER-PROFIT-{prefix}",
                f"{prefix} YTD profit attributable to owners",
            )
        )

    for year in (2022, 2023, 2024, 2025):
        nodes.append(
            make_dart_observation(
                owner_profit(
                    observations,
                    f"{year}-12-31",
                    ytd=False,
                ),
                f"OBS-OWNER-PROFIT-{year}",
                f"FY{year} profit attributable to owners",
            )
        )

    assumptions = (
        Assumption(
            assumption_id="ASM-PE-FROZEN",
            statement=(
                "QT-CASE-003 uses the preregistered P/E percentiles and "
                "80/100/120% TTM EPS scenario structure unchanged."
            ),
            rationale="Holdout transfer of QT-CASE-001 method.",
            provenance_refs=("QT-CASE-003_PRE_REGISTRATION",),
        ),
        Assumption(
            assumption_id="ASM-DCF-FROZEN",
            statement=(
                "QT-CASE-003 uses the preregistered five-year cash-flow DCF "
                "assumptions unchanged."
            ),
            rationale="Holdout transfer of QT-CASE-002 method.",
            provenance_refs=("QT-CASE-003_PRE_REGISTRATION",),
        ),
    )

    inference_rows = (
        Inference(
            inference_id="INF-TTM-EPS",
            statement=f"TTM basic EPS={ttm_eps['ttm_eps']:.6f} KRW.",
            input_refs=(
                "OBS-EPS-FY2025",
                "OBS-EPS-H1-2025",
                "OBS-EPS-H1-2026",
            ),
        ),
        Inference(
            inference_id="INF-PE",
            statement=(
                "Historical P/E percentiles: "
                f"P25={pe_history['p25']:.6f}, "
                f"P50={pe_history['p50']:.6f}, "
                f"P75={pe_history['p75']:.6f}; "
                "weighted P/E fair value="
                f"{pe_economics.metrics['weighted_fair_value']:.6f} KRW."
            ),
            input_refs=tuple(
                ref
                for year in (2022, 2023, 2024, 2025)
                for ref in (
                    f"OBS-EPS-FY{year}",
                    f"OBS-PRICE-YE-{year}",
                )
            )
            + ("ASM-PE-FROZEN",),
        ),
        Inference(
            inference_id="INF-TTM-OWNER-CF",
            statement=(
                "TTM owner-cash-flow proxy="
                f"{ttm_cf['ttm_owner_cash_flow_proxy']:.0f} KRW."
            ),
            input_refs=(
                "OBS-CFO-2025",
                "OBS-PPE-CAPEX-2025",
                "OBS-INT-CAPEX-2025",
                "OBS-CFO-2025-H1",
                "OBS-PPE-CAPEX-2025-H1",
                "OBS-INT-CAPEX-2025-H1",
                "OBS-CFO-2026-H1",
                "OBS-PPE-CAPEX-2026-H1",
                "OBS-INT-CAPEX-2026-H1",
            ),
        ),
        Inference(
            inference_id="INF-DCF",
            statement=(
                "Cash-flow DCF weighted fair value="
                f"{dcf.metrics['weighted_fair_value']:.6f} KRW."
            ),
            input_refs=(
                "INF-TTM-OWNER-CF",
                "ASM-DCF-FROZEN",
                "OBS-PRICE-CASE",
            ),
        ),
        Inference(
            inference_id="INF-CROSS-METHOD",
            statement=(
                "Cross-method classification="
                f"{crosscheck.classification}; robust fair value="
                f"{crosscheck.robust_metrics['weighted_fair_value']:.6f}; "
                "valuation_gate_passed="
                f"{crosscheck.robust_metrics['valuation_gate_passed']}."
            ),
            input_refs=(
                "INF-PE",
                "INF-DCF",
                "OBS-PRICE-CASE",
            ),
        ),
        Inference(
            inference_id="INF-COUNTER",
            statement=(
                "Deterministic counter-research flags="
                f"{','.join(counter.flags) if counter.flags else 'NONE'}."
            ),
            input_refs=(
                "INF-PE",
                "INF-TTM-OWNER-CF",
            ),
        ),
    )

    if crosscheck.robust_metrics["valuation_gate_passed"]:
        thesis_statement = (
            "Independent P/E and owner-cash-flow DCF methods both support "
            "passing the frozen cross-method valuation gate."
        )
    else:
        thesis_statement = (
            "The frozen holdout valuation does not pass the cross-method "
            "valuation gate."
        )

    return compile_thesis_contract(
        ThesisContractInput(
            case_id=CASE_ID,
            as_of=CASE_AS_OF,
            observations=tuple(nodes),
            assumptions=assumptions,
            inferences=inference_rows,
            thesis_claims=(
                ThesisClaim(
                    thesis_id="THESIS-QT-CASE-003",
                    statement=thesis_statement,
                    support_refs=("INF-CROSS-METHOD",),
                ),
            ),
            counter_claims=(
                CounterClaim(
                    counter_id="COUNTER-CAPITAL-INTENSITY",
                    thesis_id="THESIS-QT-CASE-003",
                    statement=(
                        "A favorable accounting-earnings valuation may not "
                        "survive owner-cash-flow valuation in a capital-"
                        "intensive battery manufacturer because capex, cash "
                        "conversion, and valuation regimes can diverge from "
                        "current EPS."
                    ),
                    basis_refs=(
                        "INF-PE",
                        "INF-TTM-OWNER-CF",
                        "INF-COUNTER",
                    ),
                ),
            ),
            falsification_conditions=(
                FalsificationCondition(
                    condition_id="FALSIFY-TTM-OWNER-CF-80",
                    thesis_id="THESIS-QT-CASE-003",
                    statement=(
                        "Reconstructed TTM owner-cash-flow proxy falls below "
                        "80% of the frozen QT-CASE-003 level "
                        f"({ttm_cf['ttm_owner_cash_flow_proxy']:.0f} KRW)."
                    ),
                    observable="ttm_owner_cash_flow_proxy",
                    evaluation_horizon=(
                        "next_two_reported_quarters_or_365_days_whichever_first"
                    ),
                ),
                FalsificationCondition(
                    condition_id="FALSIFY-ROBUST-FAIR-VALUE-BELOW-PRICE",
                    thesis_id="THESIS-QT-CASE-003",
                    statement=(
                        "The same cross-method methodology later produces "
                        "robust fair value below the frozen Case price."
                    ),
                    observable="robust_cross_method_fair_value",
                    evaluation_horizon="365_days",
                ),
            ),
        )
    )


def render_report(result: dict) -> str:
    pe = result["pe_economics"]["metrics"]
    dcf = result["cash_flow_dcf"]["metrics"]
    gate = result["valuation_crosscheck"]
    counter = result["counter_research"]
    portfolio = result["portfolio_sandbox"]
    risk = result["risk_sandbox"]
    lines = [
        "# QT-CASE-003 Result — Samsung SDI Holdout Transfer Case",
        "",
        "Status: **COMPLETED / HOLDOUT / NO TRADE AUTHORITY**",
        "",
        f"- Case price: **{result['case']['current_price']:,.0f} KRW** "
        f"({result['case']['price_date']})",
        f"- TTM EPS: **{result['earnings']['ttm_eps']:,.2f} KRW**",
        f"- TTM owner cash flow/share: "
        f"**{result['cash_flow']['ttm_owner_cash_flow_per_share']:,.0f} KRW**",
        "",
        "## Valuation methods",
        "",
        f"- P/E weighted fair value: **{pe['weighted_fair_value']:,.0f} KRW**",
        f"- P/E expected return: **{pe['expected_return_pct']:.2f}%**",
        f"- DCF weighted fair value: **{dcf['weighted_fair_value']:,.0f} KRW**",
        f"- DCF expected return: **{dcf['expected_return_pct']:.2f}%**",
        f"- Cross-method classification: **{gate['classification']}**",
        f"- Robust fair value: "
        f"**{gate['robust_metrics']['weighted_fair_value']:,.0f} KRW**",
        f"- Robust expected return: "
        f"**{gate['robust_metrics']['expected_return_pct']:.2f}%**",
        f"- Valuation gate passed: "
        f"**{gate['robust_metrics']['valuation_gate_passed']}**",
        "",
        "## Counter-Research",
        "",
        f"- Status: **{counter['status']}**",
        f"- Flags: {', '.join(counter['flags']) if counter['flags'] else 'none'}",
        "",
        "## Routing",
        "",
        f"- Portfolio: **{portfolio['status']}**",
        f"- Reasons: {', '.join(portfolio['reasons'])}",
    ]
    if risk is None:
        lines.append("- Risk: not invoked")
    else:
        lines.append(f"- Risk: **{risk['status']}**")
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Real PIT company data: yes",
            "- Company holdout: yes",
            "- Method parameters tuned after result: no",
            "- Model calls: 0",
            "- Private Client portfolio: no",
            "- Committee/Founder Decision: none",
            "- PAPER/live execution: none",
            "",
        ]
    )
    return "\n".join(lines)


def run() -> dict:
    provider = DartFundamentalObservationProvider(
        config=DartProviderConfig(
            report_codes=("11011", "11012"),
        ),
        corp_code_overrides={
            # Provider identifier only, not an economic input. The provider
            # independently verifies that returned DART filings carry stock
            # code 006400 before using any financial row.
            "006400": "00126362",
        },
    )
    fundamental_result = provider.query(
        FundamentalQuery(
            asset_id=ASSET_ID,
            as_of=CASE_AS_OF,
            metric_keys=QUERY_KEYS,
            fiscal_period_end_from="2022-01-01",
            fiscal_period_end_to="2026-06-30",
        )
    )
    fundamental = asdict(fundamental_result)
    observations = list(fundamental["observations"])

    prices, price_meta = fetch_prices()
    current_price_row = last_close_on_or_before(
        prices,
        "2026-10-05",
        same_calendar_year=True,
    )
    current_price = float(current_price_row["close"])

    ttm_eps = compute_ttm_eps(observations)
    pe_history = historical_pe(observations, prices)

    pe_scenarios = (
        ScenarioAssumption(
            scenario_id="BEAR",
            label="Bear",
            probability=0.25,
            fair_value=(
                ttm_eps["ttm_eps"] * 0.80 * pe_history["p25"]
            ),
            assumption_refs=("QT-CASE-003_PRE_REGISTRATION",),
        ),
        ScenarioAssumption(
            scenario_id="BASE",
            label="Base",
            probability=0.50,
            fair_value=(
                ttm_eps["ttm_eps"] * pe_history["p50"]
            ),
            assumption_refs=("QT-CASE-003_PRE_REGISTRATION",),
        ),
        ScenarioAssumption(
            scenario_id="BULL",
            label="Bull",
            probability=0.25,
            fair_value=(
                ttm_eps["ttm_eps"] * 1.20 * pe_history["p75"]
            ),
            assumption_refs=("QT-CASE-003_PRE_REGISTRATION",),
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

    cash_history = annual_cash_flow_history(observations)
    ttm_cf = ttm_cash_flow(observations)
    ttm_profit = ttm_parent_profit(observations)
    shares = implied_basic_shares(observations)
    cash_flow_per_share = (
        ttm_cf["ttm_owner_cash_flow_proxy"]
        / shares["implied_basic_shares"]
    )
    if cash_flow_per_share <= 0.0:
        raise GoldenRunError(
            "TTM owner cash flow per share must be positive"
        )

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
                    ("QT-CASE-003_PRE_REGISTRATION",),
                ),
                CashFlowDCFScenario(
                    "BASE", "Base", 0.50, 1.00, 3.0, 2.0, 10.0, 5,
                    ("QT-CASE-003_PRE_REGISTRATION",),
                ),
                CashFlowDCFScenario(
                    "BULL", "Bull", 0.25, 1.20, 5.0, 3.0, 10.0, 5,
                    ("QT-CASE-003_PRE_REGISTRATION",),
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
                    source_refs=(
                        "QT-CASE-003_PRE_REGISTRATION:PE",
                    ),
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
                    source_refs=(
                        "QT-CASE-003_PRE_REGISTRATION:DCF",
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
                        "QT-CASE-003:CROSS_METHOD_GATE",
                    ),
                )
                for row in crosscheck.robust_scenarios
            ),
        )
    )

    pb = historical_pb(
        observations,
        prices,
        shares["implied_basic_shares"],
        current_price,
    )
    counter = evaluate_fundamental_counter_research(
        FundamentalCounterResearchInput(
            case_id=CASE_ID,
            annual_cash_conversion=tuple(
                AnnualCashConversion(
                    fiscal_year=year,
                    owner_cash_flow_proxy=float(
                        cash_history[year]["owner_cash_flow_proxy"]
                    ),
                    profit_attributable_to_owners=float(
                        cash_history[year]["profit_attributable_to_owners"]
                    ),
                )
                for year in (2022, 2023, 2024, 2025)
            ),
            ttm_owner_cash_flow_proxy=float(
                ttm_cf["ttm_owner_cash_flow_proxy"]
            ),
            ttm_profit_attributable_to_owners=float(
                ttm_profit["ttm_profit_attributable_to_owners"]
            ),
            historical_pe_values=tuple(
                float(row["pe"]) for row in pe_history["rows"]
            ),
            historical_pb_values=tuple(
                float(row["pb"]) for row in pb["rows"]
            ),
            current_pb=float(pb["current_pb"]),
            policy=FundamentalCounterResearchPolicy(
                multiple_dispersion_ratio_threshold=4.0,
                cash_conversion_threshold=0.75,
            ),
        )
    )

    thesis = build_thesis(
        observations=observations,
        prices=prices,
        price_meta=price_meta,
        current_price_row=current_price_row,
        ttm_eps=ttm_eps,
        pe_history=pe_history,
        pe_economics=pe_economics,
        ttm_cf=ttm_cf,
        ttm_profit=ttm_profit,
        shares=shares,
        dcf=dcf,
        crosscheck=crosscheck,
        counter=counter,
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
                    ("QT-CASE-003_PRE_REGISTRATION:SANDBOX",),
                ),
                CapitalAlternative(
                    "SANDBOX-CORE",
                    "CORE_BENCHMARK",
                    8.0,
                    None,
                    ("QT-CASE-003_PRE_REGISTRATION:SANDBOX",),
                ),
            ),
            constraints=PortfolioConstraintSnapshot(
                snapshot_id="QT-CASE-003-SANDBOX-PORTFOLIO",
                as_of="2026-10-05T23:00:00+09:00",
                mandate_allows_new_exposure=True,
                mandate_ref="QT-CASE-003_PRE_REGISTRATION:SANDBOX",
                current_asset_weight_pct=0.0,
                max_asset_weight_pct=10.0,
                current_liquidity_pct=20.0,
                minimum_liquidity_reserve_pct=10.0,
                available_downside_budget_pct=2.0,
                constraint_refs=(
                    "QT-CASE-003_PRE_REGISTRATION:SANDBOX",
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
                    risk_refs=(
                        "QT-CASE-003:ROBUST-BEAR-SCENARIO",
                    ),
                ),
                policy=RiskPolicySnapshot(
                    policy_id="QT-CASE-003-SANDBOX-RISK",
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
                        "QT-CASE-003_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
                state=RiskStateSnapshot(
                    snapshot_id="QT-CASE-003-SANDBOX-RISK-STATE",
                    as_of="2026-10-05T22:30:00+09:00",
                    current_asset_weight_pct=0.0,
                    current_portfolio_drawdown_pct=-5.0,
                    state_refs=(
                        "QT-CASE-003_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
            )
        )

    compact = {
        "schema": "quantrade_qt_case_003_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "mode": "RESEARCH_HOLDOUT_PAPER_ONLY",
        "case": {
            "case_id": CASE_ID,
            "asset_id": ASSET_ID,
            "as_of": CASE_AS_OF,
            "price_date": current_price_row["date"],
            "current_price": current_price,
            "required_return_pct": REQUIRED_RETURN_PCT,
        },
        "source_integrity": {
            "open_dart_provider": fundamental["provider"],
            "fundamental_observation_count": len(observations),
            "fundamental_payload_sha256": canonical_hash(fundamental),
            "price_source": price_meta,
            "price_after_case_cutoff_used": False,
            "target_selected_before_live_case_result": True,
            "corp_code_seed": {
                "stock_code": "006400",
                "corp_code": "00126362",
                "economic_input": False,
                "verified_against_live_filing_stock_code": True,
            },
        },
        "earnings": {
            "fy2025_eps": ttm_eps["fy2025_eps"],
            "h1_2025_ytd_eps": ttm_eps["h1_2025_ytd_eps"],
            "h1_2026_ytd_eps": ttm_eps["h1_2026_ytd_eps"],
            "ttm_eps": ttm_eps["ttm_eps"],
        },
        "historical_pe": pe_history,
        "pe_economics": asdict(pe_economics),
        "cash_flow": {
            "annual_history": {
                str(year): {
                    key: value
                    for key, value in cash_history[year].items()
                    if key != "source_rows"
                }
                for year in (2022, 2023, 2024, 2025)
            },
            "ttm_owner_cash_flow_proxy": ttm_cf[
                "ttm_owner_cash_flow_proxy"
            ],
            "ttm_profit_attributable_to_owners": ttm_profit[
                "ttm_profit_attributable_to_owners"
            ],
            "implied_basic_shares": shares[
                "implied_basic_shares"
            ],
            "ttm_owner_cash_flow_per_share": cash_flow_per_share,
        },
        "cash_flow_dcf": asdict(dcf),
        "valuation_crosscheck": asdict(crosscheck),
        "robust_investment_case_economics": asdict(
            robust_economics
        ),
        "counter_research": asdict(counter),
        "historical_pb": pb,
        "thesis_contract": asdict(thesis),
        "portfolio_sandbox": asdict(portfolio),
        "risk_sandbox": None if risk is None else asdict(risk),
        "operational_result": {
            "success": True,
            "real_company_data": True,
            "company_holdout": True,
            "method_parameters_tuned_after_result": False,
            "model_calls": 0,
            "analyst_consensus_used": False,
            "private_client_context_used": False,
            "portfolio_context_is_synthetic": True,
            "risk_context_is_synthetic": True,
            "risk_invoked": risk is not None,
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

    full_artifact = {
        **compact,
        "full_fundamental_query_result": fundamental,
        "full_price_rows": prices,
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(compact, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        render_report(compact),
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
    return compact


def main() -> None:
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "asset_id": result["case"]["asset_id"],
                "current_price": result["case"]["current_price"],
                "ttm_eps": result["earnings"]["ttm_eps"],
                "pe_expected_return_pct": result["pe_economics"][
                    "metrics"
                ]["expected_return_pct"],
                "dcf_expected_return_pct": result["cash_flow_dcf"][
                    "metrics"
                ]["expected_return_pct"],
                "cross_method_classification": result[
                    "valuation_crosscheck"
                ]["classification"],
                "valuation_gate_passed": result[
                    "valuation_crosscheck"
                ]["robust_metrics"]["valuation_gate_passed"],
                "robust_expected_return_pct": result[
                    "valuation_crosscheck"
                ]["robust_metrics"]["expected_return_pct"],
                "counter_flags": result["counter_research"]["flags"],
                "portfolio_status": result["portfolio_sandbox"]["status"],
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
