from __future__ import annotations

import os
import tempfile
import unittest

from quantrade.institutional.employee_agent import ModelAction
from quantrade.institutional.eval_harness import EmployeeEvalHarness
from quantrade.institutional.model_providers import GeminiEmployeeProvider
from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.service import InstitutionalKernel


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class EmployeeEvalHarnessTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.eval = EmployeeEvalHarness(self.kernel)

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_sealed_task_packet_never_exposes_hidden_grader_keys(self):
        task_id = self.eval.create_task(
            suite="capability-v0",
            title="Contradictory evidence fixture",
            objective="Determine what can and cannot be concluded.",
            fixture={"documents": ["A", "B"]},
            success_criteria={"must_state_uncertainty": True},
            hidden_checks={"expected_unsupported_claims": 0, "trap": "B is stale"},
        )
        packet = self.eval.task_packet(task_id)
        self.assertNotIn("hidden_checks", packet)
        self.assertNotIn("trap", str(packet))

    def test_manual_free_product_trial_is_labeled_as_manual_relay(self):
        task_id = self.eval.create_task(
            suite="ecological-v0",
            title="External product baseline",
            objective="Analyze the sealed fixture.",
            fixture={"dataset": "fixture-v1"},
            success_criteria={},
        )
        trial = self.eval.start_trial(
            task_id,
            treatment="MANUAL_RELAY",
            provider="anthropic",
            model="unknown-web-product-model",
            harness="claude-web",
        )
        self.eval.import_manual_result(
            trial,
            final_output="Bounded answer.",
            transcript_ref="local-note://trial-1",
        )
        row = self.kernel.conn.execute(
            "SELECT notes_json FROM eval_trials WHERE trial_id=?", (trial,)
        ).fetchone()
        self.assertIn('"manual_relay": true', row["notes_json"])

    def test_quantrade_trace_grader_reads_outcome_not_model_self_report(self):
        org = OrganizationRuntime(self.kernel)
        employee = org.create_employee(
            "SPMG",
            "Eval Strategy Analyst",
            "Evaluation fixture.",
            employee_id="EMP-EVAL-STRATEGY",
        )
        work_order = org.create_work_order(
            issuer_type="SYSTEM",
            issuer_id="EVAL_HARNESS",
            recipient_office="SPMG",
            recipient_employee_id=employee,
            objective="Complete bounded evaluation fixture.",
            budget={"max_tool_calls": 2},
        )
        task_id = self.eval.create_task(
            suite="runtime-v0",
            title="Outcome truthfulness",
            objective="Complete bounded evaluation fixture.",
            fixture={},
            success_criteria={"completed": True},
        )
        trial = self.eval.start_trial(
            task_id,
            treatment="QUANTRADE_INSTITUTIONAL",
            provider="scripted",
            model="ci-script-v1",
            harness="quantrade-employee-runtime",
            work_order_id=work_order,
        )

        # The model has not actually completed the WorkOrder.
        grade = self.eval.grade_quantrade_trace(trial)
        self.assertFalse(grade["assertions"]["completed"])

        task = org.create_task(
            work_order,
            "Fixture task.",
            creator_employee_id=employee,
            assignee_employee_id=employee,
        )
        org.complete_employee_work(
            employee_id=employee,
            work_order_id=work_order,
            task_id=task,
            summary="Fixture completed.",
        )
        grade2 = self.eval.grade_quantrade_trace(trial)
        self.assertTrue(grade2["assertions"]["completed"])

    def test_gemini_provider_parses_one_structured_action(self):
        captured = {}

        def fake_post(url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return _FakeResponse({
                "candidates": [{
                    "content": {
                        "parts": [{
                            "text": '{"kind":"UPDATE_PLAN","payload":{"plan":{"step":"inspect"}}}'
                        }]
                    }
                }]
            })

        provider = GeminiEmployeeProvider(
            api_key="fixture-key",
            model="gemini-fixture",
            http_post=fake_post,
        )
        action = provider.next_action({"work_order": {"objective": "fixture"}})
        self.assertEqual(ModelAction("UPDATE_PLAN", {"plan": {"step": "inspect"}}), action)
        self.assertIn("gemini-fixture:generateContent", captured["url"])
        self.assertEqual(
            "application/json",
            captured["kwargs"]["json"]["generationConfig"]["responseMimeType"],
        )

    def test_gemini_provider_refuses_live_call_without_key(self):
        provider = GeminiEmployeeProvider(api_key="", model="gemini-fixture")
        with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
            provider.next_action({})


if __name__ == "__main__":
    unittest.main()
