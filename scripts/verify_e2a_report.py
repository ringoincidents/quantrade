"""Offline verification: no provider credentials, network or broker access."""
import argparse
from pathlib import Path

from quantrade.institutional.experiment_receipt import verify_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify_report(args.report, args.receipt)
    except (OSError, ValueError) as exc:
        print(f"Verification could not complete: {exc}")
        return 2
    print(
        f"{receipt['execution_status']}: {receipt['completed']}/{receipt['planned_trials']} "
        f"completed, {receipt['execution_errors']} execution errors, "
        f"{receipt['grade_failures']} graded failures"
    )
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
