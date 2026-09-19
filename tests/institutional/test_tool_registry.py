from __future__ import annotations

import os
import tempfile
import unittest

from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.service import InstitutionalKernel
from quantrade.institutional.tools import (
    ToolBudgetExceeded,
    ToolDefinition,
    ToolInputError,
    ToolPermissionError,
    ToolRegistry,
)


class ToolRegistryTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.org = OrganizationRuntime(self.kernel)
        self.employee = self.org.create_employee(
            "SPMG", "Strategy Analyst", "Research candidates.",
            authority={"live_orders": False},
            employee_id="EMP-STRAT-TOOL",
        )
        self.other = self.org.create_employee(
            "IPRO", "Risk Analyst", "Independent risk review.",
            authority={"live_orders": False},
            employee_id="EMP-RISK-TOOL",
        )
        self.order = self.org.create_work_order(
            issuer_type="FOUNDER", issuer_id="FOUNDER",
            recipient_employee_id=self.employee,
            objective="Screen candidates.",
            budget={"max_tool_calls": 2},
        )
        self.registry = ToolRegistry(self.kernel)
        self.registry.register(
            ToolDefinition(
                name="universe.filter",
                description="Filter a supplied security universe with deterministic predicates.",
                input_schema={"required": ["rows", "min_sales_growth"]},
                deterministic=True,
                side_effect_class="COMPUTE",
            ),
            lambda args: [
                row for row in args["rows"]
                if row["sales_growth"] >= args["min_sales_growth"]
            ],
        )
        self.registry.register(
            ToolDefinition(
                name="broker.submit_order",
                description="Forbidden placeholder.",
                input_schema={"required": ["symbol"]},
                deterministic=False,
                side_effect_class="PRIVILEGED",
            ),
            lambda args: {"submitted": True},
        )
        self.registry.grant(self.employee, "universe.filter")

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_employee_discovers_only_granted_capabilities(self):
        tools = self.registry.discover(self.employee)
        self.assertEqual(["universe.filter"], [t["name"] for t in tools])
        self.assertTrue(tools[0]["deterministic"])
        self.assertEqual("COMPUTE", tools[0]["side_effect_class"])
        self.assertEqual([], self.registry.discover(self.other))

    def test_employee_composes_deterministic_tool_with_natural_task_context(self):
        rows = [
            {"symbol": "A", "sales_growth": 25.0},
            {"symbol": "B", "sales_growth": 12.0},
            {"symbol": "C", "sales_growth": 31.0},
        ]
        out = self.registry.invoke(
            employee_id=self.employee,
            work_order_id=self.order,
            tool_name="universe.filter",
            arguments={"rows": rows, "min_sales_growth": 20.0},
        )
        self.assertEqual(["A", "C"], [r["symbol"] for r in out])

    def test_missing_tool_input_is_explicit_error(self):
        with self.assertRaises(ToolInputError):
            self.registry.invoke(
                employee_id=self.employee,
                work_order_id=self.order,
                tool_name="universe.filter",
                arguments={"rows": []},
            )

    def test_ungranted_tool_is_denied(self):
        with self.assertRaises(ToolPermissionError):
            self.registry.invoke(
                employee_id=self.other,
                work_order_id=self.order,
                tool_name="universe.filter",
                arguments={"rows": [], "min_sales_growth": 20},
            )

    def test_privileged_tool_cannot_execute_even_if_granted(self):
        self.registry.grant(self.employee, "broker.submit_order")
        with self.assertRaises(ToolPermissionError):
            self.registry.invoke(
                employee_id=self.employee,
                work_order_id=self.order,
                tool_name="broker.submit_order",
                arguments={"symbol": "A"},
            )

    def test_work_order_tool_budget_is_enforced(self):
        args = {"rows": [], "min_sales_growth": 20}
        self.registry.invoke(
            employee_id=self.employee, work_order_id=self.order,
            tool_name="universe.filter", arguments=args,
        )
        self.registry.invoke(
            employee_id=self.employee, work_order_id=self.order,
            tool_name="universe.filter", arguments=args,
        )
        with self.assertRaises(ToolBudgetExceeded):
            self.registry.invoke(
                employee_id=self.employee, work_order_id=self.order,
                tool_name="universe.filter", arguments=args,
            )

    def test_tool_invocations_are_auditable(self):
        self.registry.invoke(
            employee_id=self.employee, work_order_id=self.order,
            tool_name="universe.filter",
            arguments={"rows": [{"symbol": "A", "sales_growth": 21}], "min_sales_growth": 20},
        )
        row = self.kernel.conn.execute(
            """SELECT status,tool_name,input_json,output_json
            FROM tool_invocations WHERE work_order_id=?""",
            (self.order,),
        ).fetchone()
        self.assertEqual("COMPLETED", row["status"])
        self.assertEqual("universe.filter", row["tool_name"])
        self.assertIsNotNone(row["input_json"])
        self.assertIsNotNone(row["output_json"])
        self.assertTrue(self.kernel.verify_ledger_chain())


if __name__ == "__main__":
    unittest.main()
