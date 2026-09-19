from __future__ import annotations

import os
import tempfile
import unittest

from quantrade.institutional.employee_agent import (
    EmployeeAgent,
    ModelAction,
    ScriptedModelProvider,
)
from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.service import InstitutionalKernel
from quantrade.institutional.tools import ToolRegistry


class RuntimeTruthfulnessTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.org = OrganizationRuntime(self.kernel)
        self.tools = ToolRegistry(self.kernel)
        self.strategy = self.org.create_employee(
            "SPMG",
            "Strategy Analyst",
            "Own strategy research work.",
            authority={"read_only_research": True, "live_orders": False},
            employee_id="EMP-EPOCH-A-STRATEGY",
        )
        self.chart = self.org.create_employee(
            "IID-CHART",
            "Chart Analyst",
            "Own chart research work.",
            authority={"read_only_research": True, "live_orders": False},
            employee_id="EMP-EPOCH-A-CHART",
        )

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_office_work_is_claimed_delegated_waited_and_resumed(self):
        parent = self.org.create_work_order(
            issuer_type="SYSTEM",
            issuer_id="AUTONOMOUS_WORK_ENGINE",
            recipient_office="SPMG",
            objective="Investigate the current strategy coverage gap.",
            authority_scope={"research": True, "trade": False},
            budget={"max_tool_calls": 10},
        )

        self.assertEqual(parent, self.org.claim_office_work_order(self.strategy))
        assigned = self.kernel.conn.execute(
            "SELECT recipient_employee_id,status FROM work_orders WHERE work_order_id=?",
            (parent,),
        ).fetchone()
        self.assertEqual(self.strategy, assigned["recipient_employee_id"])
        self.assertEqual("ASSIGNED", assigned["status"])

        strategy_provider = ScriptedModelProvider([
            ModelAction("REQUEST_WORK", {
                "recipient_office": "IID-CHART",
                "objective": "Check whether the candidate set has abnormal technical concentration.",
                "context_refs": ["parent:strategy-coverage-gap"],
            }),
            ModelAction("FINISH", {
                "summary": "Strategy work is ready after the independent chart dependency returns."
            }),
        ])
        first = EmployeeAgent(
            self.kernel, self.org, self.tools, strategy_provider
        ).run(employee_id=self.strategy, work_order_id=parent)

        self.assertEqual("WAITING_DEPENDENCIES", first["status"])
        self.assertEqual(
            "WAITING_DEPENDENCY",
            self.kernel.conn.execute(
                "SELECT status FROM work_orders WHERE work_order_id=?", (parent,)
            ).fetchone()["status"],
        )

        claimed = self.org.claim_office_work_request(self.chart)
        self.assertIsNotNone(claimed)
        child = claimed["child_work_order_id"]

        child_result = EmployeeAgent(
            self.kernel,
            self.org,
            self.tools,
            ScriptedModelProvider([
                ModelAction("FINISH", {
                    "summary": "No abnormal technical concentration found in the bounded review."
                }),
            ]),
        ).run(employee_id=self.chart, work_order_id=child)
        self.assertEqual("COMPLETED", child_result["status"])

        request = self.kernel.conn.execute(
            "SELECT status,response_note FROM work_requests WHERE request_id=?",
            (claimed["request_id"],),
        ).fetchone()
        self.assertEqual("COMPLETED", request["status"])
        self.assertIn("No abnormal", request["response_note"])

        parent_state = self.kernel.conn.execute(
            "SELECT status FROM work_orders WHERE work_order_id=?", (parent,)
        ).fetchone()["status"]
        self.assertEqual("OPEN", parent_state)
        self.assertEqual([], self.org.pending_dependencies(parent))

        resumed = EmployeeAgent(
            self.kernel,
            self.org,
            self.tools,
            ScriptedModelProvider([
                ModelAction("FINISH", {
                    "summary": "Strategy coverage review completed with chart dependency resolved."
                }),
            ]),
        ).run(
            employee_id=self.strategy,
            work_order_id=parent,
            task_id=first["task_id"],
        )
        self.assertEqual("COMPLETED", resumed["status"])

        event_types = [e["event_type"] for e in self.kernel.ledger(parent)]
        self.assertIn("WORK_ORDER_CLAIMED", event_types)
        self.assertIn("WORK_REQUEST_CREATED", event_types)
        self.assertIn("WORK_COMPLETION_BLOCKED", event_types)
        self.assertIn("WORK_REQUEST_ACCEPTED", event_types)
        self.assertIn("WORK_REQUEST_COMPLETED", event_types)
        self.assertIn("WORK_ORDER_RESUMED", event_types)
        self.assertIn("EMPLOYEE_WORK_FINISHED", event_types)
        self.assertTrue(self.kernel.verify_ledger_chain())

    def test_employee_cannot_claim_work_from_another_office(self):
        order = self.org.create_work_order(
            issuer_type="SYSTEM",
            issuer_id="AUTONOMOUS_WORK_ENGINE",
            recipient_office="SPMG",
            objective="Strategy-only work.",
        )
        self.assertIsNone(self.org.claim_office_work_order(self.chart))
        self.assertEqual(order, self.org.claim_office_work_order(self.strategy))


if __name__ == "__main__":
    unittest.main()
