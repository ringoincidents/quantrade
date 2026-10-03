from __future__ import annotations

import unittest

from quantrade.institutional.trading_process_lab import (
    DecisionEpisodeInput,
    InstitutionalAction,
    ModelCallEconomics,
    PipelineTiming,
    PricingSnapshot,
    ShockDetector,
    ShockPolicy,
    ShockSeverity,
    TradingFriction,
    compare_episode_baselines,
    evaluate_decision_episode,
    latency_move_bps,
)


class TradingProcessLabTests(unittest.TestCase):
    def test_shock_detector_escalates_without_increasing_exposure(self):
        detector = ShockDetector(
            ShockPolicy(
                elevated_pct=1.0,
                high_pct=3.0,
                critical_pct=5.0,
                window_seconds=300,
            )
        )
        result = detector.evaluate(100.0, 94.0)

        self.assertEqual(ShockSeverity.CRITICAL, result.severity)
        self.assertEqual("DOWN", result.direction)
        self.assertIn(InstitutionalAction.EXIT, result.immediate_actions)
        self.assertIn(
            InstitutionalAction.PAUSE_NEW_ENTRY,
            result.immediate_actions,
        )
        self.assertNotIn(
            InstitutionalAction.ENTER_NOW,
            result.immediate_actions,
        )

    def test_model_cost_uses_versioned_pricing_snapshot(self):
        pricing = PricingSnapshot(
            pricing_id="fixture-2026-10-03",
            provider="fixture",
            model="reasoner-v1",
            effective_at="2026-10-03T00:00:00+00:00",
            input_usd_per_million=2.0,
            cached_input_usd_per_million=0.5,
            output_usd_per_million=8.0,
            reasoning_usd_per_million=8.0,
        )
        call = ModelCallEconomics(
            role="risk",
            provider="fixture",
            model="reasoner-v1",
            latency_ms=1400,
            input_tokens=1000,
            cached_input_tokens=400,
            output_tokens=200,
            reasoning_tokens=100,
        )

        self.assertAlmostEqual(
            ((600 * 2.0) + (400 * 0.5) + (200 * 8.0) + (100 * 8.0))
            / 1_000_000,
            call.cost_usd(pricing),
        )

    def test_long_entry_delay_is_recorded_as_adverse_bps(self):
        self.assertAlmostEqual(
            100.0,
            latency_move_bps(
                event_price=100.0,
                executable_price=101.0,
                action=InstitutionalAction.ENTER_NOW,
                position_direction="FLAT",
            ),
        )

    def test_long_exit_price_drop_is_recorded_as_adverse_delay(self):
        self.assertAlmostEqual(
            100.0,
            latency_move_bps(
                event_price=100.0,
                executable_price=99.0,
                action=InstitutionalAction.EXIT,
                position_direction="LONG",
            ),
        )

    def test_episode_counts_model_friction_and_latency_cost_separately(self):
        pricing = PricingSnapshot(
            pricing_id="fixture-pricing",
            provider="fixture",
            model="reasoner-v1",
            effective_at="2026-10-03T00:00:00+00:00",
            input_usd_per_million=1.0,
            output_usd_per_million=4.0,
        )
        episode = DecisionEpisodeInput(
            episode_id="EP-001",
            baseline="INSTITUTIONAL",
            action=InstitutionalAction.ENTER_NOW,
            event_price=100.0,
            executable_price=101.0,
            position_direction="FLAT",
            gross_trading_pnl_usd=1.0,
            market_exposure_usd=30.0,
            model_calls=(
                ModelCallEconomics(
                    role="research",
                    provider="fixture",
                    model="reasoner-v1",
                    latency_ms=1200,
                    input_tokens=2000,
                    output_tokens=500,
                ),
                ModelCallEconomics(
                    role="risk",
                    provider="fixture",
                    model="reasoner-v1",
                    latency_ms=800,
                    input_tokens=1000,
                    output_tokens=250,
                ),
            ),
            pipeline_timing=PipelineTiming(
                market_data_ms=50,
                deterministic_features_ms=3,
                committee_assembly_ms=10,
                execution_adapter_ms=20,
            ),
            friction=TradingFriction(
                fee_usd=0.03,
                fill_slippage_usd=0.015,
                infra_usd=0.002,
            ),
        )

        result = evaluate_decision_episode(
            episode,
            pricing={("fixture", "reasoner-v1"): pricing},
        )

        self.assertTrue(result["pricing_complete"])
        self.assertEqual(2, result["model_call_count"])
        self.assertAlmostEqual(2000, result["model_latency_ms"])
        self.assertAlmostEqual(83, result["non_model_latency_ms"])
        self.assertAlmostEqual(2083, result["workflow_latency_proxy_ms"])
        self.assertAlmostEqual(100.0, result["latency_move_bps"])
        self.assertAlmostEqual(0.3, result["latency_opportunity_cost_usd"])
        self.assertGreater(result["model_cost_usd"], 0)
        self.assertLess(
            result["conservative_net_after_latency_usd"],
            result["gross_trading_pnl_usd"],
        )

    def test_chart_vision_can_be_compared_as_a_cost_latency_variant(self):
        structured = evaluate_decision_episode(
            DecisionEpisodeInput(
                episode_id="EP-VISION",
                baseline="INSTITUTIONAL_STRUCTURED",
                action=InstitutionalAction.WAIT,
                event_price=100.0,
                executable_price=100.0,
                position_direction="FLAT",
                gross_trading_pnl_usd=0.0,
                market_exposure_usd=30.0,
                chart_vision_used=False,
                pipeline_timing=PipelineTiming(
                    deterministic_features_ms=5,
                ),
            )
        )
        vision = evaluate_decision_episode(
            DecisionEpisodeInput(
                episode_id="EP-VISION",
                baseline="INSTITUTIONAL_VISION",
                action=InstitutionalAction.WAIT,
                event_price=100.0,
                executable_price=100.0,
                position_direction="FLAT",
                gross_trading_pnl_usd=0.0,
                market_exposure_usd=30.0,
                chart_vision_used=True,
                pipeline_timing=PipelineTiming(
                    deterministic_features_ms=5,
                    chart_render_ms=200,
                ),
                friction=TradingFriction(infra_usd=0.001),
            )
        )

        comparison = compare_episode_baselines([structured, vision])
        self.assertEqual("EP-VISION", comparison["episode_id"])
        self.assertEqual(
            "INSTITUTIONAL_STRUCTURED",
            comparison["best_observed_baseline"],
        )
        self.assertGreater(comparison["net_spread_usd"], 0)


if __name__ == "__main__":
    unittest.main()
