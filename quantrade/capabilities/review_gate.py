"""Deterministic gate for deciding whether bounded AI/research review is warranted.

This module never calls a model and never makes an investment decision.
It only classifies review necessity from already-structured organizational events.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable


class ReviewLevel(str, Enum):
    NO_REVIEW = "NO_REVIEW"
    BOUNDED_REVIEW = "BOUNDED_REVIEW"
    MANDATORY_REVIEW = "MANDATORY_REVIEW"


@dataclass(frozen=True)
class ReviewEvent:
    event_type: str
    materiality: float
    source_role: str
    unresolved: bool = False


@dataclass(frozen=True)
class ReviewGatePolicy:
    bounded_materiality: float = 0.50
    mandatory_materiality: float = 0.85
    mandatory_event_types: tuple[str, ...] = (
        "RISK_POLICY_BREACH",
        "CLIENT_MANDATE_CONFLICT",
        "LIQUIDITY_CONSTRAINT_BREACH",
    )


@dataclass(frozen=True)
class ReviewGateResult:
    schema: str
    level: str
    reasons: tuple[str, ...]
    event_count: int
    authority: dict[str, bool]


def evaluate_review_need(
    events: Iterable[ReviewEvent],
    policy: ReviewGatePolicy | None = None,
) -> ReviewGateResult:
    """Classify review necessity without invoking AI or changing authority."""
    policy = policy or ReviewGatePolicy()
    items = tuple(events)
    reasons: list[str] = []

    for event in items:
        if not 0.0 <= event.materiality <= 1.0:
            raise ValueError("event materiality must be between 0 and 1")
        if not event.event_type.strip() or not event.source_role.strip():
            raise ValueError("event_type and source_role are required")

    mandatory = [
        event for event in items
        if event.event_type in policy.mandatory_event_types
        or event.materiality >= policy.mandatory_materiality
    ]
    if mandatory:
        level = ReviewLevel.MANDATORY_REVIEW
        reasons.extend(
            f"MANDATORY:{event.source_role}:{event.event_type}"
            for event in mandatory
        )
    else:
        bounded = [
            event for event in items
            if event.materiality >= policy.bounded_materiality or event.unresolved
        ]
        if bounded:
            level = ReviewLevel.BOUNDED_REVIEW
            reasons.extend(
                f"BOUNDED:{event.source_role}:{event.event_type}"
                for event in bounded
            )
        else:
            level = ReviewLevel.NO_REVIEW
            reasons.append("NO_MATERIAL_OR_UNRESOLVED_EVENT")

    return ReviewGateResult(
        schema="quantrade_review_gate_v1",
        level=level.value,
        reasons=tuple(reasons),
        event_count=len(items),
        authority={
            "ai_called": False,
            "research_conclusion_created": False,
            "portfolio_proposal_created": False,
            "risk_veto_overridden": False,
            "investment_decision_created": False,
            "execution_authorized": False,
        },
    )


def to_artifact(result: ReviewGateResult) -> dict:
    return asdict(result)
