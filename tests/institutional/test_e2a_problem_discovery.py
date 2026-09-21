from __future__ import annotations

import json
import unittest

from quantrade.institutional.e2a_runner import run_e2a_trial
from quantrade.institutional.e2a_suite import (
    E2A_CASES,
    case_by_id,
    public_packet,
    seed_e2a_tasks,
)
from quantrade.institutional.employee_agent import ModelAction, ScriptedModelProvider
from quantrade.institutional.eval_harness import EmployeeEvalHarness
from quantrade.institutional.service import InstitutionalKernel


class E2AProblemDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.kernel = InstitutionalKernel(":memory:")
        self.harness = EmployeeEvalHarness(self.kernel)
        seed_e2a_tasks(self.harness)

    def tearDown(self):
        self.kernel.close()

    def test_public_packets_do_not_contain_private_diagnostics_memory_or_labels(self):
        for case in E2A_CASES:
            packet = public_packet(case)
            text = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            self.assertNotIn("material_issue_types", text)
            self.assertNotIn("forbidden_false_positive_types", text)
            self.assertNotIn("decoy_refs", text)
            self.assertNotIn("factor_exposures_pct", text)
            self.assertNotIn("falsification_conditions", text)
            self.assertNotIn("cash_shortfall_pct", text)
            self.assertNotIn("diversification_ratio", text)

    def test_snapshot_only_has_no_hidden_tools(self):
        provider = ScriptedModelProvider([
            ModelAction(
                "FINISH",
                {
                    "summary": json.dumps({
                        "issues": [],
                        "no_other_material_issues": True,
                    })
                },
            )
        ])
        result = run_e2a_trial(
            self.kernel,
            eval_task_id="E2A-PD-06",
            treatment="E2A_SNAPSHOT_ONLY",
            provider=provider,
            seed_label="ci",
        )
        self.assertTrue(result.passed)
        self.assertEqual(0, result.metrics["tool_calls"])

    def test_memory_treatment_can_retrieve_thesis_and_detect_break(self):
        provider = ScriptedModelProvider([
            ModelAction(
                "TOOL",
                {"tool_name": "e2.investment_memory", "arguments": {}},
            ),
            ModelAction(
                "FINISH",
                {
                    "summary": json.dumps({
                        "issues": [{
                            "issue_type": "THESIS_BREAK",
                            "priority": "HIGH",
                            "action": "INVESTIGATE",
                            "reason": "Current margin/churn breach prior falsification conditions.",
                            "evidence_refs": ["FILING-SS", "MEM-PD02"],
                        }],
                        "no_other_material_issues": True,
                    })
                },
            ),
        ])
        result = run_e2a_trial(
            self.kernel,
            eval_task_id="E2A-PD-02",
            treatment="E2A_PLUS_DIAGNOSTICS_MEMORY",
            provider=provider,
            seed_label="ci",
        )
        self.assertTrue(result.passed)
        self.assertEqual(1.0, result.observed["material_issue_recall"])
        self.assertEqual(1.0, result.observed["material_issue_precision"])

    def test_diagnostics_treatment_exposes_diagnostics_but_not_memory(self):
        provider = ScriptedModelProvider([
            ModelAction(
                "TOOL",
                {"tool_name": "e2.portfolio_diagnostics", "arguments": {}},
            ),
            ModelAction(
                "FINISH",
                {
                    "summary": json.dumps({
                        "issues": [{
                            "issue_type": "CORRELATION_SHIFT",
                            "priority": "HIGH",
                            "action": "RISK_REVIEW",
                            "reason": "Recent co-movement is materially above the historical regime.",
                            "evidence_refs": ["DIAG-PD04"],
                        }],
                        "no_other_material_issues": True,
                    })
                },
            ),
        ])
        result = run_e2a_trial(
            self.kernel,
            eval_task_id="E2A-PD-04",
            treatment="E2A_PLUS_DIAGNOSTICS",
            provider=provider,
            seed_label="ci",
        )
        self.assertTrue(result.passed)
        rows = self.kernel.conn.execute(
            """SELECT tool_name FROM tool_invocations
            WHERE work_order_id=? ORDER BY started_at""",
            (result.work_order_id,),
        ).fetchall()
        self.assertEqual(["e2.portfolio_diagnostics"], [r["tool_name"] for r in rows])

    def test_decoy_escalation_is_visible_as_failure(self):
        case = case_by_id("E2A-PD-05")
        self.assertIn("NEWS-TINY", case["hidden"]["decoy_refs"])
        provider = ScriptedModelProvider([
            ModelAction(
                "FINISH",
                {
                    "summary": json.dumps({
                        "issues": [{
                            "issue_type": "OTHER",
                            "priority": "HIGH",
                            "action": "INVESTIGATE",
                            "reason": "Dramatic CEO resignation.",
                            "evidence_refs": ["NEWS-TINY"],
                        }],
                        "no_other_material_issues": False,
                    })
                },
            )
        ])
        result = run_e2a_trial(
            self.kernel,
            eval_task_id="E2A-PD-05",
            treatment="E2A_SNAPSHOT_ONLY",
            provider=provider,
            seed_label="ci-decoy",
        )
        self.assertFalse(result.passed)
        self.assertTrue(result.observed["decoy_escalated"])
        self.assertEqual(0.0, result.observed["material_issue_recall"])


if __name__ == "__main__":
    unittest.main()
