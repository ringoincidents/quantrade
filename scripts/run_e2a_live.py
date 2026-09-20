from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from quantrade.institutional.e2a_runner import TREATMENTS, run_e2a_trial
from quantrade.institutional.e2a_suite import E2A_CASES, seed_e2a_tasks
from quantrade.institutional.eval_harness import EmployeeEvalHarness
from quantrade.institutional.model_providers import GeminiEmployeeProvider
from quantrade.institutional.service import InstitutionalKernel


def main() -> None:
    parser = argparse.ArgumentParser(description="Run E2-A portfolio discovery calibration.")
    parser.add_argument("--db", default="e2a_calibration.sqlite3")
    parser.add_argument("--report", default="e2a_calibration_report.json")
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--pace-seconds", type=float, default=20.0)
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is required")

    db_path = Path(args.db)
    if db_path.exists():
        db_path.unlink()

    kernel = InstitutionalKernel(str(db_path))
    try:
        harness = EmployeeEvalHarness(kernel)
        seed_e2a_tasks(harness)
        results = []
        for repeat in range(1, args.repeats + 1):
            for case in E2A_CASES:
                for treatment in sorted(TREATMENTS):
                    provider = GeminiEmployeeProvider(
                        api_key=api_key,
                        model=args.model,
                    )
                    started = time.monotonic()
                    row = {
                        "eval_task_id": case["eval_task_id"],
                        "treatment": treatment,
                        "repeat": repeat,
                    }
                    try:
                        result = run_e2a_trial(
                            kernel,
                            eval_task_id=case["eval_task_id"],
                            treatment=treatment,
                            provider=provider,
                            seed_label=f"r{repeat}",
                        )
                        row.update({
                            "status": "COMPLETED",
                            "passed": result.passed,
                            "checks": result.checks,
                            "observed": result.observed,
                            "model_usage": result.metrics.get("model_usage"),
                            "tool_calls": result.metrics.get("tool_calls"),
                        })
                    except Exception as exc:
                        row.update({
                            "status": "ERROR",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        })
                    row["elapsed_seconds"] = round(time.monotonic() - started, 3)
                    results.append(row)
                    if args.pace_seconds:
                        time.sleep(args.pace_seconds)

        aggregates = {}
        for treatment in sorted(TREATMENTS):
            rows = [r for r in results if r["treatment"] == treatment]
            completed = [r for r in rows if r["status"] == "COMPLETED"]
            usage = {
                "input_context_chars": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "trials_with_provider_usage": 0,
            }
            for row in completed:
                u = row.get("model_usage") or {}
                usage["input_context_chars"] += int(u.get("input_context_chars") or 0)
                if isinstance(u.get("total_tokens"), int):
                    usage["trials_with_provider_usage"] += 1
                    for key in ("input_tokens", "output_tokens", "total_tokens"):
                        usage[key] += int(u.get(key) or 0)
            aggregates[treatment] = {
                "trials": len(rows),
                "completed": len(completed),
                "strict_passes": sum(bool(r.get("passed")) for r in completed),
                "mean_material_recall": (
                    sum(r["observed"]["material_issue_recall"] for r in completed) / len(completed)
                    if completed else None
                ),
                "mean_material_precision": (
                    sum(r["observed"]["material_issue_precision"] for r in completed) / len(completed)
                    if completed else None
                ),
                "false_research_count": sum(
                    int(r["observed"]["false_research_count"]) for r in completed
                ),
                "decoy_escalations": sum(
                    bool(r["observed"]["decoy_escalated"]) for r in completed
                ),
                "usage": usage,
            }

        report = {
            "suite": "E2A-PROBLEM-DISCOVERY-V0",
            "model": args.model,
            "repeats": args.repeats,
            "treatments": sorted(TREATMENTS),
            "aggregates": aggregates,
            "results": results,
        }
        Path(args.report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    finally:
        kernel.close()


if __name__ == "__main__":
    main()
