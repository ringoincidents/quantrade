from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connect
from .domain import (
    CaseStatus,
    DecisionAction,
    EscalationAction,
    FixtureEscalationPolicy,
    Materiality,
    TimingMode,
)


class InvalidTransition(ValueError):
    pass


class ImmutableRecordError(ValueError):
    pass


TRANSITIONS = {
    CaseStatus.OPEN: {CaseStatus.RESEARCH},
    CaseStatus.RESEARCH: {CaseStatus.PORTFOLIO_REVIEW},
    CaseStatus.PORTFOLIO_REVIEW: {CaseStatus.RISK_REVIEW},
    CaseStatus.RISK_REVIEW: {CaseStatus.ADVERSARIAL_REVIEW},
    CaseStatus.ADVERSARIAL_REVIEW: {CaseStatus.COMMITTEE},
    CaseStatus.COMMITTEE: {CaseStatus.FOUNDER_PENDING, CaseStatus.DECIDED},
    CaseStatus.FOUNDER_PENDING: {CaseStatus.DECIDED, CaseStatus.RESEARCH},
    CaseStatus.DECIDED: {CaseStatus.DECISION_MANAGEMENT, CaseStatus.CLOSED},
    CaseStatus.DECISION_MANAGEMENT: {CaseStatus.EXECUTION_PENDING},
    CaseStatus.EXECUTION_PENDING: {CaseStatus.OUTCOME_TRACKING},
    CaseStatus.OUTCOME_TRACKING: {CaseStatus.CLOSED},
    CaseStatus.CLOSED: set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class InstitutionalKernel:
    def __init__(self, db_path: str = ":memory:", policy=None):
        self.conn = connect(db_path)
        self.policy = policy or FixtureEscalationPolicy()

    def close(self) -> None:
        self.conn.close()

    def _ledger(self, aggregate_type: str, aggregate_id: str, event_type: str, payload: dict) -> None:
        prev = self.conn.execute(
            "SELECT event_hash FROM ledger_events ORDER BY ledger_id DESC LIMIT 1"
        ).fetchone()
        previous_hash = prev["event_hash"] if prev else None
        occurred_at = _now()
        body = _json({
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "event_type": event_type,
            "payload": payload,
            "occurred_at": occurred_at,
            "previous_hash": previous_hash,
        })
        event_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        self.conn.execute(
            """INSERT INTO ledger_events
            (aggregate_type, aggregate_id, event_type, payload, occurred_at, previous_hash, event_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (aggregate_type, aggregate_id, event_type, _json(payload), occurred_at, previous_hash, event_hash),
        )

    def ingest_event(
        self,
        event_type: str,
        source: str,
        subject: str,
        payload: dict,
        *,
        event_id: str | None = None,
        case_id: str | None = None,
        title: str | None = None,
    ) -> dict:
        event_id = event_id or _id("EVT")
        now = _now()
        result = self.policy.evaluate(event_type, payload)
        with self.conn:
            self.conn.execute(
                """INSERT INTO events
                (event_id,event_type,occurred_at,source,subject,payload,resolution_status,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (event_id, event_type, now, source, subject, _json(payload), result.action.value, now),
            )
            self._ledger("Event", event_id, "EVENT_INGESTED", {
                "event_type": event_type, "resolution": result.action.value
            })
            if result.action == EscalationAction.INTERNAL_LOG:
                self._ledger("Event", event_id, "EVENT_RESOLVED_INTERNAL", {"reason": result.reason})
                return {"event_id": event_id, "case_id": None, "route": "INTERNAL"}

            cid = case_id or _id("QT")
            materiality = result.materiality.value
            self.conn.execute(
                """INSERT INTO cases
                (case_id,title,trigger_event_id,subject,status,materiality,opened_at)
                VALUES (?,?,?,?,?,?,?)""",
                (cid, title or f"Review: {subject}", event_id, subject, CaseStatus.OPEN.value, materiality, now),
            )
            self._ledger("Case", cid, "CASE_OPENED", {
                "trigger_event_id": event_id, "materiality": materiality
            })
            route = "INTERNAL"
            if result.materiality == Materiality.MEDIUM:
                self.conn.execute(
                    "INSERT INTO founder_briefing_queue(case_id,created_at) VALUES (?,?)", (cid, now)
                )
                route = "FOUNDER_BRIEFING"
            elif result.materiality == Materiality.HIGH:
                route = "CASE_HIGH"
            return {"event_id": event_id, "case_id": cid, "route": route}

    def get_case(self, case_id: str) -> dict:
        row = self.conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not row:
            raise KeyError(case_id)
        return dict(row)

    def transition(self, case_id: str, target: CaseStatus | str) -> None:
        target = CaseStatus(target)
        with self.conn:
            row = self.conn.execute(
                "SELECT status,version FROM cases WHERE case_id=?", (case_id,)
            ).fetchone()
            if not row:
                raise KeyError(case_id)
            current = CaseStatus(row["status"])
            if target not in TRANSITIONS[current]:
                raise InvalidTransition(f"{current.value} -> {target.value}")
            closed_at = _now() if target == CaseStatus.CLOSED else None
            self.conn.execute(
                "UPDATE cases SET status=?, version=version+1, closed_at=COALESCE(?,closed_at) WHERE case_id=?",
                (target.value, closed_at, case_id),
            )
            if target == CaseStatus.FOUNDER_PENDING:
                self.conn.execute(
                    "INSERT OR IGNORE INTO founder_desk(case_id,created_at) VALUES (?,?)",
                    (case_id, _now()),
                )
            self._ledger("Case", case_id, "CASE_TRANSITIONED", {
                "from": current.value, "to": target.value
            })

    def add_evidence(self, case_id: str, source: str, fact: str, provenance: dict) -> str:
        eid = _id("EVD")
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO evidence
                (evidence_id,case_id,source,observed_at,fact,provenance,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (eid, case_id, source, now, fact, _json(provenance), now),
            )
            self._ledger("Case", case_id, "EVIDENCE_ATTACHED", {"evidence_id": eid, "source": source})
        return eid

    def add_snapshot(self, case_id: str, snapshot: dict, source: str = "fixture") -> str:
        sid = _id("SNP")
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO portfolio_snapshots
                (snapshot_id,case_id,as_of,source,snapshot,created_at) VALUES (?,?,?,?,?,?)""",
                (sid, case_id, now, source, _json(snapshot), now),
            )
            self._ledger("Case", case_id, "PORTFOLIO_SNAPSHOT_ATTACHED", {"snapshot_id": sid})
        return sid

    def add_risk_assessment(self, case_id: str, snapshot_id: str, result: dict, policy_version: str) -> str:
        aid = _id("RSK")
        with self.conn:
            self.conn.execute(
                """INSERT INTO risk_assessments
                (assessment_id,case_id,snapshot_id,policy_version,result,created_at)
                VALUES (?,?,?,?,?,?)""",
                (aid, case_id, snapshot_id, policy_version, _json(result), _now()),
            )
            self._ledger("Case", case_id, "RISK_ASSESSED", {
                "assessment_id": aid, "policy_version": policy_version
            })
        return aid

    def add_position(
        self, case_id: str, office: str, stance: str, rationale: str,
        evidence_refs: list[str] | None = None, supersedes_id: str | None = None
    ) -> str:
        pid = _id("POS")
        with self.conn:
            self.conn.execute(
                """INSERT INTO institutional_positions
                (position_id,case_id,office,stance,rationale,evidence_refs,supersedes_id,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (pid, case_id, office, stance, rationale, _json(evidence_refs or []), supersedes_id, _now()),
            )
            self._ledger("Case", case_id, "POSITION_RECORDED", {
                "position_id": pid, "office": office, "stance": stance, "supersedes_id": supersedes_id
            })
        return pid

    def add_challenge(self, case_id: str, thesis: str, counter_thesis: str, unresolved: bool = True) -> str:
        cid = _id("CHL")
        with self.conn:
            self.conn.execute(
                """INSERT INTO challenges
                (challenge_id,case_id,thesis_challenged,counter_thesis,unresolved,created_at)
                VALUES (?,?,?,?,?,?)""",
                (cid, case_id, thesis, counter_thesis, int(unresolved), _now()),
            )
            self._ledger("Case", case_id, "CHALLENGE_RECORDED", {
                "challenge_id": cid, "unresolved": unresolved
            })
        return cid

    def build_committee_package(
        self, case_id: str, proposed_action: str, unresolved_questions: list[str]
    ) -> dict:
        positions = [dict(r) for r in self.conn.execute(
            "SELECT * FROM institutional_positions WHERE case_id=? ORDER BY created_at", (case_id,)
        )]
        challenges = [dict(r) for r in self.conn.execute(
            "SELECT * FROM challenges WHERE case_id=? ORDER BY created_at", (case_id,)
        )]
        package = {
            "case_id": case_id,
            "positions": positions,
            "challenges": challenges,
            "unresolved_questions": unresolved_questions,
            "proposed_action": proposed_action,
        }
        pid = _id("ICP")
        with self.conn:
            self.conn.execute(
                """INSERT INTO committee_packages
                (package_id,case_id,proposed_action,unresolved_questions,package_json,generated_at)
                VALUES (?,?,?,?,?,?)""",
                (pid, case_id, proposed_action, _json(unresolved_questions), _json(package), _now()),
            )
            self._ledger("Case", case_id, "COMMITTEE_PACKAGE_CREATED", {
                "package_id": pid, "challenge_count": len(challenges), "position_count": len(positions)
            })
        package["package_id"] = pid
        return package

    def decide(self, case_id: str, action: DecisionAction | str, founder_note: str) -> str:
        action = DecisionAction(action)
        current = CaseStatus(self.get_case(case_id)["status"])
        if current != CaseStatus.FOUNDER_PENDING:
            raise InvalidTransition("Founder decision requires FOUNDER_PENDING")
        did = _id("DEC")
        with self.conn:
            self.conn.execute(
                """INSERT INTO decisions
                (decision_id,case_id,action,founder_note,decided_at) VALUES (?,?,?,?,?)""",
                (did, case_id, action.value, founder_note, _now()),
            )
            self.conn.execute("DELETE FROM founder_desk WHERE case_id=?", (case_id,))
            self._ledger("Case", case_id, "FOUNDER_DECISION_RECORDED", {
                "decision_id": did, "action": action.value
            })
        self.transition(case_id, CaseStatus.DECIDED)
        return did

    def update_decision(self, decision_id: str, **changes) -> None:
        raise ImmutableRecordError(
            "InvestmentDecision is immutable; create an explicit superseding record instead"
        )

    def create_decision_plan(
        self, decision_id: str, timing_mode: TimingMode | str, condition_text: str | None = None
    ) -> str:
        timing_mode = TimingMode(timing_mode)
        decision = self.conn.execute(
            "SELECT case_id,action FROM decisions WHERE decision_id=?", (decision_id,)
        ).fetchone()
        if not decision:
            raise KeyError(decision_id)
        if decision["action"] != DecisionAction.APPROVE.value:
            raise ValueError("DecisionPlan requires an approved decision")
        pid = _id("PLN")
        with self.conn:
            self.conn.execute(
                """INSERT INTO decision_plans
                (plan_id,decision_id,timing_mode,condition_text,status,created_at)
                VALUES (?,?,?,?,?,?)""",
                (pid, decision_id, timing_mode.value, condition_text, "PLANNED", _now()),
            )
            self._ledger("Case", decision["case_id"], "DECISION_PLAN_CREATED", {
                "plan_id": pid, "timing_mode": timing_mode.value
            })
        return pid

    def record_simulated_execution(self, plan_id: str, details: dict) -> str:
        plan = self.conn.execute(
            """SELECT p.plan_id,d.case_id FROM decision_plans p
               JOIN decisions d ON d.decision_id=p.decision_id WHERE p.plan_id=?""", (plan_id,)
        ).fetchone()
        if not plan:
            raise KeyError(plan_id)
        eid = _id("EXE")
        with self.conn:
            self.conn.execute(
                """INSERT INTO execution_records
                (execution_id,plan_id,mode,status,details,executed_at)
                VALUES (?,?,?,?,?,?)""",
                (eid, plan_id, "SIMULATED", "RECORDED", _json(details), _now()),
            )
            self._ledger("Case", plan["case_id"], "SIMULATED_EXECUTION_RECORDED", {
                "execution_id": eid, "broker_side_effect": False
            })
        return eid

    def schedule_reviews(self, case_id: str, horizons=(30, 90)) -> list[str]:
        ids = []
        now = datetime.now(timezone.utc)
        with self.conn:
            for days in horizons:
                rid = _id("REV")
                due = (now + timedelta(days=days)).isoformat()
                self.conn.execute(
                    """INSERT INTO review_schedules
                    (review_id,case_id,horizon_days,due_at,status) VALUES (?,?,?,?,?)""",
                    (rid, case_id, days, due, "SCHEDULED"),
                )
                ids.append(rid)
                self._ledger("Case", case_id, "OUTCOME_REVIEW_SCHEDULED", {
                    "review_id": rid, "horizon_days": days
                })
        return ids

    def ledger(self, aggregate_id: str | None = None) -> list[dict]:
        if aggregate_id:
            rows = self.conn.execute(
                "SELECT * FROM ledger_events WHERE aggregate_id=? ORDER BY ledger_id", (aggregate_id,)
            )
        else:
            rows = self.conn.execute("SELECT * FROM ledger_events ORDER BY ledger_id")
        return [dict(r) for r in rows]

    def founder_desk(self) -> list[str]:
        return [r["case_id"] for r in self.conn.execute("SELECT case_id FROM founder_desk")]

    def briefing_queue(self) -> list[str]:
        return [r["case_id"] for r in self.conn.execute("SELECT case_id FROM founder_briefing_queue")]
