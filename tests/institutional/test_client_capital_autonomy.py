from __future__ import annotations

import json
import os
import tempfile
import unittest

from quantrade.institutional.client_capital import (
    AutonomousWorkEngine,
    ClientCapitalRuntime,
)
from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.service import InstitutionalKernel


class ClientCapitalAutonomyTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.org = OrganizationRuntime(self.kernel)
        self.capital = ClientCapitalRuntime(self.kernel, self.org)
        self.capital.create_client(
            "CLIENT-FIXTURE",
            profile={
                "essential_monthly_spend": 1_000_000,
                "emergency_reserve_months": 6,
                "max_drawdown_pct": 18.0,
                "max_planning_return_pct": 15.0,
                "research_universe": ["KR", "US"],
                "prohibited_actions": [
                    "LIVE_ORDER_WITHOUT_HUMAN_APPROVAL",
                    "SILENT_POLICY_CHANGE",
                ],
            },
            effective_at="2026-01-01",
        )

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def _normal_plan_and_mandate(self):
        self.capital.add_cashflow(
            "CLIENT-FIXTURE",
            flow_type="INCOME",
            amount=2_500_000,
            cadence="MONTHLY",
            start_date="2026-01-01",
            label="recurring income",
        )
        self.capital.add_cashflow(
            "CLIENT-FIXTURE",
            flow_type="EXPENSE",
            amount=1_000_000,
            cadence="MONTHLY",
            start_date="2026-01-01",
            label="living cost",
            reserved=False,
        )
        self.capital.add_cashflow(
            "CLIENT-FIXTURE",
            flow_type="EXPENSE",
            amount=3_000_000,
            cadence="ONE_TIME",
            start_date="2026-08-01",
            label="planned education cost",
            reserved=True,
        )
        self.capital.add_goal(
            "CLIENT-FIXTURE",
            "Long-term capital target",
            80_000_000,
            "2031-01-01",
            metadata={"funding_bucket": "investment"},
        )
        cpid = self.capital.build_capital_plan(
            "CLIENT-FIXTURE",
            liquid_assets=20_000_000,
            portfolio_value=10_000_000,
            as_of="2026-01-01",
        )
        return cpid, self.capital.create_mandate(cpid)

    def test_client_intelligence_is_versioned_not_silently_overwritten(self):
        self.capital.update_profile(
            "CLIENT-FIXTURE",
            {
                "essential_monthly_spend": 1_200_000,
                "emergency_reserve_months": 6,
                "max_drawdown_pct": 15.0,
            },
            effective_at="2026-06-01",
        )
        rows = self.kernel.conn.execute(
            """SELECT version,profile_json FROM client_profile_versions
            WHERE client_id=? ORDER BY version""",
            ("CLIENT-FIXTURE",),
        ).fetchall()
        self.assertEqual([1, 2], [r["version"] for r in rows])
        self.assertEqual(1_000_000, json.loads(rows[0]["profile_json"])["essential_monthly_spend"])
        self.assertEqual(1_200_000, json.loads(rows[1]["profile_json"])["essential_monthly_spend"])

    def test_capital_plan_protects_client_money_before_investable_surplus(self):
        cpid, _ = self._normal_plan_and_mandate()
        plan = self.capital.get_capital_plan(cpid)
        self.assertEqual(6_000_000, plan["emergency_reserve"])
        self.assertEqual(3_000_000, plan["scheduled_reserved_outflows"])
        self.assertEqual(9_000_000, plan["liquidity_reserve"])
        self.assertEqual(11_000_000, plan["investable_now"])
        self.assertEqual(1_500_000, plan["monthly_investable_surplus"])
        self.assertGreaterEqual(plan["required_return_pct"], 0.0)
        self.assertIn("required return is a deterministic planning rate, not a forecast", plan["limitations"])

    def test_unrealistic_goal_creates_conflict_instead_of_silently_raising_risk(self):
        self.capital.add_goal(
            "CLIENT-FIXTURE",
            "Aggressive fixture target",
            500_000_000,
            "2028-01-01",
            metadata={"funding_bucket": "investment"},
        )
        cpid = self.capital.build_capital_plan(
            "CLIENT-FIXTURE",
            liquid_assets=20_000_000,
            portfolio_value=0,
            as_of="2026-01-01",
        )
        plan = self.capital.get_capital_plan(cpid)
        self.assertTrue(plan["conflicts"])
        mandate_id = self.capital.create_mandate(cpid)
        mandate = self.capital.get_mandate(mandate_id)
        self.assertEqual("REVIEW_REQUIRED", mandate["status"])
        self.assertFalse(mandate["authority"]["live_execution"])
        self.assertFalse(mandate["authority"]["policy_change"])

    def test_mandate_carries_client_constraints_not_security_picks(self):
        _, mid = self._normal_plan_and_mandate()
        mandate = self.capital.get_mandate(mid)
        self.assertEqual(["KR", "US"], mandate["research_universe"])
        self.assertEqual(18.0, mandate["max_drawdown_pct"])
        self.assertTrue(mandate["human_approval_required_for_live_execution"])
        self.assertNotIn("recommended_symbols", mandate)
        self.assertNotIn("buy", mandate)

    def test_autonomous_engine_discovers_internal_work_from_mandate_gaps(self):
        _, mid = self._normal_plan_and_mandate()
        engine = AutonomousWorkEngine(self.capital)
        created = engine.evaluate(
            mid,
            {
                "strategy_coverage": {"status": "INSUFFICIENT", "region": "KR"},
                "allocation_gap": {"material": True, "gap": "KR active alpha"},
                "risk_state": {"policy_breach": False},
                "new_investable_surplus": 4_000_000,
                "strategy_performance": {"review_required": True, "strategy": "fixture-alpha"},
            },
        )
        self.assertEqual(4, len(created))
        rows = self.kernel.conn.execute(
            """SELECT recipient_office,objective,authority_scope_json
            FROM work_orders WHERE work_order_id IN (?,?,?,?)""",
            tuple(created),
        ).fetchall()
        offices = sorted(r["recipient_office"] for r in rows)
        self.assertEqual(["ISLL", "SPMG", "SPMG", "SPMG"], offices)
        for row in rows:
            authority = json.loads(row["authority_scope_json"])
            self.assertFalse(authority["trade"])
            self.assertFalse(authority["policy_change"])
        objectives = " ".join(r["objective"] for r in rows)
        self.assertIn("Research strategy opportunities", objectives)
        self.assertIn("deployment/reinvestment plan", objectives)
        self.assertIn("strategy performance and attribution", objectives)

    def test_same_trigger_is_idempotent_and_does_not_spam_staff(self):
        _, mid = self._normal_plan_and_mandate()
        engine = AutonomousWorkEngine(self.capital)
        state = {"strategy_coverage": {"status": "INSUFFICIENT", "region": "KR"}}
        first = engine.evaluate(mid, state)
        second = engine.evaluate(mid, state)
        self.assertEqual(1, len(first))
        self.assertEqual([], second)

    def test_risk_breach_generates_independent_risk_work_not_trade(self):
        _, mid = self._normal_plan_and_mandate()
        created = AutonomousWorkEngine(self.capital).evaluate(
            mid,
            {
                "strategy_coverage": {"status": "ADEQUATE"},
                "risk_state": {
                    "policy_breach": True,
                    "rule": "fixture concentration limit",
                    "observed": 27,
                    "limit": 20,
                },
            },
        )
        self.assertEqual(1, len(created))
        row = self.kernel.conn.execute(
            "SELECT recipient_office,authority_scope_json FROM work_orders WHERE work_order_id=?",
            (created[0],),
        ).fetchone()
        self.assertEqual("IPRO", row["recipient_office"])
        self.assertFalse(json.loads(row["authority_scope_json"])["trade"])

    def test_twelve_month_horizon_has_exactly_twelve_monthly_slots(self):
        self.capital.add_cashflow(
            "CLIENT-FIXTURE",
            flow_type="EXPENSE",
            amount=100_000,
            cadence="MONTHLY",
            start_date="2026-01-01",
            label="reserved monthly fixture",
            reserved=True,
        )
        cpid = self.capital.build_capital_plan(
            "CLIENT-FIXTURE",
            liquid_assets=20_000_000,
            as_of="2026-01-01",
        )
        plan = self.capital.get_capital_plan(cpid)
        self.assertEqual(1_200_000, plan["scheduled_reserved_outflows"])

    def test_future_income_is_not_counted_as_current_surplus_but_enters_goal_schedule(self):
        self.capital.add_goal(
            "CLIENT-FIXTURE",
            "Two year fixture goal",
            12_000_000,
            "2028-01-01",
            metadata={"funding_bucket": "investment"},
        )
        before_id = self.capital.build_capital_plan(
            "CLIENT-FIXTURE",
            liquid_assets=6_000_000,
            as_of="2026-01-01",
        )
        before = self.capital.get_capital_plan(before_id)
        self.assertTrue(any(
            c["type"] == "GOAL_UNREACHABLE_WITHIN_PLANNING_SEARCH"
            for c in before["conflicts"]
        ))

        self.capital.add_cashflow(
            "CLIENT-FIXTURE",
            flow_type="INCOME",
            amount=1_000_000,
            cadence="MONTHLY",
            start_date="2026-07-01",
            label="future income fixture",
        )
        after_id = self.capital.build_capital_plan(
            "CLIENT-FIXTURE",
            liquid_assets=6_000_000,
            as_of="2026-01-01",
        )
        after = self.capital.get_capital_plan(after_id)
        self.assertEqual(0.0, after["recurring_monthly_income"])
        self.assertEqual(0.0, after["monthly_investable_surplus"])
        self.assertEqual(0.0, after["required_return_pct"])
        self.assertFalse(any(
            c["type"] == "GOAL_UNREACHABLE_WITHIN_PLANNING_SEARCH"
            for c in after["conflicts"]
        ))

    def test_ended_monthly_income_is_not_current_surplus(self):
        self.capital.add_cashflow(
            "CLIENT-FIXTURE",
            flow_type="INCOME",
            amount=2_000_000,
            cadence="MONTHLY",
            start_date="2025-01-01",
            end_date="2025-12-31",
            label="ended income fixture",
        )
        cpid = self.capital.build_capital_plan(
            "CLIENT-FIXTURE",
            liquid_assets=6_000_000,
            as_of="2026-01-01",
        )
        plan = self.capital.get_capital_plan(cpid)
        self.assertEqual(0.0, plan["recurring_monthly_income"])
        self.assertEqual(0.0, plan["monthly_investable_surplus"])

    def test_client_capital_and_autonomous_work_are_auditable(self):
        cpid, mid = self._normal_plan_and_mandate()
        AutonomousWorkEngine(self.capital).evaluate(
            mid, {"strategy_coverage": {"status": "INSUFFICIENT"}}
        )
        client_types = [e["event_type"] for e in self.kernel.ledger("CLIENT-FIXTURE")]
        self.assertIn("CAPITAL_PLAN_CREATED", client_types)
        self.assertIn("INVESTMENT_MANDATE_CREATED", client_types)
        mandate_types = [e["event_type"] for e in self.kernel.ledger(mid)]
        self.assertIn("AUTONOMOUS_WORK_ISSUED", mandate_types)
        self.assertTrue(self.kernel.verify_ledger_chain())


if __name__ == "__main__":
    unittest.main()
