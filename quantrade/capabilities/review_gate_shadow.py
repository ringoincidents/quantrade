"""Shadow-mode measurement for ReviewGate.

Shadow evaluation observes what the gate *would* recommend while preserving
the actual organizational decision path as source of truth.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from quantrade.capabilities.review_gate import (
    ReviewEvent,
    ReviewGatePolicy,
    evaluate_review_need,
)


@dataclass(frozen=True)
class ActualReviewOutcome:
    review_performed: bool
    review_level: str | None = None
    estimated_model_cost_usd: float | None = None
    estimated_latency_ms: float | None = None


@dataclass(frozen=True)
class ShadowReviewRecord:
    schema: str
    gate_result: dict
    actual: dict
    measurement: dict
    authority: dict


def observe_shadow(
    events: Iterable[ReviewEvent],
    actual: ActualReviewOutcome,
    policy: ReviewGatePolicy | None = None,
) -> ShadowReviewRecord:
    if actual.estimated_model_cost_usd is not None and actual.estimated_model_cost_usd < 0:
        raise ValueError("estimated_model_cost_usd cannot be negative")
    if actual.estimated_latency_ms is not None and actual.estimated_latency_ms < 0:
        raise ValueError("estimated_latency_ms cannot be negative")

    gate = evaluate_review_need(events, policy=policy)

    avoidable_review_candidate = (
        actual.review_performed and gate.level == "NO_REVIEW"
    )
    potential_false_negative = (
        not actual.review_performed and gate.level != "NO_REVIEW"
    )
    escalation_match = (
        actual.review_performed
        and actual.review_level is not None
        and actual.review_level == gate.level
    )

    return ShadowReviewRecord(
        schema="quantrade_review_gate_shadow_v1",
        gate_result=asdict(gate),
        actual=asdict(actual),
        measurement={
            "avoidable_review_candidate": avoidable_review_candidate,
            "potential_false_negative": potential_false_negative,
            "escalation_match": escalation_match,
            "observed_cost_usd": actual.estimated_model_cost_usd,
            "observed_latency_ms": actual.estimated_latency_ms,
            "savings_claimed_usd": 0.0,
        },
        authority={
            "shadow_only": True,
            "actual_path_changed": False,
            "ai_call_suppressed": False,
            "provider_promoted": False,
            "investment_decision_changed": False,
            "execution_changed": False,
        },
    )


def summarize_shadow(records: Iterable[ShadowReviewRecord]) -> dict:
    items = tuple(records)
    counts = {"NO_REVIEW": 0, "BOUNDED_REVIEW": 0, "MANDATORY_REVIEW": 0}
    for record in items:
        counts[record.gate_result["level"]] += 1

    return {
        "schema": "quantrade_review_gate_shadow_summary_v1",
        "sample_count": len(items),
        "gate_distribution": counts,
        "avoidable_review_candidates": sum(
            bool(r.measurement["avoidable_review_candidate"]) for r in items
        ),
        "potential_false_negatives": sum(
            bool(r.measurement["potential_false_negative"]) for r in items
        ),
        "escalation_matches": sum(
            bool(r.measurement["escalation_match"]) for r in items
        ),
        "observed_model_cost_usd": sum(
            float(r.measurement["observed_cost_usd"] or 0.0) for r in items
        ),
        "observed_latency_ms": sum(
            float(r.measurement["observed_latency_ms"] or 0.0) for r in items
        ),
        "claimed_savings_usd": 0.0,
        "promotion_recommendation": "REVIEW_REQUIRED",
        "authority": {
            "production_gate_enabled": False,
            "automatic_promotion_allowed": False,
        },
    }
