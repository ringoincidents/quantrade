"""QT-CASE-002 — Samsung cash-flow and cross-method robustness Golden Run.

Frozen methodology:
research/experiments/QT-CASE-002_PRE_REGISTRATION.md

The run challenges QT-CASE-001 with:
- point-in-time Open DART operating cash flow and capex;
- a deterministic 5-year cash-flow DCF;
- lower-of-two P/E vs DCF scenario valuation;
- deterministic counter-research;
- the same synthetic Portfolio/Risk context as QT-CASE-001.

No model, broker, Founder Decision, DecisionPlan, PAPER, or live execution path
exists in this runner.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
from statistics import median

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
from scripts.run_qt_case_001 import (
    fetch_naver_prices,
    last_close_on_or_before,
    percentile_linear,
)


EXPERIMENT_ID = "QT-CASE-002"
PREREGISTRATION_COMMIT = "63325f10b4e4da6d5daa1b9510dbe45cab157bcb"
CASE001_RESULT_PATH = Path("research/experiments/QT-CASE-001_RESULT.json")
CASE_ID = "QT-CASE-002:KRX:005930"
ASSET_ID = "KRX:005930"
CASE_AS_OF = "2026-10-05T23:59:59+09:00"
REQUIRED_RETURN_PCT = 15.0
VALUATION_HORIZON_DAYS = 365

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
BASIC_EPS_PERIOD_KEY = (
    "DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:"
    "IS:CURRENT_PERIOD"
)
PARENT_EQUITY_KEY = (
    "DART_ACCOUNT:ifrs-full_EquityAttributableToOwnersOfParent:"
    "BS:CURRENT_PERIOD"
)

QUERY_KEYS = (
    CFO_KEY,
    PPE_CAPEX_KEY,
    INTANGIBLE_CAPEX_KEY,
    OWNER_PROFIT_PERIOD_KEY,
    OWNER_PROFIT_YTD_KEY,
    BASIC_EPS_PERIOD_KEY,
    PARENT_EQUITY_KEY,
)

RESULT_PATH = Path("research/experiments/QT-CASE-002_RESULT.json")
REPORT_PATH = Path("research/experiments/QT-CASE-002_RESULT_REPORT.md")
FULL_ARTIFACT_PATH = Path("/tmp/QT-CASE-002_FULL_ARTIFACT.json")


class GoldenRunError(RuntimeError):
    """Raised when a preregistered QT-CASE-002 requirement is not met."""


def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_case001() -> dict:
    if not CASE001_RESULT_PATH.exists():
        raise GoldenRunError(
            "immutable QT-CASE-001 result is required"
        )
    result = json.loads(CASE001_RESULT_PATH.read_text(encoding="utf-8"))
    if result.get("experiment_id") != "QT-CASE-001":
        raise GoldenRunError("invalid QT-CASE-001 result artifact")
    if result.get("authority", {}).get("execution_authorized") is not False:
        raise GoldenRunError(
            "QT-CASE-001 artifact must remain non-execution-authoritative"
        )
    return result


def select_unique(
    observations: list[dict],
    *,
    fiscal_period_end: str,
    metric_key: str,
) -> dict:
    matches = [
        row
        for row in observations
        if row.get("fiscal_period_end") == fiscal_period_end
        and row.get("metric_key") == metric_key
    ]
    if len(matches) != 1:
        raise GoldenRunError(
            "required DART observation must be unique: "
            f"period={fiscal_period_end} metric={metric_key} "
            f"count={len(matches)}"
        )
    value = matches[0].get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GoldenRunError("DART observation must be numeric")
    if not math.isfinite(float(value)):
        raise GoldenRunError("DART observation must be finite")
    return matches[0]


def owner_cash_flow_for_period(
    observations: list[dict],
    fiscal_period_end: str,
) -> dict:
    cfo = select_unique(
        observations,
        fiscal_period_end=fiscal_period_end,
        metric_key=CFO_KEY,
    )
    ppe = select_unique(
        observations,
        fiscal_period_end=fiscal_period_end,
        metric_key=PPE_CAPEX_KEY,
    )
    intangible = select_unique(
        observations,
        fiscal_period_end=fiscal_period_end,
        metric_key=INTANGIBLE_CAPEX_KEY,
    )
    values = {
        "operating_cash_flow": float(cfo["value"]),
        "ppe_capex": float(ppe["value"]),
        "intangible_capex": float(intangible["value"]),
    }
    proxy = (
        values["operating_cash_flow"]
        - values["ppe_capex"]
        - values["intangible_capex"]
    )
    return {
        "fiscal_period_end": fiscal_period_end,
        **values,
        "owner_cash_flow_proxy": proxy,
        "source_observation_ids": (
            cfo["observation_id"],
            ppe["observation_id"],
            intangible["observation_id"],
        ),
        "source_rows": {
            "cfo": cfo,
            "ppe_capex": ppe,
            "intangible_capex": intangible,
        },
    }


def owner_profit(
    observations: list[dict],
    fiscal_period_end: str,
    *,
    ytd: bool,
) -> dict:
    return select_unique(
        observations,
        fiscal_period_end=fiscal_period_end,
        metric_key=(
            OWNER_PROFIT_YTD_KEY
            if ytd
            else OWNER_PROFIT_PERIOD_KEY
        ),
    )


def parent_equity(
    observations: list[dict],
    fiscal_period_end: str,
) -> dict:
    return select_unique(
        observations,
        fiscal_period_end=fiscal_period_end,
        metric_key=PARENT_EQUITY_KEY,
    )


def annual_cash_flow_history(observations: list[dict]) -> dict[int, dict]:
    result = {}
    for year in (2022, 2023, 2024, 2025):
        period = f"{year}-12-31"
        cf = owner_cash_flow_for_period(observations, period)
        profit = owner_profit(observations, period, ytd=False)
        result[year] = {
            **cf,
            "profit_attributable_to_owners": float(profit["value"]),
            "profit_observation_id": profit["observation_id"],
            "profit_evidence_ref": profit["evidence_ref"],
            "cash_conversion_ratio": (
                cf["owner_cash_flow_proxy"]
                / float(profit["value"])
            ),
        }
        if float(profit["value"]) <= 0.0:
            raise GoldenRunError(
                f"{year} profit attributable to owners must be positive"
            )
    return result


def ttm_cash_flow(observations: list[dict]) -> dict:
    fy2025 = owner_cash_flow_for_period(
        observations,
        "2025-12-31",
    )
    h1_2025 = owner_cash_flow_for_period(
        observations,
        "2025-06-30",
    )
    h1_2026 = owner_cash_flow_for_period(
        observations,
        "2026-06-30",
    )
    ttm = (
        fy2025["owner_cash_flow_proxy"]
        + h1_2026["owner_cash_flow_proxy"]
        - h1_2025["owner_cash_flow_proxy"]
    )
    if ttm <= 0.0:
        raise GoldenRunError(
            "NON_POSITIVE_TTM_OWNER_CASH_FLOW"
        )
    return {
        "fy2025": fy2025,
        "h1_2025": h1_2025,
        "h1_2026": h1_2026,
        "ttm_owner_cash_flow_proxy": ttm,
        "formula": (
            "FY2025 owner cash flow + 2026-H1 owner cash flow "
            "- 2025-H1 owner cash flow"
        ),
    }


def ttm_parent_profit(observations: list[dict]) -> dict:
    fy2025 = owner_profit(
        observations,
        "2025-12-31",
        ytd=False,
    )
    h1_2025 = owner_profit(
        observations,
        "2025-06-30",
        ytd=True,
    )
    h1_2026 = owner_profit(
        observations,
        "2026-06-30",
        ytd=True,
    )
    value = (
        float(fy2025["value"])
        + float(h1_2026["value"])
        - float(h1_2025["value"])
    )
    if value <= 0.0:
        raise GoldenRunError(
            "TTM profit attributable to owners must be positive"
        )
    return {
        "fy2025": float(fy2025["value"]),
        "h1_2025_ytd": float(h1_2025["value"]),
        "h1_2026_ytd": float(h1_2026["value"]),
        "ttm_profit_attributable_to_owners": value,
        "source_rows": {
            "fy2025": fy2025,
            "h1_2025": h1_2025,
            "h1_2026": h1_2026,
        },
    }


def implied_basic_shares(observations: list[dict]) -> dict:
    profit = owner_profit(
        observations,
        "2025-12-31",
        ytd=False,
    )
    eps = select_unique(
        observations,
        fiscal_period_end="2025-12-31",
        metric_key=BASIC_EPS_PERIOD_KEY,
    )
    profit_value = float(profit["value"])
    eps_value = float(eps["value"])
    if profit_value <= 0.0 or eps_value <= 0.0:
        raise GoldenRunError(
            "implied-share inputs must be positive"
        )
    shares = profit_value / eps_value
    return {
        "profit_attributable_to_owners": profit_value,
        "basic_eps": eps_value,
        "implied_basic_shares": shares,
        "profit_observation_id": profit["observation_id"],
        "eps_observation_id": eps["observation_id"],
        "accounting_derived_approximation": True,
    }


def historical_pb(
    observations: list[dict],
    price_rows: list[dict],
    shares: float,
    current_price: float,
) -> dict:
    rows = []
    for year in (2022, 2023, 2024, 2025):
        equity = parent_equity(
            observations,
            f"{year}-12-31",
        )
        price = last_close_on_or_before(
            price_rows,
            f"{year}-12-31",
            same_calendar_year=True,
        )
        bvps = float(equity["value"]) / shares
        if bvps <= 0.0:
            raise GoldenRunError(
                f"{year} parent-equity BVPS must be positive"
            )
        pb = float(price["close"]) / bvps
        rows.append(
            {
                "year": year,
                "price_date": price["date"],
                "year_end_close": float(price["close"]),
                "parent_equity": float(equity["value"]),
                "bvps": bvps,
                "pb": pb,
                "equity_observation_id": equity["observation_id"],
                "equity_evidence_ref": equity["evidence_ref"],
            }
        )
    pb_values = [row["pb"] for row in rows]
    fy2025_bvps = rows[-1]["bvps"]
    return {
        "rows": rows,
        "p25": percentile_linear(pb_values, 0.25),
        "p50": percentile_linear(pb_values, 0.50),
        "p75": percentile_linear(pb_values, 0.75),
        "current_pb": current_price / fy2025_bvps,
    }


def dart_observation(
    row: dict,
    *,
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


def price_observation(
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
            "https://api.finance.naver.com/siseJson.naver"
            f"#sha256={price_hash}&date={row['date']}"
        ),
        source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
        observed_at=f"{row['date']}T15:30:00+09:00",
    )


def build_thesis(
    *,
    observations: list[dict],
    price_rows: list[dict],
    price_hash: str,
    case001: dict,
    cash_history: dict[int, dict],
    ttm_cf: dict,
    ttm_profit: dict,
    shares: dict,
    pb: dict,
    dcf: object,
    robust_economics: object,
    counter: object,
) -> object:
    nodes: list[Observation] = []

    for year in (2022, 2023, 2024, 2025):
        cf = cash_history[year]
        nodes.extend(
            (
                dart_observation(
                    cf["source_rows"]["cfo"],
                    observation_id=f"OBS-CFO-{year}",
                    label=f"FY{year} operating cash flow",
                ),
                dart_observation(
                    cf["source_rows"]["ppe_capex"],
                    observation_id=f"OBS-PPE-CAPEX-{year}",
                    label=f"FY{year} PP&E purchases",
                ),
                dart_observation(
                    cf["source_rows"]["intangible_capex"],
                    observation_id=f"OBS-INT-CAPEX-{year}",
                    label=f"FY{year} intangible purchases",
                ),
                dart_observation(
                    select_unique(
                        observations,
                        fiscal_period_end=f"{year}-12-31",
                        metric_key=OWNER_PROFIT_PERIOD_KEY,
                    ),
                    observation_id=f"OBS-OWNER-PROFIT-{year}",
                    label=f"FY{year} profit attributable to owners",
                ),
                dart_observation(
                    parent_equity(
                        observations,
                        f"{year}-12-31",
                    ),
                    observation_id=f"OBS-PARENT-EQUITY-{year}",
                    label=f"FY{year} parent equity",
                ),
            )
        )
        pe_row = next(
            row for row in case001["historical_pe"]["rows"]
            if row["year"] == year
        )
        nodes.append(
            price_observation(
                {
                    "date": pe_row["price_date"],
                    "close": pe_row["year_end_close"],
                },
                observation_id=f"OBS-PRICE-YE-{year}",
                label=f"{year} year-end close",
                price_hash=price_hash,
            )
        )

    for prefix, period, source in (
        ("2025-H1", "2025-06-30", ttm_cf["h1_2025"]),
        ("2026-H1", "2026-06-30", ttm_cf["h1_2026"]),
    ):
        nodes.extend(
            (
                dart_observation(
                    source["source_rows"]["cfo"],
                    observation_id=f"OBS-CFO-{prefix}",
                    label=f"{prefix} operating cash flow",
                ),
                dart_observation(
                    source["source_rows"]["ppe_capex"],
                    observation_id=f"OBS-PPE-CAPEX-{prefix}",
                    label=f"{prefix} PP&E purchases",
                ),
                dart_observation(
                    source["source_rows"]["intangible_capex"],
                    observation_id=f"OBS-INT-CAPEX-{prefix}",
                    label=f"{prefix} intangible purchases",
                ),
                dart_observation(
                    owner_profit(
                        observations,
                        period,
                        ytd=True,
                    ),
                    observation_id=f"OBS-OWNER-PROFIT-{prefix}",
                    label=f"{prefix} YTD profit attributable to owners",
                ),
            )
        )

    nodes.extend(
        (
            dart_observation(
                select_unique(
                    observations,
                    fiscal_period_end="2025-12-31",
                    metric_key=BASIC_EPS_PERIOD_KEY,
                ),
                observation_id="OBS-EPS-FY2025",
                label="FY2025 basic EPS",
            ),
            price_observation(
                last_close_on_or_before(
                    price_rows,
                    "2026-10-05",
                    same_calendar_year=True,
                ),
                observation_id="OBS-PRICE-CASE",
                label="Case-date close",
                price_hash=price_hash,
            ),
        )
    )

    assumptions = (
        Assumption(
            assumption_id="ASM-DCF-FROZEN",
            statement=(
                "The preregistered five-year Bear/Base/Bull cash-flow "
                "growth, discount-rate, and terminal-growth assumptions "
                "are used unchanged."
            ),
            rationale="QT-CASE-002 preregistered DCF assumptions.",
            provenance_refs=("QT-CASE-002_PRE_REGISTRATION",),
        ),
        Assumption(
            assumption_id="ASM-CASE001-PE-REUSE",
            statement=(
                "QT-CASE-001 P/E scenario fair values are reused unchanged "
                "as the second valuation method."
            ),
            rationale=(
                "Cross-method robustness requires an immutable first method."
            ),
            provenance_refs=(
                "research/experiments/QT-CASE-001_RESULT.json",
            ),
        ),
    )

    inference_rows: list[Inference] = []
    for year in (2022, 2023, 2024, 2025):
        inference_rows.append(
            Inference(
                inference_id=f"INF-CASH-CONVERSION-{year}",
                statement=(
                    f"FY{year} owner-cash-flow proxy="
                    f"{cash_history[year]['owner_cash_flow_proxy']:.0f} KRW; "
                    f"cash conversion="
                    f"{cash_history[year]['cash_conversion_ratio']:.6f}."
                ),
                input_refs=(
                    f"OBS-CFO-{year}",
                    f"OBS-PPE-CAPEX-{year}",
                    f"OBS-INT-CAPEX-{year}",
                    f"OBS-OWNER-PROFIT-{year}",
                ),
            )
        )

    inference_rows.extend(
        (
            Inference(
                inference_id="INF-TTM-CASH-FLOW",
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
                inference_id="INF-TTM-CASH-CONVERSION",
                statement=(
                    "TTM cash conversion="
                    f"{counter.metrics['ttm_cash_conversion']:.6f}."
                ),
                input_refs=(
                    "INF-TTM-CASH-FLOW",
                    "OBS-OWNER-PROFIT-2025",
                    "OBS-OWNER-PROFIT-2025-H1",
                    "OBS-OWNER-PROFIT-2026-H1",
                ),
            ),
            Inference(
                inference_id="INF-IMPLIED-SHARES",
                statement=(
                    "FY2025 accounting-derived implied basic shares="
                    f"{shares['implied_basic_shares']:.6f}."
                ),
                input_refs=(
                    "OBS-OWNER-PROFIT-2025",
                    "OBS-EPS-FY2025",
                ),
            ),
            Inference(
                inference_id="INF-DCF",
                statement=(
                    "Pre-registered cash-flow DCF weighted fair value="
                    f"{dcf.metrics['weighted_fair_value']:.6f} KRW; "
                    f"expected return={dcf.metrics['expected_return_pct']:.6f}%."
                ),
                input_refs=(
                    "INF-TTM-CASH-FLOW",
                    "INF-IMPLIED-SHARES",
                    "ASM-DCF-FROZEN",
                    "OBS-PRICE-CASE",
                ),
            ),
            Inference(
                inference_id="INF-PE-REGIME",
                statement=(
                    "QT-CASE-001 historical P/E max/min dispersion ratio="
                    f"{counter.metrics['multiple_dispersion_ratio']:.6f}."
                ),
                input_refs=tuple(
                    ref
                    for year in (2022, 2023, 2024, 2025)
                    for ref in (
                        f"OBS-PRICE-YE-{year}",
                        f"OBS-OWNER-PROFIT-{year}",
                    )
                )
                + ("ASM-CASE001-PE-REUSE",),
            ),
            Inference(
                inference_id="INF-PB-SANITY",
                statement=(
                    "Current P/B="
                    f"{pb['current_pb']:.6f}; historical P75="
                    f"{pb['p75']:.6f}."
                ),
                input_refs=(
                    "OBS-PARENT-EQUITY-2022",
                    "OBS-PARENT-EQUITY-2023",
                    "OBS-PARENT-EQUITY-2024",
                    "OBS-PARENT-EQUITY-2025",
                    "OBS-PRICE-YE-2022",
                    "OBS-PRICE-YE-2023",
                    "OBS-PRICE-YE-2024",
                    "OBS-PRICE-YE-2025",
                    "OBS-PRICE-CASE",
                    "INF-IMPLIED-SHARES",
                ),
            ),
            Inference(
                inference_id="INF-ROBUST-VALUATION",
                statement=(
                    "Lower-of-two cross-method weighted fair value="
                    f"{robust_economics.metrics['weighted_fair_value']:.6f} "
                    "KRW; expected return="
                    f"{robust_economics.metrics['expected_return_pct']:.6f}%; "
                    "hurdle="
                    + (
                        "CLEARED"
                        if robust_economics.metrics[
                            "expected_return_hurdle_met"
                        ]
                        else "NOT_CLEARED"
                    )
                    + "."
                ),
                input_refs=(
                    "INF-DCF",
                    "INF-PE-REGIME",
                    "ASM-CASE001-PE-REUSE",
                    "OBS-PRICE-CASE",
                ),
            ),
        )
    )

    robust_cleared = robust_economics.metrics[
        "expected_return_hurdle_met"
    ]
    thesis_statement = (
        "The conservative lower-of-two P/E and cash-flow DCF valuation "
        "clears the frozen 15% required-return hurdle."
        if robust_cleared
        else
        "The conservative lower-of-two P/E and cash-flow DCF valuation "
        "does not clear the frozen 15% required-return hurdle."
    )

    counter_basis = [
        "INF-PE-REGIME",
        "INF-TTM-CASH-CONVERSION",
        "INF-PB-SANITY",
    ]
    counter_basis.extend(
        f"INF-CASH-CONVERSION-{year}"
        for year in (2022, 2023, 2024, 2025)
    )

    return compile_thesis_contract(
        ThesisContractInput(
            case_id=CASE_ID,
            as_of=CASE_AS_OF,
            observations=tuple(nodes),
            assumptions=assumptions,
            inferences=tuple(inference_rows),
            thesis_claims=(
                ThesisClaim(
                    thesis_id="THESIS-QT-CASE-002",
                    statement=thesis_statement,
                    support_refs=("INF-ROBUST-VALUATION",),
                ),
            ),
            counter_claims=(
                CounterClaim(
                    counter_id="COUNTER-CASH-FLOW-CYCLE",
                    thesis_id="THESIS-QT-CASE-002",
                    statement=(
                        "The P/E upside may not survive cash-flow valuation "
                        "because semiconductor earnings, capital intensity, "
                        "cash conversion, and valuation regimes are cyclical."
                    ),
                    basis_refs=tuple(counter_basis),
                ),
            ),
            falsification_conditions=(
                FalsificationCondition(
                    condition_id="FALSIFY-TTM-OWNER-CF-80",
                    thesis_id="THESIS-QT-CASE-002",
                    statement=(
                        "Reconstructed TTM owner-cash-flow proxy falls below "
                        "80% of the frozen QT-CASE-002 level "
                        f"({ttm_cf['ttm_owner_cash_flow_proxy']:.0f} KRW)."
                    ),
                    observable="ttm_owner_cash_flow_proxy",
                    evaluation_horizon=(
                        "next_two_reported_quarters_or_365_days_whichever_first"
                    ),
                ),
                FalsificationCondition(
                    condition_id="FALSIFY-ROBUST-FAIR-VALUE-BELOW-PRICE",
                    thesis_id="THESIS-QT-CASE-002",
                    statement=(
                        "The same lower-of-two cross-method methodology later "
                        "produces robust fair value below the frozen Case price."
                    ),
                    observable="robust_cross_method_fair_value",
                    evaluation_horizon="365_days",
                ),
            ),
        )
    )


def render_report(result: dict) -> str:
    dcf = result["cash_flow_dcf"]
    robust = result["robust_investment_case_economics"]
    counter = result["counter_research"]
    portfolio = result["portfolio_sandbox"]
    risk = result["risk_sandbox"]

    lines = [
        "# QT-CASE-002 Result — Samsung Cash-Flow & Cross-Method Robustness",
        "",
        "Status: **COMPLETED / RESEARCH-PAPER ONLY / NO TRADE AUTHORITY**",
        "",
        "## Frozen Case",
        "",
        f"- Asset: {result['case']['asset_id']}",
        f"- As-of: {result['case']['as_of']}",
        f"- Market close: {result['case']['current_price']:,.0f} KRW",
        "",
        "## Cash-flow reconstruction",
        "",
        f"- FY2025 owner-cash-flow proxy: "
        f"{result['cash_flow']['fy2025_owner_cash_flow_proxy']/1e12:,.2f}T KRW",
        f"- 2025-H1 owner-cash-flow proxy: "
        f"{result['cash_flow']['h1_2025_owner_cash_flow_proxy']/1e12:,.2f}T KRW",
        f"- 2026-H1 owner-cash-flow proxy: "
        f"{result['cash_flow']['h1_2026_owner_cash_flow_proxy']/1e12:,.2f}T KRW",
        f"- TTM owner-cash-flow proxy: "
        f"**{result['cash_flow']['ttm_owner_cash_flow_proxy']/1e12:,.2f}T KRW**",
        f"- Implied basic shares: "
        f"{result['cash_flow']['implied_basic_shares']/1e9:,.3f}B",
        f"- TTM owner cash flow/share: "
        f"**{result['cash_flow']['ttm_owner_cash_flow_per_share']:,.0f} KRW**",
        "",
        "## Cash-flow DCF",
        "",
    ]
    for row in dcf["scenarios"]:
        lines.append(
            f"- {row['label']}: **{row['fair_value']:,.0f} KRW** "
            f"(return {row['scenario_return_pct']:.2f}%, "
            f"p={row['probability']:.0%})"
        )
    lines.extend(
        [
            "",
            f"- DCF weighted fair value: "
            f"**{dcf['metrics']['weighted_fair_value']:,.0f} KRW**",
            f"- DCF expected return: "
            f"**{dcf['metrics']['expected_return_pct']:.2f}%**",
            "",
            "## Cross-method robustness",
            "",
            f"- QT-CASE-001 P/E weighted fair value: "
            f"{result['cross_method']['pe_weighted_fair_value']:,.0f} KRW",
            f"- DCF weighted fair value: "
            f"{result['cross_method']['dcf_weighted_fair_value']:,.0f} KRW",
            f"- Classification: "
            f"**{result['cross_method']['classification']}**",
            f"- Lower-of-two weighted fair value: "
            f"**{robust['metrics']['weighted_fair_value']:,.0f} KRW**",
            f"- Robust expected return: "
            f"**{robust['metrics']['expected_return_pct']:.2f}%**",
            f"- 15% hurdle: "
            f"**{'CLEARED' if robust['metrics']['expected_return_hurdle_met'] else 'NOT CLEARED'}**",
            "",
            "## Deterministic Counter-Research",
            "",
            f"- Status: **{counter['status']}**",
            f"- Flags: "
            f"{', '.join(counter['flags']) if counter['flags'] else 'none'}",
            f"- P/E max/min dispersion: "
            f"{counter['metrics']['multiple_dispersion_ratio']:.2f}x",
            f"- Median annual cash conversion: "
            f"{counter['metrics']['median_annual_cash_conversion']:.2%}",
            f"- TTM cash conversion: "
            f"{counter['metrics']['ttm_cash_conversion']:.2%}",
            f"- Current P/B: {counter['metrics']['current_pb']:.2f}x",
            f"- Historical P/B P75: "
            f"{counter['metrics']['historical_pb_p75']:.2f}x",
            "",
            "## Portfolio/Risk sandbox",
            "",
            f"- Portfolio: **{portfolio['status']}**",
            f"- Portfolio reasons: {', '.join(portfolio['reasons'])}",
            f"- Capital upper bound: "
            f"{portfolio['capital_headroom']['deterministic_upper_bound_pct']:.2f}% "
            "(not target weight)",
        ]
    )
    if risk is None:
        lines.append("- Risk: not invoked because Portfolio was not eligible.")
    else:
        lines.extend(
            [
                f"- Risk: **{risk['status']}**",
                f"- Risk reasons: {', '.join(risk['reasons'])}",
                f"- Risk ceiling: "
                f"{risk['limits']['risk_position_ceiling_pct']:.2f}% "
                "(not target weight)",
            ]
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Real Open DART data: yes",
            "- Model calls: 0",
            "- Sell-side target prices: none",
            "- Private Client portfolio: no; sandbox only",
            "- Founder/Committee Decision: none",
            "- PAPER/live execution: none",
            "",
            "QT-CASE-002 is a robustness challenge to a known QT-CASE-001 "
            "result. It is not independent proof of alpha.",
            "",
        ]
    )
    return "\n".join(lines)


def run() -> dict:
    case001 = load_case001()

    provider = DartFundamentalObservationProvider(
        config=DartProviderConfig(
            report_codes=("11011", "11012"),
        ),
        corp_code_overrides={"005930": "00126380"},
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

    price_rows, price_meta = fetch_naver_prices()
    current_price_row = last_close_on_or_before(
        price_rows,
        "2026-10-05",
        same_calendar_year=True,
    )
    current_price = float(current_price_row["close"])
    if current_price != float(case001["case"]["current_price"]):
        raise GoldenRunError(
            "QT-CASE-002 frozen Case price must match QT-CASE-001"
        )
    if current_price_row["date"] != case001["case"]["price_date"]:
        raise GoldenRunError(
            "QT-CASE-002 frozen price date must match QT-CASE-001"
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

    dcf_artifact = evaluate_cash_flow_dcf(
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
                    scenario_id="BEAR",
                    label="Bear",
                    probability=0.25,
                    starting_cash_flow_factor=0.80,
                    explicit_growth_pct=0.0,
                    terminal_growth_pct=0.0,
                    discount_rate_pct=10.0,
                    explicit_years=5,
                    assumption_refs=(
                        "QT-CASE-002_PRE_REGISTRATION",
                    ),
                ),
                CashFlowDCFScenario(
                    scenario_id="BASE",
                    label="Base",
                    probability=0.50,
                    starting_cash_flow_factor=1.00,
                    explicit_growth_pct=3.0,
                    terminal_growth_pct=2.0,
                    discount_rate_pct=10.0,
                    explicit_years=5,
                    assumption_refs=(
                        "QT-CASE-002_PRE_REGISTRATION",
                    ),
                ),
                CashFlowDCFScenario(
                    scenario_id="BULL",
                    label="Bull",
                    probability=0.25,
                    starting_cash_flow_factor=1.20,
                    explicit_growth_pct=5.0,
                    terminal_growth_pct=3.0,
                    discount_rate_pct=10.0,
                    explicit_years=5,
                    assumption_refs=(
                        "QT-CASE-002_PRE_REGISTRATION",
                    ),
                ),
            ),
        )
    )

    pe_inputs = case001["scenario_inputs"]
    pe_scenario_values = {
        key.upper(): float(value["fair_value"])
        for key, value in pe_inputs.items()
    }
    dcf_scenario_values = {
        row["scenario_id"]: float(row["fair_value"])
        for row in dcf_artifact.scenarios
    }
    robust_scenarios = []
    robust_detail = {}
    for scenario_id, probability in (
        ("BEAR", 0.25),
        ("BASE", 0.50),
        ("BULL", 0.25),
    ):
        pe_value = pe_scenario_values[scenario_id]
        dcf_value = dcf_scenario_values[scenario_id]
        robust_value = min(pe_value, dcf_value)
        robust_detail[scenario_id] = {
            "pe_fair_value": pe_value,
            "dcf_fair_value": dcf_value,
            "robust_lower_of_two_fair_value": robust_value,
            "binding_method": (
                "PE" if pe_value <= dcf_value else "DCF"
            ),
        }
        robust_scenarios.append(
            ScenarioAssumption(
                scenario_id=scenario_id,
                label=scenario_id.title(),
                probability=probability,
                fair_value=robust_value,
                thesis_note=(
                    "QT-CASE-002 preregistered lower-of-two cross-method "
                    "scenario value."
                ),
                evidence_refs=(),
                assumption_refs=(
                    "QT-CASE-001_RESULT",
                    "QT-CASE-002_PRE_REGISTRATION",
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
            scenarios=tuple(robust_scenarios),
            consensus=None,
        )
    )

    pe_expected = float(
        case001["investment_case_economics"]["metrics"][
            "expected_return_pct"
        ]
    )
    dcf_expected = float(
        dcf_artifact.metrics["expected_return_pct"]
    )
    pe_clears = pe_expected >= REQUIRED_RETURN_PCT
    dcf_clears = dcf_expected >= REQUIRED_RETURN_PCT
    if pe_clears and dcf_clears:
        classification = "CROSS_METHOD_CONFIRMED"
    elif pe_clears or dcf_clears:
        classification = "CROSS_METHOD_MIXED"
    else:
        classification = "CROSS_METHOD_REJECTED"

    pb = historical_pb(
        observations,
        price_rows,
        shares["implied_basic_shares"],
        current_price,
    )
    annual_counter_rows = tuple(
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
    )
    pe_values = tuple(
        float(row["pe"])
        for row in case001["historical_pe"]["rows"]
    )
    counter = evaluate_fundamental_counter_research(
        FundamentalCounterResearchInput(
            case_id=CASE_ID,
            annual_cash_conversion=annual_counter_rows,
            ttm_owner_cash_flow_proxy=float(
                ttm_cf["ttm_owner_cash_flow_proxy"]
            ),
            ttm_profit_attributable_to_owners=float(
                ttm_profit["ttm_profit_attributable_to_owners"]
            ),
            historical_pe_values=pe_values,
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
        price_rows=price_rows,
        price_hash=price_meta["sha256"],
        case001=case001,
        cash_history=cash_history,
        ttm_cf=ttm_cf,
        ttm_profit=ttm_profit,
        shares=shares,
        pb=pb,
        dcf=dcf_artifact,
        robust_economics=robust_economics,
        counter=counter,
    )

    portfolio = assess_portfolio_opportunity(
        PortfolioOpportunityInput(
            case_economics=robust_economics,
            alternatives=(
                CapitalAlternative(
                    alternative_id="SANDBOX-CASH",
                    alternative_type="CASH",
                    expected_return_pct=3.0,
                    downside_pct=0.0,
                    basis_refs=(
                        "QT-CASE-002_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
                CapitalAlternative(
                    alternative_id="SANDBOX-CORE",
                    alternative_type="CORE_BENCHMARK",
                    expected_return_pct=8.0,
                    downside_pct=None,
                    basis_refs=(
                        "QT-CASE-002_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
            ),
            constraints=PortfolioConstraintSnapshot(
                snapshot_id="QT-CASE-002-SANDBOX-PORTFOLIO",
                as_of="2026-10-05T23:00:00+09:00",
                mandate_allows_new_exposure=True,
                mandate_ref="QT-CASE-002_PRE_REGISTRATION:SANDBOX",
                current_asset_weight_pct=0.0,
                max_asset_weight_pct=10.0,
                current_liquidity_pct=20.0,
                minimum_liquidity_reserve_pct=10.0,
                available_downside_budget_pct=2.0,
                constraint_refs=(
                    "QT-CASE-002_PRE_REGISTRATION:SANDBOX",
                ),
            ),
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
                        "QT-CASE-002:ROBUST-BEAR-SCENARIO",
                    ),
                ),
                policy=RiskPolicySnapshot(
                    policy_id="QT-CASE-002-SANDBOX-RISK",
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
                        "QT-CASE-002_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
                state=RiskStateSnapshot(
                    snapshot_id="QT-CASE-002-SANDBOX-RISK-STATE",
                    as_of="2026-10-05T22:30:00+09:00",
                    current_asset_weight_pct=0.0,
                    current_portfolio_drawdown_pct=-5.0,
                    state_refs=(
                        "QT-CASE-002_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
            )
        )

    selected_ids: set[str] = set()
    for year in (2022, 2023, 2024, 2025):
        selected_ids.update(
            cash_history[year]["source_observation_ids"]
        )
        selected_ids.add(cash_history[year]["profit_observation_id"])
        selected_ids.add(pb["rows"][year - 2022]["equity_observation_id"])
    for block in (
        ttm_cf["h1_2025"],
        ttm_cf["h1_2026"],
    ):
        selected_ids.update(block["source_observation_ids"])
    for row in ttm_profit["source_rows"].values():
        selected_ids.add(row["observation_id"])
    selected_ids.add(shares["profit_observation_id"])
    selected_ids.add(shares["eps_observation_id"])

    selected_evidence = [
        {
            "observation_id": row["observation_id"],
            "metric_key": row["metric_key"],
            "fiscal_period_end": row["fiscal_period_end"],
            "value": row["value"],
            "unit": row["unit"],
            "published_at": row["published_at"],
            "source_document_id": row["source_document_id"],
            "evidence_ref": row["evidence_ref"],
            "restated": row.get("restated"),
        }
        for row in observations
        if row["observation_id"] in selected_ids
    ]

    compact = {
        "schema": "quantrade_qt_case_002_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "mode": "RESEARCH_PAPER_ONLY",
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
            "selected_evidence": selected_evidence,
            "price_source": price_meta,
            "qt_case_001_result_sha256": canonical_hash(case001),
            "price_after_case_cutoff_used": False,
        },
        "cash_flow": {
            "annual_history": {
                str(year): {
                    key: value
                    for key, value in cash_history[year].items()
                    if key != "source_rows"
                }
                for year in (2022, 2023, 2024, 2025)
            },
            "fy2025_owner_cash_flow_proxy": ttm_cf["fy2025"][
                "owner_cash_flow_proxy"
            ],
            "h1_2025_owner_cash_flow_proxy": ttm_cf["h1_2025"][
                "owner_cash_flow_proxy"
            ],
            "h1_2026_owner_cash_flow_proxy": ttm_cf["h1_2026"][
                "owner_cash_flow_proxy"
            ],
            "ttm_owner_cash_flow_proxy": ttm_cf[
                "ttm_owner_cash_flow_proxy"
            ],
            "ttm_profit_attributable_to_owners": ttm_profit[
                "ttm_profit_attributable_to_owners"
            ],
            "ttm_cash_conversion": counter.metrics[
                "ttm_cash_conversion"
            ],
            "implied_basic_shares": shares[
                "implied_basic_shares"
            ],
            "implied_shares_is_accounting_approximation": True,
            "ttm_owner_cash_flow_per_share": cash_flow_per_share,
        },
        "cash_flow_dcf": asdict(dcf_artifact),
        "cross_method": {
            "pe_weighted_fair_value": case001[
                "investment_case_economics"
            ]["metrics"]["weighted_fair_value"],
            "pe_expected_return_pct": pe_expected,
            "dcf_weighted_fair_value": dcf_artifact.metrics[
                "weighted_fair_value"
            ],
            "dcf_expected_return_pct": dcf_expected,
            "classification": classification,
            "scenario_comparison": robust_detail,
            "lower_of_two_rule": True,
        },
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
            "known_case_robustness_challenge": True,
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
        "full_price_rows": price_rows,
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(
            compact,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
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
                "current_price": result["case"]["current_price"],
                "ttm_owner_cash_flow_proxy": result["cash_flow"][
                    "ttm_owner_cash_flow_proxy"
                ],
                "ttm_owner_cash_flow_per_share": result["cash_flow"][
                    "ttm_owner_cash_flow_per_share"
                ],
                "dcf_weighted_fair_value": result["cash_flow_dcf"][
                    "metrics"
                ]["weighted_fair_value"],
                "dcf_expected_return_pct": result["cash_flow_dcf"][
                    "metrics"
                ]["expected_return_pct"],
                "cross_method_classification": result[
                    "cross_method"
                ]["classification"],
                "robust_weighted_fair_value": result[
                    "robust_investment_case_economics"
                ]["metrics"]["weighted_fair_value"],
                "robust_expected_return_pct": result[
                    "robust_investment_case_economics"
                ]["metrics"]["expected_return_pct"],
                "counter_flags": result["counter_research"][
                    "flags"
                ],
                "portfolio_status": result["portfolio_sandbox"][
                    "status"
                ],
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
