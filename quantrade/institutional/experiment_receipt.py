"""Execution evidence for E2-A; not an investment-quality or safety certificate."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .e2a_runner import TREATMENTS
from .e2a_suite import E2A_CASES


def build_receipt(report: object, *, report_sha256: str) -> dict:
    errors = []
    counts = Counter()
    seen = set()
    expected = set()
    if not isinstance(report, dict):
        errors.append("report must be an object")
        report = {}
    repeats = report.get("repeats")
    if type(repeats) is not int or not 1 <= repeats <= 100:
        errors.append("repeats must be an integer from 1 to 100")
    else:
        expected = {
            (case["eval_task_id"], treatment, repeat)
            for case in E2A_CASES
            for treatment in TREATMENTS
            for repeat in range(1, repeats + 1)
        }
    if report.get("suite") != "E2A-PROBLEM-DISCOVERY-V0":
        errors.append("unsupported suite")
    if not isinstance(report.get("model"), str) or not report["model"].strip():
        errors.append("model is missing")
    treatments = report.get("treatments")
    if not isinstance(treatments, list) or sorted(treatments, key=str) != sorted(TREATMENTS):
        errors.append("treatment set differs from E2-A")
    rows = report.get("results")
    if not isinstance(rows, list):
        errors.append("results must be a list")
        rows = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {index}: not an object")
            continue
        task, treatment, repeat = (row.get(k) for k in ("eval_task_id", "treatment", "repeat"))
        if not isinstance(task, str) or not isinstance(treatment, str) or type(repeat) is not int:
            errors.append(f"row {index}: invalid identity")
            continue
        key = (task, treatment, repeat)
        if key in seen:
            errors.append(f"row {index}: duplicate identity")
        seen.add(key)
        if key not in expected:
            errors.append(f"row {index}: unexpected identity")
        status = row.get("status")
        if status == "ERROR":
            counts["execution_errors"] += 1
            if not isinstance(row.get("error_type"), str) or not row["error_type"]:
                errors.append(f"row {index}: error_type is missing")
            if row.get("passed") is True:
                errors.append(f"row {index}: ERROR cannot pass")
        elif status == "COMPLETED":
            counts["completed"] += 1
            checks = row.get("checks")
            valid_checks = isinstance(checks, dict) and bool(checks) and all(
                type(value) is bool for value in checks.values()
            )
            if type(row.get("passed")) is not bool or not valid_checks:
                errors.append(f"row {index}: invalid grading fields")
            elif row["passed"] != all(checks.values()):
                errors.append(f"row {index}: passed contradicts checks")
            else:
                counts["grade_passes" if row["passed"] else "grade_failures"] += 1
        else:
            errors.append(f"row {index}: nonterminal or unknown status")
    missing = expected - seen
    if missing:
        errors.append(f"missing {len(missing)} planned trials")
    status = "INVALID" if errors else (
        "COMPLETE_WITH_ERRORS" if counts["execution_errors"] else "COMPLETE"
    )
    return {
        "schema": "quantrade.execution-receipt.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "suite": report.get("suite"),
        "model": report.get("model"),
        "report_sha256": report_sha256,
        "execution_status": status,
        "exit_code": {"INVALID": 2, "COMPLETE_WITH_ERRORS": 3, "COMPLETE": 0}[status],
        "planned_trials": len(expected),
        "reported_rows": len(rows),
        "completed": counts["completed"],
        "execution_errors": counts["execution_errors"],
        "grade_passes": counts["grade_passes"],
        "grade_failures": counts["grade_failures"],
        "validation_errors": errors,
        "limits": [
            "Completion is not a claim of investment skill, profitability, or broker safety.",
            "Hash identifies report bytes; this is not signed independent attestation.",
            "Aggregate scores are not trusted or recomputed by this execution check.",
            "Report is not reconciled against the SQLite trace by this version.",
        ],
    }


def verify_report(report_path: Path, receipt_path: Path) -> dict:
    if report_path.resolve() == receipt_path.resolve():
        raise ValueError("receipt must not replace its source report")
    data = report_path.read_bytes()
    try:
        report = json.loads(data)
    except (ValueError, UnicodeError):
        report = None
    receipt = build_receipt(report, report_sha256=hashlib.sha256(data).hexdigest())
    # Exclusive creation preserves prior experiment evidence on accidental rerun.
    with receipt_path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return receipt
