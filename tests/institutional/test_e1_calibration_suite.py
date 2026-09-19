from __future__ import annotations

import os
import tempfile
import unittest

from quantrade.institutional.e1_runner import run_e1_trial
from quantrade.institutional.e1_suite import E1_TASKS, seed_e1_tasks
from quantrade.institutional.employee_agent import ModelAction, ScriptedModelProvider
from quantrade.institutional.eval_harness import EmployeeEvalHarness
from quantrade.institutional.service import InstitutionalKernel


class E1CalibrationSuiteTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.harness = EmployeeEvalHarness(self.kernel)
        seed_e1_tasks(self.harness)

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_six_public_packets_are_seeded_without_hidden_checks(self):
        self.assertEqual(6, len(E1_TASKS))
        for task in E1_TASKS:
            packet = self.harness.task_packet(task["eval_task_id"])
            self.assertNotIn("hidden_checks", packet)
            self.assertNotIn("expected_answer", str(packet))

    def _calc_provider(self):
        return ScriptedModelProvider([
            ModelAction("TOOL", {
                "tool_name": "finance.growth_pct",
                "arguments": {"start": 120, "end": 150},
            }),
            ModelAction("FINISH", {
                "summary": (
                    '{"answer":25.0,"status":"SUPPORTED",'
                    '"evidence_ids":[],"uncertainty":null}'
                )
            }),
        ])

    def test_same_scripted_brain_passes_direct_and_institutional_calc_task(self):
        direct = run_e1_trial(
            self.kernel,
            eval_task_id="E1-03",
            treatment="DIRECT_SINGLE_AGENT",
            provider=self._calc_provider(),
            seed_label="direct-1",
        )
        institutional = run_e1_trial(
            self.kernel,
            eval_task_id="E1-03",
            treatment="QUANTRADE_INSTITUTIONAL",
            provider=self._calc_provider(),
            seed_label="institutional-1",
        )
        self.assertTrue(direct.passed)
        self.assertTrue(institutional.passed)

        rows = self.kernel.conn.execute(
            """SELECT treatment,metrics_json FROM eval_trials
            WHERE eval_task_id='E1-03' ORDER BY treatment"""
        ).fetchall()
        self.assertEqual(2, len(rows))
        self.assertEqual(
            {"DIRECT_SINGLE_AGENT", "QUANTRADE_INSTITUTIONAL"},
            {r["treatment"] for r in rows},
        )

    def test_missing_data_task_rewards_unknown_not_activity(self):
        provider = ScriptedModelProvider([
            ModelAction("TOOL", {
                "tool_name": "eval.catalog",
                "arguments": {},
            }),
            ModelAction("TOOL", {
                "tool_name": "eval.document",
                "arguments": {"doc_id": "LIQUIDITY-NOTE"},
            }),
            ModelAction("FINISH", {
                "summary": (
                    '{"answer":null,"status":"UNKNOWN",'
                    '"evidence_ids":["LIQUIDITY-NOTE"],'
                    '"uncertainty":"2027 maturity is absent from frozen evidence"}'
                )
            }),
        ])
        result = run_e1_trial(
            self.kernel,
            eval_task_id="E1-04",
            treatment="QUANTRADE_INSTITUTIONAL",
            provider=provider,
            seed_label="unknown-1",
        )
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
