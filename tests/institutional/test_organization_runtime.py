from __future__ import annotations

import json
import os
import tempfile
import unittest

from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.service import InstitutionalKernel


class OrganizationRuntimeTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.org = OrganizationRuntime(self.kernel)
        self.strategy = self.org.create_employee(
            "SPMG",
            "Strategy Analyst",
            "Discover and evaluate portfolio candidates.",
            authority={"read_only_research": True, "live_orders": False},
            workstation_profile={"profile": "strategy"},
            employee_id="EMP-STRATEGY-01",
        )
        self.chart = self.org.create_employee(
            "IID-CHART",
            "Chart Analyst",
            "Perform technical and event-study analysis.",
            authority={"read_only_research": True, "live_orders": False},
            workstation_profile={"profile": "chart"},
            employee_id="EMP-CHART-01",
        )

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_broad_work_order_can_be_decomposed_by_employee(self):
        wid = self.org.create_work_order(
            issuer_type="FOUNDER",
            issuer_id="FOUNDER",
            recipient_employee_id=self.strategy,
            recipient_office="SPMG",
            objective="Find Korean names with improving fundamentals and real buying pressure.",
            authority_scope={"research": True, "trade": False},
            budget={"max_tool_calls": 30},
        )
        task = self.org.create_task(
            wid,
            "Discover available financial and flow data, then design a screen.",
            creator_employee_id=self.strategy,
            assignee_employee_id=self.strategy,
            plan={"steps": ["discover schemas", "screen", "validate", "report"]},
        )
        row = self.kernel.conn.execute(
            "SELECT objective,plan_json FROM tasks WHERE task_id=?", (task,)
        ).fetchone()
        self.assertIn("design a screen", row["objective"])
        self.assertEqual(
            ["discover schemas", "screen", "validate", "report"],
            json.loads(row["plan_json"])["steps"],
        )

    def test_employee_can_revise_plan_without_new_bespoke_command(self):
        wid = self.org.create_work_order(
            issuer_type="FOUNDER", issuer_id="FOUNDER",
            recipient_employee_id=self.strategy,
            objective="Screen Korean equities."
        )
        task = self.org.create_task(
            wid, "Build candidate screen",
            creator_employee_id=self.strategy, assignee_employee_id=self.strategy,
            plan={"filters": ["sales_growth", "op_margin", "foreign_flow"]},
        )
        self.org.update_task_plan(
            task,
            {"filters": [
                "sales_growth", "op_margin", "foreign_flow",
                "institution_flow", "pension_flow",
            ]},
        )
        row = self.kernel.conn.execute(
            "SELECT plan_json FROM tasks WHERE task_id=?", (task,)
        ).fetchone()
        filters = json.loads(row["plan_json"])["filters"]
        self.assertIn("institution_flow", filters)
        self.assertIn("pension_flow", filters)

    def test_cross_office_request_uses_common_protocol(self):
        wid = self.org.create_work_order(
            issuer_type="FOUNDER", issuer_id="FOUNDER",
            recipient_employee_id=self.strategy,
            objective="Investigate candidate set."
        )
        task = self.org.create_task(
            wid, "Evaluate candidates",
            creator_employee_id=self.strategy, assignee_employee_id=self.strategy,
        )
        request = self.org.create_work_request(
            wid,
            self.strategy,
            "IID-CHART",
            "Compare daily/weekly technical structure of the candidate set.",
            task_id=task,
            recipient_employee_id=self.chart,
            context_refs=["ART-CANDIDATE-SET"],
        )
        inbox = self.org.employee_inbox(self.chart)
        self.assertEqual(request, inbox["work_requests"][0]["request_id"])
        self.org.respond_work_request(
            request, status="COMPLETED",
            response_note="Technical comparison artifact produced.",
        )
        row = self.kernel.conn.execute(
            "SELECT status,response_note FROM work_requests WHERE request_id=?",
            (request,),
        ).fetchone()
        self.assertEqual("COMPLETED", row["status"])

    def test_workspace_persists_employee_work_context(self):
        wid = self.org.create_work_order(
            issuer_type="FOUNDER", issuer_id="FOUNDER",
            recipient_employee_id=self.strategy,
            objective="Research a screen."
        )
        wsid = self.org.get_or_create_workspace(self.strategy, wid)
        self.org.save_workspace_state(wsid, {
            "hypothesis": "growth plus buying pressure",
            "candidate_set_ref": "ART-001",
            "failed_approaches": ["raw PER filter"],
        })
        same = self.org.get_or_create_workspace(self.strategy, wid)
        self.assertEqual(wsid, same)
        row = self.kernel.conn.execute(
            "SELECT state_json FROM workspaces WHERE workspace_id=?", (wsid,)
        ).fetchone()
        state = json.loads(row["state_json"])
        self.assertEqual("ART-001", state["candidate_set_ref"])
        self.assertIn("raw PER filter", state["failed_approaches"])

    def test_artifact_is_not_automatically_evidence_or_decision(self):
        wid = self.org.create_work_order(
            issuer_type="FOUNDER", issuer_id="FOUNDER",
            recipient_employee_id=self.strategy,
            objective="Produce candidate table."
        )
        aid = self.org.create_artifact(
            wid, "TABLE", "Candidate screen",
            producer_employee_id=self.strategy,
            content_ref="workspace://candidate_screen.csv",
            metadata={"rows": 5},
        )
        self.assertTrue(aid.startswith("ART-"))
        evidence = self.kernel.conn.execute("SELECT COUNT(*) c FROM evidence").fetchone()["c"]
        decisions = self.kernel.conn.execute("SELECT COUNT(*) c FROM decisions").fetchone()["c"]
        self.assertEqual(0, evidence)
        self.assertEqual(0, decisions)

    def test_organization_activity_is_reconstructable_from_ledger(self):
        wid = self.org.create_work_order(
            issuer_type="FOUNDER", issuer_id="FOUNDER",
            recipient_employee_id=self.strategy,
            objective="Research independently."
        )
        self.org.create_task(
            wid, "Plan research",
            creator_employee_id=self.strategy, assignee_employee_id=self.strategy,
        )
        self.org.create_artifact(
            wid, "MEMO", "Research note", producer_employee_id=self.strategy
        )
        events = self.kernel.ledger(wid)
        types = [e["event_type"] for e in events]
        self.assertEqual(
            ["WORK_ORDER_CREATED", "TASK_CREATED", "ARTIFACT_CREATED"],
            types,
        )
        self.assertTrue(self.kernel.verify_ledger_chain())

    def test_employee_authority_explicitly_denies_live_orders(self):
        row = self.kernel.conn.execute(
            "SELECT authority_json FROM employees WHERE employee_id=?",
            (self.strategy,),
        ).fetchone()
        authority = json.loads(row["authority_json"])
        self.assertFalse(authority["live_orders"])


if __name__ == "__main__":
    unittest.main()
