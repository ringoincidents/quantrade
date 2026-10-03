from __future__ import annotations

import argparse
import json
from time import perf_counter

from quantrade.institutional.domain import (
    CaseStatus,
    DecisionAction,
    Materiality,
    TimingMode,
)
from quantrade.institutional.service import InstitutionalKernel


def run_replay(*, committee_action: str) -> dict:
    if committee_action not in {"ENTER_NOW", "WAIT"}:
        raise ValueError("committee_action must be ENTER_NOW or WAIT")

    kernel = InstitutionalKernel(":memory:")
    started = perf_counter()
    try:
        opened = kernel.ingest_event(
            "MATERIAL_REVIEW_REQUIRED",
            "QT-LIVE-002-REPLAY",
            "BTCUSDT",
            {
                "reason": "institutional entry decision replay",
                "paper_only": True,
            },
            title="QT-LIVE-002 institutional entry decision",
        )
        case_id = opened["case_id"]
        assert case_id

        evidence_id = kernel.add_evidence(
            case_id,
            "QT-LIVE-002-REPLAY",
            "BTCUSDT market state requires an institutional entry decision.",
            {
                "kind": "replay_fixture",
                "paper_only": True,
            },
        )
        snapshot_id = kernel.add_snapshot(
            case_id,
            {
                "symbol": "BTCUSDT",
                "paper_equity_usd": 30.0,
                "position": None,
            },
            source="QT-LIVE-002-REPLAY",
        )
        risk_id = kernel.add_risk_assessment(
            case_id,
            snapshot_id,
            {
                "paper_only": True,
                "max_loss_usd": 0.90,
                "live_order_authorized": False,
            },
            "qt-live-002-paper-risk-v1",
        )

        research_stance = (
            "ENTER"
            if committee_action == "ENTER_NOW"
            else "WAIT"
        )
        portfolio_id = kernel.add_position(
            case_id,
            "SPMG",
            research_stance,
            (
                "Paper portfolio supports a bounded entry."
                if committee_action == "ENTER_NOW"
                else "Paper portfolio prefers no entry until confirmation."
            ),
            [evidence_id],
        )
        risk_position_id = kernel.add_position(
            case_id,
            "IPRO",
            (
                "ALLOW_BOUNDED_PAPER_ENTRY"
                if committee_action == "ENTER_NOW"
                else "NO_ENTRY"
            ),
            (
                "Entry is acceptable only inside the paper loss budget."
                if committee_action == "ENTER_NOW"
                else "Waiting has lower exposure while uncertainty remains."
            ),
            [risk_id],
        )
        challenge_id = kernel.add_challenge(
            case_id,
            thesis=(
                "Enter now because trend and institutional evidence are sufficient."
            ),
            counter_thesis=(
                "The move may reverse and deliberation latency can erase the edge."
            ),
            unresolved=False,
        )

        readiness = kernel.enter_committee(case_id)
        package = kernel.build_committee_package(
            case_id,
            proposed_action=committee_action,
            unresolved_questions=[],
        )
        route = kernel.assess_materiality(
            case_id,
            Materiality.HIGH,
            "QT-LIVE-002 forces explicit Founder-gated paper decision for replay.",
        )

        if committee_action == "ENTER_NOW":
            decision_id = kernel.decide(
                case_id,
                DecisionAction.APPROVE,
                "QT-LIVE-002 replay: approve simulated entry only.",
            )
            plan_id = kernel.create_decision_plan(
                decision_id,
                TimingMode.NOW,
            )
            kernel.transition(case_id, CaseStatus.DECISION_MANAGEMENT)
            kernel.transition(case_id, CaseStatus.EXECUTION_PENDING)
            execution_id = kernel.record_simulated_execution(
                plan_id,
                {
                    "symbol": "BTCUSDT",
                    "mode": "PAPER",
                    "action": "ENTER_NOW",
                    "live_order_authorized": False,
                },
            )
            kernel.transition(case_id, CaseStatus.OUTCOME_TRACKING)
        else:
            decision_id = kernel.decide(
                case_id,
                DecisionAction.HOLD,
                "QT-LIVE-002 replay: WAIT means no simulated entry.",
            )
            plan_id = None
            execution_id = None

        elapsed_ms = (perf_counter() - started) * 1000.0
        return {
            "schema": "qt_live_002_institutional_replay_v1",
            "case_id": case_id,
            "committee_action": committee_action,
            "committee_package_id": package["package_id"],
            "decision_id": decision_id,
            "decision_plan_id": plan_id,
            "execution_id": execution_id,
            "route": route,
            "committee_ready": readiness["ready"],
            "artifacts": {
                "evidence_id": evidence_id,
                "portfolio_snapshot_id": snapshot_id,
                "risk_assessment_id": risk_id,
                "portfolio_position_id": portfolio_id,
                "risk_position_id": risk_position_id,
                "challenge_id": challenge_id,
            },
            "final_case_status": kernel.get_case(case_id)["status"],
            "broker_side_effect": False,
            "elapsed_ms": elapsed_ms,
            "ledger_chain_valid": kernel.verify_ledger_chain(),
        }
    finally:
        kernel.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        choices=["ENTER_NOW", "WAIT"],
        default="ENTER_NOW",
    )
    args = parser.parse_args()
    print(json.dumps(run_replay(committee_action=args.action), indent=2))


if __name__ == "__main__":
    main()
