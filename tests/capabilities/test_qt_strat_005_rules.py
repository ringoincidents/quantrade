import unittest

from scripts.run_qt_strat_005 import (
    SYMBOLS,
    aggregate_partition,
    selection_key,
    stage_a_criteria,
    stage_b_criteria,
)


def _evaluation(
    *,
    net,
    sharpe=1.0,
    turnover=0.1,
    mdd=-10.0,
    periods=241,
):
    return {
        "metrics": {
            "net_total_return_pct": float(net),
            "sharpe": sharpe,
            "turnover_per_period": float(turnover),
            "maximum_drawdown_pct": float(mdd),
            "return_periods": int(periods),
        }
    }


class QtStrat005RulesTests(unittest.TestCase):
    def test_cross_section_summary_uses_stock_specific_controls(self):
        candidate = {
            symbol: _evaluation(net=value)
            for symbol, value in zip(
                SYMBOLS,
                [12, 8, 6, 4, 2],
            )
        }
        controls = {
            symbol: _evaluation(net=value)
            for symbol, value in zip(
                SYMBOLS,
                [10, 7, 7, 1, 3],
            )
        }
        summary = aggregate_partition(candidate, controls)
        self.assertEqual(3, summary["stocks_beating_cost_adjusted_control"])
        self.assertEqual(
            {
                SYMBOLS[0]: 2.0,
                SYMBOLS[1]: 1.0,
                SYMBOLS[2]: -1.0,
                SYMBOLS[3]: 3.0,
                SYMBOLS[4]: -1.0,
            },
            summary["per_stock_excess_vs_control_pct"],
        )
        self.assertEqual(1.0, summary["median_excess_vs_control_pct"])

    def test_stage_a_requires_at_least_three_validation_wins(self):
        train = {
            symbol: _evaluation(net=0, periods=734)
            for symbol in SYMBOLS
        }
        validation_summary = {
            "per_stock_return_periods": {
                symbol: 241 for symbol in SYMBOLS
            },
            "stocks_beating_cost_adjusted_control": 2,
            "median_excess_vs_control_pct": 3.0,
            "median_sharpe": 1.0,
            "worst_maximum_drawdown_pct": -20.0,
            "median_turnover_per_period": 0.1,
        }
        result = stage_a_criteria(train, validation_summary)
        self.assertFalse(result["eligible"])
        self.assertFalse(
            result["checks"][
                "validation_beats_control_on_at_least_3_of_5"
            ]
        )

    def test_stage_a_can_pass_only_when_all_frozen_checks_pass(self):
        train = {
            symbol: _evaluation(net=0, periods=734)
            for symbol in SYMBOLS
        }
        validation_summary = {
            "per_stock_return_periods": {
                symbol: 241 for symbol in SYMBOLS
            },
            "stocks_beating_cost_adjusted_control": 3,
            "median_excess_vs_control_pct": 0.01,
            "median_sharpe": 0.01,
            "worst_maximum_drawdown_pct": -30.0,
            "median_turnover_per_period": 0.25,
        }
        result = stage_a_criteria(train, validation_summary)
        self.assertTrue(result["eligible"])
        self.assertTrue(all(result["checks"].values()))

    def test_stage_b_is_independent_confirmation_gate(self):
        test_summary = {
            "per_stock_return_periods": {
                symbol: 181 for symbol in SYMBOLS
            },
            "stocks_beating_cost_adjusted_control": 3,
            "median_excess_vs_control_pct": 1.0,
            "median_sharpe": 0.5,
            "worst_maximum_drawdown_pct": -29.0,
            "median_turnover_per_period": 0.2,
        }
        self.assertTrue(stage_b_criteria(test_summary)["test_confirmed"])
        failed = dict(test_summary)
        failed["median_excess_vs_control_pct"] = -0.01
        self.assertFalse(stage_b_criteria(failed)["test_confirmed"])

    def test_research_priority_prefers_breadth_before_return_size(self):
        a = {
            "candidate": {"candidate_id": "A"},
            "validation_summary": {
                "stocks_beating_cost_adjusted_control": 4,
                "median_excess_vs_control_pct": 1.0,
                "median_sharpe": 0.5,
                "median_turnover_per_period": 0.2,
            },
        }
        b = {
            "candidate": {"candidate_id": "B"},
            "validation_summary": {
                "stocks_beating_cost_adjusted_control": 3,
                "median_excess_vs_control_pct": 50.0,
                "median_sharpe": 3.0,
                "median_turnover_per_period": 0.01,
            },
        }
        self.assertGreater(selection_key(a), selection_key(b))


if __name__ == "__main__":
    unittest.main()
