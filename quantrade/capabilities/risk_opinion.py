"""Independent deterministic Risk Opinion for QuanTrade Investment Cases.

Risk receives only Portfolio-review-eligible Cases. It may pass, constrain, veto,
or require missing information. It cannot create an Investment Committee
Decision or execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import math

from quantrade.capabilities.portfolio_opportunity import (
    PortfolioOpportunityAssessment,
)


class RiskOpinionError(ValueError):
    """Raised when a Risk Opinion input violates the contract."""


class RiskOpinionStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_LIMITS = "PASS_WITH_LIMITS"
    VETO = "VETO"
    REQUIRE_MORE_INFORMATION = "REQUIRE_MORE_INFORMATION"


@dataclass(frozen=True)
class CandidateRiskProfile:
    asset_id: str
    worst_case_return_pct: float
    max_abs_correlation_to_portfolio: float | None
    estimated_exit_days: float | None
    uses_leverage: bool
    risk_refs: tuple[str, ...]


@dataclass(frozen=True)
class RiskPolicySnapshot:
    policy_id: str
    as_of: str
    max_single_asset_weight_pct: float
    max_incremental_downside_budget_pct: float
    max_portfolio_drawdown_pct: float
    max_abs_correlation_to_portfolio: float | None
    max_exit_days: float | None
    leverage_allowed: bool
    require_correlation_data: bool
    require_liquidity_data: bool
    policy_refs: tuple[str, ...]


@dataclass(frozen=True)
class RiskStateSnapshot:
    snapshot_id: str
    as_of: str
    current_asset_weight_pct: float
    current_portfolio_drawdown_pct: float
    state_refs: tuple[str, ...]


@dataclass(frozen=True)
class RiskOpinionInput:
    portfolio_assessment: PortfolioOpportunityAssessment
    candidate: CandidateRiskProfile
    policy: RiskPolicySnapshot
    state: RiskStateSnapshot


@dataclass(frozen=True)
class RiskOpinion:
    schema: str
    case_id: str
    status: str
    reasons: tuple[str, ...]
    candidate: dict
    policy: dict
    state: dict
    limits: dict
    authority: dict


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RiskOpinionError(f"{field_name} is required")
    return value.strip()


def _time(value: str, field_name: str) -> datetime:
    raw = _text(value, field_name).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise RiskOpinionError(
            f"{field_name} must be valid ISO-8601"
        ) from exc
    if parsed.tzinfo is None:
        raise RiskOpinionError(
            f"{field_name} must include timezone information"
        )
    return parsed.astimezone(timezone.utc)


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RiskOpinionError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise RiskOpinionError(f"{field_name} must be finite")
    return number


def _range(
    value: object,
    field_name: str,
    low: float,
    high: float,
) -> float:
    number = _finite(value, field_name)
    if number < low or number > high:
        raise RiskOpinionError(
            f"{field_name} must be between {low} and {high}"
        )
    return number


def _refs(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    for value in values:
        _text(value, field_name)
    return values


def _validate_candidate(item: CandidateRiskProfile) -> None:
    _text(item.asset_id, "asset_id")
    downside = _finite(
        item.worst_case_return_pct,
        "worst_case_return_pct",
    )
    if downside < -100.0:
        raise RiskOpinionError(
            "worst_case_return_pct cannot be below -100"
        )
    if item.max_abs_correlation_to_portfolio is not None:
        _range(
            item.max_abs_correlation_to_portfolio,
            "max_abs_correlation_to_portfolio",
            0.0,
            1.0,
        )
    if item.estimated_exit_days is not None:
        exit_days = _finite(
            item.estimated_exit_days,
            "estimated_exit_days",
        )
        if exit_days < 0.0:
            raise RiskOpinionError(
                "estimated_exit_days cannot be negative"
            )
    if not _refs(item.risk_refs, "risk_ref"):
        raise RiskOpinionError("candidate risk profile requires risk_refs")


def _validate_policy(item: RiskPolicySnapshot) -> None:
    _text(item.policy_id, "policy_id")
    _time(item.as_of, "policy as_of")
    _range(
        item.max_single_asset_weight_pct,
        "max_single_asset_weight_pct",
        0.0,
        100.0,
    )
    _range(
        item.max_incremental_downside_budget_pct,
        "max_incremental_downside_budget_pct",
        0.0,
        100.0,
    )
    drawdown = _finite(
        item.max_portfolio_drawdown_pct,
        "max_portfolio_drawdown_pct",
    )
    if drawdown >= 0.0 or drawdown < -100.0:
        raise RiskOpinionError(
            "max_portfolio_drawdown_pct must be negative and >= -100"
        )
    if item.max_abs_correlation_to_portfolio is not None:
        _range(
            item.max_abs_correlation_to_portfolio,
            "policy max_abs_correlation_to_portfolio",
            0.0,
            1.0,
        )
    if item.max_exit_days is not None:
        if _finite(item.max_exit_days, "max_exit_days") < 0.0:
            raise RiskOpinionError("max_exit_days cannot be negative")
    if not _refs(item.policy_refs, "policy_ref"):
        raise RiskOpinionError("Risk policy requires policy_refs")


def _validate_state(item: RiskStateSnapshot) -> None:
    _text(item.snapshot_id, "snapshot_id")
    _time(item.as_of, "risk state as_of")
    _range(
        item.current_asset_weight_pct,
        "current_asset_weight_pct",
        0.0,
        100.0,
    )
    drawdown = _finite(
        item.current_portfolio_drawdown_pct,
        "current_portfolio_drawdown_pct",
    )
    if drawdown > 0.0 or drawdown < -100.0:
        raise RiskOpinionError(
            "current_portfolio_drawdown_pct must be between -100 and 0"
        )
    if not _refs(item.state_refs, "state_ref"):
        raise RiskOpinionError("Risk state requires state_refs")


def create_risk_opinion(request: RiskOpinionInput) -> RiskOpinion:
    """Produce an independent deterministic Risk Opinion."""
    portfolio = request.portfolio_assessment
    if portfolio.status != "ELIGIBLE_FOR_PORTFOLIO_REVIEW":
        raise RiskOpinionError(
            "Risk Opinion requires ELIGIBLE_FOR_PORTFOLIO_REVIEW"
        )
    if portfolio.authority.get("portfolio_proposal_created") is not False:
        raise RiskOpinionError(
            "Portfolio assessment must remain non-proposal"
        )
    if portfolio.authority.get("execution_authorized") is not False:
        raise RiskOpinionError(
            "Portfolio assessment must remain non-execution-authoritative"
        )

    _validate_candidate(request.candidate)
    _validate_policy(request.policy)
    _validate_state(request.state)

    portfolio_as_of = _time(
        request.portfolio_assessment.constraints["as_of"],
        "portfolio constraints as_of",
    )
    policy_as_of = _time(request.policy.as_of, "policy as_of")
    state_as_of = _time(request.state.as_of, "risk state as_of")
    if policy_as_of > portfolio_as_of:
        raise RiskOpinionError(
            "Risk policy snapshot cannot be after Portfolio snapshot"
        )
    if state_as_of > portfolio_as_of:
        raise RiskOpinionError(
            "Risk state snapshot cannot be after Portfolio snapshot"
        )

    missing: list[str] = []
    if (
        request.policy.require_correlation_data
        and request.candidate.max_abs_correlation_to_portfolio is None
    ):
        missing.append("MISSING_CORRELATION_DATA")
    if (
        request.policy.require_liquidity_data
        and request.candidate.estimated_exit_days is None
    ):
        missing.append("MISSING_LIQUIDITY_DATA")

    opportunity_ceiling = _finite(
        portfolio.capital_headroom["deterministic_upper_bound_pct"],
        "Portfolio deterministic_upper_bound_pct",
    )
    policy_asset_headroom = max(
        0.0,
        request.policy.max_single_asset_weight_pct
        - request.state.current_asset_weight_pct,
    )

    downside = request.candidate.worst_case_return_pct
    if downside < 0.0:
        downside_fraction = abs(downside) / 100.0
        downside_ceiling = (
            request.policy.max_incremental_downside_budget_pct
            / downside_fraction
        )
    else:
        downside_ceiling = 100.0
    downside_ceiling = max(0.0, min(100.0, downside_ceiling))

    independent_ceiling = min(
        opportunity_ceiling,
        policy_asset_headroom,
        downside_ceiling,
    )

    reasons: list[str] = []
    hard_veto = False

    if (
        request.state.current_portfolio_drawdown_pct
        <= request.policy.max_portfolio_drawdown_pct
    ):
        hard_veto = True
        reasons.append("PORTFOLIO_DRAWDOWN_LIMIT_REACHED")

    if request.candidate.uses_leverage and not request.policy.leverage_allowed:
        hard_veto = True
        reasons.append("LEVERAGE_NOT_ALLOWED")

    if (
        request.policy.max_abs_correlation_to_portfolio is not None
        and request.candidate.max_abs_correlation_to_portfolio is not None
        and request.candidate.max_abs_correlation_to_portfolio
        > request.policy.max_abs_correlation_to_portfolio
    ):
        hard_veto = True
        reasons.append("CORRELATION_LIMIT_BREACH")

    if (
        request.policy.max_exit_days is not None
        and request.candidate.estimated_exit_days is not None
        and request.candidate.estimated_exit_days
        > request.policy.max_exit_days
    ):
        hard_veto = True
        reasons.append("LIQUIDITY_EXIT_LIMIT_BREACH")

    if policy_asset_headroom <= 0.0:
        hard_veto = True
        reasons.append("RISK_SINGLE_ASSET_LIMIT_REACHED")

    if downside_ceiling <= 0.0:
        hard_veto = True
        reasons.append("NO_INCREMENTAL_DOWNSIDE_BUDGET")

    if hard_veto:
        status = RiskOpinionStatus.VETO
    elif missing:
        status = RiskOpinionStatus.REQUIRE_MORE_INFORMATION
        reasons.extend(missing)
    elif independent_ceiling < opportunity_ceiling:
        status = RiskOpinionStatus.PASS_WITH_LIMITS
        reasons.append("RISK_REDUCED_PORTFOLIO_HEADROOM")
    else:
        status = RiskOpinionStatus.PASS
        reasons.append("NO_ADDITIONAL_RISK_LIMIT_REQUIRED")

    return RiskOpinion(
        schema="quantrade_risk_opinion_v1",
        case_id=portfolio.case_id,
        status=status.value,
        reasons=tuple(reasons),
        candidate=asdict(request.candidate),
        policy=asdict(request.policy),
        state=asdict(request.state),
        limits={
            "portfolio_opportunity_upper_bound_pct": round(
                opportunity_ceiling,
                6,
            ),
            "risk_single_asset_headroom_pct": round(
                policy_asset_headroom,
                6,
            ),
            "risk_downside_budget_ceiling_pct": round(
                downside_ceiling,
                6,
            ),
            "risk_position_ceiling_pct": round(
                independent_ceiling,
                6,
            ),
            "target_weight_set": False,
            "risk_ceiling_is_not_target_weight": True,
        },
        authority={
            "model_called": False,
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "target_weight_set": False,
            "risk_opinion_created": True,
            "risk_veto_present": status is RiskOpinionStatus.VETO,
            "risk_limit_changed": False,
            "committee_decision_created": False,
            "decision_plan_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )
