"""Bind ReviewGate shadow comparison to the sanitized Institutional Case precheck.

The published precheck is intentionally used instead of private Client input.
This script compares routing intent only; it does not claim an AI call occurred.
Unknown reasons are preserved as translation evidence instead of being silently
discarded or assigned invented materiality.
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


def _reason_records(precheck: dict) -> list[dict]:
    sources = (
        ("strategy_directive", precheck.get("strategy_directive", {}).get("reasons", [])),
        ("ai_call_gate", precheck.get("ai_call_gate", {}).get("reasons", [])),
    )
    records = []
    seen = set()
    for source, reasons in sources:
        for reason in reasons:
            key = (source, reason)
            if key in seen:
                continue
            seen.add(key)
            mapped = REASON_EVENT_MAP.get(reason)
            records.append({
                "source": source,
                "reason": reason,
                "translation_status": "MAPPED" if mapped else "UNMAPPED",
                "mapped_event_type": mapped[0] if mapped else None,
                "mapped_source_role": mapped[1] if mapped else None,
            })
    return records


def _events_from_records(records: list[dict]) -> list[ReviewEvent]:
    events = []
    seen = set()
    for record in records:
        if record["translation_status"] != "MAPPED":
            continue
        mapped = (record["mapped_event_type"], record["mapped_source_role"])
        if mapped in seen:
            continue
        seen.add(mapped)
        events.append(ReviewEvent(mapped[0], 0.0, mapped[1]))
    return events


def build_shadow_binding(precheck: dict) -> dict:
    reason_records = _reason_records(precheck)
    events = _events_from_records(reason_records)
    result = evaluate_review_need(events)
    legacy_gate = precheck.get("ai_call_gate", {})
    legacy_call_ai = legacy_gate.get("call_ai")
    unmapped = [record for record in reason_records if record["translation_status"] == "UNMAPPED"]

    if legacy_call_ai is True:
        agreement = result.level != "NO_REVIEW"
    elif legacy_call_ai is False:
        agreement = result.level == "NO_REVIEW"
    else:
        agreement = None

    return {
        "schema": "quantrade_review_gate_live_shadow_binding_v2",
        "source": {
            "schema": precheck.get("schema"),
            "experiment_id": precheck.get("experiment_id"),
            "run_id": precheck.get("run_id"),
            "mode": precheck.get("mode"),
            "private_client_values_consumed": False,
        },
        "reason_translation": {
            "records": reason_records,
            "reason_count": len(reason_records),
            "mapped_count": len(reason_records) - len(unmapped),
            "unmapped_count": len(unmapped),
            "coverage_complete": not unmapped,
            "unmapped_reasons": [record["reason"] for record in unmapped],
            "policy": "Preserve unknown reasons; do not invent materiality or production authority.",
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
            "translation_coverage_complete": not unmapped,
            "requires_translation_review": bool(unmapped),
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
            "unmapped_reason_auto_escalated": False,
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
