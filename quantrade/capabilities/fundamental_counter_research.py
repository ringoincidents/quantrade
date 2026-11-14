"""Deterministic counter-research for fundamental Investment Cases.

This capability turns pre-specified falsification / robustness checks into
explicit counter-evidence. It does not decide whether a security should be
bought or sold and cannot create capital authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from statistics import median


class FundamentalCounterResearchError(ValueError):
    """Raised when counter-research inputs violate the contract."""


@dataclass(frozen=True)
class AnnualCashConversion:
    fiscal_year: int
    owner_cash_flow_proxy: float
    profit_attributable_to_owners: float


@dataclass(frozen=True)
class FundamentalCounterResearchPolicy:
    multiple_dispersion_ratio_threshold: float
    cash_conversion_threshold: float


@dataclass(frozen=True)
class FundamentalCounterResearchInput:
    case_id: str
    annual_cash_conversion: tuple[AnnualCashConversion, ...]
    ttm_owner_cash_flow_proxy: float
    ttm_profit_attributable_to_owners: float
    historical_pe_values: tuple[float, ...]
    historical_pb_values: tuple[float, ...]
    current_pb: float
    policy: FundamentalCounterResearchPolicy


@dataclass(frozen=True)
class FundamentalCounterResearchArtifact:
    schema: str
    case_id: str
    status: str
    flags: tuple[str, ...]
    metrics: dict
    annual_cash_conversion: tuple[dict, ...]
    policy: dict
    authority: dict


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FundamentalCounterResearchError(
            f"{field_name} must be numeric"
        )
    number = float(value)
    if not math.isfinite(number):
        raise FundamentalCounterResearchError(
            f"{field_name} must be finite"
        )
    return number


def _percentile_linear(values: tuple[float, ...], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise FundamentalCounterResearchError(
            "percentile requires values"
        )
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * percentile
    low = int(math.floor(index))
    high = int(math.ceil(index))
    if low == high:
        return ordered[low]
    weight = index - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def evaluate_fundamental_counter_research(
    request: FundamentalCounterResearchInput,
) -> FundamentalCounterResearchArtifact:
    if not isinstance(request.case_id, str) or not request.case_id.strip():
        raise FundamentalCounterResearchError("case_id is required")
    if not request.annual_cash_conversion:
        raise FundamentalCounterResearchError(
            "annual cash-conversion history is required"
        )

    threshold = _finite(
        request.policy.cash_conversion_threshold,
        "cash_conversion_threshold",
    )
    if threshold <= 0.0:
        raise FundamentalCounterResearchError(
            "cash_conversion_threshold must be positive"
        )
    multiple_threshold = _finite(
        request.policy.multiple_dispersion_ratio_threshold,
        "multiple_dispersion_ratio_threshold",
    )
    if multiple_threshold <= 1.0:
        raise FundamentalCounterResearchError(
            "multiple_dispersion_ratio_threshold must exceed 1"
        )

    rows: list[dict] = []
    conversions: list[float] = []
    negative_cash_flow_years: list[int] = []
    years: set[int] = set()
    for item in request.annual_cash_conversion:
        if item.fiscal_year in years:
            raise FundamentalCounterResearchError(
                f"duplicate fiscal_year: {item.fiscal_year}"
            )
        years.add(item.fiscal_year)
        cash_flow = _finite(
            item.owner_cash_flow_proxy,
            f"{item.fiscal_year}.owner_cash_flow_proxy",
        )
        profit = _finite(
            item.profit_attributable_to_owners,
            f"{item.fiscal_year}.profit_attributable_to_owners",
        )
        if profit <= 0.0:
            raise FundamentalCounterResearchError(
                "annual profit attributable to owners must be positive"
            )
        conversion = cash_flow / profit
        if cash_flow <= 0.0:
            negative_cash_flow_years.append(item.fiscal_year)
        conversions.append(conversion)
        rows.append(
            {
                **asdict(item),
                "cash_conversion_ratio": round(conversion, 8),
            }
        )

    ttm_cash_flow = _finite(
        request.ttm_owner_cash_flow_proxy,
        "ttm_owner_cash_flow_proxy",
    )
    ttm_profit = _finite(
        request.ttm_profit_attributable_to_owners,
        "ttm_profit_attributable_to_owners",
    )
    if ttm_profit <= 0.0:
        raise FundamentalCounterResearchError(
            "ttm_profit_attributable_to_owners must be positive"
        )
    ttm_conversion = ttm_cash_flow / ttm_profit

    pe_values = tuple(
        _finite(value, "historical_pe_value")
        for value in request.historical_pe_values
    )
    if not pe_values or any(value <= 0.0 for value in pe_values):
        raise FundamentalCounterResearchError(
            "historical P/E values must be positive"
        )
    multiple_dispersion = max(pe_values) / min(pe_values)

    pb_values = tuple(
        _finite(value, "historical_pb_value")
        for value in request.historical_pb_values
    )
    if not pb_values or any(value <= 0.0 for value in pb_values):
        raise FundamentalCounterResearchError(
            "historical P/B values must be positive"
        )
    current_pb = _finite(request.current_pb, "current_pb")
    if current_pb <= 0.0:
        raise FundamentalCounterResearchError(
            "current_pb must be positive"
        )
    historical_pb_p75 = _percentile_linear(pb_values, 0.75)

    flags: list[str] = []
    if multiple_dispersion > multiple_threshold:
        flags.append("HIGH_MULTIPLE_REGIME_DISPERSION")
    if negative_cash_flow_years:
        flags.append("NEGATIVE_OWNER_CASH_FLOW_YEAR")
    median_conversion = median(conversions)
    if median_conversion < threshold:
        flags.append("WEAK_MEDIAN_CASH_CONVERSION")
    if ttm_conversion < threshold:
        flags.append("WEAK_TTM_CASH_CONVERSION")
    if current_pb > historical_pb_p75:
        flags.append("CURRENT_PB_ABOVE_HISTORICAL_P75")

    return FundamentalCounterResearchArtifact(
        schema="quantrade_fundamental_counter_research_v1",
        case_id=request.case_id,
        status=(
            "MATERIAL_COUNTER_EVIDENCE"
            if flags
            else "NO_MATERIAL_COUNTER_FLAG"
        ),
        flags=tuple(flags),
        metrics={
            "multiple_dispersion_ratio": round(
                multiple_dispersion,
                8,
            ),
            "median_annual_cash_conversion": round(
                median_conversion,
                8,
            ),
            "ttm_cash_conversion": round(
                ttm_conversion,
                8,
            ),
            "negative_cash_flow_years": tuple(
                negative_cash_flow_years
            ),
            "historical_pb_p75": round(
                historical_pb_p75,
                8,
            ),
            "current_pb": round(current_pb, 8),
        },
        annual_cash_conversion=tuple(rows),
        policy=asdict(request.policy),
        authority={
            "model_called": False,
            "canonical_evidence_created": False,
            "thesis_truth_validated": False,
            "portfolio_proposal_created": False,
            "risk_opinion_created": False,
            "committee_decision_created": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )
