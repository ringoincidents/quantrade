"""Bind ReviewGate shadow comparison to the sanitized Institutional Case precheck.

The published precheck is intentionally used instead of private Client input.
This script compares routing intent only; it does not claim an AI call occurred.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from quantrade.capabilities.review_gate import ReviewEvent, evaluate_review_need


REASON_EVENT_MAP = {
    "CLIENT_MANDATE_CONFLICT": ("CLIENT_MANDATE_CONFLICT", "Strategy"),
    "CLIENT_PLAN_CONFLICT": ("CLIENT_MANDATE_CONFLICT", "Strategy"),
    "LIQUIDITY_CONSTRAINT_BREACH": ("LIQUIDITY_CONSTRAINT_BREACH", "Client Intelligence"),
    "RISK_POLICY_BREACH": ("RISK_POLICY_BREACH", "Risk & Compliance"),
}


def _events_from_precheck(precheck: dict) -> list[ReviewEvent]:
    reasons = []
    reasons.extend(precheck.get("strategy_directive", {}).get("reasons", []))
    reasons.extend(precheck.get("ai_call_gate", {}).get("reasons", []))

    events = []
    seen = set()
    for reason in reasons:
        mapped = REASON_EVENT_MAP.get(reason)
        if mapped and mapped not in seen:
            seen.add(mapped)
            event_type, source_role = mapped
            events.append(ReviewEvent(event_type, 0.0, source_role))
    return events


def build_shadow_binding(precheck: dict) -> dict:
    events = _events_from_precheck(precheck)
    result = evaluate_review_need(events)
    legacy_gate = precheck.get("ai_call_gate", {})
    legacy_call_ai = legacy_gate.get("call_ai")

    if legacy_call_ai is True:
        agreement = result.level != "NO_REVIEW"
    elif legacy_call_ai is False:
        agreement = result.level == "NO_REVIEW"
    else:
        agreement = None

    return {
        "schema": "quantrade_review_gate_live_shadow_binding_v1",
        "source": {
            "schema": precheck.get("schema"),
            "experiment_id": precheck.get("experiment_id"),
            "run_id": precheck.get("run_id"),
            "mode": precheck.get("mode"),
            "private_client_values_consumed": False,
        },
        "translated_events": [
            {
                "event_type": event.event_type,
                "source_role": event.source_role,
                "materiality": event.materiality,
                "unresolved": event.unresolved,
            }
            for event in events
        ],
        "shadow_gate": {
            "level": result.level,
            "reasons": list(result.reasons),
        },
        "existing_routing_intent": {
            "call_ai": legacy_call_ai,
            "call_type": legacy_gate.get("call_type"),
            "reasons": legacy_gate.get("reasons", []),
        },
        "comparison": {
            "routing_intent_agreement": agreement,
            "actual_ai_call_observed": None,
            "model_cost_usd_observed": None,
            "latency_ms_observed": None,
            "savings_claimed_usd": 0.0,
        },
        "authority": {
            "shadow_only": True,
            "existing_gate_replaced": False,
            "actual_path_changed": False,
            "ai_call_suppressed": False,
            "investment_decision_changed": False,
            "execution_changed": False,
            "automatic_promotion_allowed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--precheck", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    precheck = json.loads(Path(args.precheck).read_text(encoding="utf-8"))
    artifact = build_shadow_binding(precheck)
    Path(args.output).write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
