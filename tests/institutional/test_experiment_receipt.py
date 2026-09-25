import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from quantrade.institutional.e2a_runner import TREATMENTS
from quantrade.institutional.e2a_suite import E2A_CASES
from quantrade.institutional.experiment_receipt import build_receipt, verify_report


def complete_report():
    return {
        "suite": "E2A-PROBLEM-DISCOVERY-V0", "model": "offline-test",
        "repeats": 1, "treatments": sorted(TREATMENTS),
        "results": [
            {"eval_task_id": c["eval_task_id"], "treatment": t, "repeat": 1,
             "status": "COMPLETED", "passed": True, "checks": {"test": True}}
            for c in E2A_CASES for t in sorted(TREATMENTS)
        ],
    }


class ExperimentReceiptTests(unittest.TestCase):
    def receipt(self, report):
        return build_receipt(report, report_sha256="test-hash")

    def test_complete_does_not_require_scientific_success(self):
        report = complete_report()
        for row in report["results"]:
            row.update(passed=False, checks={"material_recall": False})
        receipt = self.receipt(report)
        self.assertEqual(0, receipt["exit_code"])
        self.assertEqual(18, receipt["grade_failures"])
        self.assertEqual(0, receipt["grade_passes"])

    def test_execution_error_is_not_green(self):
        report = complete_report()
        report["results"][0].update(status="ERROR", error_type="ValueError", passed=False)
        receipt = self.receipt(report)
        self.assertEqual("COMPLETE_WITH_ERRORS", receipt["execution_status"])
        self.assertEqual(3, receipt["exit_code"])
        self.assertEqual(17, receipt["completed"])

    def test_missing_duplicate_and_unexpected_rows_are_invalid(self):
        for change in ("missing", "duplicate", "unexpected"):
            report = complete_report()
            if change == "missing":
                report["results"].pop()
            elif change == "duplicate":
                report["results"][-1] = copy.deepcopy(report["results"][0])
            else:
                report["results"][0]["eval_task_id"] = "unknown"
            with self.subTest(change=change):
                self.assertEqual(2, self.receipt(report)["exit_code"])

    def test_running_and_contradictory_grades_are_invalid(self):
        for patch in ({"status": "RUNNING"}, {"checks": {}}, {"checks": {"x": 1}},
                      {"passed": False}, {"status": "ERROR", "error_type": "X"},
                      {"repeat": True}, {"treatment": []}):
            report = complete_report()
            report["results"][0].update(patch)
            with self.subTest(patch=patch):
                self.assertEqual(2, self.receipt(report)["exit_code"])

    def test_invalid_top_level_and_repeat_bounds(self):
        for value in (None, [], {}, {"results": "wrong"}):
            self.assertEqual(2, self.receipt(value)["exit_code"])
        for repeat in (True, 0, -1, 101, "1", None):
            report = complete_report()
            report["repeats"] = repeat
            self.assertEqual(2, self.receipt(report)["exit_code"])

    def test_aggregate_claim_cannot_hide_execution_error(self):
        report = complete_report()
        report["aggregates"] = {"all_passed": True}
        report["results"][0].update(status="ERROR", passed=False, error_type="X")
        self.assertEqual(3, self.receipt(report)["exit_code"])

    def test_hash_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            receipt = Path(directory) / "receipt.json"
            report.write_text(json.dumps(complete_report()))
            original = report.read_bytes()
            result = verify_report(report, receipt)
            self.assertEqual(hashlib.sha256(original).hexdigest(), result["report_sha256"])
            with self.assertRaises(FileExistsError):
                verify_report(report, receipt)
            with self.assertRaises(ValueError):
                verify_report(report, report)
            self.assertEqual(original, report.read_bytes())

    def test_malformed_json_produces_invalid_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "broken.json"
            report.write_text("{broken")
            result = verify_report(report, Path(directory) / "receipt.json")
            self.assertEqual(2, result["exit_code"])

    def test_real_wave2_cli_keeps_two_failures_visible(self):
        root = Path(__file__).resolve().parents[2]
        report = root / "docs/experiments/E2A_CALIBRATION_WAVE2_RAW.json"
        original = report.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            proc = subprocess.run(
                [sys.executable, str(root / "scripts/verify_e2a_report.py"),
                 "--report", str(report), "--receipt", str(output)],
                cwd=root, env={**os.environ, "PYTHONPATH": str(root)},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(3, proc.returncode, proc.stderr)
            receipt = json.loads(output.read_text())
            self.assertEqual((18, 16, 2), (receipt["planned_trials"],
                receipt["completed"], receipt["execution_errors"]))
            self.assertEqual(original, report.read_bytes())


if __name__ == "__main__":
    unittest.main()
