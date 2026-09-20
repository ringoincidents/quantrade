from __future__ import annotations

import json
import unittest

from quantrade.institutional.direct_agent import DirectAgentRunner
from quantrade.institutional.employee_agent import (
    EmployeeAgent,
    ModelAction,
    ScriptedModelProvider,
)
from quantrade.institutional.eval_harness import EmployeeEvalHarness
from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.service import InstitutionalKernel
from quantrade.institutional.tools import ToolRegistry


class ModelUsageTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.kernel = InstitutionalKernel(":memory:")
        self.org = OrganizationRuntime(self.kernel)
        self.tools = ToolRegistry(self.kernel)

    def tearDown(self):
        self.kernel.close()

    def _employee_and_work(self, suffix: str):
        employee = self.org.create_employee(
            "E1-LAB",
            "Evaluation Analyst",
            "Usage telemetry fixture.",
            employee_id=f"EMP-USAGE-{suffix}",
        )
        work_order = self.org.create_work_order(
            issuer_type="SYSTEM",
            issuer_id="USAGE-TEST",
            recipient_office="E1-LAB",
            recipient_employee_id=employee,
            objective="Finish the telemetry fixture.",
            budget={"max_tool_calls": 3},
        )
        return employee, work_order

    def test_direct_agent_persists_usage_and_context_size(self):
        employee, work_order = self._employee_and_work("DIRECT")
        provider = ScriptedModelProvider([
            ModelAction(
                "FINISH",
                {"summary": '{"status":"SUPPORTED"}'},
                usage={
                    "input_tokens": 100,
                    "output_tokens": 12,
                    "total_tokens": 112,
                    "provider_raw": {"fixture": True},
                },
            )
        ])
        DirectAgentRunner(
            self.kernel, self.tools, provider, max_iterations=2
        ).run(
            employee_id=employee,
            work_order_id=work_order,
            task_packet={"objective": "finish"},
        )

        row = self.kernel.conn.execute(
            """SELECT usage_json,input_context_chars FROM model_calls
            WHERE work_order_id=?""",
            (work_order,),
        ).fetchone()
        usage = json.loads(row["usage_json"])
        self.assertEqual(100, usage["input_tokens"])
        self.assertEqual(12, usage["output_tokens"])
        self.assertEqual(112, usage["total_tokens"])
        self.assertGreater(row["input_context_chars"], 0)

        harness = EmployeeEvalHarness(self.kernel)
        task = harness.create_task(
            suite="USAGE",
            title="usage",
            objective="usage",
            fixture={},
            success_criteria={},
        )
        trial = harness.start_trial(
            task,
            treatment="DIRECT_SINGLE_AGENT",
            provider="scripted",
            model="ci-script-v1",
            harness="usage-test",
            work_order_id=work_order,
        )
        trace = harness.grade_quantrade_trace(trial)
        self.assertEqual(100, trace["observed"]["model_usage"]["input_tokens"])
        self.assertEqual(12, trace["observed"]["model_usage"]["output_tokens"])
        self.assertEqual(112, trace["observed"]["model_usage"]["total_tokens"])
        self.assertGreater(
            trace["observed"]["model_usage"]["input_context_chars"], 0
        )

    def test_institutional_agent_persists_usage(self):
        employee, work_order = self._employee_and_work("INSTITUTIONAL")
        provider = ScriptedModelProvider([
            ModelAction(
                "FINISH",
                {"summary": '{"status":"SUPPORTED"}'},
                usage={
                    "input_tokens": 220,
                    "output_tokens": 20,
                    "total_tokens": 240,
                },
            )
        ])
        EmployeeAgent(
            self.kernel,
            self.org,
            self.tools,
            provider,
            max_iterations=2,
        ).run(employee_id=employee, work_order_id=work_order)

        row = self.kernel.conn.execute(
            """SELECT usage_json,input_context_chars FROM model_calls
            WHERE work_order_id=?""",
            (work_order,),
        ).fetchone()
        usage = json.loads(row["usage_json"])
        self.assertEqual(220, usage["input_tokens"])
        self.assertEqual(20, usage["output_tokens"])
        self.assertEqual(240, usage["total_tokens"])
        self.assertGreater(row["input_context_chars"], 0)


if __name__ == "__main__":
    unittest.main()
