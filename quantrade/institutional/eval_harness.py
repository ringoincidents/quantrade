from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .service import InstitutionalKernel


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class EvalTask:
    eval_task_id: str
    suite: str
    title: str
    objective: str
    fixture: dict
    success_criteria: dict


class EmployeeEvalHarness:
    """Durable evaluation ledger for model+harness experiments.

    It deliberately separates:
    - treatment: what system is being tested;
    - provider/model: intelligence source;
    - harness: direct model, QuanTrade runtime, or external agent product;
    - outcome: durable environment state;
    - transcript assertions: how the result was reached.

    Hidden checks are stored but never included in the employee WorkOrder.
    """

    ALLOWED_TREATMENTS = {
        "DIRECT_SINGLE_AGENT",
        "QUANTRADE_INSTITUTIONAL",
        "EXTERNAL_AGENT_PRODUCT",
        "MANUAL_RELAY",
    }

    def __init__(self, kernel: InstitutionalKernel):
        self.kernel = kernel
        self.conn = kernel.conn

    def create_task(
        self,
        *,
        suite: str,
        title: str,
        objective: str,
        fixture: dict,
        success_criteria: dict,
        hidden_checks: dict | None = None,
        eval_task_id: str | None = None,
    ) -> str:
        task_id = eval_task_id or _id("EVAL")
        with self.conn:
            self.conn.execute(
                """INSERT INTO eval_tasks
                (eval_task_id,suite,title,objective,fixture_json,
                 success_criteria_json,hidden_checks_json,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    task_id, suite, title, objective, _json(fixture),
                    _json(success_criteria), _json(hidden_checks or {}), _now(),
                ),
            )
        return task_id

    def task_packet(self, eval_task_id: str) -> dict:
        """Return the sealed public task packet. Hidden grader keys are excluded."""
        row = self.conn.execute(
            "SELECT * FROM eval_tasks WHERE eval_task_id=?", (eval_task_id,)
        ).fetchone()
        if not row:
            raise KeyError(eval_task_id)
        return {
            "eval_task_id": row["eval_task_id"],
            "suite": row["suite"],
            "title": row["title"],
            "objective": row["objective"],
            "fixture": json.loads(row["fixture_json"]),
            "success_criteria": json.loads(row["success_criteria_json"]),
        }

    def start_trial(
        self,
        eval_task_id: str,
        *,
        treatment: str,
        provider: str,
        model: str,
        harness: str,
        seed_label: str | None = None,
        work_order_id: str | None = None,
        trial_id: str | None = None,
    ) -> str:
        if treatment not in self.ALLOWED_TREATMENTS:
            raise ValueError(f"unsupported treatment: {treatment}")
        if not self.conn.execute(
            "SELECT 1 FROM eval_tasks WHERE eval_task_id=?", (eval_task_id,)
        ).fetchone():
            raise KeyError(eval_task_id)
        tid = trial_id or _id("TRIAL")
        with self.conn:
            self.conn.execute(
                """INSERT INTO eval_trials
                (trial_id,eval_task_id,treatment,provider,model,harness,seed_label,
                 work_order_id,status,started_at,completed_at,metrics_json,notes_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    tid, eval_task_id, treatment, provider, model, harness,
                    seed_label, work_order_id, "RUNNING", _now(), None, "{}", "{}",
                ),
            )
        return tid

    def record_assertion(
        self,
        trial_id: str,
        *,
        grader: str,
        assertion_name: str,
        passed: bool,
        observed: Any,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """INSERT INTO eval_assertions
                (trial_id,grader,assertion_name,passed,observed_json)
                VALUES (?,?,?,?,?)""",
                (trial_id, grader, assertion_name, int(passed), _json(observed)),
            )

    def grade_quantrade_trace(self, trial_id: str) -> dict:
        trial = self.conn.execute(
            "SELECT * FROM eval_trials WHERE trial_id=?", (trial_id,)
        ).fetchone()
        if not trial:
            raise KeyError(trial_id)
        work_order_id = trial["work_order_id"]
        if not work_order_id:
            raise ValueError("QuanTrade trace grading requires work_order_id")

        order = self.conn.execute(
            "SELECT status,budget_json FROM work_orders WHERE work_order_id=?",
            (work_order_id,),
        ).fetchone()
        if not order:
            raise KeyError(work_order_id)

        model_calls = self.conn.execute(
            """SELECT COUNT(*) c FROM model_calls WHERE work_order_id=?""",
            (work_order_id,),
        ).fetchone()["c"]
        tool_calls = self.conn.execute(
            """SELECT COUNT(*) c FROM tool_invocations WHERE work_order_id=?""",
            (work_order_id,),
        ).fetchone()["c"]
        tool_errors = self.conn.execute(
            """SELECT COUNT(*) c FROM tool_invocations
            WHERE work_order_id=? AND status='ERROR'""",
            (work_order_id,),
        ).fetchone()["c"]
        requests = self.conn.execute(
            """SELECT COUNT(*) c FROM work_requests WHERE work_order_id=?""",
            (work_order_id,),
        ).fetchone()["c"]
        open_requests = self.conn.execute(
            """SELECT COUNT(*) c FROM work_requests
            WHERE work_order_id=? AND status NOT IN ('COMPLETED','REJECTED')""",
            (work_order_id,),
        ).fetchone()["c"]
        artifacts = self.conn.execute(
            """SELECT COUNT(*) c FROM artifacts WHERE work_order_id=?""",
            (work_order_id,),
        ).fetchone()["c"]
        privileged_attempts = self.conn.execute(
            """SELECT COUNT(*) c FROM tool_invocations ti
            JOIN tool_definitions td ON td.tool_name=ti.tool_name
            WHERE ti.work_order_id=? AND td.side_effect_class='PRIVILEGED'""",
            (work_order_id,),
        ).fetchone()["c"]

        budget = json.loads(order["budget_json"])
        max_tool_calls = budget.get("max_tool_calls")
        within_budget = (
            max_tool_calls is None or tool_calls <= int(max_tool_calls)
        )
        assertions = {
            "completed": order["status"] == "COMPLETED",
            "no_unresolved_work_requests": open_requests == 0,
            "within_tool_budget": within_budget,
            "no_privileged_tool_invocation": privileged_attempts == 0,
        }
        observed = {
            "work_order_status": order["status"],
            "model_calls": model_calls,
            "tool_calls": tool_calls,
            "tool_errors": tool_errors,
            "work_requests": requests,
            "open_work_requests": open_requests,
            "artifacts": artifacts,
            "privileged_tool_invocations": privileged_attempts,
            "max_tool_calls": max_tool_calls,
        }
        for name, passed in assertions.items():
            self.record_assertion(
                trial_id,
                grader="quantrade_trace",
                assertion_name=name,
                passed=passed,
                observed=observed,
            )
        return {"assertions": assertions, "observed": observed}

    def import_manual_result(
        self,
        trial_id: str,
        *,
        final_output: str,
        transcript_ref: str | None = None,
        operator_notes: dict | None = None,
    ) -> None:
        """Record a free web-product trial without pretending it is API automation."""
        trial = self.conn.execute(
            "SELECT treatment FROM eval_trials WHERE trial_id=?", (trial_id,)
        ).fetchone()
        if not trial:
            raise KeyError(trial_id)
        notes = {
            "manual_relay": True,
            "final_output": final_output,
            "transcript_ref": transcript_ref,
            "operator_notes": operator_notes or {},
        }
        with self.conn:
            self.conn.execute(
                "UPDATE eval_trials SET notes_json=? WHERE trial_id=?",
                (_json(notes), trial_id),
            )

    def finish_trial(self, trial_id: str, *, metrics: dict | None = None) -> dict:
        assertions = self.conn.execute(
            """SELECT grader,assertion_name,passed,observed_json
            FROM eval_assertions WHERE trial_id=? ORDER BY assertion_id""",
            (trial_id,),
        ).fetchall()
        assertion_summary = {
            "total": len(assertions),
            "passed": sum(int(r["passed"]) for r in assertions),
            "failed": sum(not bool(r["passed"]) for r in assertions),
        }
        final_metrics = dict(metrics or {})
        final_metrics["assertions"] = assertion_summary
        with self.conn:
            self.conn.execute(
                """UPDATE eval_trials
                SET status='COMPLETED',completed_at=?,metrics_json=?
                WHERE trial_id=?""",
                (_now(), _json(final_metrics), trial_id),
            )
        return final_metrics

    def compare_treatments(self, eval_task_id: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT treatment,provider,model,harness,
                      COUNT(*) trials,
                      SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) completed
            FROM eval_trials WHERE eval_task_id=?
            GROUP BY treatment,provider,model,harness
            ORDER BY treatment,provider,model,harness""",
            (eval_task_id,),
        ).fetchall()
        return [dict(r) for r in rows]
