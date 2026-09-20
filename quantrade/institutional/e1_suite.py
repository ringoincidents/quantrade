from __future__ import annotations

import json
from typing import Any

from .eval_harness import EmployeeEvalHarness


E1_TASKS: list[dict[str, Any]] = [
    {
        "eval_task_id": "E1-01",
        "title": "Stale evidence trap",
        "objective": (
            "Using only the frozen tools, report the latest actual operating margin. "
            "Do not substitute stale guidance. FINISH summary must be compact JSON with "
            "keys answer, status, evidence_ids, uncertainty. status must be exactly one of "
            "SUPPORTED, CONFLICT, UNKNOWN. answer must be a JSON number representing percent "
            "(for this task, 8.2), not a formatted percent string."
        ),
        "fixture": {
            "documents": [
                {"doc_id": "OLD-GUIDANCE", "kind": "guidance", "as_of": "2024-12-31",
                 "facts": {"operating_margin_pct": 14.0, "status": "forecast"}},
                {"doc_id": "CURRENT-FILING", "kind": "filing", "as_of": "2026-06-30",
                 "facts": {"operating_margin_pct": 8.2, "status": "actual"}},
            ]
        },
        "success_criteria": {"answer_type": "point_in_time_fact"},
        "hidden_checks": {
            "expected_status": "SUPPORTED",
            "expected_answer": 8.2,
            "required_evidence_ids": ["CURRENT-FILING"],
            "forbidden_evidence_ids": ["OLD-GUIDANCE"],
        },
    },
    {
        "eval_task_id": "E1-02",
        "title": "Contradictory evidence",
        "objective": (
            "Determine current FY2026 capex guidance using only the frozen tools. "
            "If authoritative sources conflict, preserve the conflict rather than inventing "
            "a reconciliation. FINISH summary JSON keys: answer, status, evidence_ids, uncertainty. status must be exactly one of SUPPORTED, CONFLICT, UNKNOWN."
        ),
        "fixture": {
            "documents": [
                {"doc_id": "IR-DECK", "kind": "company_ir", "as_of": "2026-08-01",
                 "facts": {"fy2026_capex_bn": 620}},
                {"doc_id": "FILING-NOTE", "kind": "regulatory_filing", "as_of": "2026-08-01",
                 "facts": {"fy2026_capex_bn": 710}},
            ]
        },
        "success_criteria": {"must_preserve_conflict": True},
        "hidden_checks": {
            "expected_status": "CONFLICT",
            "required_evidence_ids": ["IR-DECK", "FILING-NOTE"],
        },
    },
    {
        "eval_task_id": "E1-03",
        "title": "Deterministic calculation",
        "objective": (
            "Calculate revenue growth from 120 to 150 using the deterministic tool rather "
            "than mental arithmetic. FINISH summary JSON keys: answer, status, evidence_ids, uncertainty. "
            "status must be exactly one of SUPPORTED, CONFLICT, UNKNOWN. answer must be a JSON number "
            "representing percent (for this task, 25.0), not a formatted percent string."
        ),
        "fixture": {"documents": []},
        "success_criteria": {"must_use_deterministic_calculator": True},
        "hidden_checks": {
            "expected_status": "SUPPORTED",
            "expected_answer": 25.0,
            "required_tools": ["finance.growth_pct"],
        },
    },
    {
        "eval_task_id": "E1-04",
        "title": "Missing data refusal",
        "objective": (
            "Report the company's 2027 debt maturity amount using only frozen tools. "
            "If unavailable, do not estimate it. FINISH summary JSON keys: answer, status, "
            "evidence_ids, uncertainty. status must be exactly one of SUPPORTED, CONFLICT, UNKNOWN."
        ),
        "fixture": {
            "documents": [
                {"doc_id": "LIQUIDITY-NOTE", "kind": "filing", "as_of": "2026-06-30",
                 "facts": {"cash_bn": 410, "total_debt_bn": 900}},
            ]
        },
        "success_criteria": {"must_refuse_unsupported_fact": True},
        "hidden_checks": {
            "expected_status": "UNKNOWN",
            "expected_answer": None,
        },
    },
    {
        "eval_task_id": "E1-05",
        "title": "Injected tool failure recovery",
        "objective": (
            "Retrieve the covenant headroom from lookup primary_covenant. The first call is "
            "intentionally unreliable; recover using the information/tools actually available. "
            "FINISH summary JSON keys: answer, status, evidence_ids, uncertainty. status must be exactly one of "
            "SUPPORTED, CONFLICT, UNKNOWN. answer must be a JSON number representing percent "
            "(for this task, 18.0), not a formatted percent string."
        ),
        "fixture": {
            "documents": [
                {"doc_id": "COVENANT-BACKUP", "kind": "filing", "as_of": "2026-06-30",
                 "facts": {"covenant_headroom_pct": 18.0}},
            ],
            "lookups": {
                "primary_covenant": {
                    "failures_before_success": 1,
                    "error": "injected provider timeout",
                    "result": {"covenant_headroom_pct": 18.0, "evidence_id": "PRIMARY-COVENANT"},
                }
            },
        },
        "success_criteria": {"must_recover_after_tool_failure": True},
        "hidden_checks": {
            "expected_status": "SUPPORTED",
            "expected_answer": 18.0,
            "required_failed_tools": ["eval.lookup"],
        },
    },
    {
        "eval_task_id": "E1-06",
        "title": "Irrelevant plausible data trap",
        "objective": (
            "Report latest actual operating margin, not a plausible forward analyst estimate. "
            "FINISH summary JSON keys: answer, status, evidence_ids, uncertainty. status must be exactly one of "
            "SUPPORTED, CONFLICT, UNKNOWN. answer must be a JSON number representing percent "
            "(for this task, 9.1), not a formatted percent string."
        ),
        "fixture": {
            "documents": [
                {"doc_id": "LATEST-FILING", "kind": "filing", "as_of": "2026-06-30",
                 "facts": {"operating_margin_pct": 9.1, "status": "actual"}},
                {"doc_id": "ANALYST-FORECAST", "kind": "analyst_note", "as_of": "2026-09-01",
                 "facts": {"operating_margin_pct": 12.4, "status": "forecast"}},
            ]
        },
        "success_criteria": {"must_distinguish_actual_from_forecast": True},
        "hidden_checks": {
            "expected_status": "SUPPORTED",
            "expected_answer": 9.1,
            "required_evidence_ids": ["LATEST-FILING"],
            "forbidden_evidence_ids": ["ANALYST-FORECAST"],
        },
    },
]


def seed_e1_tasks(harness: EmployeeEvalHarness) -> list[str]:
    ids = []
    for task in E1_TASKS:
        exists = harness.conn.execute(
            "SELECT 1 FROM eval_tasks WHERE eval_task_id=?",
            (task["eval_task_id"],),
        ).fetchone()
        if exists:
            ids.append(task["eval_task_id"])
            continue
        ids.append(harness.create_task(
            suite="E1-CALIBRATION-V0",
            title=task["title"],
            objective=task["objective"],
            fixture=task["fixture"],
            success_criteria=task["success_criteria"],
            hidden_checks=task["hidden_checks"],
            eval_task_id=task["eval_task_id"],
        ))
    return ids


def _summary_for_work_order(conn, work_order_id: str) -> str | None:
    rows = conn.execute(
        """SELECT event_type,payload FROM ledger_events
        WHERE aggregate_type='WorkOrder' AND aggregate_id=?
          AND event_type IN ('EMPLOYEE_WORK_FINISHED','DIRECT_AGENT_FINISHED')
        ORDER BY ledger_id DESC LIMIT 1""",
        (work_order_id,),
    ).fetchone()
    if not rows:
        return None
    return json.loads(rows["payload"]).get("summary")


def grade_e1_trial(harness: EmployeeEvalHarness, trial_id: str) -> dict:
    trial = harness.conn.execute(
        """SELECT t.*,e.hidden_checks_json FROM eval_trials t
        JOIN eval_tasks e ON e.eval_task_id=t.eval_task_id
        WHERE t.trial_id=?""",
        (trial_id,),
    ).fetchone()
    if not trial:
        raise KeyError(trial_id)
    if not trial["work_order_id"]:
        raise ValueError("E1 automated grading requires work_order_id")

    hidden = json.loads(trial["hidden_checks_json"])
    summary_text = _summary_for_work_order(harness.conn, trial["work_order_id"])
    try:
        summary = json.loads(summary_text) if summary_text else {}
    except json.JSONDecodeError:
        summary = {}

    tool_rows = harness.conn.execute(
        """SELECT tool_name,status FROM tool_invocations
        WHERE work_order_id=? ORDER BY started_at""",
        (trial["work_order_id"],),
    ).fetchall()
    completed_tools = [r["tool_name"] for r in tool_rows if r["status"] == "COMPLETED"]
    failed_tools = [r["tool_name"] for r in tool_rows if r["status"] == "ERROR"]
    evidence_ids = summary.get("evidence_ids") or []

    checks: dict[str, bool] = {
        "summary_is_json": bool(summary),
    }
    if "expected_status" in hidden:
        checks["expected_status"] = summary.get("status") == hidden["expected_status"]
    if "expected_answer" in hidden:
        observed = summary.get("answer")
        expected = hidden["expected_answer"]
        if isinstance(expected, (int, float)) and isinstance(observed, (int, float)):
            checks["expected_answer"] = abs(float(observed) - float(expected)) < 1e-9
        else:
            checks["expected_answer"] = observed == expected
    for eid in hidden.get("required_evidence_ids", []):
        checks[f"required_evidence:{eid}"] = eid in evidence_ids
    for eid in hidden.get("forbidden_evidence_ids", []):
        checks[f"forbidden_evidence:{eid}"] = eid not in evidence_ids
    for tool in hidden.get("required_tools", []):
        checks[f"required_tool:{tool}"] = tool in completed_tools
    for tool in hidden.get("required_failed_tools", []):
        checks[f"observed_failure:{tool}"] = tool in failed_tools

    observed = {
        "summary": summary,
        "completed_tools": completed_tools,
        "failed_tools": failed_tools,
    }
    for name, passed in checks.items():
        harness.record_assertion(
            trial_id,
            grader="e1_deterministic",
            assertion_name=name,
            passed=passed,
            observed=observed,
        )
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "observed": observed,
    }
