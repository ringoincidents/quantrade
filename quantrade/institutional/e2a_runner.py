from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .direct_agent import DirectAgentRunner
from .e2a_suite import case_by_id, grade_e2a_trial, public_packet
from .employee_agent import ModelProvider
from .eval_harness import EmployeeEvalHarness
from .organization import OrganizationRuntime
from .service import InstitutionalKernel
from .tools import ToolDefinition, ToolRegistry


TREATMENTS = {
    "E2A_SNAPSHOT_ONLY",
    "E2A_PLUS_DIAGNOSTICS",
    "E2A_PLUS_DIAGNOSTICS_MEMORY",
}


@dataclass(frozen=True)
class E2ATrialResult:
    trial_id: str
    treatment: str
    work_order_id: str
    runtime_status: str
    passed: bool
    checks: dict
    observed: dict
    metrics: dict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _employee_id(treatment: str, eval_task_id: str, seed_label: str) -> str:
    safe = seed_label.replace(" ", "-").replace("/", "-")
    return f"EMP-E2A-{treatment[-8:]}-{eval_task_id}-{safe}"


def _install_capabilities(
    tools: ToolRegistry,
    *,
    employee_id: str,
    treatment: str,
    case: dict,
) -> None:
    if treatment in {
        "E2A_PLUS_DIAGNOSTICS",
        "E2A_PLUS_DIAGNOSTICS_MEMORY",
    }:
        tools.register(
            ToolDefinition(
                name="e2.portfolio_diagnostics",
                description=(
                    "Return frozen deterministic portfolio/risk diagnostics for the "
                    "current snapshot. Read-only; it does not prescribe an investment decision."
                ),
                input_schema={"type": "object", "properties": {}},
                deterministic=True,
                side_effect_class="READ_ONLY",
            ),
            lambda _args: case["diagnostics"],
        )
        tools.grant(employee_id, "e2.portfolio_diagnostics")

    if treatment == "E2A_PLUS_DIAGNOSTICS_MEMORY":
        tools.register(
            ToolDefinition(
                name="e2.investment_memory",
                description=(
                    "Return frozen prior thesis/decision/client-memory records relevant to "
                    "the current portfolio. Read-only historical institutional memory."
                ),
                input_schema={"type": "object", "properties": {}},
                deterministic=True,
                side_effect_class="READ_ONLY",
            ),
            lambda _args: case["memory"],
        )
        tools.grant(employee_id, "e2.investment_memory")


def run_e2a_trial(
    kernel: InstitutionalKernel,
    *,
    eval_task_id: str,
    treatment: str,
    provider: ModelProvider,
    seed_label: str,
    max_iterations: int = 10,
    max_tool_calls: int = 4,
) -> E2ATrialResult:
    if treatment not in TREATMENTS:
        raise ValueError(f"unsupported E2-A treatment: {treatment}")

    case = case_by_id(eval_task_id)
    packet = public_packet(case)
    harness = EmployeeEvalHarness(kernel)
    org = OrganizationRuntime(kernel)
    tool_registry = ToolRegistry(kernel)

    employee = org.create_employee(
        "E2A-LAB",
        "Portfolio Review Analyst",
        "Discover material portfolio questions without making trades.",
        authority={"research": True, "live_orders": False},
        employee_id=_employee_id(treatment, eval_task_id, seed_label),
    )
    _install_capabilities(
        tool_registry,
        employee_id=employee,
        treatment=treatment,
        case=case,
    )

    work_order = org.create_work_order(
        issuer_type="SYSTEM",
        issuer_id="E2A_EVAL_HARNESS",
        recipient_office="E2A-LAB",
        recipient_employee_id=employee,
        objective="Review the sealed portfolio snapshot for material attention-worthy issues.",
        constraints={
            "eval_task_id": eval_task_id,
            "seed_label": seed_label,
            "no_trades": True,
        },
        authority_scope={"research": True, "trade": False, "policy_change": False},
        budget={"max_tool_calls": max_tool_calls},
    )
    trial = harness.start_trial(
        eval_task_id,
        treatment=treatment,
        provider=provider.provider_name,
        model=provider.model_name,
        harness="e2a-direct-capability-stack-v0",
        seed_label=seed_label,
        work_order_id=work_order,
    )

    try:
        runtime = DirectAgentRunner(
            kernel, tool_registry, provider, max_iterations=max_iterations
        ).run(
            employee_id=employee,
            work_order_id=work_order,
            task_packet=packet,
        )
    except Exception as exc:
        with kernel.conn:
            kernel.conn.execute(
                "UPDATE work_orders SET status='FAILED',updated_at=? WHERE work_order_id=?",
                (_now(), work_order),
            )
        harness.fail_trial(
            trial,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise

    grade = grade_e2a_trial(harness, trial)
    trace = harness.grade_quantrade_trace(trial)
    final_metrics = harness.finish_trial(
        trial,
        metrics={
            "e2a_passed": grade["passed"],
            "runtime_status": runtime["status"],
            "material_issue_recall": grade["observed"]["material_issue_recall"],
            "material_issue_precision": grade["observed"]["material_issue_precision"],
            "false_research_count": grade["observed"]["false_research_count"],
            "decoy_escalated": grade["observed"]["decoy_escalated"],
            "model_calls": trace["observed"]["model_calls"],
            "model_usage": trace["observed"]["model_usage"],
            "tool_calls": trace["observed"]["tool_calls"],
            "tool_errors": trace["observed"]["tool_errors"],
        },
    )
    return E2ATrialResult(
        trial_id=trial,
        treatment=treatment,
        work_order_id=work_order,
        runtime_status=runtime["status"],
        passed=grade["passed"],
        checks=grade["checks"],
        observed=grade["observed"],
        metrics=final_metrics,
    )
