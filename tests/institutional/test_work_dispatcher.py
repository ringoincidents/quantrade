from __future__ import annotations

import os
import tempfile
import unittest

from quantrade.institutional.employee_agent import (
    ModelAction,
    ScriptedModelProvider,
)
from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.service import InstitutionalKernel
from quantrade.institutional.tools import ToolRegistry
from quantrade.institutional.work_dispatcher import WorkDispatcher


class WorkDispatcherTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.org = OrganizationRuntime(self.kernel)
        self.tools = ToolRegistry(self.kernel)
        self.strategy = self.org.create_employee(
            "SPMG",
            "Strategy Analyst",
            "Own strategy research.",
            authority={"read_only_research": True, "live_orders": False},
            employee_id="EMP-DISPATCH-STRATEGY",
        )
        self.chart = self.org.create_employee(
            "IID-CHART",
            "Chart Analyst",
            "Own technical review.",
            authority={"read_only_research": True, "live_orders": False},
            employee_id="EMP-DISPATCH-CHART",
        )

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_generated_work_runs_across_departments_and_resumes_parent(self):
        parent = self.org.create_work_order(
            issuer_type="SYSTEM",
            issuer_id="AUTONOMOUS_WORK_ENGINE",
            recipient_office="SPMG",
            objective="Investigate a strategy coverage gap.",
            authority_scope={"research": True, "trade": False},
        )

        providers = {
            self.strategy: [
                ScriptedModelProvider([
                    ModelAction("REQUEST_WORK", {
                        "recipient_office": "IID-CHART",
                        "objective": "Independently review technical concentration.",
                    }),
                    ModelAction("FINISH", {
                        "summary": "Waiting for independent chart review."
                    }),
                ]),
                ScriptedModelProvider([
                    ModelAction("FINISH", {
                        "summary": "Strategy review completed after chart dependency."
                    }),
                ]),
            ],
            self.chart: [
                ScriptedModelProvider([
                    ModelAction("FINISH", {
                        "summary": "Independent chart review completed."
                    }),
                ]),
            ],
        }

        def provider_factory(employee_id: str, work_order_id: str):
            return providers[employee_id].pop(0)

        dispatcher = WorkDispatcher(
            self.kernel, self.org, self.tools, provider_factory
        )

        first = dispatcher.run_once(
            employee_id=self.strategy, worker_id="worker-strategy-1"
        )
        self.assertEqual(parent, first["work_order_id"])
        self.assertEqual("OFFICE_QUEUE", first["source"])
        self.assertEqual("WAITING_DEPENDENCIES", first["status"])
        self.assertIsNone(self.org.current_work_order_lease(parent))

        chart = dispatcher.run_once(
            employee_id=self.chart, worker_id="worker-chart-1"
        )
        self.assertEqual("WORK_REQUEST", chart["source"])
        self.assertEqual("COMPLETED", chart["status"])

        parent_status = self.kernel.conn.execute(
            "SELECT status FROM work_orders WHERE work_order_id=?", (parent,)
        ).fetchone()["status"]
        self.assertEqual("OPEN", parent_status)

        resumed = dispatcher.run_once(
            employee_id=self.strategy, worker_id="worker-strategy-2"
        )
        self.assertEqual(parent, resumed["work_order_id"])
        self.assertEqual("ASSIGNED", resumed["source"])
        self.assertEqual("COMPLETED", resumed["status"])

        requests = self.kernel.conn.execute(
            "SELECT status FROM work_requests WHERE work_order_id=?", (parent,)
        ).fetchall()
        self.assertEqual(["COMPLETED"], [r["status"] for r in requests])
        self.assertEqual(
            "COMPLETED",
            self.kernel.conn.execute(
                "SELECT status FROM work_orders WHERE work_order_id=?", (parent,)
            ).fetchone()["status"],
        )
        self.assertIsNone(self.org.current_work_order_lease(parent))
        self.assertTrue(self.kernel.verify_ledger_chain())

    def test_dispatcher_is_idle_when_employee_has_no_work(self):
        dispatcher = WorkDispatcher(
            self.kernel,
            self.org,
            self.tools,
            lambda employee_id, work_order_id: ScriptedModelProvider([]),
        )
        result = dispatcher.run_once(
            employee_id=self.strategy, worker_id="idle-worker"
        )
        self.assertEqual("IDLE", result["status"])

    def test_failed_worker_run_retains_lease_for_expiry_based_recovery(self):
        work_order = self.org.create_work_order(
            issuer_type="SYSTEM",
            issuer_id="AUTONOMOUS_WORK_ENGINE",
            recipient_office="SPMG",
            objective="Failure recovery fixture.",
        )
        dispatcher = WorkDispatcher(
            self.kernel,
            self.org,
            self.tools,
            lambda employee_id, wid: ScriptedModelProvider([]),
            lease_seconds=300,
        )
        result = dispatcher.run_once(
            employee_id=self.strategy, worker_id="failing-worker"
        )
        self.assertEqual("FAILED", result["status"])
        self.assertEqual(work_order, result["work_order_id"])
        self.assertTrue(result["lease_retained"])
        self.assertIsNotNone(self.org.current_work_order_lease(work_order))

        types = [e["event_type"] for e in self.kernel.ledger(work_order)]
        self.assertIn("WORKER_RUN_FAILED", types)


if __name__ == "__main__":
    unittest.main()
