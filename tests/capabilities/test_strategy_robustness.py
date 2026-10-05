import unittest

from quantrade.capabilities.strategy_robustness import (
    CandidateReviewInput,
    RobustnessGateError,
    RobustnessPolicy,
    SpecialistReviewContext,
    build_robustness_review_batch,
    build_specialist_work,
    evaluate_candidate_robustness,
)


class StrategyRobustnessTests(unittest.TestCase):
    def _evaluation(
        self,
        *,
        disposition="SURVIVES_DETERMINISTIC_SCREEN",
        periods=60,
        drawdown=-10.0,
        excess=5.0,
        turnover=0.10,
        gross=10.0,
        net=9.0,
        sharpe=1.0,
    ):
        return {
            "screening": {"disposition": disposition},
            "metrics": {
                "return_periods": periods,
                "maximum_drawdown_pct": drawdown,
                "benchmark_excess_return_pct": excess,
                "turnover_per_period": turnover,
                "gross_total_return_pct": gross,
                "net_total_return_pct": net,
                "sharpe": sharpe,
            },
        }

    def _item(self, candidate_id, positions, **kwargs):
        return CandidateReviewInput(
            candidate_id,
            self._evaluation(**kwargs),
            tuple(float(v) for v in positions),
        )

    def test_upstream_rejection_cannot_reenter_review(self):
        result = evaluate_candidate_robustness(
            self._item(
                "REJECTED",
                [1, 0, 1, 0],
                disposition="REJECTED_DETERMINISTIC_SCREEN",
            ),
            RobustnessPolicy(min_return_periods=1),
        )
        self.assertEqual("ROBUSTNESS_REJECTED", result["disposition"])
        self.assertTrue(
            any(reason.startswith("UPSTREAM_SCREEN") for reason in result["reasons"])
        )
        self.assertFalse(result["authority"]["strategy_approved"])
        self.assertFalse(result["authority"]["execution_authorized"])

    def test_cost_sensitive_candidate_is_rejected(self):
        result = evaluate_candidate_robustness(
            self._item(
                "COSTLY",
                [1, 0, 1, 0],
                gross=20.0,
                net=5.0,
            ),
            RobustnessPolicy(
                min_return_periods=1,
                max_drawdown_pct=-100,
                min_benchmark_excess_return_pct=-100,
                max_turnover_per_period=1.0,
                max_cost_drag_pct=5.0,
            ),
        )
        self.assertEqual("ROBUSTNESS_REJECTED", result["disposition"])
        self.assertIn("COST_SENSITIVITY:15.0>5.0", result["reasons"])

    def test_near_duplicate_signal_path_is_suppressed(self):
        policy = RobustnessPolicy(
            min_return_periods=1,
            max_drawdown_pct=-100,
            min_benchmark_excess_return_pct=-100,
            max_turnover_per_period=1.0,
            max_cost_drag_pct=100,
            signal_similarity_threshold=0.90,
            top_k=3,
        )
        batch = build_robustness_review_batch(
            [
                self._item("A", [1, 1, 0, 0, 1, 1], excess=8.0),
                self._item("B", [1, 1, 0, 0, 1, 1], excess=7.0),
            ],
            policy=policy,
        )
        self.assertEqual(["A"], [x["candidate_id"] for x in batch["selected"]])
        self.assertEqual("B", batch["suppressed"][0]["candidate_id"])
        self.assertEqual("A", batch["suppressed"][0]["duplicate_of"])
        self.assertEqual(
            "NEAR_DUPLICATE_SIGNAL_PATH",
            batch["suppressed"][0]["reason"],
        )

    def test_top_k_bounds_expensive_review(self):
        policy = RobustnessPolicy(
            min_return_periods=1,
            max_drawdown_pct=-100,
            min_benchmark_excess_return_pct=-100,
            max_turnover_per_period=1.0,
            max_cost_drag_pct=100,
            signal_similarity_threshold=1.0,
            top_k=2,
        )
        batch = build_robustness_review_batch(
            [
                self._item("A", [1, 1, 1, 0], excess=8.0),
                self._item("B", [1, 1, 0, 0], excess=7.0),
                self._item("C", [1, 0, 0, 0], excess=6.0),
            ],
            policy=policy,
        )
        self.assertEqual(2, batch["selected_count"])
        self.assertEqual(["A", "B"], [x["candidate_id"] for x in batch["selected"]])
        self.assertTrue(
            any(
                row["candidate_id"] == "C"
                and row["reason"] == "TOP_K_BOUND:2"
                for row in batch["suppressed"]
            )
        )

    def test_specialists_are_planned_only_when_context_can_change_decision(self):
        work = build_specialist_work(
            "A",
            SpecialistReviewContext(
                has_portfolio_context=True,
                risk_review_required=True,
                external_dependency_requires_review=False,
            ),
        )
        roles = {row.role for row in work}
        self.assertEqual(
            {
                "QUANT_MARKET",
                "COUNTER_RESEARCH",
                "PORTFOLIO_MANAGEMENT",
                "RISK_COMPLIANCE",
            },
            roles,
        )
        self.assertNotIn("DEEP_EXTERNAL_RESEARCH", roles)
        self.assertTrue(all(row.max_model_calls == 1 for row in work))
        self.assertTrue(all(row.max_tool_rounds == 3 for row in work))

    def test_survivor_batch_routes_bounded_review_without_invoking_models(self):
        policy = RobustnessPolicy(
            min_return_periods=1,
            max_drawdown_pct=-100,
            min_benchmark_excess_return_pct=-100,
            max_turnover_per_period=1.0,
            max_cost_drag_pct=100,
            top_k=1,
        )
        batch = build_robustness_review_batch(
            [self._item("A", [1, 0, 1, 0])],
            policy=policy,
            review_context=SpecialistReviewContext(
                has_portfolio_context=False,
                risk_review_required=True,
                external_dependency_requires_review=True,
            ),
        )
        self.assertEqual("BOUNDED_REVIEW", batch["review_gate"]["level"])
        self.assertGreater(batch["telemetry"]["specialists_planned"], 0)
        self.assertEqual(0, batch["telemetry"]["specialists_invoked"])
        self.assertEqual(0, batch["telemetry"]["model_calls"])
        self.assertFalse(batch["authority"]["strategy_approved"])
        self.assertFalse(batch["authority"]["automatic_promotion_allowed"])
        self.assertFalse(batch["authority"]["execution_authorized"])

    def test_all_rejected_candidates_create_no_specialist_work(self):
        policy = RobustnessPolicy(
            min_return_periods=1000,
            max_drawdown_pct=-100,
            min_benchmark_excess_return_pct=-100,
            max_turnover_per_period=1.0,
            max_cost_drag_pct=100,
        )
        batch = build_robustness_review_batch(
            [self._item("A", [1, 0, 1, 0])],
            policy=policy,
        )
        self.assertEqual(0, batch["selected_count"])
        self.assertEqual("NO_REVIEW", batch["review_gate"]["level"])
        self.assertEqual([], batch["specialist_work_requests"])
        self.assertEqual(0, batch["telemetry"]["specialists_planned"])

    def test_invalid_position_vector_fails_closed(self):
        with self.assertRaisesRegex(RobustnessGateError, "long/flat"):
            evaluate_candidate_robustness(
                self._item("A", [1, 0.5, 0, 1]),
                RobustnessPolicy(min_return_periods=1),
            )


if __name__ == "__main__":
    unittest.main()
