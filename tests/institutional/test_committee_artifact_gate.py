from __future__ import annotations

import json
import os
import tempfile
import unittest

from quantrade.institutional.domain import CaseStatus
from quantrade.institutional.service import InstitutionalKernel, InvalidTransition


class CommitteeArtifactGateTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def _case(self, suffix: int) -> str:
        case_id = f"QT-2026-{suffix:04d}"
        result = self.kernel.ingest_event(
            "MATERIAL_REVIEW_REQUIRED",
            "fixture",
            f"SUBJECT-{suffix}",
            {"mock": True},
            case_id=case_id,
        )
        self.kernel.transition(case_id, CaseStatus.INSTITUTIONAL_REVIEW)
        return result["case_id"]

    def _complete_artifacts(self, case_id: str, *, risk_first: bool = False) -> dict:
        evidence = self.kernel.add_evidence(
            case_id,
            "fixture-source",
            "Canonical sourced fact.",
            {"url": "fixture://evidence", "quality": "fixture"},
        )
        snapshot = self.kernel.add_snapshot(
            case_id, {"positions": [{"symbol": "MOCK", "weight": 0.1}]}
        )

        if risk_first:
            risk_assessment = self.kernel.add_risk_assessment(
                case_id,
                snapshot,
                {"concentration_pct": 10.0, "policy_breach": False},
                "fixture-risk-v1",
            )
            risk_position = self.kernel.add_position(
                case_id, "IPRO", "WITHIN_LIMITS", "Deterministic risk result."
            )
            portfolio_position = self.kernel.add_position(
                case_id, "SPMG", "KEEP", "Portfolio thesis.", [evidence]
            )
        else:
            portfolio_position = self.kernel.add_position(
                case_id, "SPMG", "KEEP", "Portfolio thesis.", [evidence]
            )
            risk_position = self.kernel.add_position(
                case_id, "IPRO", "WITHIN_LIMITS", "Deterministic risk result."
            )
            risk_assessment = self.kernel.add_risk_assessment(
                case_id,
                snapshot,
                {"concentration_pct": 10.0, "policy_breach": False},
                "fixture-risk-v1",
            )

        challenge = self.kernel.add_challenge(
            case_id,
            "Keep the position.",
            "The thesis may fail if the observed improvement reverses.",
            unresolved=True,
            office="ARU",
        )
        return {
            "evidence": evidence,
            "snapshot": snapshot,
            "risk_assessment": risk_assessment,
            "portfolio_position": portfolio_position,
            "risk_position": risk_position,
            "challenge": challenge,
        }

    def test_gate_reports_explicit_missing_artifacts_without_percentage(self):
        case_id = self._case(6101)
        readiness = self.kernel.committee_readiness(case_id)
        self.assertFalse(readiness["ready"])
        self.assertEqual(
            {
                "evidence_id",
                "portfolio_position_id",
                "risk_assessment_id",
                "risk_position_id",
                "adversarial_challenge_id",
            },
            set(readiness["missing"]),
        )
        self.assertNotIn("completion_percentage", readiness)
        with self.assertRaisesRegex(InvalidTransition, "artifact gate missing"):
            self.kernel.enter_committee(case_id)

    def test_portfolio_and_risk_can_arrive_in_either_order(self):
        first = self._case(6102)
        second = self._case(6103)
        self._complete_artifacts(first, risk_first=False)
        self._complete_artifacts(second, risk_first=True)

        self.assertTrue(self.kernel.committee_readiness(first)["ready"])
        self.assertTrue(self.kernel.committee_readiness(second)["ready"])
        self.kernel.enter_committee(first)
        self.kernel.enter_committee(second)
        self.assertEqual("COMMITTEE", self.kernel.get_case(first)["status"])
        self.assertEqual("COMMITTEE", self.kernel.get_case(second)["status"])

    def test_readiness_selects_latest_non_superseded_positions(self):
        case_id = self._case(6104)
        ids = self._complete_artifacts(case_id)
        newer_portfolio = self.kernel.add_position(
            case_id,
            "SPMG",
            "REDUCE",
            "New evidence changed the portfolio stance.",
            supersedes_id=ids["portfolio_position"],
        )
        newer_risk = self.kernel.add_position(
            case_id,
            "IPRO",
            "TIGHTEN_LIMIT",
            "Updated risk interpretation.",
            supersedes_id=ids["risk_position"],
        )

        readiness = self.kernel.committee_readiness(case_id)
        self.assertEqual(
            newer_portfolio, readiness["artifacts"]["portfolio_position_id"]
        )
        self.assertEqual(newer_risk, readiness["artifacts"]["risk_position_id"])

        history = self.kernel.conn.execute(
            """SELECT COUNT(*) c FROM institutional_positions
            WHERE case_id=?""",
            (case_id,),
        ).fetchone()["c"]
        self.assertEqual(4, history)

    def test_unresolved_aru_dissent_survives_committee_entry_without_founder_route(self):
        case_id = self._case(6105)
        ids = self._complete_artifacts(case_id)
        readiness = self.kernel.enter_committee(case_id)

        self.assertIn(ids["challenge"], readiness["unresolved_challenge_ids"])
        challenge = self.kernel.conn.execute(
            "SELECT unresolved,office FROM challenges WHERE challenge_id=?",
            (ids["challenge"],),
        ).fetchone()
        self.assertEqual(1, challenge["unresolved"])
        self.assertEqual("ARU", challenge["office"])
        self.assertEqual([], self.kernel.founder_desk())
        self.assertEqual([], self.kernel.briefing_queue())

        gate_event = [
            e for e in self.kernel.ledger(case_id)
            if e["event_type"] == "COMMITTEE_GATE_ENTERED"
        ][0]
        payload = json.loads(gate_event["payload"])
        self.assertEqual(
            ids["risk_assessment"], payload["artifacts"]["risk_assessment_id"]
        )
        self.assertEqual(
            ids["challenge"], payload["artifacts"]["adversarial_challenge_id"]
        )
        self.assertTrue(self.kernel.verify_ledger_chain())


if __name__ == "__main__":
    unittest.main()
