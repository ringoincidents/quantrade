from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from .direct_agent import DirectAgentRunner
from .e1_suite import grade_e1_trial
from .employee_agent import ModelProvider
from .eval_harness import EmployeeEvalHarness
from .eval_workstation import EvalFixturePlane, install_eval_workstation
from .organization import OrganizationRuntime
from .service import InstitutionalKernel
from .tools import ToolRegistry
from .work_dispatcher import WorkDispatcher


@dataclass(frozen=True)
class E1TrialResult:
    trial_id: str
    treatment: str
    work_order_id: str
    runtime_status: str
    passed: bool
    checks: dict
    metrics: dict


def _now_for_eval_failure() -> str:
    return datetime.now(timezone.utc).isoformat()


def _employee_id(treatment: str, eval_task_id: str, seed_label: str) -> str:
    safe = seed_label.replace(" ", "-").replace("/", "-")
    return f"EMP-E1-{treatment[:6]}-{eval_task_id}-{safe}"


def run_e1_trial(
    kernel: InstitutionalKernel,
    *,
    eval_task_id: str,
    treatment: str,
    provider: ModelProvider,
    seed_label: str,
    max_iterations: int = 12,
    max_tool_calls: int = 10,
) -> E1TrialResult:
    """Run one controlled E1 trial.

    A fresh employee and fresh fixture plane are created per trial so stateful
    injected failures cannot leak between treatments or repeats.
    """
    if treatment not in {"DIRECT_SINGLE_AGENT", "QUANTRADE_INSTITUTIONAL"}:
        raise ValueError("E1 controlled runner supports only controlled treatments")

    harness = EmployeeEvalHarness(kernel)
    packet = harness.task_packet(eval_task_id)
    public_packet = harness.model_task_packet(eval_task_id)
    org = OrganizationRuntime(kernel)
    tools = ToolRegistry(kernel)
    employee = org.create_employee(
        "E1-LAB",
        "Evaluation Analyst",
        "Solve the sealed task using only authorized frozen tools.",
        authority={"research": True, "live_orders": False},
        employee_id=_employee_id(treatment, eval_task_id, seed_label),
    )
    plane = EvalFixturePlane(packet["fixture"])
    install_eval_workstation(tools, employee, plane)

    objective = (
        packet["objective"]
        + "\nSEALED PUBLIC TASK PACKET:\n"
        + json.dumps(public_packet, ensure_ascii=False, sort_keys=True)
    )
    work_order = org.create_work_order(
        issuer_type="SYSTEM",
        issuer_id="E1_EVAL_HARNESS",
        recipient_office="E1-LAB",
        recipient_employee_id=employee,
        objective=objective,
        constraints={"eval_task_id": eval_task_id, "seed_label": seed_label},
        authority_scope={"research": True, "trade": False, "policy_change": False},
        budget={"max_tool_calls": max_tool_calls},
    )
    trial = harness.start_trial(
        eval_task_id,
        treatment=treatment,
        provider=provider.provider_name,
        model=provider.model_name,
        harness=(
            "direct-agent-v0"
            if treatment == "DIRECT_SINGLE_AGENT"
            else "quantrade-institutional-v0"
        ),
        seed_label=seed_label,
        work_order_id=work_order,
    )

    try:
        if treatment == "DIRECT_SINGLE_AGENT":
            runtime = DirectAgentRunner(
                kernel, tools, provider, max_iterations=max_iterations
            ).run(
                employee_id=employee,
                work_order_id=work_order,
                task_packet=public_packet,
            )
        else:
            dispatcher = WorkDispatcher(
                kernel,
                org,
                tools,
                lambda _employee_id, _work_order_id: provider,
                max_iterations=max_iterations,
            )
            runtime = dispatcher.run_once(
                employee_id=employee,
                worker_id=f"e1:{eval_task_id}:{seed_label}",
            )

    except Exception as exc:
        with kernel.conn:
            kernel.conn.execute(
                "UPDATE work_orders SET status='FAILED',updated_at=? WHERE work_order_id=?",
                (_now_for_eval_failure(), work_order),
            )
        harness.fail_trial(
            trial,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise

    grade = grade_e1_trial(harness, trial)
    trace = harness.grade_quantrade_trace(trial)
    final_metrics = harness.finish_trial(
        trial,
        metrics={
            "e1_passed": grade["passed"],
            "runtime_status": runtime["status"],
            "model_calls": trace["observed"]["model_calls"],
            "model_usage": trace["observed"]["model_usage"],
            "tool_calls": trace["observed"]["tool_calls"],
            "tool_errors": trace["observed"]["tool_errors"],
        },
    )
    return E1TrialResult(
        trial_id=trial,
        treatment=treatment,
        work_order_id=work_order,
        runtime_status=runtime["status"],
        passed=grade["passed"],
        checks=grade["checks"],
        metrics=final_metrics,
    )
