from __future__ import annotations

import copy
import inspect
import os
import tempfile
import unittest

from quantrade.institutional import InstitutionalKernel
from quantrade.institutional.portfolio_adapters import (
    DeterministicRiskAdapter,
    PortfolioRuleEventAdapter,
    RealPortfolioSnapshotAdapter,
    audit_portfolio_data_quality,
)


REAL_FIXTURE = {
    "synced_at": "2026-09-19T00:00:00+00:00",
    "cash": 100000.0,
    "positions": [
        {
            "symbol": "A",
            "name": "Fixture A",
            "market_country": "KR",
            "currency": "KRW",
            "quantity": 10,
            "avg_price": 50000,
            "current_price": 60000,
            "eval_amount": 600000,
            "eval_amount_krw": 600000,
            "return_pct": 20.0,
        },
        {
            "symbol": "B",
            "name": "Fixture B",
            "market_country": "US",
            "currency": "USD",
            "quantity": 2,
            "avg_price": 100,
            "current_price": 90,
            "eval_amount": 180,
            "eval_amount_krw": 300000,
            "return_pct": -10.0,
        },
    ],
}

ASSET_MAPPING = {
    "mappings": [
        {"symbol": "A", "asset_class": "fixture", "asset_type": "individual_stock", "active": True},
        {"symbol": "OLD", "asset_class": "fixture", "asset_type": "individual_stock", "active": True},
    ]
}
ROLE_MAPPING = {
    "source": "fixture — 초안",
    "mappings": [
        {"symbol": "A", "role": "core", "active": True},
        {"symbol": "OLDROLE", "role": "satellite", "active": True},
    ],
}
TARGET = {"provisional": True}


class PortfolioRiskAdapterTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_snapshot_is_read_only_and_matches_deterministic_totals(self):
        source = copy.deepcopy(REAL_FIXTURE)
        before = copy.deepcopy(source)
        snapshot = RealPortfolioSnapshotAdapter().build(
            source,
            asset_class_mapping=ASSET_MAPPING,
            role_mapping=ROLE_MAPPING,
            target_allocation=TARGET,
        )
        self.assertEqual(before, source)
        self.assertEqual(1000000.0, snapshot["calculated"]["total_assets_krw"])
        self.assertEqual(60.0, snapshot["calculated"]["positions"][0]["weight_pct"])
        self.assertEqual(10.0, snapshot["calculated"]["cash_pct"])
        self.assertEqual("real_portfolio_read_only", snapshot["source"])
        self.assertTrue(snapshot["read_only"])

    def test_mapping_drift_is_reported_not_repaired(self):
        quality = audit_portfolio_data_quality(
            REAL_FIXTURE, ASSET_MAPPING, ROLE_MAPPING, TARGET
        )
        self.assertEqual(["B"], quality["missing_asset_class_mapping"])
        self.assertEqual(["B"], quality["missing_role_mapping"])
        self.assertEqual(["OLD"], quality["active_asset_mappings_not_held"])
        self.assertEqual(["OLDROLE"], quality["active_role_mappings_not_held"])
        self.assertTrue(quality["policy_flags"]["target_allocation_provisional"])
        self.assertTrue(quality["policy_flags"]["role_mapping_provisional"])

    def test_risk_is_deterministic_and_keeps_provisional_status(self):
        snapshot = RealPortfolioSnapshotAdapter().build(
            REAL_FIXTURE, asset_class_mapping=ASSET_MAPPING
        )
        assessment = DeterministicRiskAdapter().evaluate(
            snapshot,
            symbol_closes={},
            asset_class_mapping=ASSET_MAPPING,
            today="2026-09-19",
        )
        self.assertTrue(assessment["deterministic"])
        self.assertFalse(assessment["llm_used"])
        self.assertTrue(assessment["policy_provisional"])
        self.assertTrue(
            any(m["rule"] == "집중도" and m["symbol"] == "A"
                for m in assessment["rule_matches"])
        )
        self.assertTrue(any("price history unavailable" in x for x in assessment["limitations"]))
        self.assertTrue(any("not peak-to-trough MDD" in x for x in assessment["limitations"]))

    def test_rule_match_becomes_observation_event_not_decision(self):
        snapshot = RealPortfolioSnapshotAdapter().build(
            REAL_FIXTURE, asset_class_mapping=ASSET_MAPPING
        )
        assessment = DeterministicRiskAdapter().evaluate(
            snapshot, asset_class_mapping=ASSET_MAPPING, today="2026-09-19"
        )
        events = PortfolioRuleEventAdapter().build(assessment["rule_matches"])
        self.assertGreaterEqual(len(events), 1)
        event = events[0]
        self.assertEqual("PORTFOLIO_RULE_MATCH", event["event_type"])
        self.assertTrue(event["payload"]["observation_only"])
        result = self.kernel.ingest_event(**event)
        self.assertEqual("INTERNAL", result["route"])
        self.assertIsNone(result["case_id"])
        self.assertEqual([], self.kernel.founder_desk())
        decision_count = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM decisions"
        ).fetchone()["c"]
        self.assertEqual(0, decision_count)

    def test_snapshot_and_risk_can_attach_to_existing_case(self):
        opened = self.kernel.ingest_event(
            "MATERIAL_REVIEW_REQUIRED",
            "fixture",
            "A",
            {"reason": "fixture institutional review"},
            case_id="QT-2026-4101",
        )
        case_id = opened["case_id"]
        snapshot = RealPortfolioSnapshotAdapter().build(
            REAL_FIXTURE, asset_class_mapping=ASSET_MAPPING
        )
        adapter = DeterministicRiskAdapter()
        assessment = adapter.evaluate(
            snapshot, asset_class_mapping=ASSET_MAPPING, today="2026-09-19"
        )
        snapshot_id, risk_id = adapter.attach(
            self.kernel, case_id, snapshot, assessment
        )
        stored_snapshot = self.kernel.conn.execute(
            "SELECT source FROM portfolio_snapshots WHERE snapshot_id=?", (snapshot_id,)
        ).fetchone()
        stored_risk = self.kernel.conn.execute(
            "SELECT policy_version FROM risk_assessments WHERE assessment_id=?", (risk_id,)
        ).fetchone()
        self.assertEqual("real_portfolio_read_only", stored_snapshot["source"])
        self.assertEqual(adapter.policy_version, stored_risk["policy_version"])
        self.assertEqual([], self.kernel.founder_desk())

    def test_missing_price_history_is_not_fabricated(self):
        snapshot = RealPortfolioSnapshotAdapter().build(
            REAL_FIXTURE, asset_class_mapping=ASSET_MAPPING
        )
        assessment = DeterministicRiskAdapter().evaluate(
            snapshot, symbol_closes={}, asset_class_mapping=ASSET_MAPPING
        )
        sizing = assessment["risk_engine"]["position_sizing"]
        self.assertTrue(all(row["sizing"] is None for row in sizing))
        self.assertEqual({}, assessment["risk_engine"]["correlation"]["matrix"])

    def test_adapter_has_no_broker_or_autoexec_dependency(self):
        import quantrade.institutional.portfolio_adapters as module

        source = inspect.getsource(module)
        self.assertNotIn("import autoexec", source)
        self.assertNotIn("from autoexec", source)
        self.assertNotIn("pending_actions", source)
        self.assertNotIn("import real_portfolio_sync", source)
        self.assertNotIn("from real_portfolio_sync", source)


if __name__ == "__main__":
    unittest.main()
