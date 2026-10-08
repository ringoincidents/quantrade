"""QT-CASE-001 — first real Investment Office Golden Run.

Frozen methodology:
research/experiments/QT-CASE-001_PRE_REGISTRATION.md

This runner uses:
- live Open DART point-in-time fundamentals;
- Naver historical closes bounded by the frozen Case date;
- deterministic P/E scenario valuation;
- structured Thesis / CounterClaim / Falsification;
- synthetic Portfolio/Risk context solely to exercise program routing.

It makes zero model calls and has no broker / DecisionPlan / execution path.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from quantrade.capabilities.dart_fundamental_provider import (
    DartFundamentalObservationProvider,
    DartProviderConfig,
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


EXPERIMENT_ID = "QT-CASE-001"
PREREGISTRATION_COMMIT = "96af7467cb052b4cc90828135276ba9f6b68f7df"
CASE_ID = "QT-CASE-001:KRX:005930"
ASSET_ID = "KRX:005930"
SYMBOL = "005930"
CASE_AS_OF = "2026-10-05T23:59:59+09:00"
FUNDAMENTAL_FROM = "2022-01-01"
FUNDAMENTAL_TO = "2026-06-30"
PRICE_START = "2022-01-01"
PRICE_END = "2026-10-05"
VALUATION_HORIZON_DAYS = 365
REQUIRED_RETURN_PCT = 15.0

EPS_PERIOD_KEY = (
    "DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:"
    "IS:CURRENT_PERIOD"
)
EPS_YTD_KEY = (
    "DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:"
    "IS:CURRENT_YTD"
)
REVENUE_PERIOD_KEY = "REVENUE:IS:CURRENT_PERIOD"
REVENUE_YTD_KEY = "REVENUE:IS:CURRENT_YTD"
OPERATING_INCOME_PERIOD_KEY = "OPERATING_INCOME:IS:CURRENT_PERIOD"
OPERATING_INCOME_YTD_KEY = "OPERATING_INCOME:IS:CURRENT_YTD"

DART_METRIC_KEYS = (
    EPS_PERIOD_KEY,
    EPS_YTD_KEY,
    REVENUE_PERIOD_KEY,
    REVENUE_YTD_KEY,
    OPERATING_INCOME_PERIOD_KEY,
    OPERATING_INCOME_YTD_KEY,
)

NAVER_ENDPOINT = "https://api.finance.naver.com/siseJson.naver"
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; quantrade-investment-case/1.0)"
}

RESULT_PATH = Path("research/experiments/QT-CASE-001_RESULT.json")
REPORT_PATH = Path("research/experiments/QT-CASE-001_RESULT_REPORT.md")
FULL_ARTIFACT_PATH = Path("/tmp/QT-CASE-001_FULL_ARTIFACT.json")


class GoldenRunError(RuntimeError):
    """Raised when a preregistered QT-CASE-001 requirement is not met."""


def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def percentile_linear(values: list[float], percentile: float) -> float:
    if not values:
        raise GoldenRunError("percentile requires at least one value")
    if percentile < 0.0 or percentile > 1.0:
        raise GoldenRunError("percentile must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    if any(not math.isfinite(value) for value in ordered):
        raise GoldenRunError("percentile values must be finite")
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * percentile
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def fetch_naver_prices() -> tuple[list[dict], dict]:
    params = {
        "symbol": SYMBOL,
        "requestType": 1,
        "startTime": PRICE_START.replace("-", ""),
        "endTime": PRICE_END.replace("-", ""),
        "timeframe": "day",
    }
    url = f"{NAVER_ENDPOINT}?{urlencode(params)}"
    request = Request(url, headers=HTTP_HEADERS)
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
    dates = [row["date"] for row in parsed]
    if dates != sorted(dates):
        raise GoldenRunError("Naver price dates are not increasing")
    if len(dates) != len(set(dates)):
        raise GoldenRunError("Naver price dates contain duplicates")
    if any(row["close"] <= 0 for row in parsed):
        raise GoldenRunError("Naver dataset contains non-positive close")
    if parsed[-1]["date"] > PRICE_END:
        raise GoldenRunError("Naver dataset escaped frozen Case cutoff")
    digest = canonical_hash(parsed)
    return parsed, {
        "provider": "naver-finance-historical",
        "endpoint": NAVER_ENDPOINT,
        "params": params,
        "http_status": status,
        "row_count": len(parsed),
        "first_trading_date": parsed[0]["date"],
        "last_trading_date": parsed[-1]["date"],
        "sha256": digest,
    }


def last_close_on_or_before(
    rows: list[dict],
    date_text: str,
    *,
    same_calendar_year: bool = False,
) -> dict:
    target = datetime.fromisoformat(date_text).date()
    candidates = []
    for row in rows:
        row_date = datetime.fromisoformat(row["date"]).date()
        if row_date > target:
            continue
        if same_calendar_year and row_date.year != target.year:
            continue
        candidates.append(row)
    if not candidates:
        raise GoldenRunError(
            f"no Naver close available on/before {date_text}"
        )
    return candidates[-1]


def select_unique_fundamental(
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
            "required fundamental observation must be unique: "
            f"period={fiscal_period_end} metric={metric_key} "
            f"count={len(matches)}"
        )
    value = matches[0].get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GoldenRunError("fundamental value must be numeric")
    if not math.isfinite(float(value)):
        raise GoldenRunError("fundamental value must be finite")
    return matches[0]


def annual_eps_history(observations: list[dict]) -> dict[int, dict]:
    result = {}
    for year in (2022, 2023, 2024, 2025):
        row = select_unique_fundamental(
            observations,
            fiscal_period_end=f"{year}-12-31",
            metric_key=EPS_PERIOD_KEY,
        )
        if float(row["value"]) <= 0.0:
            raise GoldenRunError(
                f"{year} annual EPS is non-positive"
            )
        result[year] = row
    return result


def compute_ttm_eps(observations: list[dict]) -> dict:
    fy2025 = select_unique_fundamental(
        observations,
        fiscal_period_end="2025-12-31",
        metric_key=EPS_PERIOD_KEY,
    )
    h1_2025 = select_unique_fundamental(
        observations,
        fiscal_period_end="2025-06-30",
        metric_key=EPS_YTD_KEY,
    )
    h1_2026 = select_unique_fundamental(
        observations,
        fiscal_period_end="2026-06-30",
        metric_key=EPS_YTD_KEY,
    )
    values = {
        "fy2025_eps": float(fy2025["value"]),
        "h1_2025_ytd_eps": float(h1_2025["value"]),
        "h1_2026_ytd_eps": float(h1_2026["value"]),
    }
    if any(value <= 0.0 for value in values.values()):
        raise GoldenRunError(
            "TTM EPS source values must all be positive"
        )
    ttm = (
        values["fy2025_eps"]
        + values["h1_2026_ytd_eps"]
        - values["h1_2025_ytd_eps"]
    )
    if ttm <= 0.0 or not math.isfinite(ttm):
        raise GoldenRunError("calculated TTM EPS is not positive")
    return {
        **values,
        "ttm_eps": ttm,
        "source_observation_ids": (
            fy2025["observation_id"],
            h1_2025["observation_id"],
            h1_2026["observation_id"],
        ),
        "source_rows": {
            "fy2025": fy2025,
            "h1_2025": h1_2025,
            "h1_2026": h1_2026,
        },
    }


def build_historical_pe(
    observations: list[dict],
    price_rows: list[dict],
) -> dict:
    eps_rows = annual_eps_history(observations)
    rows = []
    for year in (2022, 2023, 2024, 2025):
        price = last_close_on_or_before(
            price_rows,
            f"{year}-12-31",
            same_calendar_year=True,
        )
        eps = float(eps_rows[year]["value"])
        pe = float(price["close"]) / eps
        if pe <= 0.0 or not math.isfinite(pe):
            raise GoldenRunError(
                f"{year} historical P/E is invalid"
            )
        rows.append(
            {
                "year": year,
                "price_date": price["date"],
                "year_end_close": float(price["close"]),
                "annual_eps": eps,
                "pe": pe,
                "eps_observation_id": eps_rows[year]["observation_id"],
                "eps_evidence_ref": eps_rows[year]["evidence_ref"],
            }
        )
    values = [row["pe"] for row in rows]
    return {
        "rows": rows,
        "p25": percentile_linear(values, 0.25),
        "p50": percentile_linear(values, 0.50),
        "p75": percentile_linear(values, 0.75),
        "min": min(values),
        "max": max(values),
        "median": median(values),
    }


def make_dart_observation(row: dict, observation_id: str, label: str) -> Observation:
    return Observation(
        observation_id=observation_id,
        statement=f"{label}: {row['value']} {row.get('unit') or ''}".strip(),
        source_ref=str(row["evidence_ref"]),
        source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
        observed_at=str(row["published_at"]),
    )


def make_price_observation(
    price_row: dict,
    *,
    observation_id: str,
    label: str,
    dataset_hash: str,
) -> Observation:
    return Observation(
        observation_id=observation_id,
        statement=f"{label}: {price_row['close']} KRW",
        source_ref=(
            f"{NAVER_ENDPOINT}#sha256={dataset_hash}"
            f"&date={price_row['date']}"
        ),
        source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
        observed_at=f"{price_row['date']}T15:30:00+09:00",
    )


def build_thesis_contract(
    *,
    fundamental_rows: list[dict],
    ttm: dict,
    pe_history: dict,
    current_price_row: dict,
    price_hash: str,
    economics: object,
) -> object:
    annual_rows = {
        row["year"]: select_unique_fundamental(
            fundamental_rows,
            fiscal_period_end=f"{row['year']}-12-31",
            metric_key=EPS_PERIOD_KEY,
        )
        for row in pe_history["rows"]
    }
    observations = [
        make_dart_observation(
            ttm["source_rows"]["fy2025"],
            "OBS-EPS-FY2025",
            "FY2025 basic EPS",
        ),
        make_dart_observation(
            ttm["source_rows"]["h1_2025"],
            "OBS-EPS-H1-2025",
            "2025-H1 YTD basic EPS",
        ),
        make_dart_observation(
            ttm["source_rows"]["h1_2026"],
            "OBS-EPS-H1-2026",
            "2026-H1 YTD basic EPS",
        ),
        make_price_observation(
            current_price_row,
            observation_id="OBS-PRICE-CASE",
            label="Case-date close",
            dataset_hash=price_hash,
        ),
    ]
    for year in (2022, 2023, 2024, 2025):
        if year != 2025:
            observations.append(
                make_dart_observation(
                    annual_rows[year],
                    f"OBS-EPS-FY{year}",
                    f"FY{year} basic EPS",
                )
            )
        price = next(
            item for item in pe_history["rows"]
            if item["year"] == year
        )
        observations.append(
            make_price_observation(
                {
                    "date": price["price_date"],
                    "close": price["year_end_close"],
                },
                observation_id=f"OBS-PRICE-YE-{year}",
                label=f"{year} year-end close",
                dataset_hash=price_hash,
            )
        )

    inferences = [
        Inference(
            inference_id="INF-TTM-EPS",
            statement=(
                "Frozen TTM basic EPS = "
                f"{ttm['ttm_eps']:.6f} KRW, calculated as "
                "FY2025 + 2026-H1 YTD - 2025-H1 YTD."
            ),
            input_refs=(
                "OBS-EPS-FY2025",
                "OBS-EPS-H1-2025",
                "OBS-EPS-H1-2026",
            ),
        )
    ]
    for item in pe_history["rows"]:
        year = item["year"]
        inferences.append(
            Inference(
                inference_id=f"INF-PE-{year}",
                statement=(
                    f"{year} ex-post historical P/E = "
                    f"{item['pe']:.6f}x."
                ),
                input_refs=(
                    f"OBS-PRICE-YE-{year}",
                    f"OBS-EPS-FY{year}",
                ),
            )
        )
    inferences.extend(
        (
            Inference(
                inference_id="INF-PE-DISTRIBUTION",
                statement=(
                    "Frozen historical P/E distribution: "
                    f"P25={pe_history['p25']:.6f}x, "
                    f"P50={pe_history['p50']:.6f}x, "
                    f"P75={pe_history['p75']:.6f}x."
                ),
                input_refs=tuple(
                    f"INF-PE-{year}" for year in (2022, 2023, 2024, 2025)
                ),
            ),
            Inference(
                inference_id="INF-VALUATION-RESULT",
                statement=(
                    "Pre-registered scenario valuation produced weighted "
                    f"fair value {economics.metrics['weighted_fair_value']:.6f} "
                    f"KRW and expected return "
                    f"{economics.metrics['expected_return_pct']:.6f}%. "
                    "Economic hurdle result="
                    + (
                        "HURDLE_CLEARED"
                        if economics.metrics["expected_return_hurdle_met"]
                        else "HURDLE_NOT_CLEARED"
                    )
                    + "."
                ),
                input_refs=(
                    "INF-TTM-EPS",
                    "INF-PE-DISTRIBUTION",
                    "OBS-PRICE-CASE",
                    "ASM-TTM-PERSISTENCE",
                ),
            ),
        )
    )

    thesis_statement = (
        "The pre-registered scenario economics clear the 15% expected-return "
        "hurdle at the frozen Case price."
        if economics.metrics["expected_return_hurdle_met"]
        else
        "The pre-registered scenario economics do not clear the 15% "
        "expected-return hurdle at the frozen Case price."
    )

    contract = ThesisContractInput(
        case_id=CASE_ID,
        as_of=CASE_AS_OF,
        observations=tuple(observations),
        assumptions=(
            Assumption(
                assumption_id="ASM-TTM-PERSISTENCE",
                statement=(
                    "Frozen TTM basic EPS is a reasonable central one-year "
                    "earnings anchor."
                ),
                rationale=(
                    "QT-CASE-001 preregistered simplifying valuation "
                    "assumption; not Evidence."
                ),
                provenance_refs=(
                    "QT-CASE-001_PRE_REGISTRATION",
                ),
            ),
        ),
        inferences=tuple(inferences),
        thesis_claims=(
            ThesisClaim(
                thesis_id="THESIS-QT-CASE-001",
                statement=thesis_statement,
                support_refs=("INF-VALUATION-RESULT",),
            ),
        ),
        counter_claims=(
            CounterClaim(
                counter_id="COUNTER-CYCLICALITY",
                thesis_id="THESIS-QT-CASE-001",
                statement=(
                    "Samsung earnings and market valuation multiples are "
                    "cyclical/regime-sensitive; the TTM earnings anchor and "
                    "historical P/E distribution may be unstable."
                ),
                basis_refs=(
                    "INF-TTM-EPS",
                    "INF-PE-DISTRIBUTION",
                ),
            ),
        ),
        falsification_conditions=(
            FalsificationCondition(
                condition_id="FALSIFY-TTM-EPS-80",
                thesis_id="THESIS-QT-CASE-001",
                statement=(
                    "Reconstructed TTM basic EPS falls below 80% of the "
                    f"frozen QT-CASE-001 TTM EPS ({ttm['ttm_eps']:.6f} KRW)."
                ),
                observable="reconstructed_ttm_basic_eps",
                evaluation_horizon=(
                    "next_two_reported_quarters_or_365_days_whichever_first"
                ),
            ),
        ),
    )
    return compile_thesis_contract(contract)


def run() -> dict:
    provider = DartFundamentalObservationProvider(
        config=DartProviderConfig(
            report_codes=("11011", "11012"),
        )
    )
    fundamental_result = provider.query(
        FundamentalQuery(
            asset_id=ASSET_ID,
            as_of=CASE_AS_OF,
            metric_keys=DART_METRIC_KEYS,
            fiscal_period_end_from=FUNDAMENTAL_FROM,
            fiscal_period_end_to=FUNDAMENTAL_TO,
        )
    )
    fundamental = asdict(fundamental_result)
    observations = list(fundamental["observations"])
    if not observations:
        raise GoldenRunError("Open DART returned no selected observations")

    price_rows, price_meta = fetch_naver_prices()
    current_price_row = last_close_on_or_before(
        price_rows,
        "2026-10-05",
        same_calendar_year=True,
    )
    # The preregistration freezes the final trading close on or before the
    # Case date. Korean public holidays may make the calendar Case date a
    # non-trading day, so an earlier same-year close is valid.
    if current_price_row["date"] > "2026-10-05":
        raise GoldenRunError("price observation escaped Case cutoff")

    ttm = compute_ttm_eps(observations)
    pe_history = build_historical_pe(observations, price_rows)

    scenario_inputs = {
        "bear": {
            "probability": 0.25,
            "eps_multiplier": 0.80,
            "pe": pe_history["p25"],
        },
        "base": {
            "probability": 0.50,
            "eps_multiplier": 1.00,
            "pe": pe_history["p50"],
        },
        "bull": {
            "probability": 0.25,
            "eps_multiplier": 1.20,
            "pe": pe_history["p75"],
        },
    }
    scenarios = []
    scenario_detail = {}
    for scenario_id, config in scenario_inputs.items():
        scenario_eps = ttm["ttm_eps"] * config["eps_multiplier"]
        fair_value = scenario_eps * config["pe"]
        scenario_detail[scenario_id] = {
            **config,
            "scenario_eps": scenario_eps,
            "fair_value": fair_value,
        }
        scenarios.append(
            ScenarioAssumption(
                scenario_id=scenario_id.upper(),
                label=scenario_id.title(),
                probability=float(config["probability"]),
                fair_value=float(fair_value),
                thesis_note=(
                    "QT-CASE-001 preregistered EPS/P-E scenario."
                ),
                evidence_refs=(
                    *tuple(
                        str(row["evidence_ref"])
                        for row in ttm["source_rows"].values()
                    ),
                    f"sha256:{price_meta['sha256']}",
                ),
                assumption_refs=(
                    "ASM-TTM-PERSISTENCE",
                    "QT-CASE-001_PRE_REGISTRATION",
                ),
            )
        )

    economics = evaluate_investment_case(
        InvestmentCaseInput(
            case_id=CASE_ID,
            asset_id=ASSET_ID,
            as_of=CASE_AS_OF,
            current_price=float(current_price_row["close"]),
            currency="KRW",
            valuation_horizon_days=VALUATION_HORIZON_DAYS,
            required_return_pct=REQUIRED_RETURN_PCT,
            scenarios=tuple(scenarios),
            consensus=None,
        )
    )

    thesis = build_thesis_contract(
        fundamental_rows=observations,
        ttm=ttm,
        pe_history=pe_history,
        current_price_row=current_price_row,
        price_hash=price_meta["sha256"],
        economics=economics,
    )

    portfolio = assess_portfolio_opportunity(
        PortfolioOpportunityInput(
            case_economics=economics,
            alternatives=(
                CapitalAlternative(
                    alternative_id="SANDBOX-CASH",
                    alternative_type="CASH",
                    expected_return_pct=3.0,
                    downside_pct=0.0,
                    basis_refs=(
                        "QT-CASE-001_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
                CapitalAlternative(
                    alternative_id="SANDBOX-CORE",
                    alternative_type="CORE_BENCHMARK",
                    expected_return_pct=8.0,
                    downside_pct=None,
                    basis_refs=(
                        "QT-CASE-001_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
            ),
            constraints=PortfolioConstraintSnapshot(
                snapshot_id="QT-CASE-001-SANDBOX-PORTFOLIO",
                as_of="2026-10-05T23:00:00+09:00",
                mandate_allows_new_exposure=True,
                mandate_ref="QT-CASE-001_PRE_REGISTRATION:SANDBOX",
                current_asset_weight_pct=0.0,
                max_asset_weight_pct=10.0,
                current_liquidity_pct=20.0,
                minimum_liquidity_reserve_pct=10.0,
                available_downside_budget_pct=2.0,
                constraint_refs=(
                    "QT-CASE-001_PRE_REGISTRATION:SANDBOX",
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
                        economics.metrics[
                            "lowest_scenario_return_pct"
                        ]
                    ),
                    max_abs_correlation_to_portfolio=None,
                    estimated_exit_days=None,
                    uses_leverage=False,
                    risk_refs=(
                        "QT-CASE-001:BEAR_SCENARIO",
                    ),
                ),
                policy=RiskPolicySnapshot(
                    policy_id="QT-CASE-001-SANDBOX-RISK",
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
                        "QT-CASE-001_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
                state=RiskStateSnapshot(
                    snapshot_id="QT-CASE-001-SANDBOX-RISK-STATE",
                    as_of="2026-10-05T22:30:00+09:00",
                    current_asset_weight_pct=0.0,
                    current_portfolio_drawdown_pct=-5.0,
                    state_refs=(
                        "QT-CASE-001_PRE_REGISTRATION:SANDBOX",
                    ),
                ),
            )
        )

    investment_interpretation = (
        "HURDLE_CLEARED"
        if economics.metrics["expected_return_hurdle_met"]
        else "HURDLE_NOT_CLEARED"
    )

    selected_evidence = []
    selected_ids = set(ttm["source_observation_ids"])
    for year_row in pe_history["rows"]:
        selected_ids.add(year_row["eps_observation_id"])
    for row in observations:
        if row["observation_id"] in selected_ids:
            selected_evidence.append(
                {
                    "observation_id": row["observation_id"],
                    "metric_key": row["metric_key"],
                    "fiscal_period_end": row["fiscal_period_end"],
                    "value": row["value"],
                    "unit": row["unit"],
                    "published_at": row["published_at"],
                    "source_document_id": row["source_document_id"],
                    "evidence_ref": row["evidence_ref"],
                    "revision_id": row.get("revision_id"),
                    "restated": row.get("restated"),
                }
            )

    compact = {
        "schema": "quantrade_qt_case_001_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "mode": "RESEARCH_PAPER_ONLY",
        "case": {
            "case_id": CASE_ID,
            "asset_id": ASSET_ID,
            "as_of": CASE_AS_OF,
            "price_date": current_price_row["date"],
            "current_price": current_price_row["close"],
            "currency": "KRW",
            "valuation_horizon_days": VALUATION_HORIZON_DAYS,
            "required_return_pct": REQUIRED_RETURN_PCT,
        },
        "source_integrity": {
            "open_dart_provider": fundamental["provider"],
            "fundamental_observation_count": len(observations),
            "fundamental_payload_sha256": canonical_hash(fundamental),
            "selected_evidence": selected_evidence,
            "price_source": price_meta,
            "price_after_case_cutoff_used": False,
        },
        "earnings": {
            "ttm_formula": (
                "FY2025 EPS + 2026-H1 YTD EPS - 2025-H1 YTD EPS"
            ),
            "fy2025_eps": ttm["fy2025_eps"],
            "h1_2025_ytd_eps": ttm["h1_2025_ytd_eps"],
            "h1_2026_ytd_eps": ttm["h1_2026_ytd_eps"],
            "ttm_eps": ttm["ttm_eps"],
        },
        "historical_pe": {
            "rows": pe_history["rows"],
            "p25": round(pe_history["p25"], 8),
            "p50": round(pe_history["p50"], 8),
            "p75": round(pe_history["p75"], 8),
            "outlier_removal_applied": False,
        },
        "scenario_inputs": scenario_detail,
        "investment_case_economics": asdict(economics),
        "thesis_contract": asdict(thesis),
        "portfolio_sandbox": asdict(portfolio),
        "risk_sandbox": None if risk is None else asdict(risk),
        "investment_interpretation": investment_interpretation,
        "operational_result": {
            "success": True,
            "real_company_data": True,
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
    FULL_ARTIFACT_PATH.write_text(
        json.dumps(
            full_artifact,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    report = render_report(compact)
    REPORT_PATH.write_text(report, encoding="utf-8")
    return compact


def render_report(result: dict) -> str:
    econ = result["investment_case_economics"]["metrics"]
    portfolio = result["portfolio_sandbox"]
    risk = result["risk_sandbox"]
    pe = result["historical_pe"]
    earnings = result["earnings"]
    scenarios = result["scenario_inputs"]

    lines = [
        "# QT-CASE-001 Result — Samsung Electronics Real Investment Case",
        "",
        "Status: **COMPLETED / RESEARCH-PAPER ONLY / NO TRADE AUTHORITY**",
        "",
        "## Frozen Case",
        "",
        f"- Asset: {result['case']['asset_id']}",
        f"- As-of: {result['case']['as_of']}",
        f"- Market close: {result['case']['current_price']:,.0f} KRW",
        f"- Required return hurdle: {result['case']['required_return_pct']:.2f}%",
        "",
        "## Point-in-time earnings",
        "",
        f"- FY2025 EPS: {earnings['fy2025_eps']:,.2f} KRW",
        f"- 2025-H1 YTD EPS: {earnings['h1_2025_ytd_eps']:,.2f} KRW",
        f"- 2026-H1 YTD EPS: {earnings['h1_2026_ytd_eps']:,.2f} KRW",
        f"- Frozen TTM EPS: **{earnings['ttm_eps']:,.2f} KRW**",
        "",
        "## Historical P/E anchors",
        "",
    ]
    for row in pe["rows"]:
        lines.append(
            f"- {row['year']}: close {row['year_end_close']:,.0f} / "
            f"EPS {row['annual_eps']:,.2f} = **{row['pe']:.2f}x**"
        )
    lines.extend(
        [
            "",
            f"- P25: {pe['p25']:.2f}x",
            f"- P50: {pe['p50']:.2f}x",
            f"- P75: {pe['p75']:.2f}x",
            "",
            "## Frozen scenarios",
            "",
        ]
    )
    for name in ("bear", "base", "bull"):
        row = scenarios[name]
        lines.append(
            f"- {name.title()}: EPS {row['scenario_eps']:,.2f}, "
            f"P/E {row['pe']:.2f}x → fair value "
            f"**{row['fair_value']:,.0f} KRW** "
            f"(p={row['probability']:.0%})"
        )
    lines.extend(
        [
            "",
            "## Economics",
            "",
            f"- Weighted fair value: **{econ['weighted_fair_value']:,.0f} KRW**",
            f"- Expected return: **{econ['expected_return_pct']:.2f}%**",
            f"- Hurdle excess: {econ['expected_excess_over_hurdle_pct']:.2f}%p",
            f"- Bear return: {econ['lowest_scenario_return_pct']:.2f}%",
            f"- Bull return: {econ['highest_scenario_return_pct']:.2f}%",
            f"- P(loss): {econ['probability_of_price_loss']:.0%}",
            f"- P(meeting 15% hurdle): "
            f"{econ['probability_of_meeting_return_hurdle']:.0%}",
            f"- Investment interpretation: "
            f"**{result['investment_interpretation']}**",
            "",
            "## Portfolio sandbox",
            "",
            f"- Status: **{portfolio['status']}**",
            f"- Reasons: {', '.join(portfolio['reasons'])}",
            f"- Deterministic capital upper bound: "
            f"{portfolio['capital_headroom']['deterministic_upper_bound_pct']:.2f}%",
            "- This upper bound is **not** a target weight.",
            "",
            "## Risk sandbox",
            "",
        ]
    )
    if risk is None:
        lines.append(
            "- Risk was not invoked because Portfolio was not eligible for review."
        )
    else:
        lines.extend(
            [
                f"- Status: **{risk['status']}**",
                f"- Reasons: {', '.join(risk['reasons'])}",
                f"- Risk position ceiling: "
                f"{risk['limits']['risk_position_ceiling_pct']:.2f}%",
                "- Risk ceiling is **not** a target weight.",
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation boundaries",
            "",
            "- Real company data: yes",
            "- Real Client Portfolio context: **no** (synthetic sandbox only)",
            "- Analyst consensus: not used",
            "- Model calls: 0",
            "- Founder/Committee decision: none",
            "- PAPER/live execution: none",
            "",
            "A hurdle-cleared result is not a buy recommendation. "
            "A hurdle-failed result is not proof that the security is bad. "
            "QT-CASE-001 evaluates the frozen valuation method and organizational "
            "plumbing, not persistent alpha.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "asset_id": result["case"]["asset_id"],
                "current_price": result["case"]["current_price"],
                "ttm_eps": result["earnings"]["ttm_eps"],
                "weighted_fair_value": result[
                    "investment_case_economics"
                ]["metrics"]["weighted_fair_value"],
                "expected_return_pct": result[
                    "investment_case_economics"
                ]["metrics"]["expected_return_pct"],
                "investment_interpretation": result[
                    "investment_interpretation"
                ],
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
