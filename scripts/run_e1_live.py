from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path

from quantrade.institutional.e1_runner import run_e1_trial
from quantrade.institutional.e1_suite import seed_e1_tasks
from quantrade.institutional.eval_harness import EmployeeEvalHarness
from quantrade.institutional.model_providers import GeminiEmployeeProvider
from quantrade.institutional.service import InstitutionalKernel


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run controlled QuanTrade E1 Gemini trials."
    )
    parser.add_argument("--db", default="e1_live.sqlite3")
    parser.add_argument("--report", default="e1_live_report.json")
    parser.add_argument(
        "--tasks", default="E1-01",
        help="Comma-separated task ids, or ALL.",
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--pace-seconds", type=float, default=2.0)
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit(
            "GEMINI_API_KEY is required. Put it in an environment/CI secret, never Git."
        )
    if args.repeats < 1 or args.repeats > 5:
        raise SystemExit("--repeats must be between 1 and 5")

    db_path = Path(args.db)
    if db_path.exists():
        db_path.unlink()
    kernel = InstitutionalKernel(str(db_path))
    harness = EmployeeEvalHarness(kernel)
    task_ids = seed_e1_tasks(harness)
    selected = task_ids if args.tasks == "ALL" else [
        t.strip() for t in args.tasks.split(",") if t.strip()
    ]
    unknown = sorted(set(selected) - set(task_ids))
    if unknown:
        raise SystemExit(f"unknown E1 tasks: {unknown}")

    results = []
    try:
        for task_id in selected:
            for repeat in range(1, args.repeats + 1):
                for treatment in (
                    "DIRECT_SINGLE_AGENT",
                    "QUANTRADE_INSTITUTIONAL",
                ):
                    provider = GeminiEmployeeProvider(model=args.model)
                    label = f"r{repeat}-{treatment.lower()}"
                    started = time.monotonic()
                    try:
                        result = run_e1_trial(
                            kernel,
                            eval_task_id=task_id,
                            treatment=treatment,
                            provider=provider,
                            seed_label=label,
                        )
                        row = {
                            "task_id": task_id,
                            "repeat": repeat,
                            "treatment": treatment,
                            "trial_id": result.trial_id,
                            "passed": result.passed,
                            "runtime_status": result.runtime_status,
                            "checks": result.checks,
                            "elapsed_seconds": round(time.monotonic() - started, 3),
                        }
                    except Exception as exc:
                        row = {
                            "task_id": task_id,
                            "repeat": repeat,
                            "treatment": treatment,
                            "passed": False,
                            "runtime_status": "ERROR",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "elapsed_seconds": round(time.monotonic() - started, 3),
                        }
                    results.append(row)
                    print(json.dumps(row, ensure_ascii=False))
                    time.sleep(max(0.0, args.pace_seconds))
    finally:
        summary = {
            "model": args.model,
            "tasks": selected,
            "repeats": args.repeats,
            "results": results,
        }
        Path(args.report).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        kernel.close()

    failures = [r for r in results if not r["passed"]]
    print(
        json.dumps(
            {
                "trials": len(results),
                "passed": len(results) - len(failures),
                "failed": len(failures),
                "report": args.report,
                "database": args.db,
            },
            ensure_ascii=False,
        )
    )
    # Experimental failures are data, not CI failures. Infrastructure errors
    # remain visible inside the report for later diagnosis.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
