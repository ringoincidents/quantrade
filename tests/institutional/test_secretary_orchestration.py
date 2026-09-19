from __future__ import annotations

import json
import os
import tempfile
import unittest

from quantrade.institutional.employee_agent import (
    EmployeeAgent,
    ModelAction,
    ScriptedModelProvider,
)
from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.secretary_workstation import install_secretary_workstation
from quantrade.institutional.service import InstitutionalKernel
from quantrade.institutional.tools import ToolRegistry


class SecretaryOrchestrationTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.org = OrganizationRuntime(self.kernel)
        self.tools = ToolRegistry(self.kernel)
        self.secretary = self.org.create_employee(
            "SECRETARY",
            "Founder Secretary",
            "Translate broad Founder intent into routable work and protect Founder attention.",
            authority={
                "route_research": True,
                "create_bounded_work_orders": True,
                "live_orders": False,
                "change_policy": False,
            },
            employee_id="EMP-SECRETARY-01",
        )
        self.strategy = self.org.create_employee(
            "SPMG",
            "Strategy Analyst",
            "Discover and investigate investment candidates.",
            authority={"read_only_research": True, "live_orders": False},
            employee_id="EMP-STRATEGY-01",
        )
        install_secretary_workstation(self.tools, self.secretary, self.org)
        self.intake = self.org.create_work_order(
            issuer_type="FOUNDER",
            issuer_id="FOUNDER",
            recipient_office="SECRETARY",
            recipient_employee_id=self.secretary,
            objective=(
                "Find interesting Korean names with improving fundamentals and real "
                "buying pressure. Investigate the best ones."
            ),
            authority_scope={"research": True, "trade": False},
            budget={"max_tool_calls": 8},
        )

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_secretary_can_route_broad_founder_intent_without_microinstructions(self):
        provider = ScriptedModelProvider([
            ModelAction("UPDATE_PLAN", {"plan": {
                "intent": "candidate discovery and investigation",
                "routing": "discover staff then delegate analytical objective",
            }}),
            ModelAction("TOOL", {
                "tool_name": "org.employee_directory",
                "arguments": {"office_id": "SPMG"},
                "label": "strategy_staff",
            }),
            ModelAction("TOOL", {
                "tool_name": "org.delegate_work",
                "arguments": {
                    "parent_work_order_id": self.intake,
                    "issuer_employee_id": self.secretary,
                    "recipient_office": "SPMG",
                    "recipient_employee_id": self.strategy,
                    "objective": (
                        "Discover Korean equity candidates showing improving fundamentals "
                        "and credible buying pressure; investigate the strongest candidates, "
                        "state evidence, uncertainty and risks, and request other offices "
                        "when useful."
                    ),
                    "authority_scope": {"research": True, "trade": False},
                    "budget": {"max_tool_calls": 30},
                },
                "label": "delegated_strategy_work",
            }),
            ModelAction("FINISH", {
                "summary": "Strategy research delegated; no Founder interruption required."
            }),
        ])
        result = EmployeeAgent(
            self.kernel, self.org, self.tools, provider, max_iterations=8
        ).run(employee_id=self.secretary, work_order_id=self.intake)
        self.assertEqual("COMPLETED", result["status"])

        links = self.kernel.conn.execute(
            """SELECT child_work_order_id FROM work_order_links
            WHERE parent_work_order_id=?""",
            (self.intake,),
        ).fetchall()
        self.assertEqual(1, len(links))
        child = self.kernel.conn.execute(
            "SELECT * FROM work_orders WHERE work_order_id=?",
            (links[0]["child_work_order_id"],),
        ).fetchone()
        self.assertEqual("SPMG", child["recipient_office"])
        self.assertEqual(self.strategy, child["recipient_employee_id"])
        self.assertFalse(json.loads(child["authority_scope_json"])["trade"])
        self.assertNotIn("execute", child["objective"].lower())

    def test_strategy_employee_receives_delegated_order_in_same_org_protocol(self):
        workstation = [
            t["name"] for t in self.tools.discover(self.secretary)
        ]
        self.assertEqual(
            ["org.child_status", "org.delegate_work", "org.employee_directory"],
            workstation,
        )
        # Directly exercise the same tool the Secretary model would choose.
        out = self.tools.invoke(
            employee_id=self.secretary,
            work_order_id=self.intake,
            tool_name="org.delegate_work",
            arguments={
                "parent_work_order_id": self.intake,
                "issuer_employee_id": self.secretary,
                "recipient_office": "SPMG",
                "recipient_employee_id": self.strategy,
                "objective": "Investigate Korean candidate opportunities with evidence.",
                "authority_scope": {"research": True, "trade": False},
            },
        )
        inbox = self.org.employee_inbox(self.strategy)
        ids = [w["work_order_id"] for w in inbox["work_orders"]]
        self.assertIn(out["child_work_order_id"], ids)

    def test_secretary_can_monitor_children_without_founder_polling_departments(self):
        delegated = self.tools.invoke(
            employee_id=self.secretary,
            work_order_id=self.intake,
            tool_name="org.delegate_work",
            arguments={
                "parent_work_order_id": self.intake,
                "issuer_employee_id": self.secretary,
                "recipient_office": "SPMG",
                "recipient_employee_id": self.strategy,
                "objective": "Research candidates.",
            },
        )
        status = self.tools.invoke(
            employee_id=self.secretary,
            work_order_id=self.intake,
            tool_name="org.child_status",
            arguments={"parent_work_order_id": self.intake},
        )
        self.assertEqual(delegated["child_work_order_id"], status[0]["work_order_id"])
        self.assertEqual("OPEN", status[0]["status"])

    def test_secretary_has_no_execution_capability(self):
        names = [t["name"] for t in self.tools.discover(self.secretary)]
        self.assertTrue(all("broker" not in n and "order.submit" not in n for n in names))
        row = self.kernel.conn.execute(
            "SELECT authority_json FROM employees WHERE employee_id=?",
            (self.secretary,),
        ).fetchone()
        authority = json.loads(row["authority_json"])
        self.assertFalse(authority["live_orders"])
        self.assertFalse(authority["change_policy"])

    def test_delegation_is_reconstructable_in_parent_ledger(self):
        self.tools.invoke(
            employee_id=self.secretary,
            work_order_id=self.intake,
            tool_name="org.delegate_work",
            arguments={
                "parent_work_order_id": self.intake,
                "issuer_employee_id": self.secretary,
                "recipient_office": "SPMG",
                "recipient_employee_id": self.strategy,
                "objective": "Research candidates.",
            },
        )
        types = [e["event_type"] for e in self.kernel.ledger(self.intake)]
        self.assertIn("WORK_DELEGATED", types)
        self.assertIn("TOOL_COMPLETED", types)
        self.assertTrue(self.kernel.verify_ledger_chain())


if __name__ == "__main__":
    unittest.main()
