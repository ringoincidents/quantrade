from __future__ import annotations

import json
from typing import Any

from .eval_harness import EmployeeEvalHarness


ISSUE_TYPES = [
    "FACTOR_CONCENTRATION",
    "THESIS_BREAK",
    "LIQUIDITY_MISMATCH",
    "FX_EXPOSURE",
    "CORRELATION_SHIFT",
    "EVIDENCE_STALENESS",
    "VALUATION_RISK",
    "CLIENT_CONSTRAINT",
    "OTHER",
]

OUTPUT_CONTRACT = (
    "Review the Client portfolio and identify only material issues that deserve attention now. "
    "Do not recommend trades. It is valid to find no material issue. "
    "FINISH summary must be JSON only with keys issues and no_other_material_issues. "
    "issues must be a list of objects with issue_type, priority, action, reason, evidence_refs. "
    "issue_type must be one of: " + ", ".join(ISSUE_TYPES) + ". "
    "priority must be HIGH, MEDIUM, or LOW. action must be IGNORE, MONITOR, INVESTIGATE, "
    "or RISK_REVIEW. Escalate only when resolving the issue could plausibly change allocation, "
    "risk posture, liquidity planning, monitoring, or the investment thesis."
)


E2A_CASES: list[dict[str, Any]] = [
    {
        "eval_task_id": "E2A-PD-01",
        "title": "Hidden common-driver concentration",
        "public": {
            "as_of": "2026-09-01",
            "client": {"horizon_years": 8, "near_term_cash_need_pct": 5},
            "positions": [
                {"asset": "GridCore", "weight_pct": 18, "description": "power equipment for data centers and industrial grids"},
                {"asset": "CoolStack", "weight_pct": 16, "description": "thermal management systems with hyperscaler customers"},
                {"asset": "ChipForge", "weight_pct": 15, "description": "AI accelerator semiconductor supplier"},
                {"asset": "BroadMarketETF", "weight_pct": 25, "description": "broad equity index"},
                {"asset": "GovBondETF", "weight_pct": 16, "description": "short-duration government bonds"},
                {"asset": "Cash", "weight_pct": 10, "description": "cash"},
            ],
            "observations": [
                {"ref": "OBS-1", "text": "GridCore, CoolStack and ChipForge each report strong demand tied to data-center buildouts."}
            ],
        },
        "diagnostics": {
            "ref": "DIAG-PD01",
            "factor_exposures_pct": {"AI_DATA_CENTER_CAPEX": 49, "BROAD_EQUITY": 25, "RATES_DEFENSIVE": 26},
            "cluster_pairwise_corr_60d": {"GridCore|CoolStack": 0.79, "GridCore|ChipForge": 0.73, "CoolStack|ChipForge": 0.77},
            "single_driver_note": "49% of portfolio has material sensitivity to the same AI/data-center capex driver.",
        },
        "memory": {
            "ref": "MEM-PD01",
            "records": [
                {"asset": "GridCore", "thesis": "grid equipment backlog and data-center power demand", "status": "intact"},
                {"asset": "CoolStack", "thesis": "hyperscaler cooling capex", "status": "intact"},
                {"asset": "ChipForge", "thesis": "AI accelerator demand", "status": "intact"},
            ],
        },
        "hidden": {
            "material_issue_types": ["FACTOR_CONCENTRATION"],
            "optional_issue_types": [],
            "forbidden_false_positive_types": ["LIQUIDITY_MISMATCH", "THESIS_BREAK"],
            "decoy_refs": [],
            "min_material_recall": 1,
        },
    },
    {
        "eval_task_id": "E2A-PD-02",
        "title": "Thesis break requires memory",
        "public": {
            "as_of": "2026-09-01",
            "client": {"horizon_years": 10, "near_term_cash_need_pct": 3},
            "positions": [
                {"asset": "StableSoft", "weight_pct": 30, "description": "subscription enterprise software"},
                {"asset": "BroadMarketETF", "weight_pct": 45, "description": "broad equity index"},
                {"asset": "GovBondETF", "weight_pct": 15, "description": "short-duration government bonds"},
                {"asset": "Cash", "weight_pct": 10, "description": "cash"},
            ],
            "observations": [
                {"ref": "FILING-SS", "text": "StableSoft latest revenue growth is 18%, operating margin is 14%, and annualized churn is 7%."}
            ],
        },
        "diagnostics": {
            "ref": "DIAG-PD02",
            "position_concentration": {"largest_weight_pct": 30, "top3_weight_pct": 90},
            "volatility": "within policy range",
            "liquidity": "adequate",
        },
        "memory": {
            "ref": "MEM-PD02",
            "records": [
                {
                    "asset": "StableSoft",
                    "decision": "BUY",
                    "thesis": "durable subscription growth with operating leverage",
                    "falsification_conditions": ["operating_margin_pct < 18", "annualized_churn_pct > 5"],
                    "last_review": "2026-06-15",
                }
            ],
        },
        "hidden": {
            "material_issue_types": ["THESIS_BREAK"],
            "optional_issue_types": [],
            "forbidden_false_positive_types": ["LIQUIDITY_MISMATCH", "CORRELATION_SHIFT"],
            "decoy_refs": [],
            "min_material_recall": 1,
        },
    },
    {
        "eval_task_id": "E2A-PD-03",
        "title": "Client liquidity outranks market curiosity",
        "public": {
            "as_of": "2026-09-01",
            "client": {
                "horizon_years": 7,
                "required_cash_within_90d_pct_of_portfolio": 22,
                "current_external_cash_buffer_pct": 2,
            },
            "positions": [
                {"asset": "SmallCapValueETF", "weight_pct": 34, "liquidity": "daily"},
                {"asset": "GlobalEquityETF", "weight_pct": 36, "liquidity": "daily"},
                {"asset": "LongBondETF", "weight_pct": 20, "liquidity": "daily"},
                {"asset": "Cash", "weight_pct": 10, "liquidity": "immediate"},
            ],
            "observations": [
                {"ref": "NEWS-RATE", "text": "Central-bank speakers disagree on the timing of the next rate cut."}
            ],
        },
        "diagnostics": {
            "ref": "DIAG-PD03",
            "cash_pct": 10,
            "required_cash_within_90d_pct": 22,
            "cash_shortfall_pct": 12,
            "forced_sale_required_if_no_external_cash": True,
        },
        "memory": {
            "ref": "MEM-PD03",
            "records": [
                {"type": "client_commitment", "text": "90-day cash requirement is hard, not discretionary."}
            ],
        },
        "hidden": {
            "material_issue_types": ["LIQUIDITY_MISMATCH", "CLIENT_CONSTRAINT"],
            "optional_issue_types": [],
            "forbidden_false_positive_types": ["THESIS_BREAK"],
            "decoy_refs": ["NEWS-RATE"],
            "min_material_recall": 1,
        },
    },
    {
        "eval_task_id": "E2A-PD-04",
        "title": "Diversification weakened by correlation shift",
        "public": {
            "as_of": "2026-09-01",
            "client": {"horizon_years": 9, "near_term_cash_need_pct": 4},
            "positions": [
                {"asset": "USQualityETF", "weight_pct": 28, "description": "US quality equities"},
                {"asset": "AsiaExportETF", "weight_pct": 22, "description": "Asian exporters"},
                {"asset": "InfrastructureETF", "weight_pct": 20, "description": "global infrastructure"},
                {"asset": "IntermediateBondETF", "weight_pct": 20, "description": "investment-grade bonds"},
                {"asset": "Cash", "weight_pct": 10, "description": "cash"},
            ],
            "observations": [
                {"ref": "OBS-MACRO", "text": "A common global growth shock has recently dominated cross-asset trading."}
            ],
        },
        "diagnostics": {
            "ref": "DIAG-PD04",
            "portfolio_average_pairwise_corr": {"prior_252d": 0.29, "recent_60d": 0.71},
            "diversification_ratio": {"prior": 1.62, "recent": 1.19},
            "risk_note": "Recent co-movement is materially above the portfolio's historical regime.",
        },
        "memory": {
            "ref": "MEM-PD04",
            "records": [
                {"decision": "ALLOCATION_POLICY", "text": "The equity sleeves were intentionally split to reduce common-driver concentration."}
            ],
        },
        "hidden": {
            "material_issue_types": ["CORRELATION_SHIFT"],
            "optional_issue_types": [],
            "forbidden_false_positive_types": ["THESIS_BREAK", "LIQUIDITY_MISMATCH"],
            "decoy_refs": [],
            "min_material_recall": 1,
        },
    },
    {
        "eval_task_id": "E2A-PD-05",
        "title": "Salient headline is not the main portfolio problem",
        "public": {
            "as_of": "2026-09-01",
            "client": {"horizon_years": 8, "near_term_cash_need_pct": 5},
            "positions": [
                {"asset": "MegaPlatform", "weight_pct": 42, "description": "large technology platform with AI/cloud exposure"},
                {"asset": "TechIndexETF", "weight_pct": 28, "description": "technology-heavy index"},
                {"asset": "UtilityCo", "weight_pct": 18, "description": "regulated utility"},
                {"asset": "TinyMiner", "weight_pct": 2, "description": "small metals producer"},
                {"asset": "Cash", "weight_pct": 10, "description": "cash"},
            ],
            "observations": [
                {"ref": "NEWS-TINY", "text": "TinyMiner CEO abruptly resigns after an internal investigation; shares are highly volatile."},
                {"ref": "OBS-TECH", "text": "MegaPlatform is also the largest constituent inside TechIndexETF."}
            ],
        },
        "diagnostics": {
            "ref": "DIAG-PD05",
            "lookthrough_exposure_pct": {"MegaPlatform_direct_plus_index": 48, "technology_total": 70},
            "position_risk_contribution_pct": {"TinyMiner": 1.4, "technology_cluster": 67},
        },
        "memory": {
            "ref": "MEM-PD05",
            "records": [
                {"asset": "TinyMiner", "role": "small satellite position", "max_weight_pct": 3},
                {"asset": "MegaPlatform", "role": "core growth exposure"},
            ],
        },
        "hidden": {
            "material_issue_types": ["FACTOR_CONCENTRATION"],
            "optional_issue_types": [],
            "forbidden_false_positive_types": ["THESIS_BREAK"],
            "decoy_refs": ["NEWS-TINY"],
            "min_material_recall": 1,
        },
    },
    {
        "eval_task_id": "E2A-PD-06",
        "title": "Healthy portfolio should permit zero research",
        "public": {
            "as_of": "2026-09-01",
            "client": {"horizon_years": 8, "near_term_cash_need_pct": 8},
            "positions": [
                {"asset": "GlobalEquityETF", "weight_pct": 45, "description": "broad global equities"},
                {"asset": "GovBondETF", "weight_pct": 30, "description": "government bonds"},
                {"asset": "InflationBondETF", "weight_pct": 10, "description": "inflation-linked bonds"},
                {"asset": "Cash", "weight_pct": 15, "description": "cash"},
            ],
            "observations": [
                {"ref": "NEWS-NOISE", "text": "A widely followed strategist predicts a volatile quarter without new supporting data."}
            ],
        },
        "diagnostics": {
            "ref": "DIAG-PD06",
            "policy_breaches": [],
            "cash_need_covered": True,
            "concentration": "within policy",
            "recent_correlation": "within historical range",
            "drawdown": "within expected range",
        },
        "memory": {
            "ref": "MEM-PD06",
            "records": [
                {"type": "policy_review", "status": "intact", "last_review": "2026-08-20"},
                {"type": "thesis_monitor", "status": "no material breaks"},
            ],
        },
        "hidden": {
            "material_issue_types": [],
            "optional_issue_types": [],
            "forbidden_false_positive_types": [
                "FACTOR_CONCENTRATION", "THESIS_BREAK", "LIQUIDITY_MISMATCH",
                "CORRELATION_SHIFT", "CLIENT_CONSTRAINT"
            ],
            "decoy_refs": ["NEWS-NOISE"],
            "min_material_recall": 0,
        },
    },
]


def case_by_id(eval_task_id: str) -> dict[str, Any]:
    for case in E2A_CASES:
        if case["eval_task_id"] == eval_task_id:
            return case
    raise KeyError(eval_task_id)


def public_packet(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "eval_task_id": case["eval_task_id"],
        "suite": "E2A-PROBLEM-DISCOVERY-V0",
        "title": "Portfolio review",
        "objective": OUTPUT_CONTRACT,
        "portfolio_snapshot": case["public"],
    }


def seed_e2a_tasks(harness: EmployeeEvalHarness) -> list[str]:
    ids = []
    for case in E2A_CASES:
        task_id = case["eval_task_id"]
        exists = harness.conn.execute(
            "SELECT 1 FROM eval_tasks WHERE eval_task_id=?", (task_id,)
        ).fetchone()
        if not exists:
            harness.create_task(
                suite="E2A-PROBLEM-DISCOVERY-V0",
                title=case["title"],
                objective=OUTPUT_CONTRACT,
                fixture={
                    "diagnostics": case["diagnostics"],
                    "memory": case["memory"],
                    "hidden": case["hidden"],
                },
                success_criteria={
                    "discover_material_issues": True,
                    "avoid_unnecessary_research": True,
                },
                hidden_checks=case["hidden"],
                eval_task_id=task_id,
            )
        ids.append(task_id)
    return ids


def _summary_for_work_order(conn, work_order_id: str) -> str | None:
    row = conn.execute(
        """SELECT event_type,payload FROM ledger_events
        WHERE aggregate_type='WorkOrder' AND aggregate_id=?
          AND event_type='DIRECT_AGENT_FINISHED'
        ORDER BY ledger_id DESC LIMIT 1""",
        (work_order_id,),
    ).fetchone()
    if not row:
        return None
    return json.loads(row["payload"]).get("summary")


def _valid_summary(summary: Any) -> bool:
    if not isinstance(summary, dict) or not isinstance(summary.get("issues"), list):
        return False
    if type(summary.get("no_other_material_issues")) is not bool:
        return False
    for issue in summary["issues"]:
        if not isinstance(issue, dict):
            return False
        if issue.get("issue_type") not in ISSUE_TYPES:
            return False
        if issue.get("priority") not in ("HIGH", "MEDIUM", "LOW"):
            return False
        if issue.get("action") not in ("IGNORE", "MONITOR", "INVESTIGATE", "RISK_REVIEW"):
            return False
        if not isinstance(issue.get("reason"), str) or not issue["reason"].strip():
            return False
        refs = issue.get("evidence_refs")
        if not isinstance(refs, list) or not all(isinstance(r, str) and r.strip() for r in refs):
            return False
    return True


def _refs(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = {value["ref"]} if isinstance(value.get("ref"), str) else set()
        for child in value.values():
            found.update(_refs(child))
        return found
    if isinstance(value, list):
        return set().union(*(_refs(child) for child in value))
    return set()


def _snapshot_paths(value: Any, prefix: str = "portfolio_snapshot") -> set[str]:
    paths = {prefix}
    if isinstance(value, dict):
        for key, child in value.items():
            paths.update(_snapshot_paths(child, prefix + "." + key))
    return paths


def grade_e2a_trial(harness: EmployeeEvalHarness, trial_id: str) -> dict:
    trial = harness.conn.execute(
        """SELECT t.*,e.hidden_checks_json FROM eval_trials t
        JOIN eval_tasks e ON e.eval_task_id=t.eval_task_id
        WHERE t.trial_id=?""",
        (trial_id,),
    ).fetchone()
    if not trial or not trial["work_order_id"]:
        raise KeyError(trial_id)

    hidden = json.loads(trial["hidden_checks_json"])
    summary_text = _summary_for_work_order(harness.conn, trial["work_order_id"])
    try:
        summary = json.loads(summary_text) if summary_text else {}
    except (json.JSONDecodeError, TypeError):
        summary = {}

    contract_valid = _valid_summary(summary)
    issues = summary.get("issues", []) if contract_valid else []
    case = case_by_id(trial["eval_task_id"])
    available_refs = _refs(case["public"]) | _snapshot_paths(case["public"])
    retrieved: dict[str, set[str]] = {}
    for row in harness.conn.execute(
        """SELECT tool_name,output_json FROM tool_invocations
        WHERE work_order_id=? AND status='COMPLETED'""",
        (trial["work_order_id"],),
    ):
        try:
            refs = _refs(json.loads(row["output_json"]))
        except (json.JSONDecodeError, TypeError):
            continue
        retrieved.setdefault(row["tool_name"], set()).update(refs)
        available_refs.update(refs)

    escalated = []
    supported = set()
    unsupported = []
    all_escalated_refs = set()
    for issue in issues:
        if issue["action"] not in ("INVESTIGATE", "RISK_REVIEW"):
            continue
        issue_type = issue["issue_type"]
        refs = set(issue["evidence_refs"])
        escalated.append(issue_type)
        all_escalated_refs.update(refs)
        provenance_ok = bool(refs) and refs <= available_refs
        # PD-02's prior falsification conditions exist only in memory.
        # PD-04 has a public macro clue: do not deny A legitimate inference.
        if trial["eval_task_id"] == "E2A-PD-02" and issue_type == "THESIS_BREAK":
            provenance_ok = provenance_ok and case["memory"]["ref"] in (
                refs & retrieved.get("e2.investment_memory", set())
            )
        if provenance_ok:
            supported.add(issue_type)
        else:
            unsupported.append(issue_type)

    material = set(hidden.get("material_issue_types", []))
    escalated_set = set(escalated)
    true_positive = material & supported
    false_positive = (escalated_set - material - set(hidden.get("optional_issue_types", []))) | set(unsupported)
    recall = (1.0 if not material else len(true_positive) / len(material)) if contract_valid else 0.0
    precision = (1.0 if not escalated_set else len(true_positive) / len(escalated_set)) if contract_valid else 0.0

    decoy_refs = set(hidden.get("decoy_refs", []))
    decoy_escalated = bool(decoy_refs & all_escalated_refs)
    no_action_expected = not material
    no_action_observed = contract_valid and not escalated_set and summary["no_other_material_issues"]

    checks = {
        "summary_is_json": isinstance(summary, dict) and bool(summary),
        "output_contract_valid": contract_valid,
        "evidence_provenance_valid": contract_valid and not unsupported,
        "issues_is_list": isinstance(summary.get("issues"), list) if isinstance(summary, dict) else False,
        "material_recall": recall >= float(hidden.get("min_material_recall", 1.0)),
        "no_forbidden_false_positive": not bool(
            escalated_set & set(hidden.get("forbidden_false_positive_types", []))
        ),
        "no_decoy_escalation": not decoy_escalated,
    }
    if no_action_expected:
        checks["appropriate_no_action"] = no_action_observed

    observed = {
        "summary": summary,
        "unsupported_issue_types": sorted(set(unsupported)),
        "material_issue_types": sorted(material),
        "escalated_issue_types": sorted(escalated_set),
        "true_positive_types": sorted(true_positive),
        "false_positive_types": sorted(false_positive),
        "material_issue_recall": recall,
        "material_issue_precision": precision,
        "false_research_count": len(false_positive),
        "decoy_escalated": decoy_escalated,
        "appropriate_no_action": no_action_observed if no_action_expected else None,
    }
    for name, passed in checks.items():
        harness.record_assertion(
            trial_id,
            grader="e2a_discovery",
            assertion_name=name,
            passed=passed,
            observed=observed,
        )
    return {"passed": all(checks.values()), "checks": checks, "observed": observed}

