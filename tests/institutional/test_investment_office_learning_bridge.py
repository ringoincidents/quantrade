from __future__ import annotations

import json
import os
import tempfile
import unittest

from quantrade.institutional.client_capital import ClientCapitalRuntime
from quantrade.institutional.investment_office_learning_bridge import (
    InvestmentOfficeLearningBridgeError,
    case_learning_to_strategy_performance_state,
)
from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.performance_capital import PerformanceCapitalLoop
from quantrade.institutional.service import InstitutionalKernel


def _learning_artifact(
    *,
    thesis_status="NOT_FALSIFIED",
    forecast_hurdle=True,
    outcome_hurdle=True,
    interval_contains=True,
):
    return {
        "schema": "quantrade_case_learning_v1",
        "case_id": "CASE-LEARNING-001",
        "forecast": {
            "expected_return_pct": 20.0,
        },
        "outcome": {
            "realized_return_pct": 10.0,
            "benchmark_return_pct": 8.0,
            "counterfactual_excess_vs_benchmark_pct": 2.0,
            "scenario_value_interval_contains_realized_price": interval_contains,
        },
        "calibration": {
            "return_forecast_error_pct_points": -10.0,
            "return_forecast_absolute_error_pct_points": 10.0,
            "loss_event_brier_component": 0.0625,
            "hurdle_event_brier_component": 0.0625,
            "forecast_hurdle_met": forecast_hurdle,
            "outcome_hurdle_met": outcome_hurdle,
            "single_case_proves_alpha": False,
        },
        "thesis_learning": {
            "status": thesis_status,
            "triggered_condition_ids": (
                ["FAL-1"] if thesis_status == "FALSIFIED" else []
            ),
            "unresolved_condition_ids": (
                ["FAL-1"] if thesis_status == "UNRESOLVED" else []
            ),
            "falsification_results": [],
            "thesis_truth_proven": False,
        },
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "risk_opinion_created": False,
            "committee_decision_created": False,
            "decision_plan_created": False,
            "performance_record_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    }


class InvestmentOfficeLearningBridgeTests(unittest.TestCase):
    def test_falsified_thesis_requires_learning_review(self):
        state = case_learning_to_strategy_performance_state(
            _learning_artifact(thesis_status="FALSIFIED")
        )
        self.assertTrue(state["review_required"])
        self.assertIn("THESIS_FALSIFIED", state["trigger_reasons"])
        self.assertFalse(state["actual_portfolio_value_added_measured"])
        self.assertFalse(state["execution_authority"])

    def test_unresolved_thesis_requires_learning_review(self):
        state = case_learning_to_strategy_performance_state(
            _learning_artifact(thesis_status="UNRESOLVED")
        )
        self.assertTrue(state["review_required"])
        self.assertIn("THESIS_UNRESOLVED", state["trigger_reasons"])

    def test_hurdle_classification_miss_requires_review(self):
        state = case_learning_to_strategy_performance_state(
            _learning_artifact(
                forecast_hurdle=True,
                outcome_hurdle=False,
            )
        )
        self.assertTrue(state["review_required"])
        self.assertIn(
            "RETURN_HURDLE_CLASSIFICATION_MISS",
            state["trigger_reasons"],
        )

    def test_realized_price_outside_scenario_interval_requires_review(self):
        state = case_learning_to_strategy_performance_state(
            _learning_artifact(interval_contains=False)
        )
        self.assertTrue(state["review_required"])
        self.assertIn(
            "REALIZED_PRICE_OUTSIDE_SCENARIO_VALUE_INTERVAL",
            state["trigger_reasons"],
        )

    def test_no_structural_trigger_does_not_invent_numeric_threshold(self):
        state = case_learning_to_strategy_performance_state(
            _learning_artifact()
        )
        self.assertFalse(state["review_required"])
        self.assertEqual((), state["trigger_reasons"])
        self.assertEqual(
            "NO_STRUCTURAL_CASE_LEARNING_TRIGGER",
            state["reason"],
        )

    def test_execution_authoritative_learning_artifact_is_rejected(self):
        artifact = _learning_artifact()
        artifact["authority"]["execution_authorized"] = True
        with self.assertRaisesRegex(
            InvestmentOfficeLearningBridgeError,
            "non-execution-authoritative",
        ):
            case_learning_to_strategy_performance_state(artifact)

    def test_learning_cannot_masquerade_as_actual_performance(self):
        artifact = _learning_artifact()
        artifact["authority"]["performance_record_created"] = True
        with self.assertRaisesRegex(
            InvestmentOfficeLearningBridgeError,
            "must not masquerade as actual performance",
        ):
            case_learning_to_strategy_performance_state(artifact)


class InvestmentOfficeLearningToPerformanceLoopTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.org = OrganizationRuntime(self.kernel)
        self.capital = ClientCapitalRuntime(self.kernel, self.org)
        self.capital.create_client(
            "CLIENT-LEARN",
            profile={
                "essential_monthly_spend": 1_000_000,
                "emergency_reserve_months": 6,
                "max_drawdown_pct": 20.0,
                "max_planning_return_pct": 20.0,
                "research_universe": ["KR", "US"],
            },
        )
        self.loop = PerformanceCapitalLoop(self.capital)
        capital_plan_id = self.capital.build_capital_plan(
            "CLIENT-LEARN",
            liquid_assets=10_000_000,
            portfolio_value=20_000_000,
            as_of="2026-01-01",
        )
        self.previous_mandate = self.capital.create_mandate(
            capital_plan_id
        )

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_falsified_case_learning_generates_existing_isll_work_order(self):
        learning_state = case_learning_to_strategy_performance_state(
            _learning_artifact(thesis_status="FALSIFIED")
        )
        result = self.loop.reconcile(
            "CLIENT-LEARN",
            as_of="2026-02-01",
            client_liquid_cash=7_000_000,
            brokerage_cash=3_000_000,
            invested_market_value=20_000_000,
            previous_mandate_id=self.previous_mandate,
            strategy_performance_state=learning_state,
        )

        self.assertEqual(1, len(result["generated_work_orders"]))
        row = self.kernel.conn.execute(
            """SELECT recipient_office,objective,authority_scope_json
            FROM work_orders WHERE work_order_id=?""",
            (result["generated_work_orders"][0],),
        ).fetchone()
        self.assertEqual("ISLL", row["recipient_office"])
        self.assertIn(
            "strategy performance and attribution",
            row["objective"],
        )
        authority = json.loads(row["authority_scope_json"])
        self.assertFalse(authority["trade"])
        self.assertFalse(authority["policy_change"])

    def test_clean_case_learning_creates_no_learning_work_order(self):
        learning_state = case_learning_to_strategy_performance_state(
            _learning_artifact()
        )
        result = self.loop.reconcile(
            "CLIENT-LEARN",
            as_of="2026-02-01",
            client_liquid_cash=7_000_000,
            brokerage_cash=3_000_000,
            invested_market_value=20_000_000,
            previous_mandate_id=self.previous_mandate,
            strategy_performance_state=learning_state,
        )
        self.assertEqual([], result["generated_work_orders"])

    def test_case_learning_adapter_does_not_create_performance_record(self):
        before = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM performance_records"
        ).fetchone()["c"]
        case_learning_to_strategy_performance_state(
            _learning_artifact(thesis_status="FALSIFIED")
        )
        after = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM performance_records"
        ).fetchone()["c"]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
