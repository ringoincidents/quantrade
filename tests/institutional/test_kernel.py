from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from quantrade.institutional.domain import CaseStatus, DecisionAction, TimingMode
from quantrade.institutional.service import (
    ImmutableRecordError,
    InstitutionalKernel,
    InvalidTransition,
)


class InstitutionalKernelTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def _high_case(self, case_id="QT-2026-0041"):
        return self.kernel.ingest_event(
            "PORTFOLIO_POLICY_LIMIT_APPROACH",
            "fixture",
            "MOCK",
            {"mock": True},
            case_id=case_id,
        )["case_id"]

    def _advance_to_founder(self, case_id):
        for status in (
            CaseStatus.RESEARCH,
            CaseStatus.PORTFOLIO_REVIEW,
            CaseStatus.RISK_REVIEW,
            CaseStatus.ADVERSARIAL_REVIEW,
            CaseStatus.COMMITTEE,
            CaseStatus.FOUNDER_PENDING,
        ):
            self.kernel.transition(case_id, status)

    def test_routine_event_logs_without_case_or_founder_interrupt(self):
        result = self.kernel.ingest_event(
            "DIVIDEND_RECEIVED", "fixture", "MOCK", {"amount": 1}
        )
        self.assertIsNone(result["case_id"])
        self.assertEqual([], self.kernel.founder_desk())
        count = self.kernel.conn.execute("SELECT COUNT(*) c FROM cases").fetchone()["c"]
        self.assertEqual(0, count)
        self.assertGreaterEqual(len(self.kernel.ledger()), 2)

    def test_low_medium_high_routing(self):
        low = self.kernel.ingest_event("MATERIAL_REVIEW_LOW", "fixture", "LOW", {})
        med = self.kernel.ingest_event("MATERIAL_REVIEW_MEDIUM", "fixture", "MED", {})
        high = self.kernel.ingest_event("PORTFOLIO_POLICY_LIMIT_APPROACH", "fixture", "HIGH", {})
        self.assertEqual("LOW", self.kernel.get_case(low["case_id"])["materiality"])
        self.assertIn(med["case_id"], self.kernel.briefing_queue())
        self.assertEqual("CASE_HIGH", high["route"])
        self.assertNotIn(high["case_id"], self.kernel.founder_desk())

    def test_invalid_transition_rejected(self):
        case_id = self._high_case()
        with self.assertRaises(InvalidTransition):
            self.kernel.transition(case_id, CaseStatus.COMMITTEE)

    def test_transition_appends_ledger_atomically(self):
        case_id = self._high_case()
        before = len(self.kernel.ledger(case_id))
        self.kernel.transition(case_id, CaseStatus.RESEARCH)
        after = self.kernel.ledger(case_id)
        self.assertEqual(before + 1, len(after))
        self.assertEqual("CASE_TRANSITIONED", after[-1]["event_type"])

    def test_position_supersession_preserves_history(self):
        case_id = self._high_case()
        first = self.kernel.add_position(case_id, "SPMG", "KEEP", "first")
        second = self.kernel.add_position(
            case_id, "SPMG", "REDUCE", "new evidence", supersedes_id=first
        )
        rows = self.kernel.conn.execute(
            "SELECT position_id,supersedes_id FROM institutional_positions WHERE case_id=?",
            (case_id,),
        ).fetchall()
        self.assertEqual(2, len(rows))
        self.assertEqual(first, [r for r in rows if r["position_id"] == second][0]["supersedes_id"])

    def test_dissent_survives_committee_package(self):
        case_id = self._high_case()
        self.kernel.add_position(case_id, "SPMG", "REDUCE", "portfolio view")
        challenge = self.kernel.add_challenge(case_id, "reduce", "keep may be superior")
        package = self.kernel.build_committee_package(case_id, "REDUCE", ["uncertain catalyst"])
        self.assertTrue(any(c["challenge_id"] == challenge for c in package["challenges"]))
        self.assertEqual(["uncertain catalyst"], package["unresolved_questions"])

    def test_decision_is_immutable_and_approval_does_not_close_case(self):
        case_id = self._high_case()
        self._advance_to_founder(case_id)
        decision = self.kernel.decide(case_id, DecisionAction.APPROVE, "fixture")
        self.assertEqual(CaseStatus.DECIDED.value, self.kernel.get_case(case_id)["status"])
        self.assertIsNone(self.kernel.get_case(case_id)["closed_at"])
        with self.assertRaises(ImmutableRecordError):
            self.kernel.update_decision(decision, founder_note="rewrite")

    def test_founder_research_request_returns_case_to_research(self):
        case_id = self._high_case()
        self._advance_to_founder(case_id)
        decision = self.kernel.decide(case_id, DecisionAction.RESEARCH, "investigate uncertainty")
        self.assertEqual(CaseStatus.RESEARCH.value, self.kernel.get_case(case_id)["status"])
        self.assertNotIn(case_id, self.kernel.founder_desk())
        row = self.kernel.conn.execute(
            "SELECT action FROM decisions WHERE decision_id=?", (decision,)
        ).fetchone()
        self.assertEqual("RESEARCH", row["action"])

    def test_plan_modes_and_simulated_execution_have_no_broker_path(self):
        for idx, mode in enumerate(TimingMode, start=1):
            case_id = self._high_case(f"QT-2026-{1000+idx}")
            self._advance_to_founder(case_id)
            decision = self.kernel.decide(case_id, DecisionAction.APPROVE, "fixture")
            self.kernel.transition(case_id, CaseStatus.DECISION_MANAGEMENT)
            plan = self.kernel.create_decision_plan(decision, mode, "fixture condition")
            self.kernel.transition(case_id, CaseStatus.EXECUTION_PENDING)
            execution = self.kernel.record_simulated_execution(plan, {"mock": True})
            row = self.kernel.conn.execute(
                "SELECT mode FROM execution_records WHERE execution_id=?", (execution,)
            ).fetchone()
            self.assertEqual("SIMULATED", row["mode"])

    def test_reviews_and_reload_preserve_history(self):
        case_id = self._high_case()
        self._advance_to_founder(case_id)
        decision = self.kernel.decide(case_id, DecisionAction.APPROVE, "fixture")
        self.kernel.transition(case_id, CaseStatus.DECISION_MANAGEMENT)
        plan = self.kernel.create_decision_plan(decision, TimingMode.CONDITIONAL, "fixture")
        self.kernel.transition(case_id, CaseStatus.EXECUTION_PENDING)
        self.kernel.record_simulated_execution(plan, {"mock": True})
        self.kernel.transition(case_id, CaseStatus.OUTCOME_TRACKING)
        reviews = self.kernel.schedule_reviews(case_id)
        ledger_before = self.kernel.ledger(case_id)
        self.assertEqual(2, len(reviews))

        self.kernel.close()
        self.kernel = InstitutionalKernel(self.path)
        self.assertEqual(CaseStatus.OUTCOME_TRACKING.value, self.kernel.get_case(case_id)["status"])
        self.assertEqual(len(ledger_before), len(self.kernel.ledger(case_id)))
        horizons = {
            r["horizon_days"]
            for r in self.kernel.conn.execute(
                "SELECT horizon_days FROM review_schedules WHERE case_id=?", (case_id,)
            )
        }
        self.assertEqual({30, 90}, horizons)

    def test_sqlite_foreign_keys_enabled(self):
        enabled = self.kernel.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(1, enabled)


if __name__ == "__main__":
    unittest.main()
