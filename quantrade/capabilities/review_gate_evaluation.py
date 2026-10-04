"""Deterministic evaluation harness for ReviewGate shadow behavior.

This is an evaluation instrument, not a production router. It creates explicit
fixtures, compares expected organizational review levels, and preserves
disagreements as evidence for later Research/Risk/Performance review.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from quantrade.capabilities.review_gate import ReviewEvent, evaluate_review_need


@dataclass(frozen=True)
class EvaluationScenario:
    scenario_id: str
    description: str
    events: tuple[ReviewEvent, ...]
    expected_level: str
    owner: str
    legacy_call_ai: bool | None = None


def canonical_scenarios() -> tuple[EvaluationScenario, ...]:
    return (
        EvaluationScenario(
            "routine_observation",
            "Routine structured observation with low materiality.",
            (ReviewEvent("ROUTINE_OBSERVATION", 0.10, "Research"),),
            "NO_REVIEW",
            "Performance & Learning",
            False,
        ),
        EvaluationScenario(
            "material_research_change",
            "Material research change warrants bounded review but not authority escalation.",
            (ReviewEvent("MATERIAL_RESEARCH_CHANGE", 0.60, "Research"),),
            "BOUNDED_REVIEW",
            "Research",
            True,
        ),
        EvaluationScenario(
            "unresolved_research_disagreement",
            "Low-materiality but unresolved departmental disagreement remains reviewable.",
            (ReviewEvent("RESEARCH_DISAGREEMENT", 0.20, "Research", unresolved=True),),
            "BOUNDED_REVIEW",
            "Research",
            True,
        ),
        EvaluationScenario(
            "client_mandate_conflict",
            "Client mandate conflict must escalate regardless of numeric materiality.",
            (ReviewEvent("CLIENT_MANDATE_CONFLICT", 0.0, "Strategy"),),
            "MANDATORY_REVIEW",
            "Strategy",
            True,
        ),
        EvaluationScenario(
            "liquidity_constraint_breach",
            "Liquidity constraint breach must escalate.",
            (ReviewEvent("LIQUIDITY_CONSTRAINT_BREACH", 0.0, "Client Intelligence"),),
            "MANDATORY_REVIEW",
            "Client Intelligence",
            True,
        ),
        EvaluationScenario(
            "risk_policy_breach",
            "Risk policy breach must escalate and cannot be suppressed for cost reasons.",
            (ReviewEvent("RISK_POLICY_BREACH", 0.0, "Risk & Compliance"),),
            "MANDATORY_REVIEW",
            "Risk & Compliance",
            True,
        ),
        EvaluationScenario(
            "high_materiality_novel_event",
            "Novel event is not allowlisted but high materiality still forces mandatory review.",
            (ReviewEvent("NOVEL_FUTURE_EVENT", 0.95, "Research"),),
            "MANDATORY_REVIEW",
            "Research",
            True,
        ),
    )


def evaluate_scenario(scenario: EvaluationScenario) -> dict:
    result = evaluate_review_need(scenario.events)
    expected_match = result.level == scenario.expected_level

    if scenario.legacy_call_ai is None:
        legacy_agreement = None
    elif scenario.legacy_call_ai:
        legacy_agreement = result.level != "NO_REVIEW"
    else:
        legacy_agreement = result.level == "NO_REVIEW"

    return {
        "scenario_id": scenario.scenario_id,
        "description": scenario.description,
        "owner": scenario.owner,
        "events": [asdict(event) for event in scenario.events],
        "expected_level": scenario.expected_level,
        "observed_level": result.level,
        "expected_match": expected_match,
        "legacy_call_ai": scenario.legacy_call_ai,
        "legacy_routing_agreement": legacy_agreement,
        "reasons": list(result.reasons),
    }


def build_evaluation_artifact(
    scenarios: tuple[EvaluationScenario, ...] | None = None,
) -> dict:
    items = scenarios or canonical_scenarios()
    results = [evaluate_scenario(scenario) for scenario in items]
    mismatches = [r for r in results if not r["expected_match"]]
    legacy_disagreements = [
        r for r in results if r["legacy_routing_agreement"] is False
    ]
    return {
        "schema": "quantrade_review_gate_evaluation_v1",
        "scenario_count": len(results),
        "expected_mismatch_count": len(mismatches),
        "legacy_disagreement_count": len(legacy_disagreements),
        "results": results,
        "disagreements": {
            "expected": [r["scenario_id"] for r in mismatches],
            "legacy_routing": [r["scenario_id"] for r in legacy_disagreements],
        },
        "promotion": {
            "production_authority_granted": False,
            "automatic_promotion_allowed": False,
            "decision": "REVIEW_REQUIRED",
        },
        "authority": {
            "ai_called": False,
            "risk_policy_changed": False,
            "investment_decision_created": False,
            "execution_authorized": False,
        },
    }
