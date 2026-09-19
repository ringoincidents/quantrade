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
from quantrade.institutional.service import InstitutionalKernel
from quantrade.institutional.strategy_workstation import (
    StrategyDataPlane,
    install_strategy_workstation,
    synthetic_korea_strategy_sources,
)
from quantrade.institutional.tools import ToolRegistry


BASE_QUERY = {
    "sources": ["securities", "fundamentals", "investor_flows_10d"],
    "conditions": [
        {"field": "market", "op": "in", "value": ["KOSPI", "KOSDAQ"]},
        {"field": "sales_growth_yoy_pct", "op": ">", "value": 20.0},
        {"field": "op_margin_q_minus_1", "op": ">", "value": {"field": "op_margin_q_minus_2"}},
        {"field": "op_margin_q", "op": ">", "value": {"field": "op_margin_q_minus_1"}},
        {"field": "foreign_net_buy", "op": ">", "value": 0.0},
    ],
    "select": [
        "symbol", "name", "market", "sector", "sales_growth_yoy_pct",
        "op_margin_q_minus_2", "op_margin_q_minus_1", "op_margin_q",
        "foreign_net_buy", "institution_net_buy", "pension_net_buy",
    ],
    "sort": {"field": "sales_growth_yoy_pct", "direction": "desc"},
}

FOLLOWUP_QUERY = {
    **BASE_QUERY,
    "conditions": BASE_QUERY["conditions"] + [
        {"field": "institution_net_buy", "op": ">", "value": 0.0},
        {"field": "pension_net_buy", "op": ">", "value": 0.0},
    ],
}


class RecordingScriptedProvider(ScriptedModelProvider):
    def __init__(self, actions):
        super().__init__(actions)
        self.contexts = []

    def next_action(self, context):
        self.contexts.append(context)
        return super().next_action(context)


class StrategyEmployeeTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.org = OrganizationRuntime(self.kernel)
        self.tools = ToolRegistry(self.kernel)
        self.strategy = self.org.create_employee(
            "SPMG",
            "Strategy Analyst",
            "Discover and investigate portfolio candidates using authorized evidence and deterministic tools.",
            authority={"read_only_research": True, "internal_requests": True, "live_orders": False},
            model_profile={"provider": "replaceable"},
            workstation_profile={"profile": "strategy-v1"},
            employee_id="EMP-STRATEGY-P13C",
        )
        self.chart = self.org.create_employee(
            "IID-CHART",
            "Chart Analyst",
            "Provide independent technical structure analysis.",
            authority={"read_only_research": True, "live_orders": False},
            employee_id="EMP-CHART-P13C",
        )
        install_strategy_workstation(
            self.tools,
            self.strategy,
            StrategyDataPlane(synthetic_korea_strategy_sources()),
        )
        self.order = self.org.create_work_order(
            issuer_type="FOUNDER",
            issuer_id="FOUNDER",
            recipient_office="SPMG",
            recipient_employee_id=self.strategy,
            objective=(
                "Find KOSPI/KOSDAQ names with >20% YoY sales growth, two consecutive "
                "quarters of improving operating margin, and foreign net buying over "
                "the last 10 sessions. Add reasons and risks."
            ),
            authority_scope={"research": True, "trade": False},
            budget={"max_tool_calls": 10},
        )

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_generic_query_solves_screen_without_bespoke_screen_function(self):
        result = self.tools.invoke(
            employee_id=self.strategy,
            work_order_id=self.order,
            tool_name="data.query",
            arguments=BASE_QUERY,
        )
        self.assertEqual(["KRX002", "KRX001", "KRX003"], [r["symbol"] for r in result])
        tool_names = [t["name"] for t in self.tools.discover(self.strategy)]
        self.assertEqual(["data.catalog", "data.query"], tool_names)
        self.assertNotIn("screen.sales_growth_foreign_buy", tool_names)

    def test_employee_runs_broad_objective_through_reasoning_contract(self):
        provider = RecordingScriptedProvider([
            ModelAction("UPDATE_PLAN", {"plan": {
                "steps": [
                    "discover data", "query fundamentals and flows",
                    "inspect candidates", "request technical review", "report",
                ]
            }}),
            ModelAction("TOOL", {"tool_name": "data.catalog", "arguments": {}, "label": "catalog"}),
            ModelAction("TOOL", {"tool_name": "data.query", "arguments": BASE_QUERY, "label": "initial_candidates"}),
            ModelAction("SAVE_WORKSPACE", {"state": {
                "hypothesis": "fundamental improvement plus persistent buying pressure",
                "candidate_set_label": "initial_candidates",
                "known_limitations": ["fixture data only; no live KRX provider"],
            }}),
            ModelAction("REQUEST_WORK", {
                "recipient_office": "IID-CHART",
                "recipient_employee_id": self.chart,
                "objective": "Compare daily and weekly technical structure for the current candidates.",
                "context_refs": ["workspace:initial_candidates"],
            }),
            ModelAction("CREATE_ARTIFACT", {
                "artifact_type": "TABLE",
                "title": "Initial Korean growth + flow candidate screen",
                "content_ref": "workspace:initial_candidates",
                "metadata": {"synthetic": True, "not_investment_decision": True},
            }),
            ModelAction("FINISH", {"summary": "Initial candidate screen completed; technical review requested."}),
        ])
        agent = EmployeeAgent(self.kernel, self.org, self.tools, provider, max_iterations=10)
        result = agent.run(employee_id=self.strategy, work_order_id=self.order)
        self.assertEqual("WAITING_DEPENDENCIES", result["status"])
        self.assertTrue(any(b["kind"] == "WORK_REQUEST" for b in result["blockers"]))

        ws = self.kernel.conn.execute(
            "SELECT state_json FROM workspaces WHERE employee_id=? AND work_order_id=?",
            (self.strategy, self.order),
        ).fetchone()
        state = json.loads(ws["state_json"])
        query_outputs = [
            item["output"] for item in state["tool_outputs"]
            if item.get("label") == "initial_candidates"
        ]
        self.assertEqual(3, len(query_outputs[0]))

        req = self.kernel.conn.execute(
            "SELECT recipient_office,status FROM work_requests WHERE work_order_id=?",
            (self.order,),
        ).fetchone()
        self.assertEqual("IID-CHART", req["recipient_office"])
        self.assertEqual("OPEN", req["status"])
        order_status = self.kernel.conn.execute(
            "SELECT status FROM work_orders WHERE work_order_id=?", (self.order,)
        ).fetchone()["status"]
        self.assertEqual("WAITING_DEPENDENCY", order_status)

        self.assertIn("data.catalog", [t["name"] for t in provider.contexts[0]["available_tools"]])
        model_calls = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM model_calls WHERE work_order_id=?", (self.order,)
        ).fetchone()["c"]
        self.assertEqual(7, model_calls)

    def test_founder_followup_reuses_same_work_context_and_narrows_query(self):
        initial_provider = ScriptedModelProvider([
            ModelAction("TOOL", {"tool_name": "data.query", "arguments": BASE_QUERY, "label": "initial_candidates"}),
            ModelAction("SAVE_WORKSPACE", {"state": {"candidate_set_label": "initial_candidates"}}),
            ModelAction("FINISH", {"summary": "Initial screen done."}),
        ])
        agent = EmployeeAgent(self.kernel, self.org, self.tools, initial_provider)
        first = agent.run(employee_id=self.strategy, work_order_id=self.order)

        self.org.send_message(
            sender_type="FOUNDER",
            sender_id="FOUNDER",
            recipient_type="EMPLOYEE",
            recipient_id=self.strategy,
            body="Keep only names also net-bought by institutions and pension funds.",
            work_order_id=self.order,
            task_id=first["task_id"],
        )
        follow_provider = RecordingScriptedProvider([
            ModelAction("UPDATE_PLAN", {"plan": {
                "follow_up": "add institution and pension net-buy predicates to existing screen"
            }}),
            ModelAction("TOOL", {"tool_name": "data.query", "arguments": FOLLOWUP_QUERY, "label": "refined_candidates"}),
            ModelAction("SAVE_WORKSPACE", {"state": {"candidate_set_label": "refined_candidates"}}),
            ModelAction("CREATE_ARTIFACT", {
                "artifact_type": "TABLE",
                "title": "Refined candidate screen",
                "content_ref": "workspace:refined_candidates",
                "metadata": {"synthetic": True},
            }),
            ModelAction("FINISH", {"summary": "Existing screen refined with institution and pension buying."}),
        ])
        follow_agent = EmployeeAgent(self.kernel, self.org, self.tools, follow_provider)
        second = follow_agent.run(
            employee_id=self.strategy,
            work_order_id=self.order,
            task_id=first["task_id"],
        )
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertTrue(any(
            "pension funds" in m["body"] for m in follow_provider.contexts[0]["messages"]
        ))

        ws = self.kernel.conn.execute(
            "SELECT state_json FROM workspaces WHERE employee_id=? AND work_order_id=?",
            (self.strategy, self.order),
        ).fetchone()
        state = json.loads(ws["state_json"])
        refined = [
            item["output"] for item in state["tool_outputs"]
            if item.get("label") == "refined_candidates"
        ][0]
        self.assertEqual(["KRX001", "KRX003"], [r["symbol"] for r in refined])

    def test_model_never_gets_ungranted_or_broker_tool(self):
        provider = RecordingScriptedProvider([
            ModelAction("FINISH", {"summary": "No work."}),
        ])
        agent = EmployeeAgent(self.kernel, self.org, self.tools, provider)
        agent.run(employee_id=self.strategy, work_order_id=self.order)
        names = [t["name"] for t in provider.contexts[0]["available_tools"]]
        self.assertEqual(["data.catalog", "data.query"], names)
        self.assertFalse(provider.contexts[0]["employee"]["authority"]["live_orders"])

    def test_model_and_tool_activity_are_reconstructable(self):
        provider = ScriptedModelProvider([
            ModelAction("TOOL", {"tool_name": "data.catalog", "arguments": {}}),
            ModelAction("FINISH", {"summary": "Catalog inspected."}),
        ])
        EmployeeAgent(self.kernel, self.org, self.tools, provider).run(
            employee_id=self.strategy, work_order_id=self.order
        )
        types = [e["event_type"] for e in self.kernel.ledger(self.order)]
        self.assertIn("MODEL_ACTION", types)
        self.assertIn("TOOL_COMPLETED", types)
        self.assertIn("EMPLOYEE_WORK_FINISHED", types)
        self.assertTrue(self.kernel.verify_ledger_chain())


if __name__ == "__main__":
    unittest.main()
