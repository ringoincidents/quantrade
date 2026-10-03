from __future__ import annotations

import unittest

from quantrade.institutional.ceo_observer import (
    CEOImprovementPolicy,
    QuanTradeCEOObserver,
    build_ceo_proposals_read_model,
)
from quantrade.institutional.strategy_director import compile_company_strategy


class StrategyDirectorTests(unittest.TestCase):
    def setUp(self):
        self.mandate = {
            "investable_capital": 1000.0,
            "required_return_pct": 8.0,
            "max_drawdown_pct": 15.0,
            "liquidity_reserve": 500.0,
            "planning_conflicts": [],
            "human_approval_required_for_live_execution": True,
        }

    def test_urgent_cash_need_forces_liquidity_first_not_more_risk(self):
        directive = compile_company_strategy(
            mandate=self.mandate,
            client_state={
                "liquid_assets": 550.0,
                "urgent_cash_need_amount": 200.0,
            },
        )
        self.assertEqual("LIQUIDITY_FIRST", directive["posture"])
        self.assertGreater(directive["liquidity_shortfall"], 0)
        self.assertIn("RAISE_CASH_PLAN", directive["actions"])
        self.assertFalse(directive["execution_authority"])
        self.assertIn("never authorize automatic risk escalation", directive["policy_note"])

    def test_material_research_update_routes_rebalance_review(self):
        directive = compile_company_strategy(
            mandate=self.mandate,
            client_state={"liquid_assets": 700.0},
            research_state={
                "material_update": True,
                "regime_change": True,
            },
        )
        self.assertEqual("REBALANCE_REVIEW", directive["posture"])
        self.assertIn("RESEARCH", directive["actions"])
        self.assertIn("SPMG", directive["required_offices"])
        self.assertIn("IPRO", directive["required_offices"])

    def test_new_surplus_creates_deployment_review_only(self):
        directive = compile_company_strategy(
            mandate=self.mandate,
            client_state={
                "liquid_assets": 1000.0,
                "new_investable_surplus": 150.0,
            },
        )
        self.assertEqual("DEPLOYMENT_REVIEW", directive["posture"])
        self.assertFalse(directive["execution_authority"])


class QuanTradeCEOObserverTests(unittest.TestCase):
    def test_repeated_latency_and_cost_generate_hq_proposals(self):
        observer = QuanTradeCEOObserver(
            CEOImprovementPolicy(
                repeat_threshold=3,
                latency_budget_ms=1000.0,
                model_cost_budget_usd_per_decision=0.01,
            )
        )
        proposals = observer.review(
            decision_episodes=[
                {"workflow_latency_proxy_ms": 2000, "model_cost_usd": 0.02},
                {"workflow_latency_proxy_ms": 1500, "model_cost_usd": 0.03},
                {"workflow_latency_proxy_ms": 2500, "model_cost_usd": 0.04},
            ]
        )
        issue_types = {p["issue_type"] for p in proposals}
        self.assertIn("DECISION_LATENCY_BOTTLENECK", issue_types)
        self.assertIn("MODEL_COST_BOTTLENECK", issue_types)
        self.assertTrue(all(p["requires_hq_review"] for p in proposals))
        self.assertTrue(all(not p["auto_apply"] for p in proposals))
        self.assertTrue(all(p["proposal_id"].startswith("QTPROP-") for p in proposals))
        self.assertEqual(
            [p["proposal_id"] for p in proposals],
            [
                p["proposal_id"]
                for p in observer.review(
                    decision_episodes=[
                        {"workflow_latency_proxy_ms": 2000, "model_cost_usd": 0.02},
                        {"workflow_latency_proxy_ms": 1500, "model_cost_usd": 0.03},
                        {"workflow_latency_proxy_ms": 2500, "model_cost_usd": 0.04},
                    ]
                )
            ],
        )

    def test_proposals_build_versioned_read_model(self):
        observer = QuanTradeCEOObserver(CEOImprovementPolicy(repeat_threshold=1))
        proposals = observer.review(
            capability_gaps=[{"capability": "market_state_cache"}],
        )
        doc = build_ceo_proposals_read_model(
            proposals,
            generated_at="2026-10-03T08:00:00+00:00",
        )
        self.assertEqual("quantrade_ceo_proposals_v1", doc["schema"])
        self.assertEqual("QUANTRADE_LLM_CEO", doc["source"])
        self.assertEqual(proposals, doc["proposals"])

    def test_single_failure_does_not_spam_hq(self):
        observer = QuanTradeCEOObserver(CEOImprovementPolicy(repeat_threshold=3))
        proposals = observer.review(
            operational_events=[{"status": "FAILED"}],
            capability_gaps=[{"capability": "better_market_feed"}],
        )
        self.assertEqual([], proposals)

    def test_repeated_capability_gap_becomes_evidence_backed_request(self):
        observer = QuanTradeCEOObserver(CEOImprovementPolicy(repeat_threshold=3))
        proposals = observer.review(
            capability_gaps=[
                {"capability": "low_latency_market_feed", "case": "A"},
                {"capability": "low_latency_market_feed", "case": "B"},
                {"capability": "low_latency_market_feed", "case": "C"},
            ]
        )
        self.assertEqual(1, len(proposals))
        self.assertEqual("REPEATED_CAPABILITY_GAP", proposals[0]["issue_type"])
        self.assertEqual(3, proposals[0]["evidence"]["occurrence_count"])


if __name__ == "__main__":
    unittest.main()
