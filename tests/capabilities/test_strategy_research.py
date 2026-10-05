import unittest

from quantrade.capabilities.strategy_research import (
    CandidateStrategy,
    DatasetMetadata,
    LookaheadDetected,
    PositionSignal,
    PriceBar,
    ScreeningPolicy,
    StrategyResearchError,
    evaluate_strategy,
)
from quantrade.capabilities.strategy_research_evaluation import (
    canonical_experiment,
)


class StrategyResearchTests(unittest.TestCase):
    def _bars(self):
        return [
            PriceBar("2026-01-01T00:00:00+00:00", 100.0),
            PriceBar("2026-01-02T00:00:00+00:00", 101.0),
            PriceBar("2026-01-03T00:00:00+00:00", 100.5),
            PriceBar("2026-01-04T00:00:00+00:00", 102.0),
            PriceBar("2026-01-05T00:00:00+00:00", 103.0),
        ]

    def _dataset(self, bars, point_in_time=True):
        return DatasetMetadata(
            dataset_id="D1",
            source="fixture://prices",
            provider="fixture-provider",
            version_or_revision="v1",
            as_of_start=bars[0].observed_at,
            as_of_end=bars[-1].observed_at,
            point_in_time=point_in_time,
            point_in_time_evidence_ref="fixture://pit-manifest-v1",
        )

    def _candidate(self):
        return CandidateStrategy(
            "C1",
            "fixture",
            "TEST",
            "fixture://candidate",
            "TEST",
            "DAILY",
        )

    def _signals(self, bars, positions, lookahead=False):
        signals = []
        for i, position in enumerate(positions):
            cutoff = (
                bars[i + 1].observed_at
                if lookahead and i == 1
                else bars[i].observed_at
            )
            signals.append(
                PositionSignal(
                    bars[i].observed_at,
                    cutoff,
                    position,
                )
            )
        return signals

    def test_same_input_is_deterministic_and_non_authoritative(self):
        bars = self._bars()
        kwargs = dict(
            candidate=self._candidate(),
            bars=bars,
            signals=self._signals(bars, [1, 1, 1, 1]),
            dataset=self._dataset(bars),
            transaction_cost_bps=10,
            screening_policy=ScreeningPolicy(
                min_return_periods=1,
                max_drawdown_pct=-100,
                min_benchmark_excess_return_pct=-100,
            ),
        )
        first = evaluate_strategy(**kwargs)
        second = evaluate_strategy(**kwargs)
        self.assertEqual(first, second)
        self.assertFalse(first.authority["canonical_evidence_created"])
        self.assertFalse(first.authority["investment_decision_created"])
        self.assertFalse(first.authority["execution_authorized"])

    def test_future_information_is_rejected(self):
        bars = self._bars()
        with self.assertRaises(LookaheadDetected):
            evaluate_strategy(
                self._candidate(),
                bars,
                self._signals(
                    bars,
                    [1, 1, 1, 1],
                    lookahead=True,
                ),
                self._dataset(bars),
                screening_policy=ScreeningPolicy(min_return_periods=1),
            )

    def test_non_point_in_time_dataset_fails_closed(self):
        bars = self._bars()
        with self.assertRaisesRegex(StrategyResearchError, "point-in-time"):
            evaluate_strategy(
                self._candidate(),
                bars,
                self._signals(bars, [1, 1, 1, 1]),
                self._dataset(bars, point_in_time=False),
                screening_policy=ScreeningPolicy(min_return_periods=1),
            )

    def test_point_in_time_claim_requires_evidence_reference(self):
        bars = self._bars()
        dataset = DatasetMetadata(
            dataset_id="D1",
            source="fixture://prices",
            provider="fixture-provider",
            version_or_revision="v1",
            as_of_start=bars[0].observed_at,
            as_of_end=bars[-1].observed_at,
            point_in_time=True,
            point_in_time_evidence_ref="",
        )
        with self.assertRaisesRegex(
            StrategyResearchError,
            "evidence reference",
        ):
            evaluate_strategy(
                self._candidate(),
                bars,
                self._signals(bars, [1, 1, 1, 1]),
                dataset,
                screening_policy=ScreeningPolicy(min_return_periods=1),
            )

    def test_transaction_costs_reduce_high_turnover_result(self):
        bars = self._bars()
        signals = self._signals(bars, [1, 0, 1, 0])
        policy = ScreeningPolicy(
            min_return_periods=1,
            max_drawdown_pct=-100,
            min_benchmark_excess_return_pct=-100,
        )
        free = evaluate_strategy(
            self._candidate(),
            bars,
            signals,
            self._dataset(bars),
            transaction_cost_bps=0,
            screening_policy=policy,
        )
        costly = evaluate_strategy(
            self._candidate(),
            bars,
            signals,
            self._dataset(bars),
            transaction_cost_bps=100,
            screening_policy=policy,
        )
        self.assertLess(
            costly.metrics["net_total_return_pct"],
            free.metrics["net_total_return_pct"],
        )
        self.assertGreater(
            costly.metrics[
                "estimated_transaction_cost_pct_of_initial_equity"
            ],
            0,
        )

    def test_screening_rejects_underperforming_candidate(self):
        bars = self._bars()
        evaluation = evaluate_strategy(
            self._candidate(),
            bars,
            self._signals(bars, [0, 0, 0, 0]),
            self._dataset(bars),
            screening_policy=ScreeningPolicy(
                min_return_periods=1,
                max_drawdown_pct=-100,
                min_benchmark_excess_return_pct=0,
            ),
        )
        self.assertEqual(
            "REJECTED_DETERMINISTIC_SCREEN",
            evaluation.screening["disposition"],
        )
        self.assertTrue(
            any(
                reason.startswith("BENCHMARK_UNDERPERFORMANCE")
                for reason in evaluation.screening["reasons"]
            )
        )
        self.assertFalse(evaluation.screening["strategy_approved"])
        self.assertFalse(
            evaluation.screening["automatic_promotion_allowed"]
        )

    def test_missing_market_values_are_not_silently_imputed(self):
        bars = self._bars()
        bad = list(bars)
        bad[2] = PriceBar(bad[2].observed_at, 0.0)
        with self.assertRaisesRegex(StrategyResearchError, "positive"):
            evaluate_strategy(
                self._candidate(),
                bad,
                self._signals(bars, [1, 1, 1, 1]),
                self._dataset(bars),
                screening_policy=ScreeningPolicy(min_return_periods=1),
            )

    def test_reference_experiment_encodes_historical_safety_lessons(self):
        artifact = canonical_experiment()
        reference_keys = {
            key
            for key in artifact["results"]
            if key in {
                "buy_and_hold",
                "sma_crossover",
                "high_turnover",
            }
        }
        self.assertEqual(3, len(reference_keys))
        self.assertTrue(
            artifact["negative_controls"]["lookahead"]["detected"]
        )
        self.assertTrue(
            artifact["results"]["high_turnover_cost_comparison"][
                "cost_hurts_or_equal"
            ]
        )
        self.assertEqual(
            "REJECTED_DETERMINISTIC_SCREEN",
            artifact["results"]["high_turnover"]["screening"][
                "disposition"
            ],
        )
        self.assertFalse(artifact["authority"]["strategy_approved"])
        self.assertFalse(artifact["authority"]["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
