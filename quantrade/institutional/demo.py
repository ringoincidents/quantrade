from __future__ import annotations

import argparse
import json
import os
import tempfile

from .domain import CaseStatus, DecisionAction, TimingMode
from .service import InstitutionalKernel


def run_demo(db_path: str) -> dict:
    kernel = InstitutionalKernel(db_path)
    try:
        routine = kernel.ingest_event(
            "DIVIDEND_RECEIVED", "fixture", "MOCK-ETF", {"amount": 12.34}
        )
        material = kernel.ingest_event(
            "PORTFOLIO_POLICY_LIMIT_APPROACH",
            "fixture",
            "MOCK-ENERGY",
            {"observed_weight_pct": 26.4, "fixture": True},
            case_id="QT-2026-0041",
            title="Synthetic portfolio policy review",
        )
        case_id = material["case_id"]

        kernel.transition(case_id, CaseStatus.RESEARCH)
        ev = kernel.add_evidence(
            case_id,
            "synthetic-company-filing",
            "Fixture evidence: earnings and valuation facts collected.",
            {"mock": True, "url": None},
        )
        kernel.add_snapshot(
            case_id,
            {
                "cash": 1000,
                "positions": [{"symbol": "MOCK-ENERGY", "weight_pct": 26.4}],
                "mock": True,
            },
        )
        kernel.add_position(
            case_id, "IID", "REVIEW", "Evidence assembled for institutional review.", [ev]
        )

        kernel.transition(case_id, CaseStatus.PORTFOLIO_REVIEW)
        kernel.add_position(
            case_id,
            "SPMG",
            "REDUCE_CANDIDATE",
            "KEEP / REDUCE / EXIT considered; REDUCE retained as mock analytical alternative.",
            [ev],
        )

        kernel.transition(case_id, CaseStatus.RISK_REVIEW)
        snapshot_id = kernel.conn.execute(
            "SELECT snapshot_id FROM portfolio_snapshots WHERE case_id=?", (case_id,)
        ).fetchone()["snapshot_id"]
        kernel.add_risk_assessment(
            case_id,
            snapshot_id,
            {"concentration": "fixture-limit-approach", "liquidity": "fixture-ok", "mock": True},
            "fixture-policy-v1",
        )
        kernel.add_position(
            case_id, "IPRO", "CONDITIONAL", "Concentration requires explicit review.", [ev]
        )

        kernel.transition(case_id, CaseStatus.ADVERSARIAL_REVIEW)
        kernel.add_challenge(
            case_id,
            "Reducing concentration is necessarily superior.",
            "Reduction may sacrifice upside if the policy signal is temporary; unresolved in fixture.",
        )

        kernel.transition(case_id, CaseStatus.COMMITTEE)
        package = kernel.build_committee_package(
            case_id,
            "REDUCE",
            ["Is the concentration persistent after the named catalyst?"],
        )
        kernel.transition(case_id, CaseStatus.FOUNDER_PENDING)

        decision_id = kernel.decide(
            case_id, DecisionAction.APPROVE, "Fixture approval; no live order authorized."
        )
        kernel.transition(case_id, CaseStatus.DECISION_MANAGEMENT)
        plan_id = kernel.create_decision_plan(
            decision_id, TimingMode.CONDITIONAL, "Execute only in simulation after fixture condition."
        )
        kernel.transition(case_id, CaseStatus.EXECUTION_PENDING)
        execution_id = kernel.record_simulated_execution(
            plan_id, {"action": "REDUCE", "mode": "SIMULATED", "mock": True}
        )
        kernel.transition(case_id, CaseStatus.OUTCOME_TRACKING)
        reviews = kernel.schedule_reviews(case_id, (30, 90))

        return {
            "routine_event": routine,
            "material_event": material,
            "case": kernel.get_case(case_id),
            "committee_package_id": package["package_id"],
            "decision_id": decision_id,
            "plan_id": plan_id,
            "execution_id": execution_id,
            "review_ids": reviews,
            "ledger_count": len(kernel.ledger()),
            "broker_side_effect": False,
        }
    finally:
        kernel.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    if args.db:
        result = run_demo(args.db)
    else:
        fd, path = tempfile.mkstemp(prefix="quantrade_p1_", suffix=".sqlite3")
        os.close(fd)
        try:
            result = run_demo(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
