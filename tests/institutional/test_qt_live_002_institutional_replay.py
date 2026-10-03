from __future__ import annotations

import unittest

from scripts.run_qt_live_002_institutional_replay import run_replay


class QtLive002InstitutionalReplayTests(unittest.TestCase):
    def test_enter_now_passes_real_kernel_and_records_simulated_execution(self):
        result = run_replay(committee_action="ENTER_NOW")

        self.assertTrue(result["committee_ready"])
        self.assertEqual("FOUNDER_DESK", result["route"])
        self.assertIsNotNone(result["committee_package_id"])
        self.assertIsNotNone(result["decision_id"])
        self.assertIsNotNone(result["decision_plan_id"])
        self.assertIsNotNone(result["execution_id"])
        self.assertEqual("OUTCOME_TRACKING", result["final_case_status"])
        self.assertFalse(result["broker_side_effect"])
        self.assertTrue(result["ledger_chain_valid"])

    def test_wait_passes_committee_but_creates_no_execution(self):
        result = run_replay(committee_action="WAIT")

        self.assertTrue(result["committee_ready"])
        self.assertEqual("FOUNDER_DESK", result["route"])
        self.assertIsNotNone(result["decision_id"])
        self.assertIsNone(result["decision_plan_id"])
        self.assertIsNone(result["execution_id"])
        self.assertEqual("DECIDED", result["final_case_status"])
        self.assertFalse(result["broker_side_effect"])
        self.assertTrue(result["ledger_chain_valid"])


if __name__ == "__main__":
    unittest.main()
