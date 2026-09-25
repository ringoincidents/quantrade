import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from quantrade.institutional.employee_agent import ModelAction, ScriptedModelProvider


@unittest.skipUnless(importlib.util.find_spec("requests"), "existing requests dependency unavailable")
class LiveRunnerContractTests(unittest.TestCase):
    def run_offline(self, directory, fail=False, extra=()):
        from scripts import run_e2a_live
        args = ["run_e2a_live", "--db", str(Path(directory) / "run.db"),
                "--report", str(Path(directory) / "report.json"),
                "--receipt", str(Path(directory) / "receipt.json"), "--pace-seconds", "0", *extra]

        def provider(**_kwargs):
            if fail:
                return ScriptedModelProvider([])
            return ScriptedModelProvider([ModelAction("FINISH", {
                "summary": json.dumps({"issues": [], "no_other_material_issues": True})})])

        with patch("sys.argv", args), patch.dict(os.environ, {"GEMINI_API_KEY": "offline-dummy"}), \
             patch.object(run_e2a_live, "GeminiEmployeeProvider", side_effect=provider), \
             patch("builtins.print"):
            return run_e2a_live.main()

    def test_completed_but_wrong_answers_are_not_execution_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(0, self.run_offline(directory))
            receipt = json.loads((Path(directory) / "receipt.json").read_text())
            self.assertGreater(receipt["grade_failures"], 0)
            self.assertEqual(18, receipt["completed"])

    def test_errors_return_nonzero_after_artifacts_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(3, self.run_offline(directory, fail=True))
            receipt = json.loads((Path(directory) / "receipt.json").read_text())
            self.assertEqual(18, receipt["execution_errors"])
            self.assertTrue((Path(directory) / "run.db").exists())
            self.assertTrue((Path(directory) / "report.json").exists())

    def test_existing_evidence_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "run.db"
            db.write_bytes(b"preserve")
            with self.assertRaises(SystemExit) as error:
                self.run_offline(directory)
            self.assertEqual(2, error.exception.code)
            self.assertEqual(b"preserve", db.read_bytes())

    def test_invalid_budget_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit) as error:
                self.run_offline(directory, extra=("--repeats", "0"))
            self.assertEqual(2, error.exception.code)
            self.assertFalse((Path(directory) / "run.db").exists())
