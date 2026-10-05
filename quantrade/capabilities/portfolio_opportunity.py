"""Deterministic Portfolio Opportunity Cost assessment for QuanTrade.

Scope: RETURN_SEEKING_ACTIVE only.

This module answers a bounded Portfolio Management question:

    Even if an Investment Case is economically attractive in isolation, does it
    clear explicit opportunity-cost and capital-headroom gates strongly enough
    to deserve downstream Portfolio/Risk review?

It does not create a target weight, Risk Opinion, Committee Decision, PAPER
authority, or execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Sequence

from quantrade.capabilities.investment_case import InvestmentCaseEconomics


class PortfolioOpportunityError(ValueError):
    """Raised when opportunity-cost inputs violate deterministic contracts."""


class AlternativeType(str, Enum):
    CASH = "CASH"
    CORE_BENCHMARK = "CORE_BENCHMARK"
    CURRENT_HOLDING = "CURRENT_HOLDING"
    ACTIVE_CASE = "ACTIVE_CASE"


class PortfolioReviewStatus(str, Enum):
    MISSING_CONTEXT = "MISSING_CONTEXT"
    NOT_COMPETITIVE = "NOT_COMPETITIVE"
    ELIGIBLE_FOR_PORTFOLIO_REVIEW = "ELIGIBLE_FOR_PORTFOLIO_REVIEW"


@dataclass(frozen=True)
class CapitalAlternative:
    alternative_id: str
    alternative_type: str
    expected_return_pct: float
    downside_pct: float | None
    basis_refs: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioConstraintSnapshot:
    snapshot_id: str
    as_of: str
    mandate_allows_new_exposure: bool
    mandate_ref: str
    current_asset_weight_pct: float
    max_asset_weight_pct: float
    current_liquidity_pct: float
    minimum_liquidity_reserve_pct: float
    available_downside_budget_pct: float
    constraint_refs: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioOpportunityInput:
    case_economics: InvestmentCaseEconomics
    alternatives: tuple[CapitalAlternative, ...]
    constraints: PortfolioConstraintSnapshot


@dataclass(frozen=True)
class PortfolioOpportunityAssessment:
    schema: str
    case_id: str
    status: str
    reasons: tuple[str, ...]
    opportunity_cost: dict
    capital_headroom: dict
    alternatives: tuple[dict, ...]
    constraints: dict
    authority: dict


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PortfolioOpportunityError(f"{field_name} is required")
    return value.strip()


def _parse_time(value: str, field_name: str) -> datetime:
    raw = _text(value, field_name).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise PortfolioOpportunityError(
            f"{field_name} must be valid ISO-8601"
        ) from exc
    if parsed.tzinfo is None:
        raise PortfolioOpportunityError(
            f"{field_name} must include timezone information"
        )
    return parsed.astimezone(timezone.utc)


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PortfolioOpportunityError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise PortfolioOpportunityError(f"{field_name} must be finite")
    return number


def _pct(
    value: object,
    field_name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    number = _finite(value, field_name)
    if minimum is not None and number < minimum:
        raise PortfolioOpportunityError(
            f"{field_name} must be >= {minimum}"
        )
    if maximum is not None and number > maximum:
        raise PortfolioOpportunityError(
            f"{field_name} must be <= {maximum}"
        )
    return number


def _validate_refs(refs: Sequence[str], field_name: str) -> tuple[str, ...]:
    items = tuple(refs)
    for ref in items:
        _text(ref, field_name)
    return items


def _validate_alternative(item: CapitalAlternative) -> None:
    _text(item.alternative_id, "alternative_id")
    try:
        AlternativeType(item.alternative_type)
    except ValueError as exc:
        raise PortfolioOpportunityError(
            f"unsupported alternative_type: {item.alternative_type}"
        ) from exc
    _finite(item.expected_return_pct, "alternative expected_return_pct")
    if item.expected_return_pct <= -100.0:
        raise PortfolioOpportunityError(
            "alternative expected_return_pct must be greater than -100"
        )
    if item.downside_pct is not None:
        _finite(item.downside_pct, "alternative downside_pct")
    refs = _validate_refs(item.basis_refs, "alternative basis_ref")
    if not refs:
        raise PortfolioOpportunityError(
            f"alternative {item.alternative_id} requires basis_refs"
        )


def _validate_constraints(item: PortfolioConstraintSnapshot) -> None:
    _text(item.snapshot_id, "snapshot_id")
    _parse_time(item.as_of, "constraints as_of")
    _text(item.mandate_ref, "mandate_ref")
    refs = _validate_refs(item.constraint_refs, "constraint_ref")
    if not refs:
        raise PortfolioOpportunityError(
            "Portfolio constraints require constraint_refs"
        )

    current_weight = _pct(
        item.current_asset_weight_pct,
        "current_asset_weight_pct",
        minimum=0.0,
        maximum=100.0,
    )
    max_weight = _pct(
        item.max_asset_weight_pct,
        "max_asset_weight_pct",
        minimum=0.0,
        maximum=100.0,
    )
    if max_weight < current_weight:
        raise PortfolioOpportunityError(
            "max_asset_weight_pct cannot be below current_asset_weight_pct"
        )
    current_liquidity = _pct(
        item.current_liquidity_pct,
        "current_liquidity_pct",
        minimum=0.0,
        maximum=100.0,
    )
    reserve = _pct(
        item.minimum_liquidity_reserve_pct,
        "minimum_liquidity_reserve_pct",
        minimum=0.0,
        maximum=100.0,
    )
    if reserve > current_liquidity:
        # This is a valid real portfolio state but means no new deployment
        # headroom. Do not reject the snapshot.
        pass
    _pct(
        item.available_downside_budget_pct,
        "available_downside_budget_pct",
        minimum=0.0,
        maximum=100.0,
    )


def _expected_return(metrics: dict) -> float:
    try:
        value = metrics["expected_return_pct"]
    except KeyError as exc:
        raise PortfolioOpportunityError(
            "case economics missing expected_return_pct"
        ) from exc
    return _finite(value, "case expected_return_pct")


def _case_downside(metrics: dict) -> float:
    try:
        value = metrics["lowest_scenario_return_pct"]
    except KeyError as exc:
        raise PortfolioOpportunityError(
            "case economics missing lowest_scenario_return_pct"
        ) from exc
    return _finite(value, "case lowest_scenario_return_pct")


def _case_hurdle_met(metrics: dict) -> bool:
    value = metrics.get("expected_return_hurdle_met")
    if not isinstance(value, bool):
        raise PortfolioOpportunityError(
            "case economics missing boolean expected_return_hurdle_met"
        )
    return value


def assess_portfolio_opportunity(
    request: PortfolioOpportunityInput,
) -> PortfolioOpportunityAssessment:
    """Assess opportunity cost and deterministic capital headroom.

    The result is a review-eligibility artifact, not a Portfolio Proposal.
    """
    economics = request.case_economics
    if economics.authority.get("execution_authorized") is not False:
        raise PortfolioOpportunityError(
            "case economics must be non-execution-authoritative"
        )
    if economics.authority.get("portfolio_proposal_created") is not False:
        raise PortfolioOpportunityError(
            "case economics must not already contain Portfolio authority"
        )

    _validate_constraints(request.constraints)
    case_as_of = _parse_time(
        str(economics.case.get("as_of", "")),
        "case as_of",
    )
    constraints_as_of = _parse_time(
        request.constraints.as_of,
        "constraints as_of",
    )
    if constraints_as_of > case_as_of:
        raise PortfolioOpportunityError(
            "Portfolio constraint snapshot cannot be after case as_of"
        )

    if not request.alternatives:
        status = PortfolioReviewStatus.MISSING_CONTEXT
        reasons = ("NO_CAPITAL_ALTERNATIVES",)
        return PortfolioOpportunityAssessment(
            schema="quantrade_portfolio_opportunity_v1",
            case_id=economics.case["case_id"],
            status=status.value,
            reasons=reasons,
            opportunity_cost={
                "candidate_expected_return_pct": _expected_return(
                    economics.metrics
                ),
                "best_alternative_id": None,
                "best_alternative_expected_return_pct": None,
                "candidate_excess_vs_best_alternative_pct": None,
                "return_competition_evaluated": False,
            },
            capital_headroom=_capital_headroom(
                request.constraints,
                _case_downside(economics.metrics),
            ),
            alternatives=(),
            constraints=asdict(request.constraints),
            authority=_authority(),
        )

    ids: set[str] = set()
    for alternative in request.alternatives:
        _validate_alternative(alternative)
        if alternative.alternative_id in ids:
            raise PortfolioOpportunityError(
                f"duplicate alternative_id: {alternative.alternative_id}"
            )
        ids.add(alternative.alternative_id)

    candidate_return = _expected_return(economics.metrics)
    best = max(
        request.alternatives,
        key=lambda item: (
            item.expected_return_pct,
            item.alternative_id,
        ),
    )
    spread = candidate_return - best.expected_return_pct
    headroom = _capital_headroom(
        request.constraints,
        _case_downside(economics.metrics),
    )

    reasons: list[str] = []
    competitive = True

    if not request.constraints.mandate_allows_new_exposure:
        competitive = False
        reasons.append("MANDATE_DISALLOWS_NEW_EXPOSURE")

    if not _case_hurdle_met(economics.metrics):
        competitive = False
        reasons.append("CASE_RETURN_HURDLE_NOT_MET")

    if spread <= 0.0:
        competitive = False
        reasons.append("DOES_NOT_BEAT_BEST_CAPITAL_ALTERNATIVE")

    if headroom["deterministic_upper_bound_pct"] <= 0.0:
        competitive = False
        reasons.append("NO_DETERMINISTIC_CAPITAL_HEADROOM")

    if competitive:
        status = PortfolioReviewStatus.ELIGIBLE_FOR_PORTFOLIO_REVIEW
        reasons.append("CLEARS_RETURN_AND_HEADROOM_GATES")
    else:
        status = PortfolioReviewStatus.NOT_COMPETITIVE

    return PortfolioOpportunityAssessment(
        schema="quantrade_portfolio_opportunity_v1",
        case_id=economics.case["case_id"],
        status=status.value,
        reasons=tuple(reasons),
        opportunity_cost={
            "candidate_expected_return_pct": round(candidate_return, 6),
            "best_alternative_id": best.alternative_id,
            "best_alternative_type": best.alternative_type,
            "best_alternative_expected_return_pct": round(
                best.expected_return_pct,
                6,
            ),
            "candidate_excess_vs_best_alternative_pct": round(
                spread,
                6,
            ),
            "return_competition_evaluated": True,
            "alternative_count": len(request.alternatives),
            "investment_score_created": False,
        },
        capital_headroom=headroom,
        alternatives=tuple(
            {
                **asdict(item),
                "input_kind": "ALTERNATIVE_EXPECTATION",
                "investment_authority": False,
            }
            for item in request.alternatives
        ),
        constraints=asdict(request.constraints),
        authority=_authority(),
    )


def _capital_headroom(
    constraints: PortfolioConstraintSnapshot,
    candidate_downside_pct: float,
) -> dict:
    concentration_headroom = max(
        0.0,
        constraints.max_asset_weight_pct
        - constraints.current_asset_weight_pct,
    )
    liquidity_headroom = max(
        0.0,
        constraints.current_liquidity_pct
        - constraints.minimum_liquidity_reserve_pct,
    )

    if candidate_downside_pct < 0.0:
        downside_fraction = abs(candidate_downside_pct) / 100.0
        risk_limited_headroom = (
            constraints.available_downside_budget_pct
            / downside_fraction
            if downside_fraction > 0.0
            else 100.0
        )
    else:
        risk_limited_headroom = 100.0

    risk_limited_headroom = max(
        0.0,
        min(100.0, risk_limited_headroom),
    )
    upper_bound = min(
        concentration_headroom,
        liquidity_headroom,
        risk_limited_headroom,
    )

    return {
        "concentration_headroom_pct": round(
            concentration_headroom,
            6,
        ),
        "liquidity_headroom_pct": round(
            liquidity_headroom,
            6,
        ),
        "risk_limited_headroom_pct": round(
            risk_limited_headroom,
            6,
        ),
        "deterministic_upper_bound_pct": round(
            upper_bound,
            6,
        ),
        "candidate_downside_pct": round(
            candidate_downside_pct,
            6,
        ),
        "target_weight_proposed": False,
        "upper_bound_is_not_target_weight": True,
    }


def _authority() -> dict[str, bool]:
    return {
        "model_called": False,
        "canonical_evidence_created": False,
        "thesis_validated": False,
        "portfolio_review_eligibility_created": True,
        "portfolio_proposal_created": False,
        "target_weight_set": False,
        "risk_opinion_created": False,
        "risk_limit_changed": False,
        "committee_decision_created": False,
        "decision_plan_created": False,
        "paper_authorized": False,
        "execution_authorized": False,
        "live_order_possible": False,
    }
