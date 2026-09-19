from __future__ import annotations

import json
import os
import tempfile
import unittest

from quantrade.institutional.client_capital import ClientCapitalRuntime
from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.performance_capital import PerformanceCapitalLoop
from quantrade.institutional.service import InstitutionalKernel


class PerformanceCapitalLoopTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.org = OrganizationRuntime(self.kernel)
        self.capital = ClientCapitalRuntime(self.kernel, self.org)
        self.capital.create_client(
            "CLIENT-PERF",
            profile={
                "essential_monthly_spend": 1_000_000,
                "emergency_reserve_months": 6,
                "max_drawdown_pct": 20.0,
                "max_planning_return_pct": 20.0,
                "research_universe": ["KR", "US"],
            },
        )
        self.loop = PerformanceCapitalLoop(self.capital)

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def _baseline_mandate(self, liquid=10_000_000, portfolio=20_000_000):
        cpid = self.capital.build_capital_plan(
            "CLIENT-PERF",
            liquid_assets=liquid,
            portfolio_value=portfolio,
            as_of="2026-01-01",
        )
        return self.capital.create_mandate(cpid)

    def test_performance_is_recorded_as_fact_separate_from_reinvestment(self):
        pid = self.loop.record_performance(
            "CLIENT-PERF",
            period_start="2026-01-01",
            period_end="2026-02-01",
            start_value=20_000_000,
            end_value=22_000_000,
            net_external_flows=500_000,
            realized_pnl=600_000,
            investment_income=100_000,
            fees=20_000,
            taxes=10_000,
            attribution={"strategy": {"fixture": 1_000_000}},
        )
        record = self.loop.performance_record(pid)
        self.assertEqual(1_500_000, record["attribution"]["economic_pnl"])
        self.assertEqual(600_000, record["realized_pnl"])
        self.assertEqual(100_000, record["investment_income"])
        self.assertFalse(
            self.kernel.conn.execute(
                "SELECT 1 FROM work_orders"
            ).fetchone()
        )

    def test_realized_cash_becomes_reinvestment_planning_not_order(self):
        previous = self._baseline_mandate(liquid=10_000_000)
        # Baseline reserve is 6m, so deployable cash was 4m.
        result = self.loop.reconcile(
            "CLIENT-PERF",
            as_of="2026-02-01",
            client_liquid_cash=8_000_000,
            brokerage_cash=3_000_000,
            invested_market_value=21_000_000,
            previous_mandate_id=previous,
        )
        self.assertEqual(5_000_000, result["deployable_cash_after_client_needs"])
        self.assertEqual(1_000_000, result["incremental_investable_surplus"])
        self.assertFalse(result["live_execution_authorized"])
        rows = self.kernel.conn.execute(
            """SELECT recipient_office,objective,authority_scope_json
            FROM work_orders WHERE work_order_id IN ({})""".format(
                ",".join("?" for _ in result["generated_work_orders"])
            ),
            tuple(result["generated_work_orders"]),
        ).fetchall()
        self.assertTrue(any("deployment/reinvestment plan" in r["objective"] for r in rows))
        for row in rows:
            self.assertFalse(json.loads(row["authority_scope_json"])["trade"])

    def test_client_planned_spending_can_absorb_profit_before_reinvestment(self):
        previous = self._baseline_mandate(liquid=10_000_000)
        # New known spending is protected before deployment.
        self.capital.add_cashflow(
            "CLIENT-PERF",
            flow_type="EXPENSE",
            amount=2_000_000,
            cadence="ONE_TIME",
            start_date="2026-03-01",
            label="planned client spending",
            reserved=True,
        )
        result = self.loop.reconcile(
            "CLIENT-PERF",
            as_of="2026-02-01",
            client_liquid_cash=8_000_000,
            brokerage_cash=3_000_000,
            invested_market_value=21_000_000,
            previous_mandate_id=previous,
        )
        # 11m liquid - (6m emergency + 2m planned spending) = 3m,
        # below previous 4m deployable amount: no new surplus.
        self.assertEqual(3_000_000, result["deployable_cash_after_client_needs"])
        self.assertEqual(0.0, result["incremental_investable_surplus"])
        objectives = [
            self.kernel.conn.execute(
                "SELECT objective FROM work_orders WHERE work_order_id=?", (wid,)
            ).fetchone()["objective"]
            for wid in result["generated_work_orders"]
        ]
        self.assertFalse(any("deployment/reinvestment plan" in o for o in objectives))

    def test_unchanged_cash_does_not_create_reinvestment_work_every_cycle(self):
        previous = self._baseline_mandate(liquid=10_000_000)
        result = self.loop.reconcile(
            "CLIENT-PERF",
            as_of="2026-02-01",
            client_liquid_cash=7_000_000,
            brokerage_cash=3_000_000,
            invested_market_value=21_000_000,
            previous_mandate_id=previous,
        )
        self.assertEqual(0.0, result["incremental_investable_surplus"])
        self.assertEqual([], result["generated_work_orders"])

    def test_performance_review_can_generate_learning_work_without_founder_prompt(self):
        previous = self._baseline_mandate(liquid=10_000_000)
        result = self.loop.reconcile(
            "CLIENT-PERF",
            as_of="2026-02-01",
            client_liquid_cash=7_000_000,
            brokerage_cash=3_000_000,
            invested_market_value=19_000_000,
            previous_mandate_id=previous,
            strategy_performance_state={
                "review_required": True,
                "strategy_id": "STRAT-FIXTURE",
                "reason": "attribution review requested by deterministic performance monitor",
            },
        )
        self.assertEqual(1, len(result["generated_work_orders"]))
        row = self.kernel.conn.execute(
            "SELECT recipient_office,objective FROM work_orders WHERE work_order_id=?",
            (result["generated_work_orders"][0],),
        ).fetchone()
        self.assertEqual("ISLL", row["recipient_office"])
        self.assertIn("strategy performance and attribution", row["objective"])

    def test_reconciliation_and_performance_are_auditable(self):
        previous = self._baseline_mandate()
        pid = self.loop.record_performance(
            "CLIENT-PERF",
            period_start="2026-01-01",
            period_end="2026-02-01",
            start_value=20_000_000,
            end_value=20_500_000,
        )
        result = self.loop.reconcile(
            "CLIENT-PERF",
            as_of="2026-02-01",
            client_liquid_cash=7_000_000,
            brokerage_cash=3_000_000,
            invested_market_value=20_500_000,
            performance_id=pid,
            previous_mandate_id=previous,
        )
        types = [e["event_type"] for e in self.kernel.ledger("CLIENT-PERF")]
        self.assertIn("PERFORMANCE_RECORDED", types)
        self.assertIn("CAPITAL_RECONCILED", types)
        self.assertTrue(result["reconciliation_id"].startswith("RECON-"))
        self.assertTrue(self.kernel.verify_ledger_chain())


if __name__ == "__main__":
    unittest.main()
